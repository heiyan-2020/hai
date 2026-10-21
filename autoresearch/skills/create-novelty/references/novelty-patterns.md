# Novelty patterns: insight archetypes from 100 OSDI/SOSP papers

How to use: when you get a new topic, first sketch one complete operation of the baseline (who does it, where, when, what it guarantees, why it is slow). Then ask it each archetype's "Questions to ask", one archetype at a time. Every question that gets a "yes" is a candidate insight of the form "because X, we can Y, and so remove Z". It counts as an insight only if X can be measured or proven.
Each paper belongs to 1–3 archetypes. The full mapping is in `catalog.md`. Every `<id>` below can be looked up in `papers/<id>.md`.

## Contents

| # | Archetype | One sentence | Papers |
|---|---|---|---|
| 1 | Keep only the guarantees that are used | The baseline promises stronger guarantees than downstream needs | 26 |
| 2 | Skew and repetition | A few items take most of the load; identical computation is done only once | 9 |
| 3 | Fast common case, safe fallback | The worst case is very rare, or a mistake can be cheaply detected and undone | 14 |
| 4 | Plan ahead when the future is known | Something thought to be known only at run time was actually fixed long before | 16 |
| 5 | Defer to the point of use or a free moment | Work done at production time is too early; move it to consumption time, batch time or a free moment | 15 |
| 6 | Put it where information is complete or cost is lowest | In another layer or on another device, information is complete and cost is low | 14 |
| 7 | Split tangled responsibilities | Two things with opposite properties are bound together | 14 |
| 8 | An old premise no longer holds | The cost ratio or division of duties the design relied on is no longer true today | 14 |
| 9 | Measure the right thing | The metric or cost model the field watches is wrong | 15 |
| 10 | Reuse signals and mechanisms that already exist | The information or capability you need is already provided by someone as a side effect | 22 |
| 11 | Unify into one problem | Several special-purpose solutions are really the same problem | 14 |
| 12 | Shrink what must be proven or searched | The difficulty of the proof or search sits in one small piece | 10 |
| 13 | Build an oracle and search by bug shape | When there is no ground truth, build one yourself, and search by the shape of the bug | 8 |
| 14 | Use idle resources | During the bottleneck period, another kind of resource is idle | 8 |

Two sections follow: "New costs created by the core idea" and "Where insights come from".

---

## 1. Keep only the guarantees that are used (Relax)
Merged from: semantic relaxation, relaxable constraints, removing unnecessary strong guarantees, protecting only the constraints that matter, redefining achievable guarantees, separating ground truth from rebuildable state, substitutable redundancy, redrawing the trust boundary.

**Definition**: Because downstream never actually observes part of the guarantee the baseline promises (data can be recomputed or dropped, only a local order is needed, any order of concurrent items is legal, any k results are enough, an attacker can only touch a few channels), we can keep only the small part that is used, and so remove the coordination, replication, rewriting and copying paid for the full guarantee.

**Questions to ask**
1. List each promise of the baseline (total order, durability, contiguous storage, strong consistency, whole-system isolation, "must wait for that one result"). For each one ask: who reads it? If it is removed, which downstream component would notice?
2. Which part of the state is truly lost if it is lost (ground truth), and which part can be rebuilt from ground truth? Is it enough to protect only the former?
3. Between which objects do conflicts really occur (writes to the same address, updates to the same key, inside the same unit of work)? Can all other pairs be fully freed?
4. If an impossibility theorem blocks the ideal properties, what is the least you must give up to get the performance you want?

**Where the facts come from**: Reread the semantics (linearizability allows concurrent items in any order; GC marking order is arbitrary; SGD tolerates stale and lost updates). Survey how real applications use the guarantee (writers do not look at the returned position; readers always lag). Use impossibility theorems to locate where the cost comes from. Analyze the data plane that an attacker can actually reach under the threat model.

**Examples**
- `sosp24-lazylog`: Total order is needed only at read time, and readers naturally lag behind writers. So writes only guarantee durability, and ordering is pushed to the background.
- `sosp17-pebblesdb`: A read only needs to know which range the target falls in. So "no overlap at all within a level" is relaxed to "no overlap between ranges", and data is written only once per level.
- `osdi20-performance-optimal-read-onl`: First prove that the three fast-path properties cannot coexist with real-time order. Then give up only real-time order across clients.
- `osdi18-pocket`: Intermediate data lives a very short time, and if lost it can be recomputed from lineage. So there are no replicas, and scaling does not migrate old data.
- `sosp23-enabling-high-performance-an`: Only a small part of the shared state is ground truth; the rest can be rebuilt. So only the layout of the ground truth is specified and checked; the rest is customized by each party.
- `osdi16-ec-cache`: There is no need to wait for "that one copy" of the data; any k coded blocks can restore it. So reading one extra block lets you drop the slow node.

**When it fails / pitfalls**: The relaxed part gets observed on rare paths: failure recovery, crashes, layout changes, concurrent writes. `osdi18-legoos`, `sosp23-treesls`, `osdi22-xrp` and `osdi18-pocket` did not test this failure path. Relaxation hurt quality, but no one quantified it. `osdi16-tensorflow` does not report time-to-accuracy. `osdi20-performance-optimal-read-onl` reads stale data but gives only the freshness distribution. It holds only for applications where "a weak guarantee is enough". State the boundary clearly; do not present it as general.

**Typical evidence**: Compare a "strong-guarantee version" with a "relaxed version" in the same system. For example, PORT compares the same system before and after the change, and uses its gap to a non-transactional version as an upper bound on the cost; NOPaxos uses as a control a protocol that differs only in the ordering guarantee and has the same hardware path. Failure-path experiments are also required: inject faults or crashes, create concurrent writes, and measure the quality metric after relaxation.

## 2. Skew and repetition (Skew & redundancy)
Merged from: measured workload facts (the skew part), exploitable skew/redundancy, exploiting skew, root causes concentrated in a few patterns.

**Definition**: Because the load is highly skewed or highly repetitive (a few items take most accesses; identical computation appears again and again; the effect is concentrated in one sub-unit), and this distribution is stable across inputs, we can apply expensive handling only to hot spots or representatives and compute identical things only once, and so remove the cost of treating everything the same.

**Questions to ask**
1. How much access or computation do the top 1% of objects, paths or channels take? Is there a theoretical bound on how many hot items are enough to handle?
2. Across different requests or inputs, how much computation is identical word for word? Can it be merged into one?
3. In which sub-unit is the effect you want to detect or handle concentrated? At that granularity, is the signal-to-noise ratio orders of magnitude higher?
4. Is hotness stable across time and across inputs? Can offline statistics be used directly?

