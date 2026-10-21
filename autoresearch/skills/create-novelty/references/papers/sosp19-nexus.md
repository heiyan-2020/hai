# Nexus: a GPU cluster engine for accelerating DNN-based video analysis
SOSP'19 · Haichen Shen, Lequn Chen et al. / UW, AWS, MSR · Full text: https://homes.cs.washington.edu/~arvind/papers/nexus.pdf (camera-ready from author homepage) · Selected: Highly cited (361 citations)

**One sentence**: On a GPU, the cost of a request depends on how large a batch it is packed into, and batch size is limited by the latency SLO and the rotation cycle of the models sharing the GPU, so placement and batch size must be decided together.

## Problem
Video analysis services must run DNNs on GPU clusters for thousands of video streams, and requests have latency SLOs of tens to hundreds of ms.
GPUs are efficient only with large batches: batch 32 gives 4.7–13.3× the throughput of running one at a time.
But one application often cannot fill a GPU (LeNet needs 6.25 million inputs per second to saturate a V100), so requests of different models and tenants must be combined without violating each one's SLO.

## Strawman / Baseline
- **Clipper / TF Serving + assigning GPUs by request rate**: adaptive batching on a single machine; cluster allocation is done by a "batch-oblivious" scheduler the paper adds, using "request rate ÷ max single-GPU throughput" → this assumes a fixed per-request cost. But when low-rate models share a GPU they must take turns, so each round (duty cycle) gets shorter, batches get smaller, and per-request cost rises; a fixed cost leads to wrong allocation. Clipper puts models on the same GPU in different containers, kernels interleave arbitrarily, and latency is unpredictable.
- **Exact solution (integer programming)**: the problem is strongly NP-hard; CPLEX takes hours to solve 25 sessions.
- **Split the latency budget evenly across stages of a multi-stage query**: the best split of a detect→recognize pipeline depends on how many outputs the first stage produces per input (γ), and γ changes over time. In the example, the best split is 60/40 at γ=0.1 and 40/60 at γ=10.
- **Only identical models can be batched together**: transfer learning produces many specialized models that change only the last few layers. Frameworks treat them as different models, cannot batch them together, and each takes its own GPU memory.

## Novelty
1. **Request cost is "squeezable", so scheduling must treat batch size as a variable**
   Insight: A batch must be filled within one duty cycle, and worst-case latency is the duty cycle plus the batch execution time. The more models share a GPU, the shorter the duty cycle and the smaller the batch.
   So: Sessions with many requests first get whole GPUs, using the largest batch with 2× batch time ≤ SLO. For the remaining load, each takes its largest batch, and they are merged best-fit in decreasing order of occupancy: take the smaller duty cycle, shrink batches to match, then check whether the sum of batch times still fits.
   On each node, models run in one uniform rotation without interleaving, so the latency formula holds. This fixes "allocate GPUs by fixed cost" and also avoids integer programming.
2. **A query's latency split must be recomputed from the actual fan-out (γ)**
   Insight: The total number of GPUs is the sum over stages of "request rate × per-request cost", and the downstream request rate is γ times the upstream rate. So which stage is better given more time depends on γ.
   So: Every epoch (30–60s), run dynamic programming over the dependency tree using measured request rates, and pick a batch size for each model to minimize the total number of GPUs.
3. **Specialized models share a prefix, and the prefix can be batched across different inputs**
   Insight: Models that change only the last few layers have identical weights in all earlier layers, so different inputs can go in the same batch.
   So: At upload, hash subgraphs to find common prefixes. At run time, the prefix is batched and the suffixes run one after another; the prefix takes only one copy of GPU memory. Earlier, MCDNN and Mainstream reused prefixes to avoid repeated computation on the same input, not to batch.

Other design: early drop (drop requests that would force a batch to shrink; up to 25% better than lazy drop in simulation); overlapping CPU preprocessing with GPU execution (OL).

## Evidence
- End to end: on 16 GPUs, game-analysis throughput is 9.4×/12.7× Clipper/TF Serving (both ran only the ResNet part; otherwise they would be over 4× slower still). Traffic analysis 2.4× off-peak, 1.8× at peak. 7 applications running together use 11.7 GPUs against a lower bound of 9.8 (84%). On 100 GPUs, 0.27% of requests violate the SLO.
- Novelty 1 → 8 GPUs, 16 sessions, compared with the same system using a batch-oblivious scheduler: 11–64% higher throughput. Rotating multiple models on one GPU: 1.4–2.1× higher than TF Serving, 1.9–9.8× higher than Clipper.
- Novelty 2 → compared with an even split: 13–55% higher throughput. Removing QA in traffic analysis: 534→433 req/s (−19%).
- Novelty 3 → ResNet-50 variants on one GPU: up to 110% higher throughput; without prefix batching GPU memory runs out quickly. Removing PB in game analysis: 4120→3628.
- Gaps: The ablation turns features off cumulatively one by one, so each contribution depends on the order. In game analysis the largest step comes from the engineering optimization OL (7.4× alone). The text's "4120→2143" disagrees with 2413 in the figure. The baseline's cluster scheduler and the applications were all written by the authors.

## When it applies
Batch-time profiles are stable, per-request cost does not rise with batch size, request rates are roughly stable within an epoch, and dropping requests is allowed. When every model can fill a whole GPU on its own, squeezable bin packing is no longer useful.
