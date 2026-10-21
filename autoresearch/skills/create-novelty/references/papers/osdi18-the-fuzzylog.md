# The FuzzyLog: A Partially Ordered Shared Log
OSDI'18 · Joshua Lockerman, Jose M. Faleiro et al. / Yale, UC Berkeley, MSR, etc. · Full text: https://www.usenix.org/system/files/osdi18-lockerman.pdf (camera-ready) · Selected: Community favorite (3 sources: DSRG (charap.co), Morning Paper, Murat blog)

**One sentence**: What applications really need is only "ordered within a shard, causal across regions". So replacing the shared log's total order with a "shard × region" partially ordered DAG removes the global sequencer.

## Problem
A shared log lets control plane services append all updates to one globally ordered durable log. Each server replays it to reach a consistent state, and strong consistency, durability, and atomicity follow. A shared-log version of ZooKeeper takes only 1K lines.
But total order is expensive: at 40Gbps, 20 servers need a sequencer to issue 24 million sequence numbers per second, while existing systems manage only 200K–600K. Across regions, total order cannot stay available at all under network partitions.

## Strawman / Baseline
- **Centralized off-path sequencer (CORFU, Tango, vCorfu)**: Clients first get a sequence number, then write to storage → Even unrelated shards all go through this counter, so its throughput is the system's limit. A distant client pays one extra round trip per append.
- **Bypass the sequencer (large batches, out-of-order writes, fill holes later)**: Throughput goes up, but append latency rises, which the control plane cannot tolerate.
- **Hand-write a separate partial-order protocol (Paxos+2PC, causal consistency in COPS/Eiger, RedBlue, TARDiS)**: Each system reimplements commit, consensus, and causality tracking. This is complex and hard to compose.
- **Skeen's multi-group ordering algorithm**: Can give appends that span several servers a consistent order, but assumes participants do not fail. Yet the clients that issue appends are unreplicated application servers, and they crash.

## Novelty
1. **Order is needed for only two reasons, shards and regions, so the log can be cut along these two dimensions**
   Insight: Updates to different shards need no ordering. Cross-region deployments need only causal consistency anyway, to avoid cross-region coordination on the critical path.
   So: The log is a DAG. Each shard is a color. Each color has one totally ordered chain per region, and cross edges between chains record causal dependencies. Each region appends only to its own chain, so merges never conflict. Atomic appends to several colors implement cross-shard transactions. With one color and one region, it reduces to an ordinary shared log.
   Each color is stored on its own replica group, and a single-color append completes in one phase without a global sequencer. This removes the bottleneck of the first baseline.
2. **Ordering across colors happens only within one region, so adding client crash recovery to Skeen is enough**
   Insight: Under the semantics above, the logs touched by a multi-color append are all in the local region. Ordering cannot be blocked by cross-region partitions and only needs to handle occasional client crashes.
   So: Skeen's algorithm (each partition first returns a local timestamp, and the maximum becomes the global order) plus leases, fencing, and a WAL. Without failures it completes in two phases. After a client crash, another client takes over in three phases. A crash causes only a latency spike, not cascading recovery. The recovery protocol has a Coq proof.
3. **A network partition is just a fork in the DAG, so switching consistency becomes a replay policy**
   Insight: During a partition, appends on both sides are recorded in the DAG. After healing, all servers see the same fork.
   So: Normally CAPMap writes to the primary region's chain through a proxy (linearizable). During a partition, the secondary region writes to its local chain instead (downgraded to causal+). After healing, a join node is appended, and all servers replay the forked segment in the same deterministic order. This answers "total order is unavailable during partitions" without a new protocol.

## Evidence
- End to end: ZooKeeper on FuzzyLog (1881 lines of Rust) does 3 million single-key writes and 150,000 cross-shard atomic renames per second on 6 nodes. ZooKeeper does 36K/66K ops/s (different language and maturity, and its rename is not atomic). Map-style applications take 201–424 lines.
- Novelty 1 → Tango is emulated inside Dapple (5 partitions plus 1 sequencer). Tango stops scaling beyond 4 clients. Dapple scales nearly linearly at 0% multi-color appends, is 2× faster at 1%, equal at 10%, and slower at 100%. AtomicMap scales linearly from 1 to 16 machines, peaking above 5.5 million puts/s (without replication).
- Novelty 2 → Latency distribution: single-color 1 phase < two-color 2 phases < recovery 3 phases. No comparison with other fault-tolerant ordering protocols.
- Novelty 3 → A 2-second partition is injected between Ohio and Tokyo (RTT 168ms). The secondary region switches to local low latency with weak consistency, and there is one latency spike at healing. Only qualitative curves.
- Gaps: Tango is emulated, not the original system. CRDTMap's "regions" are virtual regions in the same EC2 region. Durability assumes battery-backed DRAM. No comparison with causal stores such as COPS/Eiger.

## When it applies
Application state must be splittable into shards, and most operations must touch only one shard. When the share of multi-color appends approaches 100%, the partial order degrades into a total order and becomes slower than a centralized sequencer. Multi-color appends are only serializable; stronger semantics need a transaction protocol on top.
