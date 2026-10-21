# Rearchitecting the Thread Model of In-Memory Key-Value Stores with μTPS
SOSP'25 · Youmin Chen, Jiwu Shu, Yanyan Shen, Linpeng Huang, Hong Mei / Shanghai Jiao Tong University, Tsinghua University · https://doi.org/10.1145/3731569.3764794
Paper type: new system / architecture (thread model; performance work driven by hardware counters)
> Spoiler: this card dissects the paper. Do not read it if you want to train on this paper.

## Dissection
- Background: RDMA/DPDK in-memory KV stores (MICA, FaRM) pin one thread per core, busy-poll the NIC, and run each request from start to finish in one function: poll, parse, index lookup, copy the value, reply. This is run-to-completion. At >10 Mops/s a request has a few hundred ns, while one cache miss costs 50–150 ns. The NIC writes packets straight into the LLC (Intel DDIO, two LLC ways). The older thread-per-stage model (SEDA; HBase has >10 stages and ~1000 threads) was dropped for fast hardware, because its OS-scheduled queues between stages cost too much.
- Problem: Run-to-completion puts steps with very different behavior into one thread on one core. Polling and replying touch a small network buffer and never conflict. Index traversal and value copy sweep a large memory area and, under skewed writes, need locks. So the large-footprint steps evict the network buffers (LLC miss rate 33%), and a thread that waits on a hot-item lock also stops polling and replying, so throughput falls as cores are added. Can the thread model itself be changed so that each kind of step keeps its own cache and its own scalability?
- Challenges: (1) Cache partitioning alone (CAT) does not fix it: DDIO writes in place into lines that already sit in any way, and one core runs both kinds of step, so both share one CAT mask. (2) Key-partitioned threads (share-nothing) remove locks but are badly imbalanced under skew, and skew is the common case in production. (3) Staged designs pay inter-core handoffs per request, and the classic many-stage, OS-scheduled version is far too slow at µs scale. (4) Hot items blur the line: under skew, part of the "large-footprint" work is actually small and cache-friendly. (5) The right number of threads per stage depends on item size, keyspace and skew, but in eRPC/FaRM-RPC the client chooses the server thread, so changing thread counts means telling every client; eRPC also allocates 15 MB of buffer per worker thread.
- Solution:
  1. Insight: the steps split cleanly by cache footprint, not by function. → Design: only two thread pools on separate cores. A cache-resident (CR) layer polls, parses, serves hot items and replies; a memory-resident (MR) layer holds the full index and data and does lookups and copies. Only CR cores touch the network buffers. With the two on different cores, CAT can give each its own ways. → Network buffers stay in cache; the motivation test (no handoff cost, deterministic replay) gives 1.22–1.54× and LLC miss 2% vs. 33% on the polling side.
  2. Insight: under skew, the hottest items are small enough to stay in cache too. → Design: a resizable hot set (count-min sketch + min-heap, ~10K items, sorted array for the tree index) served by the CR layer; the MR layer gets only misses and hides them with batched C++20 coroutines + prefetch. The hot set is kept small, because CR and MR differ by less than an order of magnitude (not DRAM vs. HDD), so a large hot set makes CR misses expensive. → Hot items stop being evicted; redirecting the hottest 0.1‰ of queries alone gives 1.08×.
  3. Insight: only index/data updates conflict; every other step scales. → Design: share-everything inside each layer, with per-item version + CAS lock bits (≤8 B updated atomically), and a thread count per layer chosen to limit how many threads contend. → A lock wait no longer stops polling and replying; no load imbalance from partitioning.
  4. Insight: with only two stages there is one handoff, and reconfiguration can stay on the server. → Design: CR-MR queue with one lock-free ring per thread pair, 16 B request descriptors, batched slots, completion piggybacked on the tail pointer, no value copy through the queue. Reconfigurable RPC: one shared receive queue (RDMA SRQ + multi-packet RQ); thread i takes slots with m mod n = i, so a new n is a server-side global variable; 64 KB response buffer per thread. An auto-tuner searches thread split (trisection, per cache size), cache size (linear probe, step 1K), and cache ways (separately, via PQOS), with a 10 ms monitoring window. → Handoff cost ~100 ns, amortized by batching; retuning takes 0.9 s and never blocks requests.
