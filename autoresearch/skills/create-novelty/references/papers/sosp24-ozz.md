# OZZ: Identifying Kernel Out-of-Order Concurrency Bugs with In-Vivo Memory Access Reordering
SOSP'24 · Dae R. Jeong et al. / KAIST, Georgia Tech, SNU · Full text: https://gts3.org/assets/papers/2024/jeong:ozz.pdf (camera-ready, author lab home page) · Selected: Best Paper

**One sentence**: Reordering visible to other threads comes in only two kinds, "a write not yet committed" and "a read that gets an old value"; both can be produced exactly in software inside the kernel, and then each hypothesis "a barrier is missing here" can be tested one by one.

## Problem
Lock-free kernel code relies on memory barriers (which stop the CPU from reordering memory accesses across them). A missing barrier causes an OoO bug: it appears only when thread interleaving and CPU reordering happen together, and the result is a null pointer or memory corruption.
These bugs mainly appear on weak memory order machines such as ARM, but syzkaller runs on x86, which does no store-store or load-load reordering, and QEMU TCG emulating ARM does not reorder memory accesses either.

## Strawman / Baseline
- **Concurrency fuzzers (SKI, Snowboard, etc.)**: control interleaving with breakpoints or by pausing vCPUs, and assume memory accesses happen in order; the breakpoints themselves make accesses complete in order and hide reordering.
- **Run on real ARM machines**: reordering happens inside the CPU, cannot be controlled or reproduced, and needs many ARM machines; full architectural simulation is too slow.
- **Offline analysis of memory access traces (in-vitro)**: simulates reordering after the fact and loses run-time context (which objects are freed, which locks are held), so detectors such as KASAN cannot be used.
- **Static pattern matching (OFence)**: relies on predefined patterns such as "barriers come in pairs", and cannot see bugs outside the patterns.
- **Once reordering is possible, try at random**: must pick both an interleaving point and a subset of accesses to reorder; k accesses give 2^k subsets, so blind tries rarely hit (the paper gives no measured scale).

## Novelty
1. **Reordering has only two externally visible effects, which can be produced exactly in a running kernel**
   Insight: other CPUs see only two kinds of reordering: a write of this thread not yet committed (store-store, store-load reordering), or a read of this thread getting an old value (load-load reordering). There is no need to simulate the pipeline.
   So: at compile time, replace every memory access with a callback (OEMU). A write can stay in a per-thread virtual store buffer and be committed at a write barrier or an interrupt; a read can take an old value from a global store history, but only values written after the previous read barrier. Only reorderings allowed by the LKMM (Linux kernel memory model) are produced, to avoid fake bugs.
   Reordering becomes a deterministic switch that can be combined with breakpoint-style interleaving control (answering concurrency fuzzers), and it happens in the real kernel, so detectors such as KASAN can be used (answering in-vitro).
2. **An OoO bug is a missing barrier, so search for "where a barrier might be missing"**
   Insight: every OoO bug corresponds to "a place where a barrier should be", and a barrier only forbids the kinds of reordering that cross it.
   So: run system calls single-threaded and record memory accesses and existing barriers; keep only addresses shared by two system calls, and split them into groups at existing barriers of the same kind. For a group of k accesses, instead of enumerating subsets × interleaving points, try only k hypothetical barrier positions (times 4 cases: which call reorders × write/read barrier). Each position opens all the reorderings it should have forbidden, with the interleaving point fixed.
   A write barrier test switches threads just before the real barrier at the end of the group: that barrier will commit the delayed writes, so this is the last moment they are uncommitted, and the other thread sees exactly "the later write is visible, the earlier one is not". A read barrier test switches threads just after the real barrier at the start of the group: the other thread writes into the store history first, so the reordered read has an old value to read.
   Positions that reorder the most accesses are tested first. It relies on no predefined patterns (answering OFence), and the report directly gives where the barrier should be added. The paper does not report the actual number of candidates.

## Evidence
- End to end: 6 weeks of fuzzing (32 VMs) on Linux 6.5-rc6 to 6.8; of 61 distinct crashes, 11 new OoO bugs were confirmed by hand (TLS, BPF, XDP, etc.): 6 fixed, 3 confirmed, 2 reported. None of them appears on x86.
- Novelty 1 → 9 known OoO bugs collected from git history; with their patches reverted, 8 were reproduced (5 store-store, 3 load-load), each needing 12–342 tests. The 1 failure depends on thread migration, while OZZ pins threads to cores. Cost: LMBench is 3.0–59.0× slower, and throughput is 1/7.9 of syzkaller (0.92 vs. 7.33 tests/s).
- Novelty 2 → of the 19 bugs in the evaluation set, 11 were triggered by the hint with the most reorderings and 6 by the second most. No comparison with random reordering: no direct ablation. Vs. OFence: 8 of the 11 new bugs fall outside its patterns; conversely, OFence's bugs are in modules that need specific hardware, which OZZ cannot test.
- Gaps: no comparison with running syzkaller on real ARM machines; new bugs were picked out of crashes by hand.

## When it applies
The bug must be caused by store-store/store-load/load-load reordering under a single missing barrier between two threads, and a detector must see it once triggered; load-store reordering and paths that need thread migration or specific hardware are out of scope.
