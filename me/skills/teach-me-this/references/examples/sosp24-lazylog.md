# LazyLog: A New Shared Log Abstraction for Low-Latency Applications
SOSP'24 · Xuhao Luo, Shreesha G. Bhat, Jiyu Hu, Ramnatthan Alagappan, Aishwarya Ganesan / UIUC, VMware Research · https://doi.org/10.1145/3694715.3695983
Paper type: new system (abstraction + two implementations)
> Spoiler: this card dissects the paper. Do not read it if you want to train on this paper.

## Dissection
- Background: A shared log is a fault-tolerant, ordered sequence of records that many clients append to and read from. Many shared logs (Corfu, Scalog) spread records over several storage shards and still give a linearizable total order across all shards: if append(b) starts after append(a) completes, b is placed after a. Databases, event sourcing, message queues, journals and log aggregation are built on them.
- Problem: Every existing shared log binds a record to its global position before acknowledging the append. Binding across shards needs coordination, so appends take 1–2 ms even at low load (Scalog), or several RTTs (Corfu). The only cheap escape, acknowledging after one replica (Kafka), loses data on failure and gives order only within a shard. Can a shared log keep durability and linearizable total order across shards, yet append in about 1 RTT?
- Challenges: (1) If position binding leaves the critical path, the order must still be the linearizable one, and it must not change after someone has read it, even when replicas fail. (2) Writing records to replicas without coordination makes each replica see concurrent appends in a different order. (3) If all data goes through the component that decides order, that component becomes the throughput bottleneck for large records.
- Solution:
  1. Insight: in these applications writers never use the returned position, and readers consume later than writers (CQRS readers lag, analytics runs hourly, journals are read only at failover). → Design: append only makes the record durable and returns no position; ordering runs in the background; a read of a not-yet-ordered position waits. → Removes ordering from the append path; reads pay nothing when they lag, and in the worst case the cost moves from append to read.
  2. Insight: if a client writes a record to all f+1 sequencing replicas before the append completes, then any append that starts later lands after it on every replica; replicas can differ only on concurrent appends, and any order of those is legal. → Design: clients write all sequencing replicas in parallel without coordination (1 RTT); the leader's log fixes the order; after a leader failure any follower's log is a valid order; a position becomes readable only once its order is stable. → Gets linearizable order without coordination, and a read order can never be rewritten by recovery.
  3. Insight: once the sequencing layer decides order, storage shards only need to make data durable. → Design (Erwin-st): clients write data straight to shard replicas and only small metadata to the sequencing layer, in parallel. → Removes the sequencing layer as the bottleneck for large records.
- Evidence: at the same throughput, up to 3.8× lower append latency than the authors' Corfu implementation and two orders of magnitude lower than open-source Scalog; on top of Kafka shards, three orders of magnitude lower than Kafka alone while adding total order across shards. Reads 3 ms behind writes see latency close to Corfu; with no lag at 5K appends/s, reads are slower than Corfu's 70 µs. Erwin-bb: ~1M appends/s with 100 B records, flattens with 4 KB; Erwin-st: ~700K appends/s on 10 shards at 29 µs. Sequencing-replica failure: ~15 ms of unavailability, 600 µs of it core recovery. KV store 3.41× faster on write-only.

## Reveal schedule
| Fact | Earliest stage |
|------|----------------|
| Shared logs exist, their API, linearizable cross-shard order, Corfu/Scalog/Kafka architectures | 1 |
| Append latency is high even at low load; Kafka acks-after-one-replica is 10× faster but loses data | 1 |
| The append waits for global position binding before it is acknowledged | 1 (learner should find this) |
| Writers ignore the returned position | 2 (hint) |
| Readers lag behind writers | 2 (hint) |
| Uncoordinated replica writes preserve real-time order | 2 (learner should find this after challenge) |
| Do not expose order until stable | 2 |
| Separate data path from ordering metadata | 2 |
| Names LazyLog, Erwin-bb, Erwin-st; any result numbers from §6 | 3 |

Protected terms: "lazy ordering", "eager ordering", "lazy binding" (3); LazyLog, Erwin (3); "sequencing layer" as the paper's component (2, only after the learner proposes something like it).
Safe background: shared log API, linearizability, total order vs. per-shard order, primary-backup replication, chain replication, Paxos, Kafka partitions and acks, CQRS and event sourcing in general (but not the claim that their readers lag; that is a stage-2 hint).

## Stage 1: Find the problem
### Background to give
You maintain the storage layer for a team that builds a distributed key-value store and an event pipeline on top of an in-house shared log. The log is sharded for throughput and promises a single total order across all shards: if one append finishes before another starts, the second is placed after the first. Its design follows Scalog: a client writes to a shard's primary, the primary replicates to a backup, shards periodically report to a Paxos-replicated ordering service, and the append returns with the record's global position.

