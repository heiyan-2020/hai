# PowerInfer: Fast Large Language Model Serving with a Consumer-grade GPU
SOSP'24 · Yixin Song, Zeyu Mi, Haotong Xie, Haibo Chen / Shanghai Jiao Tong University IPADS · Full text: https://arxiv.org/abs/2312.12456v2 (arXiv v2, SOSP'24 ACM-formatted final version) · Selected: Highly cited (383 citations)

**One sentence**: A few neurons are often activated under any input, so keep these hot neurons resident on the GPU and compute the cold neurons in place on the CPU.

## Problem
Running an LLM locally on a PC with a single consumer GPU (RTX 4090, 24 GB): batch is usually 1, and what matters is per-token latency.
OPT-66B needs about 40 GB even with 4-bit quantization, which does not fit in GPU memory, so part of the weights must sit in CPU memory.

## Strawman / Baseline
- **GPU-centric offload (FlexGen)**: weights sit on the CPU and are moved to the GPU over PCIe as needed each iteration → 99.5% of the time is spent moving weights.
- **Split by layer (llama.cpp)**: the first several layers go on the GPU, the rest are computed on the CPU → every iteration still touches all weights, with no locality. For OPT-30B only 37% fits on the GPU, the CPU takes 98% of compute time, and one iteration takes about 600 ms, vs. only 45 ms on an A100.
- **Compute only activated neurons (DejaVu)**: a small MLP predictor predicts which neurons (a row/column of a weight matrix) will be activated, and only those are computed → the activated set changes with the input, so the whole model must be on the GPU; fetching from the CPU through Unified Memory instead gives latency similar to FlexGen. Its fixed-size predictor alone needs about 27 GB of GPU memory on OPT-175B.

## Novelty
1. **Activations follow a power law, and the hot set of neurons does not change with the input**
   Insight: in OPT-30B, about 17% of neurons account for 80% of activations; across different tasks, the top 20% most often activated neurons overlap by over 90%.
   So: measure activation frequency offline on a general corpus, preload hot neurons onto the GPU at neuron granularity, and put cold neurons on the CPU. At run time, a predictor in each layer selects the neurons to compute; the GPU and the CPU each compute their own, and the results are merged on the GPU.
   Compared with splitting by layer, the GPU takes most of the activation compute; compared with DejaVu, the whole model need not be in GPU memory.
2. **Only a small part of the cold neurons is activated each iteration, so computing them in place on the CPU is faster than moving them to the GPU**
   Insight: an MLP block usually activates only about 10% of its neurons per iteration, and the batch is small. Computing this little bit on the CPU with AVX2 is faster than moving the weights over PCIe and computing them.
   So: cold neuron weights never cross PCIe; only a small piece of the result is transferred. This avoids the transfer cost of FlexGen/DejaVu-UM at the root.
3. **How large a predictor must be depends on how sparse and how skewed the layer is**
   Insight: the sparser a layer is and the more its activations concentrate in a few neurons, the easier it is to predict, and a small predictor is enough.
   So: set each layer's predictor hidden size iteratively until the perplexity deviation is under 0.1%. Total predictor size falls to about 7% of the model's parameters, leaving GPU memory for hot neurons.

Other design: sparse operators that compute by single neuron row/column, with no sparse format conversion; placement is decided by integer linear programming, with the constraint that each layer either stays off the GPU or puts enough neurons there to offset the CPU-GPU synchronization cost.

## Evidence
- End to end (RTX 4090, FP16, batch 1): 8.32 tokens/s on average; vs. llama.cpp 7.23× on average and up to 11.69× (Falcon-40B); vs. SpecInfer 6.19× on average. With INT4, OPT-175B approaches 2 tokens/s. The gap between OPT-30B and vLLM on an A100 shrinks from 93% to 18%.
- Novelty 1 → step-by-step ablation: predictor and sparse operators alone 1.87×/3.32× (Bamboo-7B/Falcon-40B); CPU-GPU hybrid within a layer but with random placement 2.60×/7.80×; placement by hotness 3.62×/11.69×. The share of activation compute on the GPU rises from 20% to 70%.
- Novelty 2 → microbenchmark: for batch below 32, computing directly on the CPU is faster than moving to the GPU and computing there. There is no end-to-end control of "move cold neurons to the GPU and compute there".
- Novelty 3 → predictors take under 10% of inference time. No direct ablation of adaptive size vs. a fixed-size predictor.
- Gaps: relies mainly on ReLU-family models (some modified by the authors); SwiGLU models are only 1.5–1.7× faster. With long prompts and short outputs, only 1.07–4× faster. At batch 32 it drops to 4.38×. Small accuracy loss (LLaMA(ReGLU)-13B average 51.73%→50.79%).

## When it applies
Needs high activation sparsity, hot neurons that are stable across inputs, and a small batch. When the batch grows or prefill dominates, the activated neurons together approach the full set and the CPU becomes the bottleneck.
