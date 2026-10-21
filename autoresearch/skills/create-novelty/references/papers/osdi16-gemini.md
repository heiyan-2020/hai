# Gemini: A Computation-Centric Distributed Graph Processing System
OSDI'16 · Xiaowei Zhu, Wenguang Chen, Weimin Zheng, Xiaosong Ma / Tsinghua University, Qatar Computing Research Institute · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-zhu.pdf (camera-ready) · Selected: Highly cited (281 citations)

**One sentence**: On fast networks, distributed graph computation is bound by computation, not communication. So build on the best single-machine implementation and add only the lightest distributed overhead.

## Problem
Distributed graph systems can process graphs that do not fit on one machine, but they are very inefficient. Running PageRank (twitter-2010) on an 8-node, 100 Gbps InfiniBand cluster, PowerGraph with 192 cores takes 40.3 s. Ligra on one 24-core machine takes only 21.9 s, and an optimized single-thread implementation takes only 99.9 s.

## Strawman / Baseline
- **Communication-centric systems (PowerGraph, PowerLyra; vertex-cut + GAS model)**: partitioning aims for low communication volume and balanced edge counts. → Measured network use averages under 3 Gbps, far from saturated. The bottleneck is computation: 7.15T instructions, 14 times Ligra, 71% LLC miss, 65.5% CPU utilization. The root cause is what was added for distribution: hash table translation between global/local IDs, vertex replicas that carry data, a communication-bound apply phase, no dynamic scheduling.
- **Hash partitioning**: scatters vertices. → It throws away the locality of the original graph, with many replicas and high cache misses.
- **Naive contiguous chunking**: split evenly by vertex count or edge count. → On power-law graphs load is badly unbalanced: 5.51 s when split by vertices, 3.95 s when split by edges.

## Novelty
1. **The network is fast enough; what distribution must do is "not slow down single-machine computation"**
   Insight: On fast networks, communication can be hidden behind computation. The real loss comes from the extra instructions and memory accesses paid for distribution.
   So: Extend the fastest single-machine approach (Ligra switches between push and pull by the number of active edges) to the cluster as is. Two user functions, signal and slot, separate "send messages" from "process edges locally". Between each master/mirror pair there is at most one message per round, so the message count drops from O(|E|) to O(|V|). A mirror is only a placeholder and stores no data. Nodes take turns sending to and receiving from each peer in ring order, overlapping communication with computation. This removes PowerGraph's replica maintenance and apply overhead.
2. **Vertex IDs in real graphs already carry locality, and contiguous chunks preserve it**
   Insight: In crawled graphs, neighboring vertices often have close IDs (for example, web pages ordered by URL in lexicographic order).
   So: Cut vertex IDs into contiguous chunks, one chunk per node. Ownership is decided by comparing boundaries, with no ID translation hash table. The local vertex array is contiguous, so random accesses land in a small chunk. Chunks can be cut again by the same rule down to sockets (NUMA) and cores. This fixes the root causes of hash partitioning losing locality and of ID translation overhead.
3. **The cost of a chunk depends on both edge count and vertex count, so balance must count both**
   Insight: Edge count decides the amount of work. The vertex count in a chunk decides the locality of random accesses. On power-law graphs the two differ greatly.
   So: When chunking, make α·|vertices| + |in-edges| equal across chunks (α defaults to 8(p−1)). Inside a node, fine-grained work stealing in groups of 64 vertices evens out imbalance across cores.

Other design: after partitioning, the index array is still O(|V|), so use compressed CSR/CSC that stores only vertices with edges.

## Evidence
- End to end: on 8 nodes running PR/CC/SSSP on 5 real graphs, it is on average 19.1× (8.91–39.8×) faster than the fastest of PowerGraph, GraphX and PowerLyra. Only Gemini finishes clueweb-12 with 42 billion edges. On one machine PR takes 12.7 s, beating Ligra at 21.2 s and Galois at 19.3 s. COST (how many cores are needed to beat a single thread) is 3.
- Novelty 1 → forcing push only or pull only: the gap between the two is large. The adaptive choice is wrong only in 2/76 rounds of CC and 5/172 rounds of SSSP. signal/slot vs GAS, and ring scheduling: no direct ablation.
- Novelty 2 → replacing hash partitioning with contiguous chunking: PR goes 3.85→3.02 s on twitter and 8.05→1.48 s on uk-2007. Removing socket-level sub-partitioning: 5.29→3.02 s, 3.85→1.48 s.
- Novelty 3 → balance metric: by vertices 5.51 s, by edges 3.95 s, mixed 3.02 s. Work stealing plus pre-balancing is 1.66×/2.18× faster than static scheduling.
- Gaps: the authors say the optimizations depend on each other, so there is no step-by-step cumulative ablation. twitter scales poorly beyond 4 nodes, because the vertex set including replicas does not shrink with node count. α is an empirical value. Applications with little computation, such as BFS, lose to Ligra.

## When it applies
The network must be fast enough that computation becomes the bottleneck, and the input's vertex IDs must have locality (otherwise reorder first). The graph must fit in cluster memory, and the BSP synchronous model is used.
