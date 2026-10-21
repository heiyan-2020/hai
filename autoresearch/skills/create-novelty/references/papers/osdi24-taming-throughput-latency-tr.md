# Taming Throughput-Latency Tradeoff in LLM Inference with Sarathi-Serve
OSDI'24 · Amey Agrawal et al. / Georgia Tech, Microsoft Research India · Full text: https://www.usenix.org/system/files/osdi24-agrawal.pdf (USENIX camera-ready) · Selected: Highly cited (927 citations)

**One sentence**: Decode iterations are bandwidth-bound and leave compute idle, while a prefill of a few hundred tokens already saturates compute, so split long prompts into chunks and fit them into every decode round.

## Problem
An LLM request has two phases: prefill processes the whole prompt in parallel at once (compute-bound), and decode produces only one token per request per round (bandwidth-bound).
Throughput comes from batching the decodes of many requests together, and how the prefill of new requests is inserted decides the TBT (time between adjacent output tokens). The goal is the maximum QPS that can be sustained while P99 TBT meets its target (capacity).

## Strawman / Baseline
- **Request-level batching, decode first (FasterTransformer)**: New requests are taken only after the whole batch finishes → TBT is stable, but the batch keeps shrinking and throughput is low.
- **Iteration-level batching, prefill first (Orca, vLLM)**: Whenever memory is free, run the whole prefill of new requests first → requests in decode get stuck (generation stall), for up to several seconds. Orca puts prefill and decode in the same batch, but a whole prefill still makes TBT up to 28.3× higher than a pure decode batch. Smaller batches do not help either: under a strict SLO, vLLM's capacity is nearly the same at batch 32/64/128.
- **Cross-node pipeline parallelism (PP) with micro-batches**: Micro-batch durations differ a lot. On Falcon-180B, one round with a 4k prompt takes about 1150 ms while decode takes about 200 ms, leaving a bubble of about 950 ms. Cross-node tensor parallelism (TP) has too much communication cost.
- **Naive chunked prefill**: Each chunk must re-read the KV cache of all earlier chunks, so the smaller the chunk, the more repeated reads.

## Novelty
1. **Decode rounds have free compute, and prefill does not need to be computed all at once**
   Insight: Decode batches are bandwidth-bound, so adding tokens adds almost no time (the linear layers of LLaMA2-70B take about the same time between 128 and 512 tokens). Prefill throughput saturates at about 512 tokens, while median prompts are 1730–7059 tokens.
   So: Set a fixed token budget per round (512–2048); put in all decodes first, and fill the rest with one chunk of prefill. New requests can join every round, yet the length of a round does not depend on prompt length. This removes both the low throughput of decode-first and the stalls of prefill-first. Attention over small chunks is still compute-bound, so the cost of re-reading KV is small.
2. **When every round has the same amount of work, PP bubbles disappear**
   Insight: Bubbles come from adjacent micro-batches having different durations, and the token budget makes the compute of every micro-batch nearly the same.
   So: TP within a node and PP across nodes; large models can be deployed over ordinary Ethernet without wasting compute.

Other design: The budget is chosen per SLO by profiling (the Vidur simulator), avoiding tile quantization (chunk length 257 is 32% slower than 256).

## Evidence
- End to end: under a strict SLO, Yi-34B capacity is 3.7× vLLM and 4.0× Orca; Mistral-7B is 2.6× vLLM; LLaMA2-70B (PP) is 4.3× vLLM and 6.3× Orca.
- Novelty 1 → Ablation (Yi-34B): mixed batching alone gives P99 TBT 0.68/1.38 s, and adding chunking gives 0.14/0.17 s; chunking alone without mixing gives TTFT 1.04 s, and both together give 0.76 s. Chunking overhead is at most about 25% at chunk length 512 and negligible at 2048.
- Novelty 2 → Falcon-180B TP4-PP2: 3.6× (strict)/1.48× (relaxed) higher than vLLM with the same configuration. Bubble length is not measured directly.
- Gaps: The PP version of vLLM was implemented by the authors themselves; no comparison with Splitwise or DistServe, which put prefill/decode on separate machines; chunked prefill first appeared in the same authors' 2023 preprint Sarathi; the budget is chosen by hand per SLO.

## When it applies
Decode rounds must be bandwidth-bound with spare compute, and prompt chunks must still saturate compute. When decode batches are already compute-bound, or TTFT matters more, the gain shrinks.
