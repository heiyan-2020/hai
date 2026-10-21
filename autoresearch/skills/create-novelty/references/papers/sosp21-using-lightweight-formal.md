# Using Lightweight Formal Methods to Validate a Key-Value Storage Node in Amazon S3
SOSP'21 · James Bornholt et al. / Amazon Web Services, UT Austin · Full text: https://www.cs.utexas.edu/~bornholt/papers/shardstore-sosp21.pdf (author home page, camera-ready) · Selected: Best Paper

**One sentence**: If the specification is a simple implementation in the same language that also serves as a mock, engineers will keep maintaining it; which data must survive a crash is decided by the write-order dependencies the implementation records itself.

## Problem
ShardStore is S3's new storage node: 44,000 lines of Rust. It ensures crash consistency with soft updates (writing to disk in dependency order, with no log), has high concurrency, has code and specification that change often, and already stores hundreds of PB of data.
The team wanted to check deep properties (API functional correctness, crash consistency, concurrency correctness), and wanted these checks to stay useful after the formal methods experts leave.

## Strawman / Baseline
- **Full formal verification (FSCQ, Yggdrasil, VeriBetrKV)**: strong guarantees → proof code is 3–10 times the implementation (VeriBetrKV has 7 lines of proof per line of implementation); not feasible at this scale and rate of change.
- **Write the specification in a modeling language (Alloy, SPIN, P)**: the authors did this at first → the model and the Rust code are two separate things; engineers will not maintain the model, and it soon drifts from the code.
- **Ordinary unit/integration tests**: already 31% of the code → they only check the scenarios written down and miss deep bugs such as crash consistency and concurrent interleavings.
- **Require the implementation and model state to be equal after each call**: works when sequential and crash-free → a crash may legally lose recent writes, and under concurrency operations overlap and there is no moment between calls to compare; the check is too strict.
- **Exhaustive block-level crash states (BOB, CrashMonkey)** → tries every subset of writebacks; much slower.
- **Check end-to-end tests with Loom (a model checker that exhausts all thread interleavings)**: one small test has tens of thousands of atomic steps, and large ones exceed 1 million → state explosion.

## Novelty
1. **Specification = a simple implementation in the same language, which doubles as a mock**
   Insight: formal specifications go stale because only experts touch them. A unit-test mock, by contrast, is something engineers must update whenever they change the code.
   So: for each component, write a reference model in Rust with the same interface (the model of the LSM tree is a hash map), and use it as the mock too. Check with property-based testing: generate random operation sequences, feed them to both the implementation and the model, and compare outputs and key-value mappings step by step. No proofs need to be written.
2. **What should survive a crash, the implementation already says**
   Insight: a soft updates implementation already has to build a write-order dependency graph (Dependency) at run time and can answer whether an operation "is persistent". That is a ready-made specification.
   So: add "dirty reboots" to operation sequences. After reboot, check that data the dependencies say is persistent can be read, and that after a clean shutdown all dependencies are persistent. Crash states are chosen only coarsely, per component, by whether it flushes; flushes of each component are interleaved into the sequence to produce partially flushed states, so block-level crash states need not be enumerated.
3. **The hard parts of concurrency are overlapping operations and the explosion of interleavings, so change the criterion and pick tools by scale**
   Insight: under concurrency there is no "between calls" to compare, but one can ask whether the result equals some serial execution; exhausting interleavings is only feasible on small code.
   So: check linearizability instead (the concurrent result equals some serial execution consistent with real-time order), against the same model. Custom concurrency primitives are checked exhaustively with Loom; end-to-end tests use the in-house Shuttle, which samples interleavings with PCT (random thread priorities, switching at a few random points). The paper does not argue why random sampling is enough; the guarantee from the original PCT paper is that a bug triggered by only a few specific orderings is found with a bounded-below probability.

Other design: argument biasing, coverage monitoring, deterministic design so failing sequences shrink automatically (61 steps to 6), IO fault injection, Miri, Crux.

## Evidence
- End to end: caught 16 issues that would have reached production (5 functional, 5 crash consistency, 6 concurrency); tens of millions of random sequences run before each deployment.
- Novelty 1 → cost: the model is 450 lines (1% of the implementation); all validation code is 20% of the implementation (formal verification: 3–10×). Two experts worked full time for 9 months to start it; afterwards, 18% of the harness code was last changed by engineers with no formal methods background, and 4 people wrote their own model-checking harnesses. Maintenance cost was not compared with a modeling-language approach: no direct ablation.
- Novelty 2 → #10 needs three things at once: the UUID's last byte equals the magic, a chunk crosses a page exactly, and the crash loses only the second page; it was found locally before review. The exhaustive block-level variant found no more bugs and was much slower.
- Novelty 3 → #14, a race between reclamation and compaction that loses the index, was found by Loom. Shuttle's coverage and misses are not quantified: no direct ablation.
- Gaps: one known miss (the test cache was too large, so the miss path was never reached), found by manual review; "concurrency + crash" and resource exhaustion were not checked; no comparison with ordinary testing on the same set of bugs.

## When it applies
The component must be describable by a much simpler sequential model, the implementation must expose its persistence promises, and execution must be deterministic. The result is a testing-level guarantee, not a proof.
