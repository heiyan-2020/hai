# LineFS: Efficient SmartNIC Offload of a Distributed File System with Pipeline Parallelism
SOSP'21 · Jongyul Kim et al. / KAIST, KTH, KAUST, UT Austin · Full text: https://www.cs.utexas.edu/users/witchel/pubs/kim21sosp-linefs.pdf (author home page, camera-ready) · Selected: Best Paper

**One sentence**: On the DFS write path, only "persist" is latency-critical; everything else can be pipelined asynchronously in log order, so a SmartNIC with slow cores and PCIe can handle it.

## Problem
Client-local PM DFSes (such as Assise) keep data in persistent memory (PM) on the machine where the application runs, to avoid the network. But publishing, indexing, replication and leases all use client host CPU.
On 100GbE with 8 clients, Assise uses 5.09 cores, 2.4× Ceph. When co-located with CPU-heavy jobs, both sides slow down and jitter.

## Strawman / Baseline
- **Keep the DFS on the host (Assise)**: co-located with streamcluster, streamcluster is 72% slower on the primary and 66% slower on the replica. When the replica is busy, the 99.9th percentile fsync latency reaches 8331 µs.
- **Host busy-polling for replication** → needs reserved dedicated cores; switching to blocking makes context-switch overhead too large for small PM writes under 10 µs.
- **Hyperloop (offload replication to an RDMA NIC)**: the host still has to post RDMA verbs periodically → a long tail whenever the host is busy.
- **Move the DFS straight onto the SmartNIC (BlueField, 16 ARM cores at 800 MHz)**: accessing host PM over PCIe takes several µs, vs. about 100 ns over DDR. Offloading Assise's SharedFS directly drops throughput to below 1/30.

## Novelty
1. **Only persist is on the critical path; everything else can move to the NIC and run asynchronously**
   Insight: the application only needs "the write is persistent", i.e. a sequential append to the local PM log, which host cores do fastest. Publishing to the shared area, checksumming, replication and recording leases can all run in the background; only replication must finish by fsync.
   So (persist-and-publish): LibFS on the host writes a private PM log; NICFS on the NIC reads the log and does publishing, replication, checksumming and lease management. Apart from fsync, slow cores and PCIe latency are off the critical path, and host cores go back to the application.
2. **The log is ordered by nature and each stage uses different resources, so it can be pipelined by chunk**
   Insight: the log is cut into 4 MB chunks. Fetching data (PCIe), checksumming (compute), and publishing or transfer (PCIe/network) use different resources. As long as commits follow log order, linearizability and prefix crash consistency (after a crash, what remains is always a prefix of the write sequence) are kept.
   So: many chunks flow through the stages in parallel; the publish and replicate pipelines share the first two stages, and a stage with a long queue gets more threads automatically. A replica writes its local PM while forwarding to the next hop. Many slow cores hide the PCIe latency, which answers the root cause "moving it over directly is 30× slower".
3. **The NIC is a separate, dedicated execution domain**
   Insight: cores on the NIC do not run applications, so busy-polling there takes nothing from applications; when the host OS crashes, the NIC can still access PM over PCIe.
   So: dedicated threads on the NIC busy-poll low-latency connections, and replication needs no host involvement, which fixes busy-polling eating cores and Hyperloop's long tail. When the host goes down, NICFS on the replica keeps serving; idle NIC cores can compress replication data.

Other design: copies during publishing go to host I/OAT DMA, with batched submission plus interrupts; leases are granted first and persisted asynchronously.

## Evidence
- End to end (3 nodes, busy replica): LevelDB sequential insert latency 80% lower than Assise; random and synchronous inserts 27% lower. Filebench Fileserver throughput 79% higher, but Varmail is 21% slower (frequent fsync, and open needs a permission check over PCIe).
- Novelty 1 → co-location: throughput 46% higher than Assise; streamcluster only 49%/19% slower (72%/66% under Assise). With a busy replica, 99.9th percentile 204 µs vs. 8331 µs. Cost: with an idle replica, average latency 149 µs vs. 76 µs for Assise.
- Novelty 2 → without the pipeline (LineFS-NotParallel): throughput at least 60% worse; it uses only 4.1 ARM cores, while LineFS uses 5.8.
- Novelty 3 → 99.9th percentile latency: Hyperloop 4125 µs, LineFS 204 µs. During an 8 s host crash, Varmail throughput does not drop. Compression saves 29–72% of bandwidth; at an 80% compression ratio, sort is 10.6% faster.
- Gaps: only 3 nodes and 25 Gbps; Hyperloop was reimplemented by the authors, driven by pre-generated traces, and compared only on microbenchmarks.

## When it applies
The workload must be mainly writes that can be replicated asynchronously. Small writes with frequent fsync and frequent open expose the NIC's slow latency; the read path is not offloaded and gains nothing.
