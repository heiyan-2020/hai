# AIFM: High-Performance, Application-Integrated Far Memory
OSDI'20 · Zhenyuan Ruan et al. / MIT CSAIL, Brown, VMware Research · Full text: https://www.usenix.org/system/files/osdi20-ruan.pdf (camera-ready) · Selected: Highly cited (261 citations)

**One sentence**: The kernel sees only pages, while the application knows object boundaries and access patterns. Put swapping inside the data structures, and use green threads to turn remote waits into usable CPU time.

## Problem
Memory is the least elastic resource in a data center: in one month at Google, 790,000 jobs had instances killed, many for lack of memory, while about 30% of memory went unaccessed for minutes.
Far memory (putting cold data in another machine's memory) adds capacity, but the common case must be as fast as local memory.

## Strawman / Baseline
- **Kernel swaps pages to remote memory (Fastswap, based on RDMA)**: Swaps in and out in 4 KB pages. → Read/write amplification for small objects: a page holding 128 KV pairs amplifies 128 times, and it pollutes local memory. Hotness can only be tracked per page. Application semantics can only come in through coarse interfaces like madvise.
- **The kernel page fault path itself**: Swapping a page in from SSD takes the device only 6 µs, but Linux needs more than 15 µs. A kernel thread switch costs about 500 ns, so Linux spins waiting for data and wastes 11.7 µs.
- **Swap per object in C/C++**: → After a dereference returns a raw pointer, the application may store it on the heap, the stack, or in registers. The runtime cannot know when it is safe to swap out. Scanning the whole address space like Boehm GC is too expensive.
- **Stop-the-world swap-out**: → Application threads stop during swap-out, with latency spikes up to 340 ms.

## Novelty
1. **Applications reach remote objects only through data structures, so swapping can be per object and use semantics**
   Insight: A data structure knows object boundaries, access direction (sequential scan of an array, list traversal), which data is used only once, and which operations do almost no computation. The kernel sees only pages. Also, once an application gets a raw pointer, it usually uses it only within one operation (such as one loop iteration).
   So: Use remote smart pointers (64 bits holding the address and hot/dirty/present bits) to swap in and out per object, with no amplification. Hotness is recorded per object. Data structures come with their own prefetchers. Accesses used only once are marked non-temporal and swapped out first. Copy and aggregation are offloaded to the remote side.
   The data structure API requires a DerefScope (dereference scope) to be passed in. Objects inside the scope are not swapped out, so the lifetime of raw pointers becomes known, and there is no need to scan the address space. This is a contract the application must keep: using a raw pointer outside the scope is undefined behavior and is not checked. To avoid code changes, there is an API that copies on dereference, with 3–8% overhead.
2. **User-space green threads let "waiting for remote" switch away**
   Insight: Remote access takes microseconds, and the cost of kernel thread switches forces the system to spin. User-space thread switches are much cheaper.
   So: The runtime is built on Shenango's green threads and kernel-bypass TCP stack. On a miss it blocks the current thread and runs other requests, so wait time turns into throughput.
3. **Dereferences far outnumber swap-outs, so all synchronization cost is pushed onto the swap-out thread**
   Insight: Dereferences are on the hot path, and swap-out is a low-frequency background task.
   So: The swap-out thread works in RCU style (readers take no lock; the writer waits until all readers pass a quiescent point). It first sets a "being swapped out" bit, and moves the object only after all application threads have seen it. Application threads only check a few bits, so a local hit adds only 3 micro-ops. If an application thread hits an object being swapped out, it copies it itself and takes it back with CAS, without blocking. This removes stop-the-world pauses.

Other design: a 2 MB log-structured allocator with mark-compact; the scheduler runs threads holding a DerefScope and swap-out threads first (with this off, memory runs out in about 0.7 s).

## Evidence
- End to end: A simulated web frontend (26 GB data, 5 GB local) reaches 370k req/s, 20 times Fastswap (19k) and 84% of all-local (440k). DataFrame analytics (31 GB working set) with only 1 GB local memory still gets 78% of all-local, while Fastswap gets only 20%.
- Novelty 1 → A hash table (Zipf 0.8) is 61 times faster than Fastswap. Fastswap spends 38% of cycles on kernel paging and 49% waiting on I/O. Removing non-temporal marks in the web frontend drops throughput from 370k to 140k req/s. In DataFrame, offloading Copy contributes 18–38%, Shuffle 2.9–13%, Aggregate 4.5–12%. DerefScope has no direct ablation.
- Novelty 2 → Reading remote objects on 4 cores, throughput is 1.8 times (4 KB) to 6.8 times (64 B) that of Fastswap, which mixes in the amplification difference. At 80% misses, throughput rises with thread count up to 160. Only thread count was varied; there is no comparison with spin waiting.
- Novelty 3 → Stop-the-world has 340 ms spikes; pauseless stays at about 25 ms. A local dereference that hits L1 has 4 times the latency of a plain pointer.
- Gaps: AIFM uses TCP and Fastswap uses RDMA, which disadvantages AIFM. The two are equal when computation between accesses reaches about 50 µs. Without offloading, DataFrame loses to Fastswap once local memory exceeds 60%.

## When it applies
Applications must switch to these data structures (DataFrame changed 1,192 lines, plus 233 lines of remote code). The prototype supports only one remote server, with no sharing and fixed capacity. There must be enough computation or concurrency between remote accesses to hide latency.