### Phenomena
1. The KV store's put latency sits at about 1.5 ms p50. You ran the cluster at 5% of capacity overnight and it barely moved.
2. A teammate proposed switching the event pipeline to Kafka with acks after the leader replica only. In their benchmark produce latency drops by about 10×. The on-call runbook bans that setting since an incident in which a broker crash lost already-acknowledged events.
3. Tracing one put: the record reaches both replicas of its shard early in the request. For most of the remaining time it sits on both replicas and nothing happens to it, until a message arrives from the ordering service; then the client gets its response.
4. The Java client occasionally shows 20 ms p99 spikes, which line up with its GC pauses.
5. Someone suggested dropping the shared log for plain per-partition Kafka. The change-data-capture consumer rejected it: it needs updates from different partitions in one consistent order, or replicas of a table diverge.
6. In a practitioner survey that is circulating on your team (RedPanda, 300 respondents), a third rate ingestion latency as the most important latency metric of their log deployment.

Tutor notes: 1 says the latency is not queueing; 3 is the core one (the record is durable early but the append waits for the position); 2 and 5 are the constraints (durability, cross-shard order) that rule out the cheap fixes; 6 says the problem matters; 4 is the distractor.

### Hint ladder
- L1: Phenomenon 3 says the record is already safe on both replicas long before the client gets its answer. What is the append still waiting for?
- L2: Phenomena 2 and 5 each remove one of the two guarantees and get faster. Which two guarantees does your log give, and which one costs the waiting in phenomenon 3?
- L3: The append returns a global position. To return it, every shard's progress must be agreed on first. Could the problem be stated as "keep both guarantees, but stop the append from paying for ___"?
- Bottom-out: state the target below.

### Target
In a sharded shared log that gives durability and a linearizable total order across shards, an append is acknowledged only after the record is bound to its global position, which needs batching and cross-shard coordination. So appends cost 1–2 ms even at low load. Dropping a guarantee (ack after one replica, or order per shard only) is fast but not acceptable. The problem: make appends fast (about 1 RTT) while keeping both durability and linearizable cross-shard order.
Checklist:
- [core] Append latency is high regardless of load (not a capacity problem).
- [core] The cause is that the append waits for global ordering / position assignment, not for durability.
- [core] Both durability and cross-shard total order must be kept; the cheap fixes give one up.
- [detail] Ingestion latency matters to many users of shared logs.

### Common wrong turns
- "Make Paxos / the ordering service faster" → Even a perfect ordering service costs at least one more round of coordination after the data is written. Is a faster round enough to get to 1 RTT?
- "Batch less" → Phenomenon 1 says latency is high even at low load, where batches are small. Is batching the root cause or one part of it?
- "It's the GC spikes" → That explains p99 spikes, not a steady 1.5 ms p50.

## Stage 2: Derive the solution
### Seed hint
Go back to the applications on top of the log. For each API call they make, look at what they do with the result, and when.

### Path
1. Learner may first try to make ordering cheaper (better consensus, smaller batches). Wall: any scheme that must know the position before returning pays a coordination round after the write. Ask: who actually needs the position, and when?
2. Learner finds (with hints) that writers ignore the position and readers come later, and proposes "make the record durable, ack, order in the background". Wall 1: if clients write replicas without coordination, the replicas see concurrent appends in different orders. Whose order counts?
3. Learner proposes "a leader's order wins". Wall 2: a reader reads position 7 from the leader's order, then the leader crashes; the new order from another replica places a different record at 7. Ask: what must hold before a position is shown to anyone? And does any replica's order respect real time, given how the append completes?
4. Learner sees that an append completes only after all replicas have the record, so later appends land after it everywhere; only concurrent ones may differ, and any order of those is linearizable. Plus: positions become readable only after the order is stable.
5. Wall 3: all record data passes through these ordering replicas; with 4 KB records they saturate. Ask: what does the ordering component actually need to see?
6. Learner proposes sending only record IDs to the ordering replicas and data straight to shards in parallel; shards then need only durability, not order.
Also discuss: what happens to a read that arrives before its position is ordered? (It waits; the cost moves from append to read. When is that bad?)

### Hint ladder
Idea 1 (order only at read time):
- L1: In the KV store, does the writer ever look at the position the append returns?
- L2: How far behind the writers are the CDC consumer, the hourly analytics job, and the failover journal reader?
- L3: If nobody needs the position until someone reads it, by when does the order have to exist?
- Bottom-out: the order only has to be fixed before the position is read; the append only needs durability.
Idea 2 (uncoordinated writes still respect real time):
- L1: When append(a) returns, which replicas hold a?
- L2: If append(b) starts after that, where can b land relative to a on each replica?
- L3: So which pairs of records can appear in different orders on different replicas, and does it matter how you order those?
- Bottom-out: only concurrent appends can differ, any order of them is linearizable, so any one replica's log is a valid order; expose a position only after its order is stable.
Idea 3 (split data from ordering):
- L1: What does the ordering component need to know about a record to place it?
- L2: Who actually has to store the bytes durably for the long term?
- Bottom-out: write only IDs to the ordering replicas and data straight to shards, in parallel; shards only need durability.

