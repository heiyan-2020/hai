# Noria: dynamic, partially-stateful data-flow for high-performance web applications
OSDI'18 · Jon Gjengset, Malte Schwarzkopf et al. / MIT CSAIL, NTNU, Harvard · Full text: https://www.usenix.org/system/files/osdi18-gjengset.pdf (camera-ready) · Selected: Community favorite (3 sources: Micah Lerner blog, Morning Paper, Murat blog)

**One sentence**: Web pages read only a few parameterized keys. So a materialized view only needs to store the entries that have been read, and it recomputes missing ones from upstream on demand.

## Problem
88%–97% of the queries in a web backend are reads. To make reads fast, developers either denormalize by hand (Lobsters stores vote counts separately in the stories table) or add memcached and write their own invalidation logic. Both are easy to get wrong. Writing the "natural" SQL directly is too slow.

## Strawman / Baseline
- **Database computes at read time (MariaDB)**: At 1000 pages/s, Lobsters fills all 16 cores with read computation. Without hand-precomputed vote counts it gets only 20 pages/s.
- **Database + memcached**: Writes must invalidate and reads must refill. When a hot key is invalidated, many clients hit the database at the same time (thundering herd).
- **Materialized views in a commercial database (System Z)**: Writes to the view contend on popular entries. When a query changes, the view must be rebuilt.
- **Streaming dataflow (Naiad/Differential Dataflow, Spark Streaming)**: State is either kept fully in memory or kept only for a time window (old data cannot be read). Changing a query needs a restart. Differential Dataflow coordinates through global progress tracking and does not scale as machines are added.
- **Keep full materialized views for all queries**: The full state of Lobsters is 789 MB, 8 times the 137 MB of base tables. A new query must first backfill its full state, and writes are blocked during that time.
- **Naively store only partial state**: A result recomputed on demand is a snapshot of one moment. It races with updates that are still propagating, and the cache can stay wrong forever.

## Novelty
1. **Reads land on only a few keys, so a materialized view can "partly exist" like a cache**
   Insight: Web page queries take parameters (WHERE id=?) and access is skewed. The entries that are read are only a small part of the total. Every missing entry can be derived again from upstream state.
   So: Stateful operators start fully empty. When a read hits a missing entry, the operator recursively sends an upquery (a request for data) upstream and fills in the result. Entries can be evicted. Updates sent to an evicted entry are simply dropped, so write load also goes down. Partial state is used only when the upquery can use an index. This removes the bloat of full views, and there is no need to keep only a time window.
2. **Ordering per entry prevents races, with no global coordination**
   Insight: Only the order of "updates and upquery responses on the same entry" matters for correctness.
   So: Each operator processes updates and upqueries on the same entry in a total order, and downstream operators keep this order. A join's upquery runs only inside a chain of operators that execute on a single thread, so no updates are in flight along the way. When an upstream entry is evicted, the downstream entries that depend on it are evicted too. This guarantees eventual consistency and avoids global progress tracking.
3. **Partial state plus subexpression reuse lets queries change without downtime**
   Insight: A new view can start empty. Common subexpressions of several queries (for example, vote counting) can be merged into the same dataflow.
   So: A new query first merges its common operators with the existing graph. New operators go live at once with empty state, and read requests fill them step by step. Upqueries hit existing precomputed state and do not need to recompute from the base tables.

Other design: double-buffered hash tables for lock-free reads; base tables stored in RocksDB; compatible with the MySQL protocol.

## Evidence
- End to end: Lobsters on one 16 vCPU machine: MariaDB holds up to 1000 pages/s. Noria gets 2.3× with the original queries and 5000 pages/s (5×) with natural queries. Vote sub-workload (Zipf, 95% reads): Noria with 4 shards serves 14M requests/s. The other database setups reach 100k–200k, and Noria also beats pure memcached. It scales linearly to 10 machines. Differential Dataflow reaches only about 20M at 10 machines.
- Novelty 1 → With partial state on, 35 of 60 stateful operators can be partial, and only 73 MB (9%) must stay resident. At 10 times the scale, a working set of 2.6 GB (38% of the 7 GB total state) is enough to keep 95% of latencies <100 ms. Writes reach 1M/s when all state is evicted and 240k/s with full state.
- Novelty 2 → The invariant is not tested or formally verified: no direct ablation. The scaling comparison with Differential Dataflow is only indirect evidence.
- Novelty 3 → Adding a view online: nearly instant with partial state and reuse on. With both off it takes 25 s, and each copy blocks writes for several seconds. The two are not ablated separately. For program changes in HotCRP and TPC-W, more than 95% can be done online.
- Gaps: Only eventual consistency is guaranteed, and eviction is random. Part of the 5× comes from natural queries themselves reducing write load.

## When it applies
Read-heavy applications that can accept eventual consistency, where queries have indexable parameters. Views without parameters (such as a front-page top-k) cannot be partial. An upquery after a cross-shard shuffle must ask all shards, which is very costly.
