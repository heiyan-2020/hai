# InfiniGen: Efficient Generative Inference of Large Language Models with Dynamic KV Cache Management
OSDI'24 · Wonbeom Lee, Jungi Lee, Junghwan Seo, Jaewoong Sim / Seoul National University · Full text: https://www.usenix.org/system/files/osdi24-lee.pdf (camera-ready) · Selected: Highly cited (372 citations)

**One sentence**: The attention inputs of adjacent layers are almost the same, so the next layer's attention can be rehearsed in the previous layer, and only the KV that is really needed is prefetched from the CPU.

## Problem
The KV cache (the key/value of each past token) grows linearly with sequence length and batch size, and soon exceeds the model weights.
Offloading systems such as FlexGen keep the KV in CPU memory and move the whole KV to the GPU over PCIe for every generated token. On OPT-13B, the transfer takes 96.9% of the time of one Transformer block.

## Strawman / Baseline
- **Full transfer + prefetch (FlexGen)**: → The transfer is much longer than the previous layer's compute, so only a small part is hidden.
- **Quantization (INT4)**: Each token's KV gets smaller, but all tokens still have to move, so the cost still grows linearly with sequence length; the speedup over FlexGen saturates at 1.92×.
- **Eviction by attention score (H2O)**: Each step deletes low-score tokens and keeps a fixed fraction. → It assumes "unimportant now means unimportant later", which does not hold: with a budget of 200 tokens, similarity to full attention drops clearly after 200 steps. The budget is the same for every layer and every query: at seq 2048 it moves 409 tokens, while on average only 73 are actually important. The speedup saturates at 3.40×.
- **Pick the exact important tokens at each step**: You must wait for this layer's query and then compute dot products with all keys to know which to pick, which is too late to prefetch; and computing the scores itself needs all keys.

## Novelty
1. **Residual connections keep adjacent layers' inputs almost unchanged, so attention can be "rehearsed" one layer early**
   Insight: Input of layer i = input of layer i−1 + attention output + FFN output. The inputs to the last two go through LayerNorm and have small values, while the block input is dominated by outliers (elements with far larger magnitude than the rest) in a few fixed channels. The cosine similarity between adjacent layers' inputs is 0.89–0.97, versus only 0.27–0.37 with the attention/FFN outputs.
   So: In layer i−1, take this layer's input, multiply it by partial query weights and a partial key cache of layer i, estimate layer i's attention scores, and prefetch the KV of only the high-score tokens, overlapped with layer i−1's compute. The full KV stays on the CPU and is not deleted. This solves both "too late to prefetch" and H2O's permanent deletion.
2. **Rotate the query/key, and attention scores concentrate in a few columns, so rehearsal is cheap and accurate**
   Insight: Q·Kᵀ is dominated by a few large-magnitude columns. Right-multiplying the query and key weights by the same orthogonal matrix leaves the dot product unchanged, but can concentrate magnitude into fewer columns.
   So: Offline, run SVD on each layer's query and multiply the right singular vector matrix into W_Q and W_K; at prefill, pick 30% of the columns as partial weights and partial key cache (15% of the KV, resident on the GPU).
3. **Select by "how far below the maximum score", so the count changes per layer and per query automatically**
   Insight: After softmax, a token whose score is α below the maximum has only e^−α of the largest weight.
   So: Take only tokens with scores above (maximum − α), with α at 4–5, using on average under 10% of the KV. Take fewer where attention is concentrated and more where it is spread out. This fixes the root cause of H2O's fixed budget.

## Evidence
- End to end: one RTX A6000, PCIe 3.0. OPT-13B, 1920 input + 128 output, batch 20: 1.63–32.93× faster than UVM, FlexGen, INT4, and H2O. Accuracy up to 32.6 percentage points higher. A single block is only 1.52× slower than keeping everything on the GPU, while other schemes are 3.90–18.55× slower.
- Novelty 1 → Per-segment perplexity: InfiniGen stays close to full KV, while H2O drifts further over time. "Predict with the previous layer's input" is not compared with other ways of predicting: no direct ablation.
- Novelty 2 → Without rotation (fixed 20% budget): accuracy drops sharply on OPT-6.7B and slightly on Llama-2 (only a figure, no numbers).
- Novelty 3 → As sequence length goes 512→2048, the speedup rises to 5.28×, while INT4/H2O saturate. α and the column fraction are only knob sweeps, with no comparison against a fixed budget under equal conditions: no direct ablation.
- Gaps: Single GPU, up to 30B; speed experiments go only to sequence 2048, and 32K is tested only for perplexity. H2O and INT4 were implemented by the authors on FlexGen.

## When it applies
Depends on residual dominance and fixed-channel outliers making adjacent layers' inputs similar; layer 0 cannot be rehearsed. The bottleneck must be moving KV over PCIe; when all KV is on the GPU, the gain is small.
