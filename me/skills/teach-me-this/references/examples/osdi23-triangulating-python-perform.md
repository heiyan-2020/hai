# Triangulating Python Performance Issues with Scalene
OSDI'23 (Best Paper) · Emery D. Berger, Sam Stern, Juan Altmayer Pizzorno / UMass Amherst · https://www.usenix.org/conference/osdi23/presentation/berger
Paper type: tool (profiler) with a measurement-style evaluation
> Spoiler: this card dissects the paper. Do not read it if you want to train on this paper.

## Dissection
- Background: CPython is a bytecode interpreter written in C. Pure Python is 1–2 orders of magnitude slower than native code (pure-Python matrix multiply takes more than 60,000× as long as BLAS), and its objects are large (the integer 1 is 4 bytes in C, 28 in Python; "a" is 2 bytes vs. 50). So the main way to speed up Python is to find hot or memory-hungry pure-Python code and move it into native libraries (NumPy, scikit-learn, TensorFlow). Python profilers come in two kinds: tracing ones built on `sys.settrace` (cProfile, profile, yappi CPU, line_profiler, pprofile det., memory_profiler) and sampling ones (pprofile stat., py-spy, pyinstrument, Austin). Memory profilers measure RSS (memory_profiler, Austin) or intercept allocations and report the peak (Fil, Memray).
- Problem: To decide what to move to native code, a developer needs, per line, how much time and memory go to Python vs. native code, on unmodified programs, at an overhead low enough to run real workloads. No existing profiler gives that. Cheap sampling profilers record zero time for native code and child threads. Tracing profilers are slow (up to 36.8× median) and distort time spent in function calls. Memory profilers are either wrong (RSS) or slow and report only the peak.
- Challenges: (1) Timer sampling in CPython goes blind exactly where native code runs and in every thread but the main one. (2) The obvious accurate fix, tracing every call, line or allocation, costs 4× (tracemalloc) to over 150× (memory_profiler) and distorts what it measures. (3) The standard cheap memory fix, rate-based sampling (tcmalloc, Go, Java TLAB/JFR), samples by bytes allocated; Python's interpreter constantly creates and frees short-lived objects, so samples go to lines that churn the allocator, not lines that grow the footprint. (4) Native and Python memory must be told apart, though Python's own allocator calls into malloc.
- Solution:
  1. Insight: CPython handles a timer signal only when the interpreter loop regains control, and only in the main thread. In virtual (CPU) time, the only reason a signal arrives late is that native code was running. → Design: at each signal, measure elapsed CPU time T against the interval q; add q to the line's Python counter and T−q to its native counter. For threads: monkey-patch blocking calls (e.g. `threading.join`) to use timeouts of `sys.getswitchinterval()` so the main thread keeps waking; keep a sleeping/executing flag per thread; on each signal enumerate threads (`threading.enumerate`, `sys._current_frames`) and count a thread as native if its current bytecode is a call (`CALL_FUNCTION`, `CALL_METHOD`, `CALL` in 3.11). → Turns the cause of the blindness into the measurement, at sampling cost, with no tracing distortion.
  2. Insight: short-lived allocations and frees cancel out; what matters is change in footprint. → Design: a shim allocator interposed on both malloc/free (LD_PRELOAD / DYLD_INSERT_LIBRARIES) and Python's allocator (`PyMem_SetAllocator`), with a thread-local "inside allocator" flag to avoid double counting; take a sample only when |allocs − frees| crosses a threshold T (a prime slightly above 10 MB); record a timestamp and footprint at each crossing. → Few, deterministic samples that point at lines that change the footprint; Python vs. native memory per line; memory over time, not just the peak.
  3. Insight: a leak is an object allocated at a new peak that is never freed. → Design: at each new maximum footprint, track one sampled object; each free checks it with one pointer compare; keep (frees, mallocs) per site and compute a leak probability with Laplace's rule of succession; report when above 95% and overall memory growth slope is at least 1%. → Replaces tracemalloc (4× slowdown) plus manual snapshot diffs.
  Also: copy volume (MB/s copied per line) by interposing on memcpy, sampled by rate, since copies only ever add up; GPU utilization and memory read at each CPU sample.
