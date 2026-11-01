# LazyLog: A New Shared Log Abstraction for Low-Latency Applications
SOSP'24 · Xuhao Luo, Shreesha G. Bhat, Jiyu Hu, Ramnatthan Alagappan, Aishwarya Ganesan / UIUC, VMware Research · https://doi.org/10.1145/3694715.3695983
Paper type: new system (abstraction + two implementations)

## Dissection
- Background: A shared log is a fault-tolerant, ordered sequence of records that many clients append to and read from. Many shared logs (Corfu, Scalog) spread records over several storage shards and still give a linearizable total order across all shards: if append(b) starts after append(a) completes, b is placed after a. Databases, event sourcing, message queues, journals and log aggregation are built on them.
- Problem: Every existing shared log binds a record to its global position before acknowledging the append. Binding across shards needs coordination, so appends take 1–2 ms even at low load (Scalog), or several RTTs (Corfu). The only cheap escape, acknowledging after one replica (Kafka), loses data on failure and gives order only within a shard. Can a shared log keep durability and linearizable total order across shards, yet append in about 1 RTT?
- Challenges: (1) If position binding leaves the critical path, the order must still be the linearizable one, and it must not change after someone has read it, even when replicas fail. (2) Writing records to replicas without coordination makes each replica see concurrent appends in a different order. (3) If all data goes through the component that decides order, that component becomes the throughput bottleneck for large records.
- Solution:
  1. Insight: in these applications writers never use the returned position, and readers consume later than writers (CQRS readers lag, analytics runs hourly, journals are read only at failover). → Design: append only makes the record durable and returns no position; ordering runs in the background; a read of a not-yet-ordered position waits. → Removes ordering from the append path; reads pay nothing when they lag, and in the worst case the cost moves from append to read.
  2. Insight: if a client writes a record to all f+1 sequencing replicas before the append completes, then any append that starts later lands after it on every replica; replicas can differ only on concurrent appends, and any order of those is legal. → Design: clients write all sequencing replicas in parallel without coordination (1 RTT); the leader's log fixes the order; after a leader failure any follower's log is a valid order; a position becomes readable only once its order is stable. → Gets linearizable order without coordination, and recovery can never rewrite an order that was read.
  3. Insight: once the sequencing layer decides order, storage shards only need to make data durable. → Design (Erwin-st): clients write data straight to shard replicas and only small metadata to the sequencing layer, in parallel. → Removes the sequencing layer as the bottleneck for large records.
- Evidence: at the same throughput, up to 3.8× lower append latency than the authors' Corfu implementation and two orders of magnitude lower than open-source Scalog; on top of Kafka shards, three orders of magnitude lower than Kafka alone while adding total order across shards. Reads 3 ms behind writes see latency close to Corfu; with no lag at 5K appends/s, reads are slower than Corfu's 70 µs. Erwin-bb: ~1M appends/s with 100 B records, flattens with 4 KB; Erwin-st: ~700K appends/s on 10 shards at 29 µs. Sequencing-replica failure: ~15 ms of unavailability, 600 µs of it core recovery. KV store 3.41× faster on write-only.

