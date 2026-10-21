# LazyLog: A New Shared Log Abstraction for Low-Latency Applications
SOSP'24 · Xuhao Luo, Shreesha G. Bhat, Jiyu Hu, Ramnatthan Alagappan, Aishwarya Ganesan / UIUC, VMware Research · Full text: https://par.nsf.gov/servlets/purl/10557948 (published conference version archived on NSF PAR, ACM pages 296–309) · Selected: Best Paper

**One sentence**: Applications only need a total order when they read, and readers naturally lag behind writers, so an append only needs to be made durable, and ordering can move to the background.

## Problem
A shared log (Corfu, Scalog) provides a linearizable total order over many storage shards: an append that starts after another append completes is always placed after it.
Databases, event sourcing and message queues all use it to record writes, but a Scalog append takes 1–2 ms; in a survey, one third of practitioners said write latency matters most.

## Strawman / Baseline
- **Scalog**: first replicate primary-backup within a shard, gather a batch, pass it to a Paxos ordering layer to set global positions, and only then acknowledge the append. → The critical path has intra-shard coordination, batching and global coordination; even at low load it takes 1–2 ms.
- **Corfu**: first get a position from the sequencer, then write replicas one by one in a chain; the position is bound only when the write reaches the chain tail. → 4 RTTs with 3 replicas.
- **Kafka acknowledging after one replica**: 10× lower latency, but failures lose data, and order holds only within a shard.
- **Naive "write first, order later"**: clients write several replicas in parallel without coordination, and each replica has a different order. If the primary replica's order has already been read and it then fails, recovering from another replica changes the order, which breaks linearizability.
- **Send all data through the ordering replicas too**: the authors' first implementation, Erwin-bb (black-box; shards can directly use existing systems such as Kafka), works this way. → With 4KB records the ordering replicas become the bottleneck, and throughput saturates quickly.

## Novelty
1. **A total order is only needed at read time, and reads naturally lag behind writes**
   Insight: writers in these applications do not use the returned position (e.g. Firescroll); readers consume at their own pace and often lag far behind (CQRS, offline analytics, journals read only on failover).
   So: an append only guarantees durability and returns no position; positions are bound in the background in batches; a read of a position not yet ordered waits for ordering to finish. When reads lag, the background has long finished ordering, and reads pay nothing extra; in the worst case the ordering cost just moves from the append to the read.
2. **Writing all replicas in parallel without coordination already preserves real-time order**
   Insight: assume f+1 ordering replicas (they hold records only briefly in memory and order them in the background). If append(a) completes before append(b) starts, a is already on all replicas, so b is placed after a on every replica. Replicas can only differ in the order of concurrent appends, and any order of those is legal.
   So: the client writes all ordering replicas in parallel and the append completes in 1 RTT. The primary replica's log decides the order; after it fails, any replica can be used to recover. The "readable upper bound" advances only after all replicas have reclaimed the ordered records, so an order that has been read cannot be rewritten by recovery. This closes the hole in the naive approach.
3. **Durability and ordering can take separate paths**
   Insight: since the order is decided by the ordering replicas, shards on the critical path only need to make data durable, with no primary-backup coordination of order.
   So: the second implementation, Erwin-st (scalable throughput), has the client write data directly to each replica of the shard in parallel within the same RTT, and write only ⟨record-id, shard-id⟩ metadata to the ordering replicas, which are no longer the bottleneck.

## Evidence
- End to end (4KB records, same throughput): up to 3.8× lower latency than the authors' own Corfu implementation, and two orders of magnitude lower mean and p99 than Scalog's open-source implementation; with Kafka as the shards, three orders of magnitude lower than Kafka alone, plus a total order across shards. KV store: 3.41× faster write-only, 1.04× read-heavy; journaling 1.17–1.66× faster.
- Novelty 1 → with reads 3 ms behind, read latency is close to Corfu. With no lag, at 45K/s it is only slightly slower than Corfu; at 5K/s almost all reads take the slow path, and latency is higher than Corfu's 70 µs.
- Novelty 2 → after an ordering replica fails, service stops for about 15 ms; core recovery takes only 600 µs, and the rest is spent in ZooKeeper. Correctness has only a proof sketch.
- Novelty 3 → Erwin-bb reaches about 1M appends/s with 100B records and saturates quickly with large records; Erwin-st reaches about 700K appends/s on 10 shards, with 29 µs latency.
- Gaps: the comparison with Scalog mixes in implementation differences (gRPC vs. eRPC). The main cluster has only 5 shards. All ordering replicas must be written, so any replica failure needs reconfiguration, and a slow replica raises tail latency. Erwin-st scales worse than Scalog.

## When it applies
Writers must not need the position right away, and there must be a time gap between readers and writers. If reads always follow writes immediately, with low write rates and small batches, reads bear the ordering latency.