- Evidence: 28 cores, Xeon Gold 6330 (42 MB LLC), ConnectX-6 200 Gbps, 10M items. vs. BaseKV (identical except run-to-completion): 1.03–5.46×. Tree index YCSB-B/C 1.30×/1.29× on average; YCSB-B tree +19.71% at 8 B, +43.53% at 1 KB; tree 8 B +11.87–26.56%, hash 8 B +3.01–8.56% (except put-skew). Put-uniform 8 B only +3.01% (hash) / +11.8% (tree), due to coherence traffic on the receive buffer. Write-skew: BaseKV collapses at 64 B/256 B with hash index, normal at 8 B; share-nothing eRPC-KV is sometimes up to 12% faster than μTPS. Scan: +33.1%/+25.1% vs. BaseKV. ETC: +29.1/13.0/26.6% (10/50/90% get). Twitter: +44.5/39.8/0.1% (Cluster-12/19/31; 31 is uniform). Latency close to BaseKV (hash median slightly higher). Few cores: equal or slightly worse. Batching: +51.6% (tree), +93.7% (hash). Load change at 4 s, tuner starts 4.3 s, done 5.2 s, +20%.

## Reveal schedule
| Fact | Earliest stage |
|------|----------------|
| Run-to-completion model, pinned polling threads, DDIO, CAT, PCM, share-nothing vs. share-everything, SEDA/HBase-style staging | 1 |
| Per-request budget of a few hundred ns; a miss costs 50–150 ns | 1 |
| 33% LLC miss on worker cores; a polling-only path nearly misses nothing | 1 |
| CAT to fence off DDIO ways barely helps | 1 |
| Put-skew throughput falls with more threads, except with 8 B values; key-partitioning is imbalanced under skew | 1 |
| The problem: one thread mixes cache-friendly/conflict-free steps with cache-hostile/conflict-prone ones | 1 (learner should find this) |
| Why CAT fails (DDIO writes in place; same core, same mask) | 2 (hint) |
| Split into two pools on separate cores by cache footprint | 2 (learner should find this) |
| Replay test: 1.22–1.54×, LLC miss 2% vs. 33% | 2 (only after the learner proposes the split) |
| Hot items on the small-footprint side; 0.1‰ redirect gives 1.08× | 2 |
| Throttle the number of threads that do updates | 2 |
| One handoff, per-pair rings, batching; shared receive queue with m mod n = i; auto-tuner | 2 |
| Names μTPS, NP-TPS, μTPS-H/-T, BaseKV; all §5 numbers | 3 |

Protected terms: μTPS, NP-TPS, "cache-resident layer", "memory-resident layer", "CR-MR queue", "reconfigurable RPC", "resizable cache" (3). In stage 2 use plain words: "the small-footprint pool" and "the large-footprint pool". "Thread-per-stage" may be said in stage 1 only as the old SEDA/HBase design, never as the answer.
Safe background: RDMA two-sided vs. one-sided verbs, busy polling, LLC ways, DDIO, CAT, Intel PCM, Zipfian/YCSB, MassTree, cuckoo hashing, optimistic version-number reads, coroutines and software prefetch, SEDA.

## Stage 1: Find the problem
### Background to give
You run the server of an RDMA in-memory KV store. The server has 28 cores on one socket of a Xeon Gold 6330 (42 MB LLC) and a ConnectX-6 200 Gbps NIC. Clients send two-sided RPCs. The store holds 10M items in MassTree (a cuckoo-hash build also exists). The thread model follows MICA/FaRM: each worker thread is pinned to a core, busy-polls for requests, and runs each request from start to finish. Any thread can serve any key. Values of 8 B or less are updated with one atomic instruction; larger values take a per-item CAS lock bit and a version number; reads are lock-free and check the version. Batching and prefetching are already on. The goal is well above 10 Mops/s. At that rate a request has a few hundred ns, and one DRAM miss costs 50–150 ns.

### Phenomena
1. 100% put, Zipfian keys, 64 B values, hash index. Throughput climbs to a peak and then falls as you add worker threads toward 28. You rerun with 8 B values: the fall is gone.
2. Intel PCM on the worker cores during a skewed read-heavy run: LLC miss rate 33%. A stripped-down build that only polls the receive buffer, parses and replies (receive buffer smaller than the LLC; the NIC writes packets straight into the LLC with DDIO) shows almost no LLC misses.
3. In the 1 KB-value runs, the one-sided-RDMA B+-tree store you compare against (Sherman) suddenly looks very good. Its throughput there is limited mainly by the 200 Gbps link.
4. Tuning attempt: with CAT you keep all worker threads out of the two LLC ways that DDIO uses. With small items, throughput is about the same as before. With larger items it rises slightly.
5. A teammate rebuilds the server on eRPC with key-partitioned threads (a request goes to thread key mod n; no locks needed). On Zipfian workloads it is much slower than your store: some threads are overloaded while others sit idle. On uniform keys it matches or beats your store. The production traces you must serve are skewed (Twitter: a read-heavy cluster has Zipf alpha 0.74, a write-heavy one 0.30).
6. YCSB-A (50% get, 50% put), 256 B values, hash index: as you go from a few threads to 28, throughput goes down, although half of the requests are gets that take no lock.