### Target
1. The order is needed only when a position is read, and readers lag; so append only makes the record durable, ordering runs in the background, and a read of an unordered position waits.
2. Writing a record to all ordering replicas before acknowledging preserves real-time order on every replica; any replica's order is valid; positions are readable only after the order is stable, so recovery cannot change what was read.
3. The ordering replicas need only record IDs; data goes straight to shards in parallel, so large records do not bottleneck the ordering path.
Checklist:
- [core] Move ordering off the append path; order before reads.
- [core] Justify why this is safe for the applications (writers do not need position; readers lag).
- [core] How the order is still linearizable and stable under failure.
- [detail] Separate data from ordering metadata for throughput.
- [detail] Reads of unordered positions wait; worst case shifts the cost to reads.

## Stage 3: Design the experiments
### Summary to give
Problem: sharded shared logs with linearizable cross-shard order acknowledge an append only after binding it to a global position, which costs 1–2 ms even at low load. Method (LazyLog): appends only make records durable, by writing them in parallel to f+1 uncoordinated sequencing replicas (1 RTT). Order is bound in the background from the leader's log, and a position is readable only once its order is stable. Reads of unordered positions wait. Two systems: Erwin-bb keeps shards as black boxes (even Kafka) but sends all data through the sequencing layer; Erwin-st sends only metadata there and data straight to modified shards.

### Key research questions
1. How much lower is append latency than eager-ordering logs, at the same throughput? This is the headline claim.
2. What do reads pay, and when is it bad? The design moves cost from append to read; a reviewer will ask for the worst case, not just the friendly case.
3. Does sending only metadata through the sequencing layer fix the large-record throughput limit? This is the ablation for idea 3.
4. What happens when a sequencing replica fails? Idea 2 is a correctness argument; its availability cost must be measured.

### Key experiments
1. Append latency. Baselines: Corfu (re-implemented in the same framework) and Scalog (public artifact); Kafka alone vs. Kafka shards under Erwin-bb. Workload: append-only, 4 KB records, each shard at ~30K appends/s, 1 and 5 shards. Metric: mean and p99, plus CDF. Result: up to 3.8× vs. Corfu, two orders of magnitude vs. Scalog. Weak designs: comparing at different throughputs; reporting only the mean; comparing against an artifact on a different RPC stack (here Scalog uses gRPC, Erwin eRPC) without a same-framework baseline (which is why Corfu was re-implemented).
2. Read cost. Vary how far reads lag behind appends (0 to a few ms) and the append rate. Result: at 3 ms lag reads match Corfu; with no lag at a low rate (5K/s) reads are slower than Corfu, since few records are ordered per batch. Weak designs: testing only lagging readers; not varying the append rate (which controls batch size).
3. Record size and scaling. Sweep record size for Erwin-bb vs. Erwin-st; scale shards. Result: Erwin-bb ~1M appends/s at 100 B and flattens at 4 KB; Erwin-st ~700K appends/s on 10 shards at 29 µs. Weak design: only small records, which hides the bottleneck.
4. Failure. Kill a sequencing replica under load and plot throughput over time. Result: ~15 ms unavailable, 600 µs core recovery, the rest is ZooKeeper.

### Reviewer probes
- At what read lag and append rate does LazyLog lose to Corfu? Is that region common for real applications?
- Every sequencing replica must ack each append, so one slow replica raises tail latency. How would you show that?
- Is linearizability argued only by a proof sketch? What test would catch a bug in recovery?
- Why only 5 shards in the main cluster? Does the scaling result transfer?

## Stage 4: Apply and extend
### Scenarios
1. Readers that never lag. A state-machine-replication system appends a command and immediately reads up to the tail to apply it. Setup: same log, but every append is followed by a read of its position. Question: what does LazyLog do here, and can you get back the benefit? Good directions: order in larger background batches so only the first read waits; let the application declare which appends will be read right away and order those eagerly; return a "ticket" that resolves to a position later.
2. Find the same pattern elsewhere. Question: name another system that computes something on the write path that consumers use only much later, and argue whether deferring it is safe. Good directions: assigning commit timestamps in a distributed database whose readers use snapshots; building secondary indexes on ingest; computing dedup or compression at write time in a backup system. A good answer names both facts: the result is not used by the writer, and the consumer is late.
3. Geo-distribution. Setup: sequencing replicas sit in three regions, so one WAN RTT is ~50 ms. Question: does the design still give 1 RTT appends, and what becomes the bottleneck? Good directions: writing to all replicas means the slowest region sets append latency, so the "all replicas" requirement now hurts; consider quorum-based variants and what they do to the real-time-order argument.
