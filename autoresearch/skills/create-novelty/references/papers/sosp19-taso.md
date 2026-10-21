# TASO: Optimizing Deep Learning Computation with Automatic Generation of Graph Substitutions
SOSP'19 · Zhihao Jia, Oded Padon, Matei Zaharia, Alex Aiken et al. / Stanford University · Full text: https://cs.stanford.edu/~padon/taso-sosp19.pdf (Oded Padon home page, camera-ready) · Selected: Highly cited (394 citations)

**One sentence**: DNN operators are a small set of branch-free dense algebraic operations, so graph rewrite rules can be found automatically, as in superoptimization, by enumeration plus random testing, and then proven with algebraic axioms.

## Problem
DNN frameworks optimize computation graphs with graph substitutions (replacing a subgraph that matches some pattern with an equivalent, faster subgraph).
All these rules are written by hand by experts: TensorFlow r1.14 has 155 rules in about 53,000 lines of C++, and plain convolution alone has 17.
Each new operator (grouped convolution, depthwise convolution) needs a batch of rules to be rewritten, and hand-written rules have had bugs that rewrite the graph incorrectly.

## Strawman / Baseline
- **Greedy rules (TensorFlow, TensorRT, TVM)**: apply hand-written rules whenever they match → miss rewrites the experts did not think of. On ResNeXt-50, TF launches 32 small convolutions separately and TensorRT merges them into one grouped convolution; neither is the fastest.
- **MetaFlow**: allows substitutions that are temporarily slower and uses backtracking search → a larger search space, but the rules are still hand-written.
- **Do graph substitution first, then choose data layout separately (TVM, MKL-DNN)** → some substitutions only become faster with a specific layout; doing it in two steps misses them.
- **Borrow the verification from compiler superoptimization (bit blasting, encoding each bit as a Boolean variable)** → needs a known data bit width, but substitution rules hold for any tensor shape.

## Novelty
1. **The operator set is small and branch-free, so rules can be enumerated and random inputs can decide equivalence**
   Insight: equivalent subgraphs usually contain only a few operators. DNN operators are arithmetic-heavy and have no if, so two non-equivalent graphs almost never give the same output on random inputs.
   So: enumerate all graphs of up to 4 operators, compute a hash of the output (fingerprint) on random integer tensors, and run floating-point tests only on graphs with the same hash, which gives candidate rules. Then prune redundant rules that differ only by renaming or contain a common subgraph (28,744 → 743). A new operator only needs its implementation and properties, not hand-written rules. This directly answers the two root causes: maintenance and missed rewrites.
2. **Tensor shapes are unknown, but operators satisfy a few algebraic properties that can be proven in first-order logic**
   Insight: a rule is correct because of properties such as linearity, associativity, and concat commuting with convolution, which do not depend on the concrete shape.
   So: write 43 first-order axioms by hand and use Z3 to prove that each candidate rule follows from the axioms. The axioms themselves are checked by symbolic execution on small tensors of ≤4×4×4×4. This avoids bit blasting's need for a fixed bit width, and turns the correctness of hand-written rules into reviewing a few dozen axioms.
3. **Operator run time is predictable, so substitution and layout can be searched together**
   Insight: a branch-free dense operator has stable run time for a given layout and parameters, so measuring each operator and summing gives an estimate of the whole graph's cost.
   So: when applying a substitution, also enumerate the layouts (row-major/column-major) of the new intermediate tensors, inside MetaFlow's cost-based backtracking search. This fixes the missed combinations of step-by-step optimization.

## Evidence
- End to end (one V100, batch 1 inference): on par with existing frameworks on ResNet-50; on ResNeXt-50, NasNet-A, NasRNN and BERT, 1.3–2.8× faster than the best existing system (cuDNN backend) and 1.1–1.8× (TVM backend). Generating the 743 rules takes about 5 minutes; search per model <10 minutes; the specification is 1,400 lines.
- Novelty 1 → MetaFlow, with the same search plus hand-written rules, can serve as a control, but the gap also includes layout optimization. Raising the rule limit from 1 to 3 operators keeps improving speed; 4 operators only makes NasNet-A another 1.2× faster. Each model uses 4–10 kinds of rules, and two groups of rewrites for NasNet-A are in no framework.
- Novelty 2 → all 743 rules are proven in <10 minutes; checking the axioms is about 1 million proof obligations, about 1 hour on 128 cores. Development found several bugs in the generator and the axioms, but there is no mutation testing: no direct ablation.
- Novelty 3 → BERT only: joint 2.77 ms, substitution only 3.67, layout only 3.27, the two done one after the other 3.15; 1.2–1.3× faster.
- Gaps: inference only; the TVM backend reuses the graph chosen by cuDNN costs; the generator is limited by memory and cannot go beyond 4 operators.

## When it applies
Operators must be branch-free operations that a few algebraic axioms can describe, and good rewrites must stay within a few operators. If an axiom is wrong, the proof guarantee fails with it.