Tutor notes: 2 is the core cache clue (the request path as a whole misses a lot, its polling part alone does not). 4 is the failed tuning attempt: the obvious cache fix does not work, and why is a stage-2 hint. 1 and 6 are the contention clues: 1 shows locks are involved (8 B values use atomics), 6 shows the stall spreads to requests that never lock. 5 is the constraint that rules out the obvious lock fix: partitioning breaks under skew, and skew is what production sends. 3 is the distractor: network bandwidth matters only at 1 KB for a different design; the problem shows at small items, far below the link limit.

### Hint ladder
- L1: In phenomenon 2, the polling part alone barely misses, but the full request path misses 33% of the time. What else runs on the same core between two polls?
- L2: List the steps of one request. For each, how much memory does it touch, and can two requests conflict on it? Do all steps look alike?
- L3: Phenomena 2 and 6 have the same shape: one step hurts another step only because both run in the same thread on the same core. Could the problem be stated as "the thread model forces ___ and ___ steps to share a core and a thread"?
- Bottom-out: state the target below.

### Target
In a run-to-completion KV server, one thread on one core runs every step of every request. The steps differ: polling, parsing and replying touch a small buffer and never conflict; index traversal and value copy touch a large area and conflict under skewed writes. Running them together lets the large-footprint steps evict the network buffers (33% LLC miss) and lets a lock wait stall polling and replying, so throughput falls as cores are added. Cache partitioning and key partitioning do not fix it. The problem: a thread model that keeps the small, conflict-free work in cache and scalable, without paying for it in handoffs.
Checklist:
- [core] The steps of one request have very different memory footprints; combining them in one thread causes the cache misses.
- [core] Only updates conflict, but a conflict blocks the whole request path of that thread.
- [core] It is the thread model, not one component: CAT and key partitioning (under skew) both fail.
- [detail] The per-request budget (a few hundred ns vs. 50–150 ns per miss) is why a few misses matter.

### Common wrong turns
- "Buy a CPU with a bigger LLC" → The index and values of 10M items still do not fit. Which data needs to stay in cache, and is it big?
- "The network is the bottleneck" → Phenomenon 3 is a different design at 1 KB. At 8–64 B values, are you anywhere near 200 Gbps?
- "Partition keys to get rid of locks" → Phenomenon 5. What does production skew do to a partitioned server?
- "It's just lock overhead; use a better lock" → Phenomenon 6: gets take no lock and still slow down. Why would a lock on a put stop a get?

## Stage 2: Derive the solution
### Seed hint
Go back to the list of steps you made for one request. Ask where each step should run so that it never disturbs the others.

### Path
1. Learner may first try to fix the cache inside the current model: stronger CAT masks, more prefetch, a smaller index. Wall: phenomenon 4. Reveal why it failed only now: DDIO allocates into its two ways only on a miss; if a buffer line already sits in another way (pulled in when a worker polled it), the NIC writes it in place, and the index walk can then evict it. And one core runs both steps, so both get the same CAT mask. Ask: what if the two kinds of access never ran on the same core?
2. Learner proposes a pipeline of stages (SEDA style), one pool per function: RPC, parse, index, copy, reply. Wall: the classic staged design. HBase has >10 stages and ~1000 threads scheduled by the OS, whose scheduling latency is in ms; every handoff is inter-core communication. Ask: what is the fewest number of stages that removes the interference, and what should decide the cut, if not function?
3. Learner cuts by footprint: one pool polls, parses and replies; the other does index lookup and value copy. Confirm with the paper's quick test (stages split, handoff removed by deterministic replay, thread counts tuned by hand): 1.22–1.54×, LLC miss on the polling side 2% vs. 33%, while the lookup side keeps about the same miss rate. Now CAT can give each pool its own ways.
4. Wall: skew. Under Zipf, the hottest keys are also small and would stay in cache; sending them to the large-footprint pool wastes the cut. Learner proposes a small hot set served by the small pool. Paper: redirecting the hottest 0.1‰ of queries alone gives 1.08×. Ask: why not cache a lot? (The two pools differ by less than 10×, unlike DRAM vs. HDD; a big hot set makes misses in the small pool costly. Keep it ~10K items, resizable.) Also: the large pool now sees only cold keys, so its batched prefetches are not wasted on lines already in cache.
5. Contention. Learner may again propose key partitioning. Wall: phenomenon 5. Ask: which step conflicts? Only updates. Once steps run in separate pools, you can cap how many threads ever touch the conflicting step, while the rest keep polling and replying (share-everything inside each pool).
6. Wall: handoff cost. A naive shared queue becomes a hot spot. Learner proposes per-pair rings with small descriptors in batches; values are not moved through the queue, the large pool copies directly between network buffer and storage. Paper: 16 B descriptors, completion signaled by moving the tail pointer, ~100 ns per inter-core hop before batching.
7. Wall: the right split changes with item size, keyspace and skew, but with eRPC/FaRM-RPC the client picks the server thread, so changing thread counts means telling every client (and eRPC uses 15 MB of buffer per thread, more than fits in cache). Learner proposes one shared receive queue that server threads divide among themselves; thread i takes slots with m mod n = i, so n changes on the server only. Then an online tuner: thread split, hot-set size, cache ways.
Also discuss: what happens with uniform keys and many puts? (No hot set to exploit; the value bytes sit in the receive buffer that the small pool already pulled into its cache while parsing, and the large pool then reads them from another core. The gain shrinks to a few percent.)

