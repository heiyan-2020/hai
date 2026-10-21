# FaSST: Fast, Scalable and Simple Distributed Transactions with Two-Sided (RDMA) Datagram RPCs
OSDI'16 · Anuj Kalia, Michael Kaminsky, David G. Andersen / CMU, Intel Labs · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-kalia.pdf (USENIX camera-ready) · Selected: Highly cited (251 citations)

**One sentence**: In real transactions, one RDMA READ cannot fetch the data, and the number of connections grows with the cluster. The InfiniBand link layer almost never drops packets. So unreliable datagram RPCs are faster and more scalable.

## Problem
In-memory distributed transaction systems such as FaRM and DrTM all rely on one-sided RDMA (READ/WRITE/ATOMIC access remote memory directly, without the remote CPU). They assume that saving the remote CPU makes them fast.
But in a symmetric deployment of tens to hundreds of machines, where each machine both sends and serves requests, this choice is costly.

## Strawman / Baseline
- **Use READs to walk remote data structures (FaRM, DrTM+R)**: one hash table lookup must first read the index and then the data, at least 2 READs. FaRM puts data inside the index, so one READ reads 6–8 times the size: a 48 B entry needs a 384 B read, giving only 6.5 Mrps. DrTM caches the index on each machine, but the index takes over 35% of memory and does not fit once the cluster grows. Locking and reading a value takes two round trips, ATOMIC + READ.
- **One-sided works only over connected transport (RC)**: one QP (queue pair, a send/receive endpoint on the NIC) per pair of threads, so each machine needs N×T of them. Beyond the NIC cache, it thrashes. On ConnectX-3, simulating 22 machines drops READ to 24% of peak. Sharing QPs cuts the count, but threads contend for locks and single-thread throughput falls 5.4×.
- **Existing RDMA RPCs**: FaRM's RPC uses WRITE plus QP sharing; it is CPU-bound and 4× slower than its own READ. HERD fits only many clients against one server.
- **Use unreliable datagrams (UD)**: acks and retransmission must be done in software, which costs CPU and adds complexity.

## Novelty
1. **"Bypassing the remote CPU" is not what matters; the number and size of messages are**
   Insight: In microbenchmarks, small-message RPCs already reach 68–106% of READ throughput. On real data structures, READ needs several accesses or is amplified, while an RPC needs one round trip.
   So: Drop one-sided entirely. All transaction steps (read+lock merged into one, validation, logging, updating replicas) go through RPC. Users write a few handlers only for single-machine storage (MICA). They need not design flat data structures for READ. This avoids multiple READs, read amplification and cached indexes.
2. **With datagram transport, the number of QPs depends only on core count, not cluster size**
   Insight: One UD QP can talk to all remote endpoints.
   So: Each thread owns one QP, with no lock contention, and the NIC cache can hold them. A batch of requests to different machines needs only one doorbell (the PCIe write by which the CPU notifies the NIC). Connected transport needs one per destination. This removes exactly the QP blowup and sharing cost of RC.
3. **The link layer already guarantees reliability, so software reliability can be dropped**
   Insight: The InfiniBand link layer uses flow control to prevent congestion loss, and retransmission and FEC to handle bit errors. Cable bit error rate is below 10⁻¹⁵.
   So: The RPC layer does no acks or retransmission. It only uses a coarse 1-second timeout to detect a stalled coroutine. If a packet is lost, treat it as a machine failure: kill the local process and hand it to failure recovery. This gets the scalability of UD without paying for software reliability.

Other design: about 20 coroutines per thread hide latency; requests to the same machine are batched; a modified driver lowers the cost of posting RECVs; OCC + two-phase commit + primary-backup replication.

## Evidence
- End to end (compared with numbers published in papers, on different hardware): TATP on 50 machines reaches 3.55 Mtps/machine, 87% higher than FaRM, using about half the NICs and CPUs. SmallBank is 1.68× higher than DrTM+R (4.5× on CIB), without assuming data locality. TATP median latency at low load is 2.8 µs.
- Novelty 1 → 48 B entries: RPC 11.4–11.8 Mrps, FaRM-style 384 B READ 6.5 Mrps (CX3). RPC beats 2 READs in every configuration.
- Novelty 2 → simulated medium-size cluster (extra QPs created): RPC throughput is unchanged, 1.38× (CIB) and 10.1× (CX3) higher than READ. One core does 3.4–4.3 Mrps, 1.7–2.15× READ with shared QPs, and 13.9× FaRM RPC.
- Novelty 3 → on a shared cluster of 69 machines, 46 hours and about 100 trillion packets, over 50 PB counting other experiments, zero packet loss (about 1500 reordered). From this they estimate five nines of availability. How much CPU dropping software reliability saves: no direct ablation.
- Gaps: FaRM is not open source and DrTM+R depends on RTM, so only published numbers can be compared. CIB has only 11 machines; large clusters are simulated by QP count. Failure recovery is not implemented, so "packet loss means crash" is not measured.

## When it applies
The network must almost never drop packets at the link layer (the paper tests only InfiniBand). If loss becomes common, "packet loss means crash" is not workable. A single message must not exceed the MTU (4 KB). If the NIC supports scalable one-sided operations (such as Portals), the gap shrinks.
