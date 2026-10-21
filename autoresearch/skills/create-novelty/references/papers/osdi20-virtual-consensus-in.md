# Virtual Consensus in Delos
OSDI'20 · Mahesh Balakrishnan et al. / Facebook · Full text: https://www.usenix.org/system/files/osdi20-balakrishnan.pdf (camera-ready) · Selected: Best Paper

**One sentence**: To replace consensus, you only need the old log to stop accepting appends and agreement on a new mapping; so reconfiguration can be a generic layer, and the log below only needs to be sealable.

## Problem
Facebook had to launch a control-plane database (Delos) within 6–9 months, and then keep switching to faster consensus.
Consensus systems are monolithic: ZooKeeper still runs its old protocol after ten years, and switching to Raft means rewriting the whole system.

## Strawman / Baseline
- **Monolithic protocols (Raft, ZAB, VR)**: Leader election, membership change, and ordering are tangled together → changing only the ordering mechanism still means rewriting the control plane.
- **Use only the shared log API (CorfuDB, LogDevice)**: The upper layer does not care about the protocol → but it cannot migrate to another implementation without downtime, and is tied forever to that implementation's performance and fault tolerance.
- **Write the next configuration into the log itself (SMART, Raft joint consensus, Stoppable Paxos)** → requires every underlying log to be writable with high availability, that is, to implement fault-tolerant consensus itself.
- **The simplest primary-backup ordering**: one sequencer (a node that assigns a position to each append and then forwards it to all storage nodes) → with 9 replicas it sends 8 copies per entry and becomes the bottleneck.

## Novelty
1. **Reconfiguration depends only on "seal + swap mapping", not on log internals**
   Insight: To replace the underlying log without downtime, only two things are needed: make the old log reject new appends, and agree on "which address range maps to which log". Neither looks inside the log.
   So: VirtualLog builds its address space from a chain of Loglets (logs that only implement the shared log API). Reconfiguration = seal the last Loglet, get its tail, then write the new chain to an external MetaStore (a versioned register that writes only when the version matches). Changing the protocol, the code base, or the deployment form all go through this one path. This solves the first two baselines.
2. **Sealing is weaker than consensus, so Loglets need not be fault tolerant**
   Insight: A seal just sets a bit on a majority. It can be built from an atomic register, is weaker than consensus, and is not bound by FLP (the impossibility theorem for consensus under asynchrony). The new configuration is written to the MetaStore, not into the old log, so the old log does not need to be writable.
   So: A Loglet can be a statically configured primary-backup protocol with no leader election; if the sequencer dies, VirtualLog seals it and swaps in a new instance. Fault-tolerant consensus is implemented only once, in the MetaStore (plain single-slot Paxos, used only during reconfiguration). This removes the requirement of the 3rd baseline.
3. **VirtualLog needs only append, a tail with a seal bit, and seal, so a composition of several Loglets is itself a Loglet**
   Insight: If the composite seals every child Loglet when it is sealed, it satisfies the same interface, and VirtualLog does not need to know it is a composite.
   So: StripedLoglet (about 300 lines) assigns logical positions to child Loglets in turn (L0→A, L1→B, L2→C, L3→A…). An append is acknowledged only after all earlier positions are filled, so it is still a total order. When the child Loglets use the same storage nodes but each has its own sequencer, the 8 sends per entry are shared among several sequencers, which targets the 4th bottleneck. When the child Loglets have disjoint nodes, storage is also sharded, and throughput grows with the number of stripes.

Other design: Operations that touch only sealed segments (truncation, rebuild) do not need a seal.

## Evidence
- End to end: launched in 8 months (with ZooKeeper as the Loglet), 1.8 billion transactions per day; in 2019 it switched online to NativeLoglet, with p99 of multi-get and index queries down 10× and multi-put down 5×, with no downtime.
- Novelty 1 → Switching to a separately deployed LogDevice: throughput at 15 ms p99 went from 15K to 150K ops/s (10×, including the effect of 2× machines and NVMe); +33% on dedicated SSDs. After a load spike, p99 exceeded 1 s, and after an online switch it went back under 15 ms. Cost of virtualization: append p99 +100–150 µs, reconfiguration tens of ms; pure puts at 26K/s versus ZooKeeper at 30K (the gap comes from RocksDB).
- Novelty 2 → NativeLoglet was written and launched in under 4 months. No comparison of engineering effort against a fault-tolerant Loglet: no direct ablation.
- Novelty 3 → On 9 nodes, two sequencers in rotation are 25% faster than NativeLoglet; a pure log with 30 stripes reaches 1M+ 1KB appends/s, and 750K/s for 4KB (CORFU 570K, Scalog 255K, not on the same hardware).
- Gaps: The 10× latency gain comes mainly from ZKLoglet writing one ZooKeeper node per append, which is crude; it proves "it can be swapped". The paper gives no formal proof of the reconfiguration protocol.

## When it applies
Requires a totally ordered log API; protocols that rely on commutativity or speculative execution do not fit. Each reconfiguration costs tens of ms and one seal, which is costly with frequent planned leader changes or across geographic regions.
