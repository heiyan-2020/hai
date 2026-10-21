# REPT: Reverse Debugging of Failures in Deployed Software
OSDI'18 · Weidong Cui, Xinyang Ge et al. / Microsoft Research, U Michigan, ASU, Georgia Tech · Full text: https://www.usenix.org/system/files/osdi18-cui.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Given the exact execution path and the final state at the crash, most intermediate data values can be inferred by working forward and backward. A wrongly inferred value will sooner or later contradict the final state.

## Problem
When deployed software crashes, developers usually get only a memory dump (a snapshot of process memory at the crash). They cannot see what happened before the crash, so many bugs cannot be fixed.
Reverse debugging (stepping back and forth in the execution history and inspecting variables) is the most useful, but production systems cannot afford to record the full execution.

## Strawman / Baseline
- **Record/replay (DoublePlay, Castor)**: Record all nondeterministic inputs online. → Overhead up to 200% with multiple cores and threads. Castor is efficient only for programs without data races.
- **Backward execution from the dump alone (RETracer, deployed in WER)**: No control flow, so few values are recovered. It can only triage memory access violations.
- **Symbolic execution (ESD, Better Bug Reporting)**: Treats every register and memory cell as a variable and builds constraints. → When the execution is long, the constraints become too large to solve.
- **Control flow trace + dump, with hypothesis testing for each write to an unknown address (POMP)**: Every possible alias must be forked and checked. The number of hypotheses grows exponentially with trace length, and only single-threaded programs are supported.
- **Naive approach**: When a write's target address is unknown, either mark all memory unknown (losing many recoverable values) or ignore the write (the old value stays and the error keeps spreading).

## Novelty
1. **Control flow + final state are enough to recover most data values**
   Insight: Intel PT (hardware control flow tracing in the CPU) records only recent execution in a ring buffer, with overhead below 2%. Once the path is fixed, the semantics of each instruction is a known constraint. A reversible instruction lets the earlier state be inferred from the later state. An overwritten value (such as xor rax,rax) can often be recomputed forward from its source operands.
   So: Start from the dump and repeat backward inference and forward execution on concrete values until a fixed point. No solver is used. This avoids the constraint explosion of symbolic execution and needs none of the online overhead of record/replay.
2. **Use suspect values optimistically and fix errors through contradictions, instead of enumerating aliases in advance**
   Insight: Errors in inference have only one source: a write to an unknown address leaves an old value in memory. The final state is ground truth, so an old value will sooner or later conflict with other inferred results.
   So: Use possibly valid values as usual. At the same time, record which values each value was inferred from (a data inference graph), and how many pointer dereferences separate it from the original value in the dump (more dereferences mean lower confidence). On a conflict, invalidate the side with lower confidence and all values inferred from it. To guarantee convergence, an invalidated value goes onto that node's blacklist.
   This replaces POMP's exponential hypothesis testing. Analysis time grows linearly with trace length.
3. **Under concurrency, only the order of "writes to the same address" affects data recovery**
   Insight: PT timestamps give a partial order between threads. The only order that cannot be decided and also affects the result is concurrent writes to the same address.
   So: Put all other instructions into one sequence in any order. For a memory access that is concurrent with some write, cut its propagation along the def-use chain and let it take part in inference only within the same instruction. This needs neither a total order nor the assumption that the program is race-free.

## Evidence
- End to end: 16 real bugs (Apache, PHP, Python, Chrome, etc.), with TTD (exact but very slow record/replay) as ground truth. On average 92% of values are recovered correctly. 14 bugs can be debugged effectively (all variables relevant to the fix are recovered correctly). Analysis of each bug takes under 20 seconds. It has shipped with Windows to hundreds of millions of machines. An Edge bug left unfixed for two years was fixed with it in a few minutes.
- Novelty 1 → Single-threaded: most bugs have accuracy >90% within tens of thousands of instructions, with error rate ≤3.05%. The worst, PHP-2012-2386, has only 71.55% (many memory allocations overwrite metadata). As the trace grows from 10K to 1M instructions, accuracy drops.
- Novelty 2 → Compared with POMP on 3 shared bugs, it is 1–3 orders of magnitude faster (PuTTY: 30 minutes vs 5.2 seconds). Accuracy of error correction versus "mark all unknown / ignore the write": no direct ablation.
- Novelty 3 → Pbzip2 accuracy is 95.33%, Python-31530 is 75.72% (510,000 instructions). On Racey, which has extreme contention, only 5.5% of accesses have concurrent writes. Removing the concurrency handling: no direct ablation.
- Gaps: Multithreaded timestamps are simulated with a modified TTD, not real PT. Runtime overhead quotes the number from prior work (<2%), and this paper does not measure it. It cannot handle JIT code modified in place, or an infinite loop that flushes the buffer.

## When it applies
The defect must fall within the recent execution covered by the ring buffer, and that execution must not be dominated by operations that overwrite a lot of metadata (such as dense allocation). It needs hardware control flow tracing, which mobile devices did not have at the time.