**Where the facts come from**: Measure real traces or model internals (memory-access locality, activation distributions, instruction-level repetition, class distributions). Statistical analysis (variance drops with finer decomposition). Borrow existing theoretical bounds (load balancing needs only O(N log N) hot items).

**Examples**
- `osdi18-legoos`: 90% of memory accesses fall in 0.06% of memory. So the compute side keeps only a small cache, and the rest of memory management moves away as a whole.
- `sosp24-powerinfer`: Access follows a power law, and the hot set is stable across inputs. So hot data stays on the fast device, and cold data is computed in place on the slow device.
- `sosp17-the-efficient-server`: Many requests take the same path and compute the same data. So during auditing, the same group is merged and executed together, and identical values are computed only once.
- `osdi18-focus`: The top-K of the cheap method almost always contains the answer of the expensive method, and the same entities repeat a lot. So ingestion only ensures recall, and precision is pushed to query time and applied only to cluster centers.
- `sosp17-netcache`: Balancing load only requires absorbing a small number of the hottest items, and this number does not depend on the total number of items. So a small, fast cache is enough.
- `sosp24-fbdetect`: Overall variance is spread over tens of thousands of sub-units, while the effect is concentrated in one of them. So detection drills down to the sub-unit level.

**When it fails / pitfalls**: The skew exists only in synthetic load (the hotness in `osdi16-ec-cache` is synthetic Zipf). There is no gain under uniform load (`sosp25-rearchitecting-the-thread` gains nothing with a hash index and uniform load; the gain of `sosp17-netcache` disappears when writes dominate). The skew depends on a particular model or structural property: `sosp24-powerinfer` is only 1.5–1.7× faster on mainstream models.

**Typical evidence**: Sweep the skew and draw the curve of gain as skew drops, until it disappears (NetCache swept several skews and cache sizes; 1000 items were enough to balance). Add steps one at a time: "random placement → hotness-based placement" (PowerInfer). Report how stable the distribution is across inputs and across time.

## 3. Fast common case, safe fallback (Optimism + cheap fallback)
Merged from: optimistic normal case + crude fallback for rare cases, optimistic use + after-the-fact verification, optimistic execution + after-the-fact correction, after-the-fact correction instead of prediction, bounded deviation with a fallback, fallback via statistical concentration bounds, pass-through on the common path.

**Definition**: Because the worst case is measured to be very rare, or errors can be found afterwards by a cheap check, or a wrong decision can be cheaply undone, we can act freely for the common case and treat the rare case as a failure, fall back to a conservative value, or roll back, and so remove the cost paid up front for every possible error (prediction, mediation, full logging, acknowledgment and retransmission).

**Questions to ask**
1. For which worst case does the baseline pay full price? How often does it appear in real traces? You need a measured number here.
2. If the rare case is simply treated as a crash, or falls back to the most conservative approach, what is the total cost?
3. Can errors be cheaply detected afterwards with a ground truth, a sequence number or a side condition? How much cheaper is detection than prevention?
4. When a one-shot decision (placement, dispatch) is wrong, can the cost of undoing it (migration, rollback) be pushed very low?

**Where the facts come from**: Long, large-scale measurement (zero packet loss over long periods of heavy traffic; joint probability of resource lifetime and invocation duration; variance within a group). Statistical concentration bounds (median, binomial distribution, Hoeffding). Analyze the structure of error sources and find that errors have only one source. Borrow optimistic concurrency control and VM live migration.

**Examples**
- `osdi16-fasst`: The underlying link almost never drops packets. So the software layer treats packet loss as a machine failure, and skips acknowledgment and retransmission.
- `sosp21-faster-and-cheaper`: Failure requires two rare events to happen at the same time. So all work runs on cheap resources that can be reclaimed.
- `sosp17-resource-central`: Problems arise only when several objects are underestimated at the same time. So predictions are used only to relax, and fall back to conservative values when confidence is low.
- `sosp21-ghost`: External decisions are committed optimistically with a sequence number and rejected if found to be based on stale state; if the agent fails, it falls back to the default policy.
- `osdi24-llumnix`: State is append-only, and the migration pause does not depend on state size. So placement can be corrected at any time afterwards; it does not have to be right the first time.
- `osdi18-rept`: First use suspect values optimistically and record the derivation dependencies; invalidate them when they conflict with the ground truth of the final state.

**When it fails / pitfalls**: The fallback path itself has never run. The "packet loss means machine down" recovery path of `osdi16-fasst` was not implemented; `sosp21-ghost` did not inject agent crashes. "Rare" was only estimated in simulation (`sosp21-faster-and-cheaper`, `sosp17-resource-central`). It degrades when the rare case becomes common, so set a limit (`osdi22-memliner` falls back to the original behavior when resources are nearly exhausted). An adversary can manufacture the "rare" case (the Sybil gap in `sosp17-prochlo`).

**Typical evidence**: First give the measured frequency of the rare event at large scale, then compute the failure rate driven by traces. Then actively inject the rare event and measure the cost of the fallback (`sosp21-linefs` injects host crashes; in `sosp23-enabling-high-performance-an` all 134 attack and corruption scenarios were detected and recovered). Compare the correction mechanism with and without it, under the same decision policy (`osdi24-llumnix` was criticized for lacking this control).

## 4. Plan ahead when the future is known (Plan ahead / make static)
Merged from: information available in advance, known beforehand → prepare proactively, determinism built into the requirement, move to an earlier time, determinism makes advance planning feasible, static at compile time, move off the critical path and do in advance, adjacent steps are similar so they can be rehearsed, take back autonomous choices in exchange for predictability.

**Definition**: Because a quantity the baseline treats as known only at run time was actually fixed at an earlier point (configuration, content before release, compile time, registration time, a constraint that exists for another purpose, stable durations), we can plan offline, prepare in advance or check at compile time, and so remove run-time guessing, passive reaction and run-time checking overhead.

**Questions to ask**
1. Of the things the system guesses, measures or waits for at run time, which can already be computed at deploy, registration, load, compile or release time?
2. Is there a hard constraint that exists for another purpose (security requires access to be independent of data, iterative computation, no data-dependent branches) that also makes the future predictable?
3. How large is the variance of a unit of work's duration? If the variance is small, profiling plus dynamic programming can replace online tuning.
4. Does the jitter come from the task itself, or from places in the lower layers that make their own choices? If those choices are taken back, can you gain predictability?

