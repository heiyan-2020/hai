# DistAI: Data-Driven Automated Invariant Learning for Distributed Protocols
OSDI'21 · Jianan Yao, Runzhou Tao, Ronghui Gu, Jason Nieh, Suman Jana, Gabriel Ryan / Columbia University · Full text: https://www.usenix.org/system/files/osdi21-yao.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Invariants of human-designed protocols are short; if you start from the strongest short formulas that fit simulation data, a failure only ever needs monotone weakening, so the search is guaranteed to converge.

## Problem
Proving a protocol safe requires an inductive invariant (a formula that holds initially, still holds after any action, and implies the safety property). The safety property itself is almost never inductive, so a person must add several auxiliary invariants.
IVy can check invariants with SMT and point out which ones fail, but a person must guess the invariants, which takes a long time even for simple protocols.

## Strawman / Baseline
- **I4**: Model-check a small instance, generalize the resulting invariant to any size, then give it to IVy to check; delete invariants that fail, and if that does not work, try a larger instance. → One instance may not represent all sizes (for example, when behavior depends on whether the node count is odd or even); the generalization can fail (decentralized lock, asynchronous lock server); and a person must add constraints by hand to shrink the state space.
- **FOL-IC3**: Calls an SMT solver repeatedly to build a formula that separates reachable states from bad states. → SMT calls are many and expensive, and the generated formulas may fall into undecidable fragments, so Z3 returns unknown.
- **Enumerate all formulas up to a bounded size and check each with SMT**: Even at modest sizes there are too many candidates to check.
- **How to fix a candidate invariant that SMT refutes**: There is no way to tell whether to strengthen or weaken it. Deleting it (what I4 does) also throws away its correct "weaker versions", so completeness is lost.

## Novelty
1. **Invariants are short and independent of size, so search the formula space and filter with simulation data instead of SMT**
   Insight: Protocols are designed and understood by people. Their invariants usually involve only two or three universally quantified variables and two or three literals (a predicate or its negation), such as "any node committed ⇒ any node voted yes". They do not depend on the node count.
   So: Fix the formula size (number of quantified variables, number of literals), not the instance size. Run random actions on several instances of random size, and project each state onto the values of k variables (a subsample). Keep only candidate formulas that hold on all subsamples; use SMT only for the final check.
   This neither depends on generalizing from one instance (I4's root cause) nor lets SMT generate formulas (FOL-IC3's root cause).
2. **Start from "the strongest formulas consistent with the data", so a failure can only need weakening**
   Insight: A true auxiliary invariant holds on all reachable states, so it also holds on all sampled data. If the candidate set contains all of the "strongest" short formulas consistent with the data (skipping those implied by shorter formulas), it must imply any correct invariant of the same size.
   So: When IVy refutes a candidate, it only needs a minimal weakening (add one more literal, or generalize to one more variable); it never needs strengthening. The candidate space shrinks strictly and monotonically and converges in a finite number of rounds; if that is not enough, increase the formula size. The authors prove: if an inductive invariant without ∃ exists, it will be found.
   Incomplete sampling only costs a few extra rounds. This answers "strengthen or weaken" and avoids the incompleteness caused by deletion.

Other design: Split templates by whether variables are equal/ordered, and use symmetry to cut the number of literals needed (chain replication from 6 to 4); treat sub-protocols as black boxes and pick random states that satisfy their postconditions.

## Evidence
- End to end: 14 protocols (including all 7 used by I4), with a one-week limit each. DistAI solved 13, I4 solved 9, FOL-IC3 solved 3 by default (9 when limited to pure ∀). DistAI finished each in under 1 minute (longest 58.8 s), up to an order of magnitude faster than I4 and two orders faster than FOL-IC3. Example, distributed lock: 12.6 s, I4 total 204.7 s, FOL-IC3 (∀) 1451.3 s.
- Novelty 1 → All solved protocols use at most 2–4 literals, which supports "invariants are short". On simple consensus: with too few samples (100), SMT refinement is very slow; with more samples, sampling time grows roughly linearly and refinement time falls roughly exponentially. No baseline of "no sampling, direct enumeration + SMT".
- Novelty 2 → A theorem proves completeness. In practice, 5 simple protocols needed no refinement, and the rest needed 2–158 refinements. Comparison with "delete failed candidates": no direct ablation.
- Gaps: ∃ is not supported, so Paxos fails (I4 also fails). On learning switch it is slower than I4 (27.6 s vs 12.4 s). I4's time excludes the manual constraint work. Parameter changes (MA 25–100, SD 2–5) only turn knobs: it still solves 13, at worst 3× slower.

## When it applies
Requires an inductive invariant without ∃ that is short enough. When ∃ is needed or the invariant is long, the enumeration does not converge. When action parameters are sparse, random simulation sampling is slow.
