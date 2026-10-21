# CortenMM: Efficient Memory Management with Strong Correctness Guarantees
SOSP'25 · Junyang Zhang et al. / Peking University, Ant Group, UCLA, Michigan Tech · Full text: https://web.cs.ucla.edu/~tamir/papers/sosp25.pdf (co-author Yuval Tamir's home page, camera-ready) · Selected: Best Paper

**One sentence**: The page tables of mainstream ISAs are all multi-level radix trees, so the VMA layer is no longer needed; with only one tree left, locking a range of addresses means locking a subtree, which both scales and can be verified.

## Problem
When multithreaded programs mmap, munmap and page-fault often, Linux memory management (MM) is a well-known scaling bottleneck.
Linux introduced fine-grained locking in 2023, and within two years concurrency bugs led to 10 CVEs.

## Strawman / Baseline
- **Linux's two-layer abstraction (VMA tree + page table)**: the VMA tree (which records the process's virtual memory ranges) and the page table have completely different structures but must be kept in sync → 4 kinds of locks and a 5000-word rule document. Page faults could run in parallel at the page table layer, but contend at the VMA layer; mmap and munmap take the global mmap_lock write lock outright.
- **Better data structures or concurrency control (RadixVM, NrOS, Bonsai)**: still keep two layers → RadixVM replicates page tables per core, with high memory overhead, and collapses above 128 cores; NrOS uses a coarse lock within each replica, performs about like Linux, and does not support demand paging.
- **Naively add reader-writer locks to the page table tree**: every operation read-locks each level's page table page from the root down, so locks on upper pages are shared by all operations → on 384 cores, high-contention page faults are 1.8× slower than Linux. The paper attributes the gap to "reader-writer locks vs. lock-free reads" without breaking down which part of the overhead it is.

## Novelty
1. **Both reasons for the VMA layer's existence are outdated**
   Insight: SunOS introduced VMAs in 1986, first to support many MMU kinds (segmented, hashed, inverted page tables), and second to store state the MMU lacks (demand paging, COW, swap). Today x86, ARM and RISC-V all use multi-level radix tree page tables, and the differences can be hidden with macros or traits; the extra state can also sit right next to the PTE.
   So: delete the VMA tree. Each page table page gets a descriptor holding one lock and an on-demand per-PTE metadata array that records each page's state (allocated but unmapped, swap location, etc.). The root cause of syncing two layers goes away.
2. **A range of addresses maps to one subtree, and finding that subtree needs no locks**
   Insight: disjoint address ranges fall in non-overlapping subtrees; walking down to find the covering page only reads and never writes, so it can go under RCU (readers take no locks, and a removed page is freed only after all readers have left).
   So: all MMU operations go through a transactional interface: first lock the range, then atomically run query/map/mark/unmap; disjoint ranges run fully in parallel. The advanced version walks lock-free to the lowest page table page that covers the range and touches no locks above it, so operations no longer share locks on upper pages. This has two costs. Other threads also walk lock-free and may skip past this thread's covering page to lock a deeper page directly, so all descendants of the covering page must be locked in DFS order. A page may be removed by unmap after the walk but before it is locked, and changes to it would be lost, so removed pages are marked stale, and hitting a stale page when locking means walking again.
3. **Concurrency control and page table operations are separate, so they can be verified separately**
   Insight: the transactional interface guarantees mutual exclusion within a range, so page table operations can be proven as sequential programs.
   So: use Verus (an SMT verifier for Rust) with state machine refinement (proving layer by layer that each step of the implementation matches some step of the abstract specification) to prove that both locking protocols give mutual exclusion (pages write-locked by two cores never have an ancestor-descendant relation), then prove that operations such as map/unmap are functionally correct and that the page table always stays well-formed. All other code is forced to use only safe Rust, so it cannot bypass the interface to change the MMU directly.

## Evidence
- End to end (384-core AMD VM, vs. Linux 6.13.8): metis 26× faster (reader-writer lock version 15×), dedup at 64 threads 2.69×, psearchy about 2×, JVM thread creation 32% faster; PARSEC does not slow down. metis on 128 cores is 1.24× faster than RadixVM.
- Novelty 1 → single-threaded, 4 of 5 microbenchmarks are faster (7.8–76.9%), mmap is 3.1% slower; fork is 17.7% slower (it must walk the page table). Memory overhead is similar to Linux; even with metadata arrays fully filled, the upper bound is within 2%. Porting to RISC-V adds 252 lines (Linux: 699 lines).
- Novelty 2 → low contention on 384 cores: 33×–2270× faster than Linux; high contention: 3×–1489×, but it stops scaling beyond 64 threads. The reader-writer lock version vs. the RCU version is the ablation of lock-free walking; removing the per-core address allocator and TLB optimizations changes metis very little.
- Novelty 3 → spec 4868 lines, proof 4279 lines, implementation 1769 lines (ratio 5.2:1), 8 person-months, verification under 20 seconds. No comparison with the cost of verifying a two-layer design, and no mutation testing: no direct ablation.
- Gaps: what is verified is a copy ported to Verus, not linked with the kernel, and consistency between them is checked by hand; locks, RCU and the page allocator are the trusted base, and sequentially consistent memory is assumed; all experiments run in VMs, and ARM is not ported.

## When it applies
The MMU must use multi-level radix tree page tables; operations that walk the whole address space (fork) get slower; it does not scale when many threads crowd onto the same last-level page table page.