**Where the facts come from**: Reread the semantics of the requirement (the security requirement of oblivious computation). Measure duration distributions (run the same task tens of millions of times). Analyze production traces and find that I/O patterns are fixed by deterministic configuration in the upper layer. Compute upper bounds with program analysis.

**Examples**
- `osdi21-mage`: Security requires the access pattern to be independent of data, so all future accesses can be computed before the input arrives, and paging is planned offline with the optimal policy.
- `osdi20-serving-dnns-like-clockwork`: The duration of the task itself is almost deterministic. So all autonomous choices in the lower layers are taken back, a central scheduler plans ahead, and work that cannot make it is dropped.
- `osdi26-teaching-the-old-dog-new-tri`: Upper-layer I/O is fixed by deterministic configuration. So the storage side packs, pre-replicates and preprocesses in advance.
- `osdi18-the-benefits-and`: Each call is bounded, and the maximum allocation can be computed statically. So it is reserved at entry while no locks are held, which removes mid-way failure and undo code.
- `osdi18-neural-adaptive-content-awar`: The content is fully known before release. So the model deliberately overfits each piece of content; the test set is the training set.
- `osdi24-infinigen`: The inputs of adjacent steps are almost the same. So the previous step rehearses the next step with partial data, and prefetches only the data that is truly needed.

**When it fails / pitfalls**: The plan grows with execution length (the plan size of `osdi21-mage` is proportional to execution time, so sort cannot run). The premise is strong (`osdi20-serving-dnns-like-clockwork` requires no dynamic branches and exclusive hardware; the hints in `osdi18-pocket` come from users, and there is no throttling when they are exceeded). Taking back choices loses the throughput that concurrency brings. There is no fallback when prediction is wrong.

**Typical evidence**: Bracket it from both ends: one end is the passive run-time approach, the other is an upper bound with perfect knowledge of the future (MAGE compares against OS paging and unlimited memory). Report prediction error (Clockwork's prediction error; the correlation between PipeDream's predicted and measured throughput). The most important ablation is to swap in an online heuristic within the same framework, and MAGE lacks exactly this one.

## 5. Defer to the point of use or a free moment (Defer, batch, piggyback)
Merged from: deferred decisions, defer to the point of consumption, slimming the critical path, naturally cheap moments, batching to amortize, batching mechanism overhead, checking at the boundary.

**Definition**: Because expensive work (ordering, validation, reorganization, metadata updates, exact evaluation) only matters when it is consumed, or the system will pass through a low-cost moment anyway (a memory trough, a rewrite that happens anyway, a full batch), we can keep only the step the user really waits for on the critical path, and defer, batch or piggyback the rest on a free moment, and so remove coordination and per-item fixed overhead from the critical path.

**Questions to ask**
1. Which step's completion does the user really wait for? After the other steps are deferred, what keeps correctness (an ordered log, prefix consistency, validation at handoff)?
2. Who consumes the result computed on the critical path, when, and how often? Does the producer itself use it?
3. Does the system have periodic troughs, or rewrites that must happen? Can the expensive operation be attached to them?
4. Which operation has a large fixed overhead? How many units of the same kind can naturally be gathered and done together?

**Where the facts come from**: Break down the write path and separate the completion point visible to the application from background work. Measure periodic curves (a 77× peak-to-trough gap in job memory). Use probability analysis to estimate how large a batch can be gathered (hash collisions follow a binomial distribution). Measure that the evaluator is nearly random on partial results.

**Examples**
- `sosp21-linefs`: The application only waits for the "persisted" step. The rest (publishing, validation, replication) is done asynchronously in the background in log order.
- `sosp21-kangaroo`: A small log is placed in front; objects of the same group are gathered and written at once. Eviction metadata is only needed when a group is rewritten, so it is deferred and persisted together with the next rewrite.
- `osdi18-gandiva`: The memory trough at an iteration boundary is a natural cheap preemption point. Suspending or migrating only needs to move very little live state.
- `sosp23-enabling-high-performance-an`: State corrupted by one party causes harm only when another party takes over. So validation moves from every operation to the handoff of write permission.
- `osdi20-ansor`: The evaluator is accurate only on complete solutions. So pruning is deferred until complete programs have been sampled.
- `osdi25-building-bridges`: It does not reason about foreign code; it only checks a value when it crosses the boundary and is used as some type.