- Evidence: 10 longest pyperformance benchmarks, median overhead 1.02× for CPU (and CPU+GPU) and 1.32× with memory on (worst: pprint 4.03×), vs. Memray 3.98×, Fil 2.71×, memory_profiler 37.11× (over 150× on three benchmarks), pprofile det. 36.83×. Function-call microbenchmark: a trace-based profiler reports 80% where the truth is 25%; Scalene is near the diagonal. 512 MB array: Scalene and Fil within 1%, Memray within 6%, RSS profilers far off. Threshold vs. rate sampling: median 18×, up to 676× fewer samples. mdp log: Scalene 32K, Austin 27 MB, Memray almost 100 MB. User case studies: NumPy code 125× faster (80 → 10,000 iterations/min), Pandas chained indexing 18×, Rich 45%, groupby 1.6 GB (43%) less memory, Semantic Scholar 92% lower cost.

## Reveal schedule
| Fact | Earliest stage |
|------|----------------|
| Python is slow and memory-hungry; moving code to native libraries is the main fix | 1 |
| Overheads of existing profilers; RSS profilers are wrong on the 512 MB test; tracing distorts function time (80% vs 25%) | 1 |
| Timer-sampling profilers show zero time for native calls and child threads | 1 |
| The need: per-line Python vs. native split of time and memory, at sampling overhead | 1 (learner should find this) |
| CPython handles signals only in the main thread, and only when the interpreter loop regains control | 2 (hint; confirm if the learner guesses it in stage 1, do not build on it) |
| Signal delay in virtual time = native execution time (q vs. T−q) | 2 (learner should find this) |
| Threads: timeouts on blocking calls, thread enumeration, CALL bytecode check | 2 |
| Rate-based sampling is biased by Python's churn; sample on net footprint change | 2 |
| Interpose on both allocators; avoid double counting | 2 |
| Peak-only reports miss earlier large objects (4 GB example) | 2 (as a wall) |
| Leak detection at new peaks; copy volume; GPU | 2 (detail) |
| Name Scalene; any number from §6 not already shown; case-study results | 3 |

Protected terms: Scalene, "triangulating" (3); "threshold-based sampling" (2, only after the learner proposes sampling on net change); "function bias" (3); "copy volume" (2, after the learner proposes counting copies); "leak score" (3).
Safe background: sampling vs. tracing profilers, `sys.settrace`, SIGPROF/`setitimer`, wall-clock vs. virtual (CPU) time, `time.process_time()`, RSS and demand paging, malloc interposition with LD_PRELOAD, the GIL, NumPy vectorization, the pyperformance suite, rate-based heap sampling in tcmalloc/Go/JFR (in general; not its bias under Python, which is a stage-2 wall).

## Stage 1: Find the problem
### Background to give
You are the performance person in a research group that writes most of its code in Python: data pipelines in Pandas, models in NumPy and PyTorch, a few long-running services. When something is slow or runs out of memory, people come to you and ask which lines to fix. You have a laptop-class 8-core machine and the usual Python profilers installed (cProfile, line_profiler, py-spy, pprofile, yappi, memory_profiler, Fil, Memray, Austin).

### Phenomena
1. You wrote two loops that do the same work. One calls a small helper function inside the loop; the other has the helper's body inlined. Timed with a high-resolution timer, the version with the call takes 25% of the run. A tracing profiler reports that it takes 80%.
2. A grad student's gradient-descent classifier "already uses NumPy" and runs at 80 iterations per minute. They ask which lines to rewrite. The group wiki says pure-Python matrix multiply is over 60,000× slower than BLAS, and that the integer 1 takes 28 bytes in Python vs. 4 in C. They want to know, line by line, where rewriting will pay off.
3. Memory test: allocate one 512 MB array, then touch a varying part of it, from 0% to 100%. memory_profiler and Austin report a size that changes with how much was touched, mostly too low and sometimes too high. Fil reports within 1% of 512 MB, Memray within 6%.
4. A colleague tried Intel VTune on a short script and got no Python data at all. The VTune docs say: "if your application has very low stack depth, which includes called functions and imported modules, the VTune Profiler does not collect Python data."
5. You run pprofile in statistical (timer-sampling) mode on a script. The line `C = A @ B` on large arrays takes most of the run by wall-clock timing, but the profile shows no time on it. A function that runs in a `threading.Thread` worker also shows zero.
6. You measured slowdowns on ten long pyperformance benchmarks (median of each tool): py-spy 1.02×, pprofile statistical 1.02×, cProfile 1.73×, profile 15.1×, pprofile deterministic 36.8×, Fil 2.71×, Memray 3.98×, memory_profiler 37× (over 150× on three of them). On one 13-second benchmark Memray wrote a log of almost 100 MB; its log grows about 3 MB/s. Turning on tracemalloc alone slows apps down about 4×.