### Hint ladder
Idea 1 (split by cache footprint onto separate cores):
- L1: In phenomenon 4, which cores fill the lines that DDIO later writes into, and which code evicts them?
- L2: CAT sets a mask per core. Can one core give its polling code one mask and its index walk another?
- L3: If no core ever ran both, how many groups of steps would you need, and what is the rule for putting a step in a group?
- Bottom-out: two pools on separate cores, one for small-footprint steps (poll, parse, reply), one for large-footprint steps (index, copy).
Idea 2 (hot items belong to the small side):
- L1: Under Zipf, how much memory do the hottest 10K items take?
- L2: Which pool fits that footprint?
- Bottom-out: serve a small, resizable hot set in the small pool; send only misses to the large pool.
Idea 3 (throttle only the conflicting step):
- L1: In phenomenon 6, which step actually waits, and which steps are made to wait with it?
- L2: After the split, who decides how many threads can run the update step?
- Bottom-out: share-everything in each pool, but pick thread counts so few threads contend; the others keep serving.
Idea 4 (cheap handoff, server-side reconfiguration):
- L1: What must cross from one pool to the other: the value, or something smaller?
- L2: If clients address server threads, what does it cost to move a thread from one pool to the other?
- Bottom-out: per-pair lock-free rings with 16 B batched descriptors; one shared receive queue divided by m mod n; an online tuner for thread split, hot-set size and cache ways.

### Target
1. Split each request by cache footprint into two pools on separate cores, so the small-footprint steps keep the network buffers in cache, and each pool can get its own cache ways.
2. Serve a small hot set in the small-footprint pool, so skewed hot items stay cached and the large pool's prefetching works on cold keys only.
3. Only updates conflict; cap the threads that do them, so a lock wait no longer stalls polling and replying, without partitioning keys.
4. Keep the split cheap and adjustable: one handoff through batched per-pair rings, a server-side shared receive queue, and an online tuner.
Checklist:
- [core] Two stages, cut by footprint, on separate cores (not by function, not many stages).
- [core] Why it removes the misses, and why CAT alone could not.
- [core] Contention handled by limiting threads on the conflicting step, not by partitioning.
- [detail] Hot set on the small side, and why it must stay small.
- [detail] Handoff cost and its amortization; server-side thread reassignment and tuning.

## Stage 3: Design the experiments
### Summary to give
Problem: run-to-completion KV servers run every step of a request in one thread on one core. Small-footprint, conflict-free steps (poll, parse, reply) and large-footprint, conflict-prone steps (index, copy) interfere: buffers get evicted and lock waits stall the whole path. Method (μTPS): a non-preemptive thread-per-stage design with only two layers. The cache-resident layer polls, parses, serves a ~10K-item resizable hot set and replies, with its own cores and LLC ways. The memory-resident layer holds the full index and data and uses batched coroutines with prefetch. They talk through the CR-MR queue (per-pair rings, 16 B descriptors, batched). Reconfigurable RPC uses one shared receive queue so thread counts change on the server only, and an auto-tuner picks thread split, cache size and cache ways. Two stores: μTPS-H (libcuckoo) and μTPS-T (MassTree).