**When it fails / pitfalls**: When consumers do not lag, deferring turns into waiting (`sosp24-lazylog` reads slow down when readers do not lag and load is low). Background work slows latency even when idle (`sosp21-linefs` doubles average latency with no load). Deferring introduces new races (`osdi18-noria`'s backfill races with in-flight updates). There must be a policy for when a batch cannot be filled (Kangaroo simply drops).

**Typical evidence**: Sweep consumer lag and load, and actively show the worst range (LazyLog). Add parts one by one (Kangaroo cuts writes by 42.6% with misses almost unchanged). Turn off batching or pipelining as a control (with pipelining off, LineFS throughput is at least 60% worse). Give the critical-path latency breakdown before and after the change.

## 6. Put it where information is complete or cost is lowest (Placement)
Merged from: placement in another layer, changing where it executes, implementing it in another layer, deciding where information is complete.

**Definition**: Because the information a function needs (object boundaries, who owns a block, whether memory is still in use, all traffic) or cheap execution conditions exist naturally only in another layer or on another device, we can move the function there (driver, data structure, framework API layer, network, switch, SmartNIC, backend), and so remove the amplification and guessing caused by missing information in the current layer, and the overhead of crossing the whole software stack each time.

**Questions to ask**
1. Which pieces of information does this decision need? Which one is missing in the layer now responsible for it? Which layer naturally has all of them?
2. Is there a layer that happens to be on the path of every request (switch, driver completion interrupt, caller)?
3. Break the latency of one operation down layer by layer: is the real overhead in the switch, or in the layers in between?
4. After moving, what are the weaknesses of the new location (slow cores, high memory-access latency, small memory, update rate)? What structure (pipelining, batching, on-chip forwarding) can hide them?

**Where the facts come from**: Measure the latency breakdown of the software stack (file system 32%, the switch only 5.6%). Compare switch costs across layers. Find the layer in the system that is most expensive to change. New hardware appears (SmartNIC, FPGA NICs, programmable switches).

**Examples**
- `osdi22-xrp`: The intermediate results of chained I/O are used only to compute the next hop. So a safe small program computes the next hop closest to the device and resubmits directly.
- `osdi20-aifm`: Only the data structure knows object boundaries and access patterns. So the swap-out logic goes into the data structure, rather than being done per page in the kernel.
- `sosp17-canopy`: Instrumentation is the hardest to change, while models change often. So instrumentation only produces low-level events, and models are interpreted in the backend.
- `sosp19-a-generic-communication`: The framework API layer is both engine-independent and able to see layer priority. So scheduling goes in this layer.
- `osdi18-capturing-and-enhancing`: When a component has a problem, it shows up directly on the caller's execution path. So the caller acts as the observer.
- `sosp17-strata`: Only the file system knows both who owns a block and who used it recently. So it is responsible for migration across tiers.

**When it fails / pitfalls**: The weaknesses of the new location eat the gain (`sosp21-linefs` is slower on workloads with frequent syncs; `sosp17-kv-direct` has no advantage under uniform load with large values). Moving to a new layer loses isolation or abstraction, and you must explain separately how to keep it (XRP). The gain is mixed with benefits that come with the new hardware and have nothing to do with the design (part of the latency advantage of `osdi20-hxdp` comes from the FPGA not going through PCIe).

**Typical evidence**: Put the same function in each of two layers and compare. XRP's numbers for the syscall layer vs. the driver layer are quoted from an old paper, so it was criticized; do this yourself in your own paper. Give the per-layer latency breakdown before and after the change. Stress-test the weaknesses of the new location.

## 7. Split tangled responsibilities (Decouple / re-partition)
Merged from: decoupling and splitting, decoupling tangled responsibilities, changing the partitioning dimension, removing a centralized privileged point.

**Definition**: Because two things bound to the same resource or component have opposite bottlenecks, costs that differ by orders of magnitude, or different rates of evolution (compute vs. bandwidth, ordering vs. delivery, policy vs. execution, hot working set vs. cold scan), we can split them, or change the partitioning dimension, and use the cheapest mechanism for each, and so remove mutual interference, over-provisioning for the stricter side, and "changing one part means rewriting everything".

**Questions to ask**
1. Which things does the bottleneck component do at the same time? Which resource does each consume? What is each one's goal?
2. Which of them is cheap and can be pushed down (separate ordering from reliability), and which is needed only rarely (separate reconfiguration from the normal path)?
3. Which part brings the performance, and which part brings the problem? Must they share resources?
4. Which work with very different cost properties does the current partitioning (by function, by hash, by data parallelism) put together? What if you partition by cache residency, by inter-layer data volume, or by ID locality instead?

**Where the facts come from**: Analyze the resource properties of each stage (roofline analysis) and latency targets. Queueing theory. Measure LLC misses. Production needs (the implementation must be swapped out repeatedly).

**Examples**
- `osdi24-distserve`: One of the two phases is compute-bound and the other is bandwidth-bound. So they are split onto different resources, and each gets its own optimal parallel configuration.
- `sosp17-zygos`: Throughput comes from per-core independence at the bottom layer; tail latency comes from upper-layer tasks being pinned. So global stealing is done only in the upper layer.
- `osdi20-virtual-consensus-in`: Swapping the lower layer only needs "sealing" plus agreement on the new mapping, and sealing is weaker than consensus. So fault-tolerant consensus is implemented only once, in the metadata store.
- `sosp25-rearchitecting-the-thread`: Part of the working set is small and can stay in cache; the other part is bound to miss. So it is split into just two stages by cache residency.
- `sosp19-pipedream`: The intermediate results passed between adjacent stages are much smaller than the global state. So the model is split by layer into a pipeline that passes only intermediate results.
- `osdi20-byzantine-ordered-consensus`: Ordering power is taken away from the leader; the order is locked with timestamps before consensus, and the leader only confirms that everything has arrived.

**When it fails / pitfalls**: After splitting, state must be passed across the new boundary, and this must be solved separately (DistServe uses layer-aligned placement). The overhead of inter-stage communication and reconfiguration. It holds only when the two parts are truly different: `sosp17-zygos` loses to a batching-enabled baseline on very small tasks, and `sosp25-rearchitecting-the-thread` gains nothing under uniform load.

**Typical evidence**: Give the unsplit version the same tuning chance, to rule out "the gain comes from tuning" (in simulation, DistServe also enumerates the best parallelism for co-located serving, i.e. vLLM++). Put the original root cause back into your own system and measure again (`osdi16-gemini` switches back to hash partitioning). Run co-location interference experiments.

## 8. An old premise no longer holds (Stale premise / environment tax)
Merged from: hardware changes cost ratios, environmental facts make old assumptions obsolete, the premise of an old abstraction no longer holds, deleting obsolete abstraction layers, removing the environment tax.

**Definition**: Because the cost ratio or division of duties that a design (or the rejection of a design) relied on no longer holds on today's hardware, deployment or special-purpose setting (persistence costs about as much as a copy; with more cores, cross-core communication is cheap; dispatch is already done by a lower layer; the network is fast enough that communication can hide behind computation; type-safe languages can provide isolation), we can delete the abstraction layer or the overhead that existed for the old premise, and so remove the part that is now only cost.

**Questions to ask**
1. What problem was the field's standard interface or layering originally introduced to solve? Is it still the thing that solves that problem today?
2. Which hardware trend made a once-expensive operation (persistence, remote access, cross-core communication, control-flow tracing) cheap? And which once-cheap operation did it turn into a bottleneck?
3. Break down the instructions or time of one operation item by item: which part is a tax paid for a general environment (kernel checks, page granularity, a general-purpose OS) that your setting does not need?
4. If an architecture rejected by history is measured again at today's cost ratios, would it still be rejected?

**Where the facts come from**: Hardware trends (NVM, SmartNIC/FPGA, programmable switches, growing core counts, cheap hardware tracing, stacked memory). Trace the historical origin of an abstraction layer. Remeasure primitives on today's hardware and at real scale. Examine, class by class, whom each kind of instruction serves.

**Examples**
- `sosp25-cortenmm`: Both reasons for introducing the intermediate abstraction layer no longer hold. So it is deleted and only one tree remains; locking a range is locking a subtree.
- `osdi23-enso`: The old interface was designed for "software does the dispatch", and dispatch has moved to a lower layer. So it becomes a contiguous data stream, removing the per-unit descriptors.
- `osdi16-gemini`: The network is fast enough that communication can be hidden by computation, and the bottleneck became the extra computation added for distribution. So it starts from the best single-machine implementation and adds only the lightest distributed overhead.
- `sosp19-snap`: Multiple cores make cross-core shared-memory communication cheap. So a once-rejected "separate user-space service" architecture becomes feasible again.
- `sosp23-treesls`: On byte-addressable persistent memory, the run-time pages are themselves persistent. So unmodified pages are their own backup.
- `osdi20-hxdp`: A large share of instructions are a tax paid for the original execution environment. So in a special-purpose executor, hardware does this work for free.

**When it fails / pitfalls**: The new hardware is not available and can only be emulated. This is the most common point of attack (`sosp17-strata` emulates NVM with DRAM; the key hardware of `osdi18-graviton` and `osdi16-just-say-no-to-paxos-overhea` was not measured on real devices). The trend holds only for specific forms (Graviton holds only for stacked packaging). The comparison between old and new platforms mixes in platform differences (`osdi23-enso` is FPGA vs. ASIC).

**Typical evidence**: First quantify the old premise on today's hardware (a cost-ratio table, a latency-budget breakdown). Then compare the old and new designs on the same new hardware. If emulation is used, report the error between emulation and real hardware, and state which paths are emulated.

## 9. Measure the right thing (Right metric / right cost model)
Merged from: measurement refutes a premise, measurement overturns an assumption, switching to the right metric, cost is a tunable variable, joint optimization of coupled knobs, noise decomposition, allocating scarce resources by measured value, modeling by generalizing from incidents.

**Definition**: Because the quantity the field watches (utilization, average latency, allocation, whether the CPU is bypassed, a fixed unit cost, aggregate-level metrics) is not the quantity that really determines the outcome (jitter, net usage, message count, goodput, cost that changes with batch size, changes at the sub-unit level), we can switch to the real quantity for detection, scheduling or allocation, and so remove misjudgment, over-provisioning and slow convergence caused by the wrong proxy metric.

**Questions to ask**
1. Has the correlation between the metric you optimize or sample and the final goal been measured? Is there an overlooked second-order quantity (variance, net change, count) that better separates good from bad?
2. Could the "cost per unit" the scheduler assumes change with the scheduling decision itself (batch size, parallelism, co-location)?
3. Is the goal determined jointly by two coupled knobs, while the baseline tunes only one and fixes the other at submission time?
4. The field assumes "X is required" or "X is the bottleneck". When was this basis last checked against real data? Can you build a control that differs in only one variable?

**Where the facts come from**: Variance decomposition (3 coarse-grained factors explain R² 0.87). Large unsampled production traces. Controlled comparisons (change the critical paths of two systems until they match line by line). Characterization experiments after injecting contention. Generalizing from incident reports. Borrowing ML theory so that quantities that used to need a trial run can be measured online.

**Examples**
- `osdi20-firm`: The fingerprint of contention is jitter; a component with high but stable latency is simply slow. So the culprit is located by jitter.
- `osdi21-pollux`: The real goal is "throughput × efficiency". So it is estimated online with intermediate quantities the job computes anyway, and two knobs are tuned jointly.
- `sosp19-nexus`: The cost of a single request changes with how it is batched. So placement and batch size must be solved as joint variables.
- `osdi16-fasst`: What determines performance is the number of messages, not whether the remote CPU is bypassed.
- `osdi20-a-large-scale`: The expiration mechanism that is always configured in practice caps the working set. So deleting expired objects promptly may matter more than improving the eviction algorithm.
- `osdi22-metastable-failures-in`: What sustains a failure is the feedback loop, not the trigger. So "vulnerability" is a degree, not a binary.

**When it fails / pitfalls**: The conclusions of a measurement paper are not themselves validated (`osdi20-a-large-scale` did not simulate how much prompt expiration saves; the key breakdown in `osdi16-network-requirements-for` uses numbers from the literature). The data has only one source, such as only one company. The training and test data of the new metric come from the same injector (`osdi20-firm`). Numbers are inconsistent within the paper (`osdi16-network-requirements-for`, `osdi23-triangulating-python-perform`).

**Typical evidence**: First show that the old metric correlates poorly with the outcome, and the new metric correlates well. Then, in the same system, change only the metric as a control (Nexus switches to batch-agnostic scheduling). A measurement paper should turn at least one conclusion into an experiment or simulation.

## 10. Reuse signals and mechanisms that already exist (Free ride)
Merged from: free use of side information, riding on existing mechanisms, cheap first-hand signals, root cause as a signal, existing artifacts as specifications, reusing existing primitives, hardware guarantees as foundation, materializing implicit state, letting the event itself carry the proof, executing in the real context, production as the test bed.

**Definition**: Because the information or capability the decision lacks has actually already been computed, seen or guaranteed by some component as a side effect (training loss, final-state snapshot, timeouts seen by the caller, program syntax, test mocks, copy-on-write layering, the hardware's "tampering only causes failure", routing weights), we can use it directly, and so remove dedicated probing, modeling, hand-written specifications, or protection implemented by ourselves.

**Questions to ask**
1. Has the quantity the decision lacks already been computed or seen by some component, or written into some artifact (logs, final state, syntax, mocks)?
2. What mechanism in the system runs every time (barriers, counters, callbacks, injected delays) and could carry the information or control you need along the way?
3. What does hardware or mature infrastructure already guarantee or provide (IOMMU, remote attestation, layered file systems, block ownership transfer) that software still does again?
4. Does the shape of the baseline's error itself (a late signal, a propagated delay) already carry the quantity you want to measure?

**Where the facts come from**: Observe how on-call engineers really debug, and production workflows. Read hardware specifications carefully. Look at who in an engineering organization has the incentive to maintain what. Study the semantic details of the host runtime.

**Examples**
- `osdi21-oort`: The value of an individual can be read for free from the loss that training computes anyway.
- `osdi23-triangulating-python-perform`: A signal arrives late only because the runtime is executing another kind of code, so the delay itself is the time spent in that kind of code.
- `sosp21-using-lightweight-formal`: Test mocks are something engineers must keep in sync. So the specification is written as a simple implementation in the same language and doubles as the mock.
- `osdi24-verismo`: Hardware guarantees that external tampering only makes access fail and never returns a wrong value. So external concurrency is wrapped once into a hardware-model layer and proven there.
- `osdi26-controlling-opaque-component`: Copy-on-write layering itself gathers all changes into one diff, which can be inspected, selected, stacked and discarded.
- `osdi20-sundial`: The rule is "forward only after receiving from upstream", so the arrival of a message itself proves the node is still connected to the root.

**When it fails / pitfalls**: It depends on an implementation detail of the host, and fails with another implementation (Scalene). The free signal does not cover everything: `osdi18-orca` cannot cover problems whose symptoms contain no specific terms, and `osdi16-early-detection-of` only covers input consumed through standard APIs. Borrowed hardware guarantees may be bypassed (`osdi25-building-bridges` can only trust the foreign library under MPK).

**Typical evidence**: First measure signal quality (Pollux's curve of prediction vs. measurement). Then ablate with and without the signal (Orca's recall goes 0.69→0.77 after adding the derived graph). Finally compare the cost with dedicated probing or a separate specification (ShardStore's model is only 1% of the implementation).

## 11. Unify into one problem (Unify / generate)
Merged from: unifying into a general problem, a unified abstraction covering heterogeneity, a unified abstraction absorbing many cases, generation replacing hand-writing.

**Definition**: Because several seemingly different special-purpose solutions are actually endpoints or instances of the same problem (the same load-allocation problem, the same DAG chained by layers, the same task of "making room", differing only in a few scheduling primitives), we can write them as one unified abstraction, one mathematical form or one generator, and so remove per-solution, per-platform and per-target hand-writing, and "changing one part means rewriting".

**Questions to ask**
1. How many special-purpose solutions does the field have? Are they the same parameter at two extremes? Would a value in between be better?
2. Can these goals or policies be written as the same function and handed to an existing solver (LP)?
3. Which part of the work grows with the product "type × platform × variant"? Can it be generated automatically from a high-level description or code analysis?
4. In which few dimensions do heterogeneous platforms really differ? Is it enough to make only these dimensions pluggable?

**Where the facts come from**: A unified communication-volume analysis of two architectures. Abstract the common mathematical form of existing policies. Distill the design principle shared by a class of systems. Analyze the computation structure of emerging applications.

**Examples**
- `osdi20-a-unified-architecture`: The two communication architectures are the two endpoints of one load-allocation problem. So load is allocated by a closed-form solution that makes the load on both kinds of machines equal.
- `osdi20-heterogeneity-aware-cluster`: The goals of common scheduling policies are all just functions of throughput. So switching to effective throughput turns any policy into a heterogeneity-aware one, solved by LP.
- `osdi24-llumnix`: Defragmentation, priorities and scale-down are all essentially "making room somewhere". So they are unified as load balancing over virtual usage.
- `osdi18-tvm`: Hardware differences come down to a few kinds of scheduling transformations. So new hardware only needs to declare its instruction semantics, and operators are generated from high-level expressions.
- `osdi24-anvil`: Systems of the same class all follow the same design principle, so one general liveness specification is enough.
- `osdi18-ray`: The state of a stateful component is uniquely determined by its call sequence. So its calls can go into the same graph as stateless tasks.

**When it fails / pitfalls**: The evidence of generality is only lines changed or single cases (`sosp21-the-demikernel-datapath` has only one person's porting experience). Peak performance is lower than special-purpose systems. After unification, the gain at intermediate points cannot be attributed (`osdi20-a-unified-architecture` is still faster than all-reduce without extra CPU machines, and the authors can only guess why).

**Typical evidence**: End-to-end experiments that cover several platforms, frameworks or policies (TVM: 4 kinds of hardware; ByteScheduler: 5 combinations; Gavel: several policies). Compare against the special-purpose version or the unaware version under the same mechanism. Quantify generality as "the incremental work to add one target or platform".

## 12. Shrink what must be proven or searched
Merged from: small specifications can be proven automatically, decomposing proof structure, proof decomposition/reduction, materializing implicit state (for proofs), enumerating a small hypothesis space + cheap filtering, monotonic search direction, layering the search space.

**Definition**: Because the difficulty (nondeterminism, external concurrency, recursive structure, arbitrary starting states, a huge search space) is concentrated in one small piece (nondeterminism on the specification side is only one or two booleans; tampering only leads to failure; recursion comes only from the shape of ownership; answers written by people have only 2–4 literals), we can isolate this piece into one layer and prove it once, or enumerate a small space and filter cheaply with random data, and so remove hand-written proofs, per-system specifications and exponential search.

**Questions to ask**
1. Where does the burden of proof or search come from (which quantifier, which kind of concurrency, which structure)? Can you change the layering or the data structure so that it appears only once?
2. Does the system have a property that reduces "any state or any concurrency" to "the initial state or sequential execution" (for example, looking only at the current state, or mutually exclusive ranges)?
3. How small are answers written by people, usually? Can you enumerate all candidates, rule them out first with random execution data, and hand only the last step to the solver?
4. Can you start from the strongest (or weakest) end, so that each failure points to only one direction of change?

**Where the facts come from**: Analyze proof structure (quantifier structure, where recursion comes from). Measure the size of answers written by people. Read hardware specifications. Use a profiler to generalize path explosion into a few patterns. Borrow "enumerate and test" from superoptimization.

**Examples**
- `osdi16-push-button-verification-of`: Nondeterminism on the specification side is tiny. So the "for all" quantifier is pushed down to a finite space and decided fully automatically by a solver, with layers proven one at a time.
- `sosp25-atmosphere`: The recursive specification comes only from "you must go through the parent to reach the child". So permissions are flattened into one table, and the recursive invariant becomes a universal quantification.
- `osdi21-distai`: Answers are short and independent of scale. So candidates are filtered with simulation data at several scales, starting from the strongest candidate, with only the minimal weakening on failure.
- `sosp19-taso`: Useful rewrites involve only a few operators. So small graphs are enumerated, candidates are found by fingerprints on random inputs, and then proven with a few axioms.
- `osdi25-basilisk`: Cross-component relations can be broken into a chain of "who wrote this value". Groups of variables that are always modified together can be read from the syntax, so provenance invariants can be generated automatically.
- `sosp17-komodo`: Its duties are cut down to checking only, no allocation, single core, interrupts off. So noninterference can be proven call by call at the call boundary.

**When it fails / pitfalls**: The trusted base is large (specification, solver, environment model, hardware model). The strength of the specification is not checked by mutation testing; almost all verification papers lack this. Expressiveness has hard limits (`osdi21-distai` does not support ∃, and fails on Paxos). What is verified is a ported copy (`sosp25-cortenmm`). The development set is the evaluation set (the first 6 protocols of `osdi25-basilisk` were used for development).

**Typical evidence**: Report the effort (proof/code ratio, person-months, the changes needed for later increments), verification time, and performance comparable to the unverified version. Add mutation testing to show the verifier rejects wrong code, and evaluate on a held-out set. Search work must also be compared against a strawman search under the same budget (TVM swapped in a genetic algorithm and random search).

## 13. Build an oracle and search by bug shape (Manufacture an oracle)
Merged from: manufacturing an oracle, a built-in oracle, metamorphic/differential oracles, directed search by defect structure, executing in the real context (the testing part).

**Definition**: Because the outputs of the system under test under a family of transformations must satisfy known relations (several independent implementations rarely make the same mistake; the output must be the same under every legal combination of internal decisions; monotonic operators make a change move in a known direction), and each class of bug corresponds to an enumerable "missing" thing (a missing barrier, two operations that almost overlap), we can use this family of transformations as the oracle and enumerate candidates by bug shape, and so remove manual labeling, reference implementations and exponential blind search.

**Questions to ask**
1. What ground truth do you need to judge right from wrong? Are there several independent implementations? Is there a family of internal freedoms that by specification should not affect the output (scheduling, compilation tier, cache)?
2. What transformation makes the output move in a known direction? Could the two runs go through the same buggy code and compute the same error twice?
3. Which kind of missing thing or "near miss" must the bug you are looking for correspond to? If you enumerate by this structure, how many candidates are there?
4. Can you inject known effects artificially (A/A experiments plus injected regressions) to build data with ground truth?

**Where the facts come from**: Borrow differential testing and metamorphic testing. Reread the semantics of the language or runtime under test (JIT is tiered and can fall back; monotonicity of operators; the visible effects defined by the memory model). Observe the distribution of bug locations in a large test environment. Study real incidents.

**Examples**
- `sosp17-deepxplore`: Several independent implementations rarely make the same mistake, so their disagreement is the oracle. The system under test is differentiable, so finding triggering inputs can be written as gradient ascent.
- `sosp23-validating-jit-compilers`: For the same input, the output must be the same under every legal combination of internal decisions, and these internal decisions can be steered from the input side.
- `osdi26-valscope`: Operators are monotonic. So the direction of a local change is pushed along the syntax tree to the output, and the operator itself is swapped so that the two runs go through different code.
- `sosp19-efficient-scalable-thread-sa`: Only operations that almost overlap are perturbed. If an injected delay is propagated, the two places have a happens-before relation.
- `sosp24-ozz`: Complex low-level behavior has only two externally visible effects, which can be created in software during real runs. Each bug corresponds to one missing constraint, so the candidates go from exponential to linear.
- `osdi24-servicelab`: A/A experiments plus manually injected regressions cheaply build data with ground truth, used to choose a statistical model for each object.

**When it fails / pitfalls**: "Disagreement" is not the same as a bug (DeepXplore's errors were not confirmed by hand; Artemis counts by seed, not by deduplicated bug). It cannot detect cases where all implementations make the same mistake. The ground truth is only the union of a few tools' results (TSVD). The false positive rate is not reported (ValScope). The bug set comes from the same source as the study that inspired the design (PCheck).

**Typical evidence**: Report the number of new bugs, and how many were confirmed and fixed. Revert historical patches and reproduce known bugs (OZZ). Compare against endpoint approaches or existing tools with the same seeds and the same budget (Artemis: 154 vs. 21). Rewrite the bugs found into the baseline's test form, and see which only your approach catches (ValScope). Ablate each search heuristic by removing it (TSVD removes the time window, removes delay inference).

## 14. Use idle resources (Harvest idle resources)
Merged from: putting idle resources to use, absorbing idle resources.

**Definition**: Because during the bottleneck period another kind of resource has slack (the compute left over in a bandwidth-bound round, the CPU of storage nodes, idle CPU machines, client GPUs, thread time while waiting on a remote side, GPU memory between a job's peaks and troughs, cheap VMs that can be reclaimed), we can put work into this slack, and so raise the effective capacity of the bottleneck resource without adding hardware or lengthening the critical path.

**Questions to ask**
1. Measure which kind of resource in the deployment has low utilization for long periods. What can it take over from the bottleneck resource (aggregation, preprocessing, computing on cold data)?
2. In some rounds or phases, does the bottleneck resource use only one dimension (compute or bandwidth), leaving the other dimension free?
3. How much data must be moved to shift the work? Will the moving eat the gain?
4. What happens when the borrowed resource must be returned at any moment (spill and slow down rather than fail; yield by iteration time)?

**Where the facts come from**: Measure utilization in production clusters. Measure duration curves in roofline style to find complementary points and saturation points of resources. Compare switch cost with waiting time.

**Examples**
- `osdi24-taming-throughput-latency-tr`: Bandwidth-bound work leaves free compute in every round. So compute-bound work is split into chunks that fill each round's fixed budget.
- `osdi20-a-unified-architecture`: Idle CPU machines become extra aggregation bandwidth; the CPU only does streaming sums that touch memory once.
- `osdi20-antman`: A job's memory rises and falls within each iteration. So the cap is tightened and loosened at iteration boundaries, troughs are lent to low-priority jobs, and overflow spills instead of failing.
- `sosp24-powerinfer`: Only a very small part of cold data is used each round; computing it in place on the slow device is cheaper than moving it to the fast device.
- `osdi18-neural-adaptive-content-awar`: Uses idle client compute in exchange for bandwidth.
- `osdi20-aifm`: Switching user-space threads is far cheaper than remote waiting, so waiting time can be turned into throughput.

**When it fails / pitfalls**: The slack may not exist (`osdi26-teaching-the-old-dog-new-tri` depends on storage nodes having idle compute, but does not report the load on the storage side). The borrower interferes with the lender, or the borrowed party gets no guarantee at all (AntMan's low-priority jobs). Clients are heterogeneous (NAS only tested high-end GPUs).

**Typical evidence**: Report the utilization of the borrowed resource before and after the change, and the impact on the lender. Component ablation (Sarathi: mixing only, chunking only, both). Give the degradation curve as the slack disappears.

---

## New costs created by the core idea

The recurring structure is this: the core insight removes the baseline's main cost, but breaks some property the old design provided "for free" (contiguity, a single owner, version consistency, fresh mappings, check and use happening at the same time, isolation). So a new cost appears, and the 2nd and 3rd novelties exist to remove it. They often reuse the same kind of archetype.

| Paper | Core idea | New cost it creates | Follow-up novelty |
|---|---|---|---|
| `sosp21-kangaroo` | Set-associative layout, almost no in-memory index | Each insert rewrites the whole set; with no metadata, only the weakest eviction is possible | A small log batches by set; 1 bit of access information is deferred and persisted when the set is rewritten |
| `osdi25-building-bridges` | Check values by type when they cross the boundary | Modified after the check and before use (TOCTOU) | Only the host itself can invalidate a value; compile-time borrow checking serves as a zero-overhead lock |
| `osdi24-distserve` | Split the two phases onto different resources | State must be passed between phases | State flows only between corresponding layers; layer-aligned placement uses only intra-machine links |
| `sosp21-linefs` | Move background work to a weak processor on the side | Memory-access latency is an order of magnitude higher | The log is ordered and stages use different resources; pipeline by chunk and hide latency with many slow cores |
| `osdi22-xrp` | Compute the next hop and resubmit in the driver layer | The driver cannot understand files | The layout rarely changes; give the driver a mapping cache that is rarely invalidated |
| `osdi24-llumnix` | Correct wrong placement by migration | Migration pauses; central tracking of every request becomes a bottleneck | Append-only state with multi-round pre-copy; unify into virtual usage so each instance reports only one number |
| `sosp17-the-efficient-server` | Reuse untrusted records for merged replay | The other side can forge self-consistent fake records | Reduce read correctness to writes, verify afterwards, and add a graph check for consistent scheduling |
| `osdi18-rept` | Use suspect values optimistically | Wrong values keep spreading | Record derivation dependencies; invalidate by confidence on conflict |
| `sosp21-ghost` | Move decisions asynchronously to user space | Decisions go stale; remote execution needs interrupts | Sequence-number checks reject stale decisions; batched commits amortize interrupts |
| `osdi16-scone` | Put the protection boundary at the system-call layer | Each switch is expensive; protected memory is scarce | Calls are delivered asynchronously without leaving the protected area; ciphertext buffers are placed outside the area |
| `sosp19-pipedream` | Pipeline by layer | The two halves of the same unit see different versions | Weight stashing |
| `sosp21-the-demikernel-datapath` | Bypass the kernel and use a library OS | Zero copy must manage memory registration and when to free | Take over the memory allocator, which already knows both |
| `osdi18-noria` | Precomputed state exists only partly and is backfilled on demand | Backfill races with in-flight updates | Order per item only |
| `osdi16-early-detection-of` | Rehearse consumer code at startup | Consumer code has side effects | Replace side-effecting calls with versions that only check and do nothing |
| `osdi16-ryoan` | Cut off externally visible behavior for each request | The environment must be rebuilt for each request | The "initialized, has not seen secrets" state is the same for all requests; snapshot it and restore only dirty pages |
| `sosp24-fbdetect` | Drill down to sub-units for detection | Cost shifts between components pollute sub-unit reports | Cost shifts only move within a domain; filter by rolling up one level |
| `osdi22-memliner` | The background follows the foreground's access order | When resources are nearly exhausted, this deviation is harmful | Set a cap by urgency, and degrade to the original behavior when needed |

How to use: after choosing a core insight, ask three questions. (1) What did the old design provide for free that my design takes away? (2) Who will be wrong or slower because of this? (3) To remove this new cost, can I apply one of the archetypes above again?
Note: these follow-up novelties most often lack ablations. XRP's mapping cache, Omniglot's static lock, DistServe's layer-aligned placement, Noria's per-item ordering and PipeDream's weight stashing all have no "what if it is removed" experiment. When designing experiments, give each novelty its own control (see experiment-playbook.md).

## Where insights come from

The counts are taken from the "Where insights come from" field of the 100 papers. Most papers combine 2 sources, so the counts add up to more than 100. The numbers are rough.

| Source | Approx. papers | Typical method | Examples |
|---|---|---|---|
| Measuring real workloads or systems | ~40 | Latency or instruction breakdown, access distribution, variance decomposition, duration distribution, utilization | `osdi22-xrp`, `osdi18-legoos`, `osdi18-gandiva`, `osdi24-servicelab`, `osdi20-serving-dnns-like-clockwork` |
| Rereading semantics or requirements | ~30 | Ask item by item "who uses this guarantee or constraint, and what happens if it is lost" | `sosp24-lazylog`, `sosp17-pebblesdb`, `osdi18-pocket`, `osdi21-mage` |
| Borrowing mature techniques | ~25 | Differential testing, queueing theory, OS paging, live migration, MDS codes, information retrieval, bandits, superoptimization, ownership types, LP | `sosp23-efficient-memory-management`, `osdi24-llumnix`, `osdi16-ec-cache`, `osdi21-oort` |
| Analysis of theory or proof structure | ~20 | Impossibility theorems, concentration bounds, quantifier structure, proof decomposition | `osdi20-performance-optimal-read-onl`, `osdi20-byzantine-ordered-consensus`, `osdi16-push-button-verification-of` |
| Hardware or environment trends | ~15–18 | NVM, SmartNIC/FPGA, programmable switches, core counts, hardware tracing, stacked memory | `sosp23-treesls`, `sosp17-kv-direct`, `sosp19-snap`, `osdi18-rept` |
| Production experience and generalizing from incidents | ~15 | Incident postmortems, operations workflows, release cycles, how on-call engineers debug | `osdi18-capturing-and-enhancing`, `osdi22-metastable-failures-in`, `osdi18-maelstrom`, `sosp21-ghost` |
| Looking at the problem from another layer | ~10 | Put the function in another layer, then ask what is missing there and what is available | `osdi20-aifm`, `sosp19-a-generic-communication`, `osdi26-controlling-opaque-component` |

Some patterns:
- The most common combination is "measurement + rereading semantics". First measure a skewed or stable fact, then ask which guarantee or constraint it makes unnecessary.
- Borrowing mature techniques almost never appears alone. The problem is always restated first, and only then does the analogy become visible: once "request state is append-only" is stated clearly, VM live migration can be used directly.
- Hardware-trend insights always come with "remeasure the cost ratio on today's hardware". Stating a trend without quantifying it is not an insight.
- For pure measurement or pure argument papers (`osdi16-network-requirements-for`, `osdi20-a-large-scale`, `osdi18-the-benefits-and`, `osdi22-metastable-failures-in`), the insight is "the field's default assumption is wrong". Their contribution is refutation and direction, not mechanism.