Safe background (may be explained whenever asked): shared log API, linearizability, total order vs. per-shard order, primary-backup replication, chain replication, Paxos, Kafka partitions and acks, CQRS and event sourcing in general (but not the claim that their readers lag; that is part of exercise 2's brief).
Protected terms (not before the reveal of exercise N): "lazy ordering", "eager ordering", "lazy binding" (2); LazyLog, Erwin, "sequencing layer" (2).

## Exercise 1: Problem finding — why are appends slow, and what must not be given up?
### Brief
You maintain the storage layer for a team that builds a distributed key-value store and an event pipeline on top of an in-house shared log. The log is sharded for throughput and promises a single total order across all shards: if one append finishes before another starts, the second is placed after the first. Its design follows Scalog: a client writes to a shard's primary, the primary replicates to a backup, shards periodically report to a Paxos-replicated ordering service, and the append returns with the record's global position.

1. The KV store's put latency sits at about 1.5 ms p50. You ran the cluster at 5% of capacity overnight and it barely moved.
2. Tracing one put: the record reaches both replicas of its shard early in the request. For most of the remaining time it sits on both replicas and nothing happens to it, until a message arrives from the ordering service. Then the client gets its response.
3. A teammate benchmarked Kafka with acks after the leader replica only: produce latency drops by about 10×. The on-call runbook bans that setting since a broker crash lost already-acknowledged events.
4. The Java client occasionally shows 20 ms p99 spikes, which line up with its GC pauses.
5. The change-data-capture consumer reads updates from all partitions. It needs them in one consistent order, or replicas of a table diverge.

Tutor notes: 1 says the latency is not queueing. 2 is the core one: the record is durable early, but the append waits for the position. 3 shows one strawman being tried (ack after one replica) and the durability constraint that kills it. 5 shows only the cross-shard order constraint; the learner should come up with the strawman it kills (order per partition only, as in plain Kafka). 4 is the distractor.
### Task
In 4–6 sentences: what fails, the root cause, the obvious fix someone would try first and why it fails, and which observations support this. Say which observation, if any, is unrelated.
### Hint
Observation 2 says the record is safe on both replicas long before the client gets its answer. What is the append still waiting for?
### Rubric
1. [P-cause] The append waits for the global position / cross-shard ordering, not for durability. Yes: says the wait is for ordering or position assignment after the data is already durable. Partial: "the ordering service is slow" or "coordination is expensive" without separating it from durability.
2. [P-strawman] The obvious fixes and why they fail: ack after one replica loses data (observation 3); order per partition only (the learner's own) breaks the CDC consumer (observation 5). Yes: names both fixes, each with the guarantee it gives up. Partial: names one, or names the fixes without saying which guarantee each breaks.
3. [P-signal] Latency is not a load problem, and the GC spikes are unrelated. Yes: uses observation 1 (low load) and sets aside 4 with a reason. Partial: does one of the two.
4. [P-goal] A goal a solution can be judged against: appends close to one round trip, with both guarantees kept. Yes: states what must improve and what must be kept. Partial: "make it faster".
### Paper's answer
In a sharded shared log with durability and a linearizable total order across shards, an append is acknowledged only after the record is bound to its global position. Binding needs batching and cross-shard coordination, so appends cost 1–2 ms even at low load (Scalog), or several round trips (Corfu). The data is durable early; the rest is waiting for order. Dropping a guarantee is fast but not acceptable: Kafka with acks=1 loses data, and per-partition order breaks consumers like CDC. The paper's problem: append in about 1 RTT while keeping both durability and linearizable cross-shard order (§1–2).
### Also tell
Nothing extra. The next brief starts from this problem statement.
### Common gaps
- "Make Paxos / the ordering service faster" → Even a perfect ordering service needs one more coordination round after the write. Is a faster round enough to reach 1 RTT?
- Blamed batching → Observation 1 says latency is high even at low load, where batches are small. Which observation did you use to rule batching in or out?
- Took the GC spikes as part of the problem → Which statistic would tell a p99 spike from a steady p50 cost?

## Exercise 2: Solution design — keep both guarantees, append in one round trip
### Brief
The problem (from exercise 1): appends wait for a global position before they are acknowledged, and both durability and linearizable cross-shard order must be kept. Some facts about how the log is used:

1. In the KV store, put() calls append and receives the record's global position. The caller discards it.
2. The CDC consumer reads the log continuously and runs behind the writers. The analytics job reads once an hour. The failover journal is read only when a node fails over.
3. Records average about 4 KB.
4. Each record is written to two replicas of its shard. One round trip inside the cluster is a small fraction of the current append latency.

Tutor notes: 1 and 2 are the insight (nobody needs the position until a read, and reads come later). 3 is neutral here; it matters for the data/metadata split, which is in "also tell". 4 says the target of 1 RTT is reachable if nothing else is on the path.
### Task
Describe your design: (a) the one fact about the problem or workload it exploits, (b) the mechanism, (c) why it is correct, including the failure case that most threatens it, (d) what it costs and when that cost is bad.
### Hint
For each application, look at what it does with the result of append, and when it reads.
### Rubric
1. [S-insight] Writers do not use the position and readers come later, so the order only has to exist by the time someone reads. Yes: states both facts and the conclusion. Partial: only one of the facts, or "order asynchronously" without saying why the applications allow it.
2. [S-mechanism] The append only makes the record durable and returns without a position; ordering runs in the background; a read of a not-yet-ordered position waits. Yes: all three parts, in any words. Partial: background ordering without saying what a read of an unordered position does.
3. [S-correct] The order stays linearizable without coordination on the write path, and a position read once cannot change after a failure. Yes: argues real-time order (for example: a record is on all ordering replicas before the append returns, so any later append lands after it everywhere; only concurrent appends can differ, and any order of those is legal) and that a position is exposed only once its order is stable. Partial: only one of the two, or "use consensus" with no argument. A correct alternative (for example a single sequencer that orders asynchronously, with a stability rule and a stated recovery plan) earns Yes.
4. [S-cost] The cost moves from appends to reads; readers that read right after writing pay it. Yes: names the read-side cost and the workload where it hurts. Partial: "some overhead" with no case.
### Paper's answer
LazyLog makes ordering lazy (§3). An append only makes the record durable: the client writes it in parallel to f+1 sequencing replicas, without coordination, and returns in about 1 RTT with no position. The order is bound in the background from the leader's log; a read of a position that is not yet ordered waits. This is safe because writers in these applications never use the position and readers lag. The order is still linearizable: an append completes only when every sequencing replica has the record, so any later append lands after it on every replica. Replicas can differ only on concurrent appends, and any order of those is legal, so after a leader failure any follower's log is a valid order. A position becomes readable only once its order is stable, so recovery never rewrites what someone has read (§4). The cost moves to reads that do not lag.
### Also tell
- Two implementations (§5). Erwin-bb keeps shards as black boxes (even Kafka) but sends all record data through the sequencing layer. Erwin-st sends only small metadata there and writes data straight to modified shards in parallel, because once the sequencing layer fixes the order, shards only need durability. This removes the sequencing layer as the bottleneck for large records.
- The next exercise uses these names.
### Common gaps
- Proposed a faster sequencer → Your design still returns a position. Which application in the brief needs it?
- Ordered in the background but let readers see any replica's order → A reader reads position 7, then the leader crashes. What does the new leader put at 7?
- No cost stated → Which reader in a different system would read its own write right away?

## Exercise 3: Experiment design — convince a reviewer
### Brief
Problem: sharded shared logs with linearizable cross-shard order acknowledge an append only after binding it to a global position, which costs 1–2 ms even at low load. Method (LazyLog): appends only make records durable, by writing them in parallel to f+1 uncoordinated sequencing replicas (1 RTT). Order is bound in the background from the leader's log, and a position is readable only once its order is stable. Reads of unordered positions wait. Two systems: Erwin-bb (shards as black boxes, all data through the sequencing layer) and Erwin-st (only metadata through the sequencing layer, data straight to shards). The authors claim much lower append latency than eager-ordering shared logs, with the same guarantees.
### Task
List the 2–3 research questions the evaluation must answer. For the most important one, give the baselines, the workload, the metric, and the result that would refute the claim. For the others, one line each.
### Hint
The design moves a cost from one operation to another. Which question checks what that costs?
### Rubric
1. [E-claim] Append latency against eager-ordering logs at the same throughput, with a strong baseline in the same framework. Yes: matched throughput and a fair strongest baseline (for example Corfu built on the same RPC stack, plus Scalog). Partial: compares latency but not at matched throughput, or only against a weak or differently-built baseline.
2. [E-cost] What reads pay, including the worst case: reads with no lag, and the append rate. Yes: varies read lag and includes the no-lag case. Partial: measures read latency only for lagging readers.
3. [E-ablation] The contribution of sending only metadata through the sequencing layer: record size sweep, Erwin-bb vs. Erwin-st. Yes: a sweep that would show the bottleneck. Partial: compares the two systems at one record size.
4. [E-refute] Tails and failures: p99 or a CDF, and a sequencing-replica failure under load. Yes: at least one of them, with what result would hurt the claim. Partial: mentions them without a metric.
### Paper's answer
§6. (1) Append latency at ~30K appends/s per shard, 4 KB records, 1 and 5 shards: up to 3.8× lower than Corfu (re-implemented on the same eRPC stack) and two orders of magnitude lower than open-source Scalog (gRPC); on Kafka shards, three orders of magnitude lower than Kafka alone. (2) Reads 3 ms behind writes match Corfu. With no lag at 5K appends/s, reads are slower than Corfu's 70 µs, because few records are ordered per batch. (3) Erwin-bb reaches ~1M appends/s with 100 B records and flattens at 4 KB; Erwin-st reaches ~700K appends/s on 10 shards at 29 µs. (4) Killing a sequencing replica gives ~15 ms of unavailability, 600 µs of it core recovery and the rest ZooKeeper. Where it falls short: the main cluster has only 5 shards; one slow sequencing replica raises every append's tail and is not isolated; linearizability is argued by a proof sketch, with no test that targets recovery bugs.
### Also tell
The KV store built on Erwin is 3.41× faster on a write-only workload.
### Common gaps
- Compared at different throughputs → If LazyLog runs at half the load of Corfu, what does the latency gap prove?
- Only friendly readers → At what read lag and append rate would LazyLog lose to Corfu, and is that region common?
- Missed the slow-replica case → Every sequencing replica must ack each append. How would you show what one slow replica does to the tail?
