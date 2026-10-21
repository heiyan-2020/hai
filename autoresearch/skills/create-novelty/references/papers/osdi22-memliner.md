# MemLiner: Lining up Tracing and Application for a Far-Memory-Friendly Runtime
OSDI'22 · Chenxi Wang, Haoran Ma et al. / UCLA, University of Chicago · Full text: https://www.usenix.org/system/files/osdi22-wang.pdf (camera-ready) · Selected: Best Paper

**One sentence**: GC can mark objects in any order, and objects the application is accessing must be live, so let the GC mark along the application's access path.

## Problem
Java applications run on swap-based far memory (local memory serves only as a cache, and pages are swapped in over RDMA on a fault).
The tracing threads of a concurrent GC (which walk the object graph from the roots and mark live objects) access the heap at the same time as the application, and their working sets are unrelated: each pushes the other's pages out, and the combined fault sequence also looks random to the prefetcher.

## Strawman / Baseline
- **Default concurrent GC (G1, Shenandoah)**: For Spark LR at 25% local memory, turning on concurrent tracing raises application-thread faults from 3.5K to 9.6K per second, and the share of faults handled by prefetch falls from 65% to 39%. Under Shenandoah, Spark is 12× slower.
- **Turn off concurrent tracing**: Shenandoah and ZGC cannot turn it off. With G1 turned off, total pause time becomes 2.7×, a single full GC takes up to 76.9 s, and end to end it is 18% slower.
- **A stronger OS prefetcher (Leap)**: The mixed access stream shows no pattern; contiguous-page prefetch does not help with GC pointer chasing.
- **Offload GC to the memory server (Semeru)**: Requires the whole heap to be remote and the memory server to have compute, and cross-server references need coordination. AIFM supports only C/C++.
- **Naive alignment**: Mark only objects the application has touched → the application may not touch some live objects for a long time, so the closure never finishes, and once the heap is full only a full GC is left.
- **GC checks the page table for every object to see whether it is local** → one system call per object.

## Novelty
1. **Marking order does not affect correctness, so GC can borrow the application's working set**
   Insight: An object the application is accessing is live right now and will be marked by GC sooner or later; tracing only requires the closure to be marked in the end, and it does not matter which object is marked first. The application's access order cannot change, but the GC's can.
   So: In the JVM's existing read/write barriers, the dereferenced object pointer is put into a per-thread lock-free ring buffer. Tracing threads mark these objects first and follow them 3 hops ahead, because the application will use them soon; a fault caused by GC is then a fault paid early on the application's behalf. Once the working sets overlap, there are fewer faults and the prefetcher can see a pattern.
2. **Spare bits in pointers can cheaply record "recently accessed"**
   Insight: An object dereferenced recently is very likely still in local memory. The barrier already runs on every dereference, and 64-bit pointers have spare bits.
   So: The kernel advances an epoch when the set of locally resident pages changes by more than a set fraction, and the barrier writes the current epoch into 4 spare bits of the pointer. In normal traversal, when GC meets an object whose epoch is too old, it postpones it, expecting the application to swap it in first.
   Without checking the page table, this tells apart objects that are "local but missed by the ring buffer" from objects that are "remote and not used soon".
3. **Alignment must be breakable based on how urgent GC is**
   Insight: The cost of postponing marking is a later closure, and that cost only really matters when the heap is nearly full.
   So: Each object can be postponed at most MAX_DL times. MAX_DL is set by the free-heap fraction: 4 above 50%, 2 at 15–50%, and 0 below 15%, which falls back to normal tracing. This solves the unfinished-closure problem of naive alignment.

Other design: When the ring buffer is full, entries are overwritten (an entry only signals priority); in G1, entries are enqueued only during concurrent tracing.

## Evidence
- End to end (5 applications, 32 GB heap): G1 is 1.48×/1.51× faster at 25%/13% local memory, and Shenandoah is 2.16×/1.80× faster. On-demand swap-ins under G1 drop by 81%. Compared with fully local runs, G1's slowdown falls from 2.17×/3.73× to 1.47×/2.48×.
- Novelty 1 → With Leap instead: still 1.6× faster, and Leap's coverage rises 1.5× and its accuracy 1.7×. In Spark, 11–45% of marks come from the ring buffer. No ablation that removes this point alone. Compared with Semeru: similar performance on the same swap system.
- Novelty 2 → With epoch estimation turned off, SLR, SKM, and STC are 8.6%, 8.8%, and 11.3% slower.
- Novelty 3 → Only memory-usage curves before and after GC (the authors say reclamation is almost not delayed). The thresholds and the 3 hops are empirical values; no direct ablation.
- Gaps: Barrier overhead when fully local is 2% (Shenandoah)/5% (G1); Shenandoah used a smaller dataset.

## When it applies
It helps only when the local memory fraction is below about 50%; above that it matches the original JVM. It removes only the interference from concurrent tracing, not the interference from concurrent evacuation.
