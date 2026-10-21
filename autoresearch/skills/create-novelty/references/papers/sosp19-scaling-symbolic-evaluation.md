# Scaling symbolic evaluation for automated verification of systems code with Serval
SOSP'19 · Luke Nelson, James Bornholt, Ronghui Gu, Andrew Baumann, Emina Torlak, Xi Wang / UW, Columbia, MSR · Full text: https://unsat.cs.washington.edu/papers/nelson-serval.pdf (author homepage version, with ACM copyright page and DOI, matching the camera-ready) · Selected: Best Paper

**One sentence**: An instruction-set interpreter run on symbolic input is a verifier. Path explosion comes from a few patterns that lose domain knowledge, and that knowledge can be added back one pattern at a time.

## Problem
Push-button verification (Hyperkernel, Nickel) requires a finite system interface (no system call has an unbounded loop). It then uses symbolic evaluation to reduce the agreement between implementation and specification to SMT queries, with no hand-written proofs.
But each verifier must be hand-written from scratch, and when symbolically evaluating real binaries, path explosion keeps verification from finishing.

## Strawman / Baseline
- **Interactive proofs (seL4, CertiKOS)**: seL4 took 11 person-years with a proof-to-code ratio of 20:1; CertiKOS's specs and proofs are about 200,000 lines.
- **Auto-active verification (Ironclad, Komodo)**: needs annotations such as pre- and postconditions, and verification performance problems are hard to debug; Vale supports only structured assembly.
- **Existing push-button verifiers**: generate SMT constraints directly in Python; each LLVM verifier is about 3000 lines. → Hard to reuse, optimize and port; they support only LLVM and cannot verify assembly such as context switching and boot code.
- **Naively use an interpreter for symbolic evaluation**: states merge where control flow joins, so pc becomes a symbolic value, and every instruction fetch must consider all instructions. Pointer arithmetic loses "which field this is", so constraints grow with the square of the number of fields. Dispatching on the system call number produces one huge combined constraint. → The refinement proofs of both security monitors time out (2 hours).

## Novelty
1. **An interpreter plus symbolic evaluation is a verifier**
   Insight: For systems with a finite interface, verification needs only "the semantics on all paths". Run an ordinary instruction-set interpreter on symbolic state, and Rosette (a Racket extension that supports symbolic evaluation) automatically turns it into constraints over all paths.
   So: Developers write only interpreters and get four verifiers, for RISC-V, x86-32, LLVM and BPF. They share a memory model and a spec library, and verify binaries produced by gcc directly. This replaces hand-written SMT-encoding verifiers one by one, and brings assembly and boot code into verification.
2. **Path explosion comes from a few recognizable patterns, which can be fixed during evaluation with domain knowledge**
   Insight: Explosion points cluster in a few recurring places: a merged symbolic pc, struct offsets of the form (C0×pid+C1) mod C0, system registers that never change after boot, and trap dispatch on the call number. This information exists at the source level but is lost at the lower level, and the solver has no way to know it.
   So: Use a symbolic profiler (ranking functions by statistics such as path splits and state merges) to locate bottlenecks, then add the knowledge back with reusable "symbolic optimizations": split on concrete values of pc; optimistically rewrite the offset to C1 and generate an equivalence side condition for the solver to check; concretize system registers using representation invariants; split on the call number. Every rewrite carries a side condition, so it is sound.
   This removes the divergence of naive evaluation.

## Evidence
- End to end: CertiKOS (x86, verified in Coq) and Komodo (ARM, verified in Dafny) were ported to RISC-V, and functional correctness and noninterference were proven on the binaries, about 4 person-weeks each. Refinement proofs take 92–138 s (CertiKOS) and 275–309 s (Komodo). 18 new bugs were found in Keystone and the Linux BPF JIT (15 in the BPF JIT), all confirmed and fixed.
- Novelty 1 → the framework is 1,244 lines, and the four verifiers total 3,153 lines of Rosette (RISC-V 1,036 lines), while one existing LLVM verifier is about 3000 lines of Python. Only line counts were compared; development effort was not measured.
- Novelty 2 → with symbolic optimizations off, the refinement proofs of both systems time out (2 hours) at every gcc optimization level. Optimizations developed on CertiKOS were directly enough for Komodo (-O0). -O1/-O2 were 5× slower; after adding one new optimization (less than a day), they came close to -O0. No per-optimization ablation.
- Gaps: The ports reused the original systems' designs and specs, so 4 person-weeks cannot be compared directly with the original effort. The noninterference proven differs from the original systems', so their strength cannot be compared directly. The verifiers themselves (instruction-set semantics) are in the trusted base and are checked only by testing. The BPF JIT was translated into Rosette by hand. Concurrency and side channels are not supported.

## When it applies
The system interface must be finite (no unbounded loops), and properties must be expressible in a decidable fragment of first-order logic. Properties that need unbounded traces (such as big-step noninterference) and multi-core concurrent code are out of scope.
