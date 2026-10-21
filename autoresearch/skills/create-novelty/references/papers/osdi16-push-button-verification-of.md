# Push-Button Verification of File Systems via Crash Refinement
OSDI'16 · Helgi Sigurbjarnarson, James Bornholt, Emina Torlak, Xi Wang / University of Washington · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-sigurbjarnarson.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Define correctness as "every crash state of the implementation is allowed by the specification". A specification's crash behavior may be only one or two booleans, so SMT can prove it fully automatically.

## Problem
A file system must keep its on-disk structures consistent under crashes and disk write reordering.
Verified file systems all rely on interactive proofs. BilbyFs took 9.25 person-months and 13,000 lines of proof (1,350 lines of code) for two operations. FSCQ took 1.5 years, with 10 times the code of xv6.
The authors want push-button verification: no proofs, no annotations, and a counterexample when there is a bug.

## Strawman / Baseline
- **Interactive theorem proving (FSCQ, Cogent, Flashix)**: hand-written Coq/Isabelle proofs → effort as above. Coq takes 11 hours to check the FSCQ proof.
- **Automated bug finding (eXplode, FiSC)**: model-check crash points → the input is a whole disk, and the combinations of paths, crash points and write reorderings explode. It can only find bugs, not prove their absence.
- **Define correctness by bisimulation (both sides step together and states stay equivalent at all times), then hand it to a solver**: → the implementation has nondeterminism from crashes and write reordering, so it can never line up step by step with the specification. The definition is too strong.
- **Hand the whole file system's implementation and specification straight to SMT**: works for a toy LFS, but a journaling file system like xv6 (Yxv6) exceeds what the solver can do.

## Novelty
1. **The specification has very little nondeterminism, so "there exists an equal specification crash state" is cheap for SMT**
   Insight: The implementation can crash in many ways (whether each write reached disk, whether it was flushed). But the specification is usually just "a transaction is either fully done or not done at all", so its crash schedule is only one or two booleans.
   So: Define crash refinement: for any crash schedule of the implementation, there exists a specification crash schedule that makes the two results equivalent (if there is a recovery function, it must also be idempotent). When the solver looks for a counterexample, the implementation's schedule is just an ordinary unknown. The only "for all" falls on the specification's few booleans, which is a bounded range in a decidable theory (bit vectors + uninterpreted functions), and Z3 can solve it. A counterexample gives the crash point and the writes that did not reach disk directly.
   This avoids three root causes at once: bisimulation is too strong, interactive proof is too expensive, and bug-finding tools cannot be exhaustive.
2. **Crash refinement composes transitively, and "fewer states" is itself a refinement**
   Insight: If the implementation is a crash refinement of the specification, the layer above only needs to see the specification. Also, a variant with fewer crash states is naturally a refinement: partitions of one disk have fewer states than many disks (one flush flushes everything), and group commit has fewer intermediate states than one transaction per call.
   So: Yxv6 has 5 layers, each proven separately. First put the log, bitmaps, inodes and so on onto 7 separate "disks", so the solver sees at once that they do not interfere. Then prove that packing them into one disk, and adding group commit, are both refinements.
   This solves "handing the whole thing to SMT does not scale".

Other design: code must be bounded; finding a free bit verifies only a result checker; unlink only moves the inode into an orphan area, to be reclaimed by a GC proven to be a no-op; the optimizer that removes flushes is not trusted, and its output is verified again; Python is compiled to C via Cython and runs on FUSE.

## Evidence
- End to end: Yxv6 has a 250-line specification, a 1,500-line implementation, 5 consistency invariants, and not a single line of proof. Yxv6+sync verifies in under 1 minute on one core. The group commit version takes 1.6 hours on 24 cores (about 36 hours on one core). On SSD, the group commit version is 3–150× faster than FSCQ and on average within 10× of ext4's default configuration. It passes fsstress and SibylFS. Reproducing Arrakis's persistent log found 2 real bugs in it (recovery is not idempotent).
- Novelty 1 → toy LFS: the verifier found 2 bugs that testing missed within seconds; after the fix, the proof finished within 30 seconds. Removing one flush produced a concrete counterexample. The comparison with FSCQ is not on the same system.
- Novelty 2 → it only says that separating the logical and physical representations cut verification time by "several orders of magnitude", with no numbers: no direct ablation.
- Gaps: no mutation testing to show the verifier rejects wrong code. The trusted base includes the specification, Z3, Cython and FUSE (Z3 was cross-checked with 1,417 versions and two other solvers, with no disagreement found). The allocator guarantees only safety; it does not guarantee allocation succeeds when space is available.

## When it applies
Single-threaded; every operation must be expressible as bounded code, and the specification's crash semantics must be simple. If the specification itself has much nondeterminism or needs higher-order logic, you are back to the case the solver cannot handle.
