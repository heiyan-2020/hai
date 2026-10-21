# Ansor: Generating High-Performance Tensor Programs for Deep Learning
OSDI'20 · Lianmin Zheng et al. / UC Berkeley, Alibaba, AWS · Full text: https://www.usenix.org/system/files/osdi20-zheng.pdf (USENIX camera-ready) · Selected: Highly cited (649 citations)

**One sentence**: A performance model is accurate only on complete programs, and good programs have only a few kinds of structure. So first enumerate structures, then sample complete programs and tune them with evolution.

## Problem
Each DNN operator needs a tensor program (the low-level loop implementation of the operator: how to tile, parallelize, vectorize, and unroll) on each kind of hardware.
Vendor libraries (cuDNN, MKL-DNN) are tuned by hand and cannot keep up with new operators and uncommon shapes. Search-based compilers search automatically from the mathematical definition, but there are billions of combinations, and measuring one needs a real compile and a real run.

## Strawman / Baseline
- **Template search (AutoTVM, FlexTensor)**: People write templates that fix the loop structure, and only parameters such as tile sizes are searched. → TVM's templates already exceed 15K lines, and must be written for each operator and each kind of hardware. Structures outside the templates (such as splitting a reduction loop, or fusion across operators) cannot be searched at all.
- **Step-by-step construction + beam search (Halide auto-scheduler)**: Make decisions one step at a time. At each step, a learned cost model (a performance predictor trained on measured data) keeps only the top-k partial programs. → The cost model can only be trained on complete programs, so on partial programs it nearly guesses: with only half the transformations done, pairwise comparison accuracy is close to the random 50%, and top-10 recall is close to 0 (read from the figure). Good programs get pruned early.
- **Tune the subgraphs of a whole network one by one (AutoTVM)**: Every subgraph gets the same number of measurements. → Budget is wasted on subgraphs that are not bottlenecks or cannot be tuned further.

## Novelty
1. **Structure choices are few and parameter choices are huge, so handle the two levels separately**
   Insight: A good structure for dense operators is decided by a few properties that can be judged statically: is there data reuse, is it an element-wise operator, is there enough parallelism in the spatial dimensions. What is truly huge in number are low-level parameters such as tile sizes, parallelization, and unrolling.
   So: Use a few derivation rules (multi-level tiling when there is much reuse, inlining for element-wise, fusion when the consumer can be fused, splitting the reduction when parallelism is not enough) to enumerate structural sketches automatically, usually fewer than 10 per subgraph. Then sample parameters uniformly at random to get complete programs. Every point in the space can be sampled, and no template is needed. This solves the problem that templates can never all be written and never cover everything.
2. **Compare only complete programs, never evaluate partial ones**
   Insight: The cost model is accurate on complete programs (R² 0.958, pairwise comparison accuracy 0.851) and inaccurate on partial ones, so pruning must wait until programs are complete.
   So: Start evolutionary search from sampled complete programs. Mutations change tiling (the product across levels stays the same, so the program stays valid), parallel granularity, pragmas, and compute location. Crossover combines the rewrite steps of two programs by DAG node. Each round, only the few programs chosen by the cost model are measured, and the results retrain the model. This avoids the root cause of beam search, which ranks partial programs.
3. **Whole-network latency is a weighted sum of subgraph latencies, so the budget is given by marginal gain**
   Insight: Subgraphs differ a lot in their contribution to whole-network latency and in how much room they have to improve. So: Each round, estimate "how much the objective drops if a subgraph gets one more round" (from its recent rate of decrease and the FLOPS reached by similar subgraphs). Give the next round to the subgraph with the largest gain, and keep probability ε for random exploration. This removes the waste of an even budget split.

Other design: reorder the layout of constant weights to match multi-level tiling (about 40% on ResNet-50).

## Evidence
- End to end (Intel 18 cores, V100, Cortex-A53; ResNet-50, MobileNet-V2, 3D-ResNet, DCGAN, BERT): Up to 3.8×, 1.7×, 2.6× faster than the best competitor respectively; 1.0–21.8× faster than AutoTVM. On 80 single-operator cases it is 1.1–22.5× faster than other search frameworks, and 1.1–14.2× on subgraphs. To reach AutoTVM's performance it needs 2.7–16.5× fewer measurements and 3.3–88.6× less wall-clock time.
- Novelty 1 → "Limited space" (limiting the space to the templates' range): on the last convolution of ResNet-50 it reaches only about 0.56 of the best (read from the figure). On whole networks it never catches up with AutoTVM.
- Novelty 2 → Same convolution: beam search pruning partial programs reaches about 0.87; random sampling only, without tuning, about 0.74 (read from the figure).
- Novelty 3 → Without the scheduler (round-robin allocation): MobileNet-V2 ends at about 1.57× vs 1.62× (relative to AutoTVM, read from the figure). The main difference is convergence speed.
- Gaps: Ablations are done on only one convolution and two networks. End-to-end comparisons with libraries mix in the gain from weight layout reordering. The CPU model labeled in Figure 6 (20-core 8269CY) does not match the text (18-core 8124M).

## When it applies
Needs static shapes and dense operators. When a good structure needs special tiling (Winograd, Tensor Core instructions), the derivation rules do not cover it, and users must add rules themselves.
