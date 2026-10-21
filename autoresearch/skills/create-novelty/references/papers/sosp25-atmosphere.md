# Atmosphere: Practical Verified Kernels with Rust and Verus
SOSP'25 · Xiangdong Chen, Zhaofeng Li, Jerry Zhang, Vikram Narayanan, Anton Burtsev / University of Utah · Full text: https://mars-research.github.io/doc/2025-sosp-atmo.pdf (research group home page, camera-ready) · Selected: Best Paper

**One sentence**: What SMT finds hard to prove is recursion, and recursion comes from layer upon layer of nested ownership; flatten each subsystem's object permissions into one table, and the kernel invariants all become first-order.

## Problem
The goal is to verify a fully functional microkernel with the SMT-based automatic verifier Verus: it has a process tree, a container tree, linked lists and multi-level page tables, and must be proven to refine an abstract specification, with non-interference between containers.
Kernel state is made of unbounded recursive pointer structures, but SMT does not support induction and can only unroll recursion a finite number of levels.

## Strawman / Baseline
- **Interactive theorem proving (seL4, CertiKOS)**: proof-to-code ratios of 20:1 and 14.9:1; the seL4 proof alone took 11 person-years.
- **Push-button SMT (Hyperkernel)**: to be fully automatic, every kernel path must be bounded; for example, open needs the user to specify the fd. One verification run takes about 30 minutes.
- **Verus + Rust's usual hierarchical ownership (NrOS page table)**: the parent holds the children's permissions, so the specification is recursive and needs manual unrolling or induction. Proving "mapping one page leaves other addresses unchanged" takes about 200 lines, and the proof-to-code ratio is 13.3:1.
- **After flattening, every operation carries all the structural invariants**: mmap only changes a quota, but SMT must still face the whole tree's invariants (acyclicity, back pointers, etc.) again, and the search space blows up.
- **Rely on Rust's automatic memory management**: cyclic structures need trusted unsafe smart pointers. The deeper problem is that the specification cannot see global memory. So the specifications of memory-related syscalls are nondeterministic, and neither leak freedom nor "one container cannot exhaust another's memory" can be proven.

## Novelty
1. **Flatten permissions, and recursive invariants become universal quantification over one table**
   Insight: recursive specifications come from "a child can only be reached through its parent". If the top level of a subsystem holds the Verus linear permissions (ghost tokens for "may access this pointer") of all its objects in one map, any node can be named directly.
   So: objects link to each other with C-style raw pointers (back pointers, intrusive lists), and each node carries a ghost root path (path) and subtree set (subtree). "The tree structure is correct" can be written as: for every node and every depth d, the prefix of path equals the path of the d-th ancestor. There is no induction anywhere; in the non-interference proof, sets such as "all threads of container A" can also be written directly.
2. **Structural invariants hide behind closed specifications and are proven separately from business changes**
   Insight: most syscalls (e.g. mmap changing a quota) do not change the tree's shape, yet would have to re-verify all structural invariants.
   So: structural invariants are written as closed functions visible only within their module. Each operation only describes how the state changes, and one lemma proves that "such a change keeps the tree well-formed". Other modules cannot see the structural invariants, so the SMT search space shrinks.
3. **Give up automatic memory management in exchange for a provable global view of memory**
   Insight: leak freedom and non-interference are both statements about "all memory". As long as the allocator state is explicitly visible, the pages each object uses can also be summed up layer by layer.
   So: kernel objects are allocated by hand in pages, and the allocator exposes four page sets: free, allocated, mapped and merged. Each object maintains a page_closure (the set of pages used by it and the objects it owns); a subsystem only proves pairwise disjointness locally and then takes the union. This avoids proving pairwise disjointness of all objects globally. On this basis, non-interference between containers is proven by unwinding conditions.

## Evidence
- End to end: 6K lines of executable code, 20.1K lines of proof (14.3K of specification), proof-to-code ratio 3.32:1. Total effort about 2.5 person-years, of which verification took 1.5 person-years. Full verification takes 1 min 7 s on 8 threads and under 20 s on a laptop; VeriSMo needs 12 min 11 s. IPC takes 1058 cycles, seL4 1026; Maglev reaches 13.3 Mpps, DPDK 9.72 Mpps; NVMe writes are 10% slower than SPDK.
- Novelty 1 → page table vs. NrOS: proof-to-code ratio 4.4:1 vs. 13.3:1; the proof of "other mappings unchanged" is 30 lines vs. about 200; single-threaded verification is 3× faster. But the control is another project's code, not the same code with flattening removed.
- Novelty 2, 3 → no direct ablation.
- Gaps: no mutation testing or bug comparison to show specification strength. The kernel runs under one big lock; only the consistency of step-by-step page table updates is additionally proven. Trusted code is about 3K lines of Rust and 172 lines of assembly, plus about 700 lines of unproven axioms. Non-interference is proven for only one three-container configuration and does not cover timing channels.

## When it applies
Needs each subsystem to own all its objects exclusively and to modify them serially under a big lock; fine-grained concurrency would break the global permission table. Fine-grained resource revocation is not supported; this is a choice made to simplify the proofs.