Tutor notes: 5 is the core one (the cheap tool is blind to native code and threads, which is exactly where the grad student's time may be). 2 is the need: the answer must split each line into Python vs. native. 1 and 6 are the constraints that rule out the obvious fix "just trace everything": tracing is slow and distorts. 3 rules out RSS as the memory fix and shows that accurate memory tools exist but are slow (6). 4 is the distractor: a tool-specific caveat, not the systematic problem. Phenomenon 5 must not be explained in stage 1; why the sampler is blind is the doorway to stage 2.

### Hint ladder
- L1: Start from phenomenon 2. What exactly does the grad student need to know about each line to decide whether rewriting it will help?
- L2: Sort the tools into cheap (about 1×) and accurate. Which cheap tool gives a right answer for a line that calls BLAS or runs in a thread? Which accurate tool is cheap?
- L3: Each failure falls on one of: time inside native code, time inside threads, memory allocated vs. touched, overhead and distortion. Can you state the problem as "per line, split time and memory into ___ vs. ___, at the cost of a ___ profiler"?
- Bottom-out: state the target below.

### Target
Python developers speed up code mainly by moving hot or memory-hungry pure-Python lines into native libraries. To choose those lines they need, per line, the time and memory spent in Python vs. in native code, including threads, on unmodified programs. Cheap timer-sampling profilers report zero time for native code and threads; tracing profilers are 1.7–37× slower and distort call-heavy code; memory profilers are either wrong (RSS) or 2.7–150× slower. The problem: get an accurate per-line Python/native split of CPU time and memory at about the overhead of sampling.
Checklist:
- [core] The decision the developer makes is Python vs. native, so total time per line is not enough.
- [core] Cheap samplers are blind to native code and child threads.
- [core] Tracing is ruled out by overhead and by distortion; accuracy must come at sampling cost.
- [core] Memory must be measured as allocations, not RSS, and also cheaply.
- [detail] Threads and long-running programs matter (log size, thread attribution).

### Common wrong turns
- "pprofile has a bug; use py-spy instead" → Suppose a sampler got total time per line right. Would the grad student then know whether a line is slow because of Python or because of the native call inside it?
- "Make tracing cheaper, write the callback in C" → cProfile already does that and is still 1.73× and function-level only. And does a faster callback remove the 25% → 80% distortion in phenomenon 1?
- "The problem is that profilers don't support Python; use VTune or perf" → Phenomenon 4 is one tool's caveat. Native profilers see C frames; does any of them tell you which Python line spent the time?
- "Just log RSS after every line" → Phenomenon 3.

## Stage 2: Derive the solution
### Seed hint
Every tool you used treats one of Python's quirks as an obstacle to work around. Find out exactly how the quirk behind phenomenon 5 behaves, and ask whether it carries information instead of only destroying it.

### Path
1. Learner may want to keep tracing but make it cheaper or more selective. Wall: phenomenon 6 and 1; per-call or per-line callbacks cost time and dilate the time of function calls. Ask: can you keep sampling and still see native time?
2. Learner may propose sampling stacks from outside the process (like py-spy or Austin). Wall: these tools are about 1× but, per the paper's comparison table, neither splits Python from native time. Ask: what does a sample need to know beyond "which line is on the stack"?
3. Learner asks why the timer sampler is blind (hint). Fact: CPython handles signals only in the main thread, and only once the interpreter loop regains control (it checks after some opcodes, such as jumps). A long native call holds the signal until it returns. Learner proposes: the signal is late by about the native time, so measure the gap. Wall: in wall-clock time, a late signal can also mean I/O or waiting. Ask: which clock removes that cause? (Virtual time: the only cause of delay left is native code.) Getting past it: charge q to Python and T−q to native on the current line.
4. Wall: child threads never get signals, and a main thread blocked in `join` gets none either. Ask: how do you force the main thread to wake, and how do you tell from outside what another thread is doing? Getting past it: replace blocking calls with versions that use short timeouts; at each signal, walk every thread's stack; a thread sitting on a call bytecode is in native code (Python code moves to the next bytecode almost at once); skip threads marked as sleeping.
5. Memory. Learner proposes recording every allocation, or reporting the peak like Fil. Walls: 4× (tracemalloc), 3.98× and 100 MB logs (Memray); and peak-only misses things: a program allocates and frees a 4 GB object, then allocates a 4 GB + 8 byte one; the peak report shows only the second, and deleting it would barely change the peak.
6. Learner proposes rate-based sampling, as in tcmalloc, Go or JFR (one sample per N bytes allocated). Wall: the interpreter creates and frees huge numbers of short-lived objects. Ask: which lines would collect the samples, and do those lines grow the footprint? Also: is the result the same from run to run? Getting past it: sample on the net change |allocs − frees| crossing a threshold (~10 MB, a prime to avoid stride effects); store a timestamp and footprint at each crossing, which also gives memory over time.
7. Wall: to split Python from native memory you must intercept both malloc and Python's allocator, but Python's allocator calls malloc. Ask: how do you avoid counting the same bytes twice? (A thread-local "inside allocator" flag; when set, just forward.)
8. Detail, if time allows: once samples fire at new peaks, how could you spot a leak cheaply? And Pandas `concat` that doubles memory: what would you count to catch hidden copies?

### Hint ladder
Idea 1 (signal delay measures native time):
- L1: In phenomenon 5 the timer did fire during `A @ B`. What happened to that tick?
- L2: If the handler runs late, by how much is it late, and what was the process doing in between?
- L3: Pick a clock under which "late" can have only one cause. What would you add to each line's Python counter and to its native counter?
- Bottom-out: with CPU-time signals of interval q, a handler that sees elapsed CPU time T charges q to Python and T−q to native for the current line.
Idea 1b (threads):
- L1: Which thread runs the handler, and what if it is blocked in `join`?
- L2: From the main thread, what can you see about another thread at the moment of the signal?
- Bottom-out: make blocking calls time out so the main thread wakes; inspect every thread's current bytecode; on a call bytecode it is native, else Python.
Idea 2 (sample by footprint change):
- L1: In a Python program, how many allocations are freed again almost at once?
- L2: Under per-byte sampling, which lines win the samples: the ones that allocate often, or the ones that make the program bigger?
- L3: What quantity should cross a line to trigger a sample, if you only care about the footprint?
- Bottom-out: sample when |allocs − frees| since the last sample crosses ~10 MB; intercept both allocators, guard against double counting, timestamp each sample.
Idea 3 (leaks, detail):
- L1: When the footprint reaches a new high, which object is a candidate leak?
- Bottom-out: track one sampled object per new peak; check it on each free with one pointer compare; estimate leak probability per site from (frees, mallocs) with Laplace's rule; report above 95% when memory keeps growing.

### Target
1. A timer signal is handled only when the interpreter regains control, so in CPU time its delay is the native time; charge q to Python and T−q to native. Threads are handled by waking the main thread with timeouts and reading each thread's current bytecode. Sampling cost, native time visible, no tracing distortion.
2. Memory is sampled on net footprint change, not bytes allocated, with both allocators intercepted. Few deterministic samples aimed at lines that grow memory, Python/native split, and a timeline instead of a peak.
3. Leaks are found by tracking one object per new peak (detail); copies by sampling memcpy (detail).
Checklist:
- [core] The blindness of signal sampling is turned into a measurement (delay = native time), and why virtual time is needed.
- [core] Thread attribution without signals in threads.
- [core] Sampling by net footprint change, and why rate-based sampling is biased in Python.
- [core] Python vs. native memory needs both allocators, without double counting.
- [detail] Memory over time instead of peak-only; leak detection; copy volume (rate-based is fine here since copies only add up); GPU read at each CPU sample.

## Stage 3: Design the experiments
### Summary to give
Problem: Python developers need a per-line split of CPU time and memory into Python vs. native code, at low overhead, and no profiler gives it. Method (Scalene): CPU sampling in virtual time, where the delay of each signal beyond the interval q is charged to native code; threads are handled by timeouts on blocking calls and a check of each thread's current bytecode. Memory: a shim on both malloc and Python's allocator, sampled whenever the net change in footprint crosses ~10 MB ("threshold-based sampling"), with timestamps for a memory timeline. On top: leak detection at new peaks, copy volume from memcpy, GPU utilization and memory.

### Key research questions
1. Is the CPU profile accurate where other tools are distorted? Accuracy is the whole point of rejecting tracing.
2. Is the memory profile accurate, compared with both RSS-based and allocation-based tools?
3. What does it cost? The claim is accuracy at sampling cost; a reviewer wants overhead on many programs and the worst case, with memory on and off.
4. Does sampling on footprint change actually cut samples and logs compared with rate-based sampling? This is the ablation for idea 2.

### Key experiments
1. CPU accuracy. Microbenchmark: two equivalent loops, one with a helper call, one inlined; vary the share of time in each; ground truth from high-resolution timers. Compare all CPU profilers. Result: trace-based profilers far off the diagonal (worst: 80% reported for 25% actual); Scalene close. Weak designs: no ground truth (comparing profilers to each other); testing only pure-Python code. Note the paper has no controlled test of the Python/native split itself; that is a probe below.
2. Memory accuracy. Allocate one 512 MB array, touch 0–100% of it. Result: Scalene and Fil within 1%, Memray within 6%, memory_profiler and Austin (RSS) wildly off. Weak designs: touching the whole array (RSS would look right); only one size.
3. Overhead. The ten longest pyperformance benchmarks, each looped past 10 s; interquartile mean of 10 runs; 8-core Ryzen 7, CPython 3.10.9. Result (median): Scalene CPU 1.02×, CPU+GPU 1.02×, full 1.32× (worst pprint 4.03×); Fil 2.71×, Memray 3.98×, memory_profiler 37.11×, pprofile det. 36.83×, py-spy 1.02×. Weak designs: reporting only the median (hides the 4.03× case); short runs where startup dominates; comparing a full-featured mode with CPU-only modes of other tools. Note: the overhead summary differs across sections (intro 0%/32%, §6.4 2%/30%, Table 3 1.02×/1.32×).
4. Sample counts. Same benchmarks, count rate-based vs. threshold samples. Result: 2× to 676× fewer (median 18×). Log size on mdp: Scalene 32K, Austin 27 MB, Memray almost 100 MB. Weak design: counting samples only, without showing that attribution is still right or that overhead drops because of it (the paper does not measure either directly).
Usefulness: external case studies (NumPy 125×, Pandas 18×, Rich 45%, groupby −1.6 GB, Semantic Scholar −92% cost). These are self-reported; the learner should see them as evidence of use, not controlled results.

### Reviewer probes
- How do you know the Python/native split is right? Design a test with a known native share (e.g. a C call of known length inside a Python loop).
- Leak detection is a contribution but has no evaluation. What would a precision/recall test look like?
- A 10 MB threshold: what happens for a program whose whole footprint is 5 MB, or one that leaks 1 MB an hour?
- The benchmarks are mostly pure Python. Where are the native-heavy and multi-threaded workloads the design is built for?
- GPU profiling is claimed but not evaluated. What is the minimum experiment?

## Stage 4: Apply and extend
### Scenarios
1. Native code that runs on many threads. Setup: the grad student's NumPy is linked to a BLAS that uses all 8 cores for `A @ B`. Question: the signal is late by the wall time of the call, but process CPU time grew by up to 8× that. What does the q / T−q rule report, and how would you fix it? Good directions: use per-thread CPU time for the main thread; report native time in core-seconds and say so; cross-check with wall time.
2. Move the insight. Question: find another system where a known "limitation" of a measurement channel encodes the quantity you want. Good directions: Perl and Ruby also defer signals, so the same trick applies; event-loop lag in Node.js or asyncio as a measure of blocking code; in the JVM, the opposite case: safepoint bias distorts samples, which AsyncProfiler avoids, so ask whether delay there carries information. A good answer names what causes the delay and why it is the only cause.
3. Churn as the problem. Setup: a service whose footprint is flat but which allocates and frees gigabytes per minute, and is slow. Question: what does sampling on footprint change show here, and what would you add? Good directions: it shows nothing, by design; keep a cheap allocation-rate counter per line beside the threshold samples; rely on the CPU profile to show the hot line, and the split to show it is in the allocator.
