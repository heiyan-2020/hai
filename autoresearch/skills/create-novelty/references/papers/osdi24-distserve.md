# DistServe: Disaggregating Prefill and Decoding for Goodput-optimized Large Language Model Serving
OSDI'24 · Yinmin Zhong et al. / Peking University, UC San Diego, StepFun · Full text: https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf (camera-ready) · Selected: Highly cited (1111 citations)

**One sentence**: Prefill and decoding have opposite bottlenecks and separate SLOs; on the same GPU you can only serve the stricter one, and only by splitting them onto different GPUs can each get its own resources.

## Problem
An LLM request has two phases: prefill processes the whole prompt at once and is compute-bound; decoding generates one token per step and is bandwidth-bound. Each phase has its own SLO: TTFT (time to first token) and TPOT (time per output token after that).
The goal is per-GPU goodput: the request rate each GPU can sustain while 90% of requests meet the SLO. A 13B model on one A100 gets only 1.6 rps, while prefill alone gets 5.6 rps and decoding alone gets 10 rps.

## Strawman / Baseline
- **Mixed batches (vLLM's continuous batching)**: Adding one long prefill to a batch slows all decoding in that batch, and TPOT shoots up, and the reverse also happens. Scheduling them separately or setting priorities only sacrifices the other phase.
- **Chunked prefill (DeepSpeed-MII)**: Split the prefill into chunks, each carrying a few decoding steps. → Interference is reduced but not removed; N chunks read the KV cache (the cached intermediate state for each token) O(N²) times.
- **Share one GPU count and one parallelism plan**: → Can only over-provision for the stricter SLO.
- **After splitting, move the KV cache across nodes**: The KV cache of one 512-token request on OPT-66B is about 1.13 GB, so 10 rps needs 90 Gbps, but the test cluster has only 25 Gbps across nodes; and a pair of 175B instances (2×350 GB) does not fit in one 8×80 GB machine.

## Novelty
1. **Both interference and resource coupling come from "the same GPU"**
   Insight: A single prefill request saturates compute, while decoding needs a large batch to use bandwidth fully, and the latency targets of the two phases are unrelated.
   So: Put the two phases in instances on different GPUs; when prefill finishes, it hands the KV cache to decoding. Several prefill instances feed one decoding instance so it can build large batches. Interference disappears outright, which targets the first two baselines.
2. **Once split, each phase is a simple queue, and its parallelism can be optimized on its own**
   Insight: An instance that does only prefill is roughly an M/D/1 queue. Intra-op parallelism (splitting one operator across GPUs) cuts execution time, which helps low load and strict SLOs; inter-op parallelism (splitting layers into pipeline stages) adds capacity, which helps high load.
   So: Each phase enumerates its own parallel configurations, uses a simulator plus binary search to find the maximum goodput, and then replicates by traffic. This removes "can only over-provision".
3. **The KV cache moves only between the same layer of the two instances**
   Insight: Layer k of decoding needs only the KV cache of layer k of prefill.
   So: On low-bandwidth clusters, split by pipeline stage, and place the prefill segment and decoding segment of the same stage on the same machine, so transfers use only in-machine NVLINK. Large models do not need to fit a whole pair in one machine, and cross-node bandwidth is avoided.

Other design: The decoding side pulls the KV cache actively to absorb bursts; batches are built by token count to reduce pipeline bubbles; the plan is recomputed when load changes.

## Evidence
- End to end: 32×A100, 25 Gbps across nodes, OPT-13B/66B/175B. On chatbot, request rate is 2.0–4.6× that of vLLM and 1.6–7.4× that of DeepSpeed-MII; code completion 5.7× that of vLLM; summarization 4.3×, and the SLO can be 12.6× stricter.
- Novelty 1 → In simulation, enumerating the best parallelism for colocated serving (vLLM++) gives the same result as default vLLM, so the gain does not come from tuning parallelism.
- Novelty 2 → Simulator error versus real machines <2%. "Per-phase search vs one shared configuration": no direct ablation.
- Novelty 3 → On OPT-175B, KV transfer is <0.1% of total latency, and 95% of requests take <30 ms. No comparison with naive cross-node placement.
- Gaps: Ablations are all done in the simulator; arrival times are synthetic Poisson, and SLOs are set by the authors; only OPT with MHA is tested; no fault tolerance.

## When it applies
Needs strict per-phase SLOs, enough GPUs, and enough bandwidth for KV transfer. For offline jobs that only want throughput, or with only one or two GPUs, chunked prefill fits better.
