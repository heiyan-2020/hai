# The benefits and costs of writing a POSIX kernel in a high-level language
OSDI'18 · Cody Cutler, M. Frans Kaashoek, Robert T. Morris / MIT CSAIL · Full text: https://www.usenix.org/system/files/osdi18-cutler.pdf (USENIX camera-ready) · Selected: Community favorite (3 sources: Cornell CS6410 2021, MIT 6.828/6.1810 2018/2024, UW CSE 551 2024)

**One sentence**: Comparing Go and C on code paths aligned line by line, the language tax is only 5–15%. It comes mainly from checks the compiler inserts, not from GC. GC overhead can be traded for memory.

## Problem
Memory safety bugs in C kernels keep coming: from January to April 2018, Linux alone had 36 commits that only fixed use-after-free. A high-level language (HLL) with GC can remove this class of bug, but mainstream OS designers doubt it can keep up in a high-performance kernel. The authors wrote Biscuit, a monolithic POSIX kernel in Go (about 28,000 lines of Go, no C, runs NGINX and Redis unmodified), to quantify the gains and losses.

## Strawman / Baseline
- **The skeptics' assumption: GC is too expensive for a kernel**: C kernels manage memory with explicit frees and special allocators. GC must stop all cores (tens of μs each time) and spend CPU tracing live objects. The more live objects and the more frequent the collection, the higher the overhead. → It really is expensive when heap memory is tight (up to 34% in Novelty 2), but nobody had measured how expensive under real kernel workloads.
- **Existing HLL kernels (Singularity, SPIN, Mirage, etc.)**: Focus on using the language to explore new OS structures. → Performance differences come from the new structures. The cost of the language itself was never measured on its own.
- **Compare all of Biscuit directly with Linux**: → The two differ in features and design (Linux is at most 10% faster), so the difference cannot be attributed to the language.
- **How Linux handles kernel heap exhaustion**: It lets the system call run first and checks for failure at each allocation point. → While holding locks it cannot wait for memory forever (that would deadlock with the OOM killer, which kills processes to free memory). So it must undo changes layer by layer and return an error. Undo code has always been buggy, and applications rarely handle this error.

## Novelty
1. **Separate the language cost from design differences**
   Insight: Only when the executed source code is nearly the same can the difference be attributed to the language.
   So: Make the pipe ping-pong path and the page fault path in Linux and Biscuit correspond almost line by line (turning off the extra features in Linux), and use CPU profiles to confirm the hottest instructions match. Also locate the checks the compiler inserted in the binary, and account for them by feature.
   Result: C is 15% and 5% faster. The gap comes mainly from stack growth checks at function entry, write barriers (recording code the compiler inserts for pointer writes while GC is running), bounds checks, and nil pointer/type checks, not from GC.
2. **GC overhead is set by headroom, and can be traded for memory**
   Insight: GC's share of CPU is roughly proportional to "live data (objects still referenced) / heap memory". The difference between the two is the headroom; the larger it is, the less often collection runs. Kernel live data is usually only tens of MB, so with enough heap memory GC is cheap. It is expensive only when memory is tight.
   Result: The live data of the three applications is 18–48 MB, and GC takes only 1–3% of CPU. With live data fixed at 640 MB, growing the kernel heap from 960 MB to 1920 MB lowers the ratio from 0.66 to 0.33 and the GC share from 34% to 9%. The advice is to size the kernel heap at 2–3 times peak live data.
3. **Kernel code is like an event handler, so the maximum heap each system call needs can be computed statically**
   Insight: A system call does a bounded amount of work and returns. Go makes call graphs and escape analysis easy.
   So: The tool MaxLive computes the upper bound of heap live at the same time for each system call. At the system call entry no locks are held yet. There, the kernel reserves that much heap first. If there is not enough, it waits and wakes a killer thread that kills the process using the most kernel resources. Once execution starts, allocation cannot fail, so no undo code is needed. Applications see delay instead of errors.

## Evidence
- End to end (4-core Xeon, CMailbench, NGINX, Redis): Total HLL-related overhead is at most 13% (function entry checks 4–6%, safety checks 2–3%, GC 1–3%). Linux throughput is 0.99–1.09× that of Biscuit.
- Novelty 1 → Ping-pong is 465,811 vs 536,193 round trips/s. Of the extra instructions per round trip, stack checks are 250, write barriers 200, and bounds checks 144. Page fault is 731 vs 695 ns.
- Novelty 2 → The heap size experiment above. When live data and heap both double and the ratio stays the same, the GC share also stays the same (19% vs 18%). In NGINX, the longest single GC pause is 115 μs. Total pause per request is at most 582 μs and 1.8 μs on average (an average request takes 45 μs).
- Novelty 3 → A malicious process repeatedly exhausts a 512 MB kernel heap for 25 minutes. Live data can reach 97% (the reservation is not too conservative). System calls of normal processes waited hundreds of thousands of times and never returned an error. Except for rename (1 MB) and fork (641 kB), every system call's bound is <500 kB. Cost: 70 map/slice size annotations, 78 loop bound annotations, and about 20 loops that reserve per iteration.
- Gaps: The safety benefit relies on a manual review of 2017 Linux CVEs (40 of 65 could be avoided or mitigated with Go), not measurement. GC also needs to allocate when no memory is free, and fragmentation can make the reservation invalid; neither is handled. Only 4 cores were tested.

## When it applies
Kernel live data must be much smaller than the memory that can be given to it, and system calls must be bounded and statically analyzable. With millions of live objects and tight memory, GC will eat a lot of CPU.