### Key research questions
1. Does the thread model alone raise throughput? Headline claim; the baseline must differ only in the thread model.
2. What does the split cost, and where does the gain vanish? An extra inter-core hop can add latency; uniform keys, hash indexes and few cores are the likely weak spots.
3. Does it fix contention under skewed writes better than both shared and partitioned designs? This tests idea 3.
4. Do batching and the tuner matter? Ablations for idea 4.

### Key experiments
1. Throughput. Baselines: BaseKV (same code, same RPC, batching and prefetching on, run-to-completion), eRPC-KV (share-nothing), passive RDMA stores (RaceHash, Sherman). Workload: YCSB A/B/C/E, 100% put/get skewed and uniform, values 8 B–1 KB, tree and hash index, 10M items; plus Meta ETC and three Twitter traces. Result: 1.03–5.46× over BaseKV; tree YCSB-B/C 1.30×/1.29×; gain grows with item size (YCSB-B tree +19.71% at 8 B, +43.53% at 1 KB); tree gains more than hash. Weak designs: comparing against MICA or FaRM directly (different RPC and index, so the thread model is not isolated); disabling batching or prefetching in the baseline; showing only skewed reads.
2. Costs and limits. Latency: P50/P99 vs. throughput, YCSB-A, 8 B, 2 to 64 client threads. Result: close to BaseKV; hash median slightly higher. Limits: put-uniform 8 B only +3.01% (hash) / +11.8% (tree); Twitter Cluster-31 (uniform, 94% put) +0.1%; with few threads, equal or slightly worse, because threads move in whole units (an ideal 2:5 split becomes 1:2 on 3 cores). Weak designs: reporting throughput only; hiding uniform or write-heavy mixes; testing only at 28 cores.
3. Contention and scaling. YCSB-A and 100% put-skew, 8 B and 256 B, 1 to 28 threads. Result: BaseKV degrades at 64 B/256 B with hash index and is normal at 8 B; μTPS keeps scaling; eRPC-KV is sometimes faster (up to 12%) under write skew, but much slower under read skew. Weak designs: only 8 B values (atomics hide the lock problem); no share-nothing baseline; no thread sweep.
4. Ablations. Batch size 1 to 20: +51.6% (tree), +93.7% (hash). Tuner: chosen splits across keyspace, item size and skew; dynamic test with values switching 512 B → 8 B at 4 s, tuning from 4.3 s to 5.2 s, +20%, no downtime. Weak designs: a fixed hand-tuned split presented as the system; no workload change over time.

### Reviewer probes
- The 1.22–1.54× motivation test removes the handoff by replay. In the full system, how much of the gain comes from the split itself, from the hot set, and from the LLC ways? (The paper has no separate ablation of the hot set or of CAT in the full system; the tuner often gives almost all ways to the memory-resident layer.)
- Idea 3 is shown only through end-to-end write-skew curves. What experiment isolates "fewer threads on the update step"?
- How does the gain change with a larger LLC (e.g., 504 MB on Xeon 6978P) or without DDIO/CAT?
- 0.9 s to retune: what happens if the hot set shifts every second?

## Stage 4: Apply and extend
### Scenarios
1. Bigger caches or different hardware. Setup: move to a CPU whose LLC is 504 MB (the paper names Xeon 6978P), or to a platform without DDIO or CAT. Question: which parts of the gain survive? Good directions: the split pays only while the index and data far exceed the cache; with a huge LLC, try a bigger keyspace before claiming a win; without DDIO the polling side still gains a smaller code and data footprint per core, but the network-buffer argument changes; without CAT, cache ways cannot be split, so measure how much ways contributed.
2. Uniform write-heavy loads. Setup: a cluster like Twitter Cluster-31 (94% put, uniform, 15 B values) gives only +0.1%. Question: what goes wrong, and how would you fix it? Good directions: the small pool pulls the receive buffer into its cache while parsing, then the large pool reads the value from another core, which causes coherence traffic; have the small pool read only the header, or receive headers and payloads into separate buffers, so the payload line is first touched by the core that writes it into storage.
3. Move the idea elsewhere. Question: name another µs-scale server where one thread mixes small, hot, conflict-free work with large, cold, conflict-prone work, and argue whether a two-pool split pays. Good directions: a DPDK load balancer or packet processor with large flow tables; a storage server on CXL memory or memory-semantic SSDs, where the larger miss cost widens the gap; a transaction server where only validation conflicts. A good answer names both facts: the footprints differ by a lot, and the cross-core handoff costs less than the misses it removes.
