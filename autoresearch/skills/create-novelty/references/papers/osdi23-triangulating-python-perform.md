# Triangulating Python Performance Issues with SCALENE
OSDI'23 · Emery D. Berger, Sam Stern, Juan Altmayer Pizzorno / UMass Amherst · Full text: https://www.usenix.org/system/files/osdi23-berger.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Python delivers a signal only when the interpreter regains control, so how late a signal arrives tells how long native code ran.

## Problem
Pure Python is 1–2 orders of magnitude slower than native code, and the integer 1 takes 28 bytes (4 bytes in C).
So the main optimization is to replace hot and memory-hungry code with native libraries such as NumPy.
This requires knowing, for each line, whether its time and memory go to Python or to native code, but existing profilers are copies of native profilers.

## Strawman / Baseline
- **Timer-signal sampling (pprofile_stat)**: Python delivers signals only to the main thread, and only handles them once the interpreter regains control → time in native calls and child threads is recorded as 0.
- **Trace-based profilers (cProfile, yappi, line_profiler)**: Every function call and every line triggers a callback → function-call time is inflated, an actual 25% is reported as 80%; pprofile has 36.8× overhead.
- **Memory by RSS (memory_profiler, Austin)**: RSS reflects only touched pages, not allocations → badly under-reports or even over-reports; memory_profiler is over 150× slower.
- **Peak only (Fil, Memray)**: Reports only objects still alive at the peak → large objects allocated and freed earlier are invisible.
- **Sampling by byte rate (tcmalloc, Go, JFR)**: Each byte triggers a sample with a fixed probability → the interpreter keeps creating and freeing short-lived objects, this churn fills the samples, and memory is charged to lines that allocate often rather than lines that grow the footprint (resident usage).
- **Leak finding (tracemalloc plus snapshot diff)**: 4× slower, and needs manual comparison.

## Novelty
1. **Signal delay is the execution time of native code**
   Insight: When timing in virtual time (CPU time only), the only reason a signal arrives late is that the interpreter is running native code.
   So: For each signal with interval q, measure the actual interval T, charge q to the current line's Python count and T−q to its native count. Child threads do not get signals: blocking calls such as join are replaced with versions that have a timeout, so the main thread wakes up regularly; then each thread's stack is scanned, and a thread stopped on a CALL bytecode counts as running native code.
   This turns the root cause of sampling (native time recorded as 0) into information, while keeping sampling's low overhead and lack of function inflation.
2. **Memory should be sampled by change in footprint, not by allocation volume**
   Insight: Allocations and frees of short-lived objects cancel out and do not change the footprint.
   So: Intercept both the system malloc and the Python allocator, to get Python and native memory separately; sample only when the net of "allocations minus frees" exceeds about 10 MB. Samples are few, results are deterministic, and lines that allocate often are not favored; samples carry timestamps, so usage over time can be plotted, not just the peak.
3. **A leak shows up as "an object sampled at a new peak is never freed"**
   So: Record one sampled object each time the footprint reaches a new high. On free, a single pointer compare tells whether it was freed. Laplace's rule of succession estimates the leak probability of that line; report it when it exceeds 95% and total memory is growing. This replaces tracemalloc's overhead and manual comparison.

Other design: Intercept memcpy to count copy volume per line (copies between Python/native and CPU/GPU); GPU utilization and GPU memory are sampled along with CPU samples.

## Evidence
- End to end: 10 pyperformance benchmarks, median overhead 1.02× with only CPU/GPU on, 1.32× with everything on (Memray 3.98×, Fil 2.71×). User cases: unvectorized NumPy 125×, Pandas chained indexing 18×, Rich 45%, groupby saves 1.6 GB, Semantic Scholar cost down 92%.
- Novelty 1 → Function-inflation microbenchmark: trace-based tools deviate a lot, Scalene is close to the true value. No controlled experiment on the accuracy of the Python/native split itself, only the NumPy case.
- Novelty 2 → Fewer samples than rate sampling, median 18×, up to 676×; error within 1% on a 512 MB test (Memray 6%); mdp log 32 KB, Austin 27 MB, Memray about 100 MB. No comparison of overhead or attribution accuracy between the two kinds of sampling, only sample counts.
- Novelty 3 → No direct ablation; leak detection is not evaluated at all.
- Gaps: Overhead numbers are inconsistent (introduction 0%/32%, §6.4 2%/30%); cases are self-reported by users; the GPU part is not evaluated.

## When it applies
Depends on CPython's semantics of delaying signal delivery and delivering only to the main thread; if the interpreter is changed to handle signals promptly even during native code, point 1 no longer works.
