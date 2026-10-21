# Performance-Optimal Read-Only Transactions
OSDI'20 · Haonan Lu, Siddhartha Sen, Wyatt Lloyd / Princeton, Microsoft Research · Full text: https://www.usenix.org/system/files/osdi20-lu.pdf (USENIX camera-ready, system name PORT) · Selected: Community favorite (3 sources: DSRG (charap.co), Princeton COS 518 2019, UIUC CS591 2020)

**One sentence**: What keeps read-only transactions from being as fast as plain reads is real-time order across clients. Give it up, and servers can reorder in place, with no blocking and no extra round.

## Problem
In sharded storage, reads far outnumber writes (99.8% of TAO's requests are reads). Consistent reads across shards need read-only transactions, but these are slower than plain reads.
The authors define "optimal" as the three properties plain reads have: non-blocking (N), one round of messages with no side messages (O), and constant metadata per request (C).

## Strawman / Baseline
- **Spanner read-only transactions**: One round and constant metadata, but to get strict serializability (serializability with real-time order) they must block until a safe time.
- **OCC (Rococo-style)**: Reads optimistically first, then reads again to validate, so at least two rounds. It must also retry on conflicts.
- **COPS-SNOW**: One round and non-blocking, but writes must send side messages, and each read must carry information about the read transactions concurrent with it, so metadata grows with concurrency.
- **Eiger**: Values read in the first round may fall on both sides of a concurrent write transaction, so a second round of reads is needed to align them. If the write transaction is still pending, a third round must query the status of all conflicting write transactions, and metadata grows linearly with the number of conflicts. 1–3 rounds in total.
- **MySQL Cluster, Spanner snapshot read**: Satisfy N+O+C, but with weak consistency: the former does not isolate transactions, and the latter cannot read data the client just wrote.

## Novelty
1. **What forces conflicts onto reads is exactly real-time order**
   Insight (the NOCS theorem): N+O+C and strict serializability cannot all hold. Real-time order requires a read to see any write that completed before it, so a read can run into writes not yet ordered. Servers then must pass dependency information, and the metadata per read is not constant. Any three of N, O, C, S can be achieved.
   So: Give up only real-time order across clients, and keep per-client order and a total order, i.e. process-ordered serializability. This is stronger than the consistency of all existing NOC systems.
2. **Without real-time order, a server can order a late write after a read**
   Insight: A read carries a version number vs. When it reaches a server, the server freezes versions up to vs. Any later write with version number ≤ vs is moved after vs ("promotion"). So transactions that read at the same vs always see the same snapshot, and the total order holds. The server need not have received all writes ≤ vs, so it never waits.
   So: The client's version clock records the largest version number returned by each server it has contacted, and the minimum of these is used as the read's vs. This makes reads land where writes are already done as much as possible, triggers fewer promotions, and gives fresher data. After a write, the clock moves forward, which guarantees reading one's own writes. Each request carries only one integer. This avoids Spanner's blocking, OCC's second round, and COPS-SNOW's variable-length metadata.
3. **With write transactions, read at the point where "no writes are pending", and add one's own writes separately**
   Insight: Each server's local safe time is the time of its earliest pending write transaction; all writes before it have committed. The global safe time is the minimum of all servers' local safe times. Reading at this point never hits a pending write transaction.
   So: All reads happen at the global safe time, so the second and third rounds disappear. If this client has written the key after that point, the server returns the client's own newer version, to guarantee reading one's own writes. Causal consistency allows different clients to see concurrent writes in different orders, so this is legal. One more scan of the version chain guarantees write transactions become visible atomically. Metadata is constant.

Other design: write omission: when a write's version number is not larger than the largest committed version of the key, the two must be concurrent. The write can be ordered before that one and is overwritten at once, so no read can see it, and it need not be written.

## Evidence
- End to end: Compared with ScyllaDB without transactions, Scylla-PORT differs by only 1–3% in throughput and latency in most cases, 8% at worst. Its throughput is at least 2 times that of OCC, with less than half the latency, and it leads by an order of magnitude under high contention. Eiger-PORT has 2× (light skew) to 3× (high skew) the throughput of Eiger, with 20–60% lower latency.
- Novelty 1 → Theoretical proof (the full version is in the technical report), no experiments.
- Novelty 2 → The gap to ScyllaDB is its whole cost. Under skewed load, ScyllaDB stops scaling at 16 machines while PORT keeps scaling. The authors attribute this to write omission, but did no ablation.
- Novelty 3 → Eiger-PORT vs Eiger: write latency also drops.
- Gaps: Data read may be stale. About 40% of reads get the latest value, and 90% of reads lag by no more than 500 ms (1 s for Eiger-PORT). No measured comparison with Spanner or COPS-SNOW.

## When it applies
The application must accept not seeing writes that other clients just committed. It does not apply when real-time consistency across clients is needed.
