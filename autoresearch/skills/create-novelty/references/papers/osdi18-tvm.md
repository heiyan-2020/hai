# TVM: An Automated End-to-End Optimizing Compiler for Deep Learning
OSDI'18 · Tianqi Chen, Thierry Moreau et al. / University of Washington, AWS, Shanghai Jiao Tong University · Full text: https://www.usenix.org/system/files/osdi18-chen.pdf (USENIX camera-ready) · Selected: Highly cited (357 citations)

**One sentence**: Hand-written operator libraries explode with the combinations of "fusion pattern × layout × hardware". Instead, generate the operators, turn hardware differences into schedule primitives, and pick implementations with a model that learns while it searches.

## Problem
DL models must be deployed to server GPUs, mobile GPUs, embedded CPUs, and FPGA/ASIC accelerators. Frameworks hand each operator to a vendor library (cuDNN, ARM Compute Library, etc.). New hardware and new operators (depthwise conv, low-bit) all need someone to hand-write them, and this cannot keep up.

## Strawman / Baseline
- **Framework + vendor library**: New operators produced by graph optimizations (such as operator fusion) must already have an implementation in the library. → The number of implementations grows with the combinations of fusion pattern × data layout × data type × hardware instruction. The framework can only pick one: do not fuse, or use an unoptimized implementation. cuDNN is poorly optimized for uncommon shapes (DQN's 4×4, stride 2 convolution).
- **Halide-style separation of compute and schedule**: The operator is written as a mathematical definition, and the schedule (a sequence of transformations such as tiling and parallelization) is given separately. → Covers only CPU/GPU. It cannot express data sharing among GPU thread groups, or accelerators' tensor instructions and on-chip buffers. DAE accelerators (memory access and compute are two pipelines, synchronized by dependency tokens inserted in software) need fine-grained synchronization written by hand.
- **Black-box auto-tuning (Tensor Comprehensions, etc.)**: Pick configurations with random or genetic algorithms and measure each one. → Each measurement takes seconds, and many are needed.
- **Predefined cost model**: Model hardware performance by hand. → Modern hardware is too complex, so the model is inaccurate, and it must be rebuilt for each kind of hardware.

## Novelty
1. **Generate every operator, and graph-level optimization is no longer limited by the library**
   Insight: The combinatorial explosion of libraries comes from "every implementation is written by a person". If any operator (including fused ones) can be generated automatically from a tensor expression, fusion and layout changes no longer need library support.
   So: Define general fusion rules by category (element-wise, reduction, fusable into its output such as conv2d, not fusable such as sort), and hand the fused result to code generation. This solves the root cause of the first baseline.
2. **Hardware differences come down to a few kinds of schedule transformations**
   Insight: CPUs, GPUs, and accelerators differ mainly in three places: memory hierarchy (shared memory, on-chip buffers), compute primitives (scalar, vector, tensor instructions), and who is responsible for hiding memory latency. An accelerator's tensor instruction is itself a small tensor computation.
   So: Add three schedule primitives. Memory scope marks data placed in shared/on-chip buffers. Tensorize declares a hardware instruction's semantics in the same expression language and replaces code by pattern matching, so new hardware only needs to declare its instructions. Virtual thread lets people write code as if it were multithreaded; the compiler inserts dependency tokens automatically and generates a single instruction stream. This fills the gap of Halide-style schedules on accelerators.
3. **Measurement must happen anyway, so use it to train a cost model**
   Insight: Search needs only the relative speed between configurations, not absolute latency. The measured data from the search is exactly the training data.
   So: Use XGBoost to train a ranking model on loop program features (memory access volume, reuse ratio, annotations). One prediction takes 0.67 ms, thousands of times faster than measurement. Simulated annealing picks a batch of configurations on the model to measure, then retrains on the results. This needs no hardware knowledge and does not rely fully on measurement.

Other design: an RPC device pool that automates cross-compilation, deployment, and measurement.

## Evidence
- End to end: On Titan X it is 1.6–3.8× faster than MXNet, TensorFlow, and TF XLA (the maximum is on DQN). On Mali T860 it is 1.2–1.6× faster than ARM Compute Library. On ARM A53 it is faster than TFLite on all 3 networks. On VDLA, an FPGA accelerator the authors built, offloaded convolution layers are 40× faster than on Cortex-A9.
- Novelty 1 → Fusion vs no fusion: 1.2–2× for single operators. On Titan X, MobileNet takes about 2.3 ms without graph optimization and about 1.0 ms with it (read from the figure).
- Novelty 2 → Without cooperative shared memory, a 2048 matrix multiply takes about 8.2 ms; with it, about 3.6 ms (read from the figure). Latency hiding raises peak compute utilization from 70% to 88%. Low-bit micro-kernels are 1.5× faster after tensorize.
- Novelty 3 → One conv2d of ResNet-18 (Titan X): the ML model reaches about 1.6× cuDNN in about 300 measurements; the genetic algorithm reaches about 1.4× in 800, and random search about 1.1× (read from the figure).
- Gaps: The schedule space still needs developers to write templates declaring tunable parameters, and this human effort is not quantified. The cost model is compared on only one operator, and not against a predefined cost model. FPGA end to end is limited by the layers that stay on the CPU.

## When it applies
Needs static shapes (each shape is searched and generated separately), and operators that can be written as tensor expressions in dense loop form. New hardware needs someone to declare its instruction semantics and runtime API (the VDLA backend is about 2k lines of Python).
