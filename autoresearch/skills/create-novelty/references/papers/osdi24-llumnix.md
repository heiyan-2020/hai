# Llumnix: Dynamic Scheduling for Large Language Model Serving
OSDI'24 · Biao Sun, Ziming Huang, Hanyu Zhao et al. / Alibaba Group · Full text: https://www.usenix.org/system/files/osdi24-sun-biao.pdf (camera-ready) · Selected: Highly cited (331 citations)

**One sentence**: At dispatch time, nobody knows how long a request will generate, so misplacement is unavoidable; the KV cache is append-only, so requests can be live-migrated like VMs and corrected afterward.

## Problem
LLM serving dispatches requests to several model instances; inside an instance it uses continuous batching and an on-demand KV cache (vLLM's PagedAttention).
Output length is unknown in advance, and the KV cache grows during generation; when GPU memory runs out, requests are preempted and recomputed later. On a single-GPU LLaMA-7B with 62% average memory load, 8% of requests are still preempted, P99 per-token latency is 3.8× P50, 70% of it comes from preemption, and in the worst case one request loses 50 s.
Requests in the same batch also interfere with each other, and decoding speed can differ by up to 2.6×.

## Strawman / Baseline
- **Round-robin dispatch (common in production)**: Splits request counts evenly. → Sequence lengths vary widely, so an even split of requests is not an even split of load.
- **Dispatch by memory load (INFaaS++, counting the demand of queued requests)**: → At dispatch time only the input length is known, final usage is unknown, and load soon goes out of balance again. Also, spreading requests out fragments free memory across instances: prefill must allocate the KV for the whole input at once, so long-input requests wait in the queue, even though the cluster's total free memory is enough for the head-of-queue requests of 3 instances.
- **Statically reserve resources for high-priority requests**: → High-priority load changes, so the reservation is either wasted or not enough. Existing systems treat all requests the same.
- **Recompute or block-copy the KV cache when migrating a request**: → The stall grows with sequence length. On LLaMA-30B, recomputing 8k tokens takes 3.5 s, equal to 54 decoding steps.
- **A centralized scheduler that tracks each request**: → With 64 instances and a high request rate, each iteration stalls up to 40 ms to sync state, and the whole system is 1.7× slower.

## Novelty
1. **The KV cache is append-only, so the migration stall does not depend on sequence length**
   Insight: The KV of tokens already generated is never modified later; new KV is only appended at the end.
   So: Copy the multi-round pre-copy of VM live migration, but with no dirty-page tracking: the source instance keeps decoding while it copies the existing KV, then copies the few blocks added meanwhile, and finally stops for only one iteration to copy the last block. Source and destination handshake at each stage to handle cases such as the destination running out of memory or the request finishing midway.
   So dispatch is no longer a one-shot decision; it can be corrected at any time as requests actually grow. This solves the problem of too little information at dispatch time.
2. **Defragmentation, priority, and scale-down all mean "free up space on some instance", so they can be unified as load balancing**
   Insight: Each of these goals only needs some instance to look fuller; load balancing will then move requests away.
   So: Each request gets a "virtual usage": a queued request at the head of the queue counts at its memory demand; a high-priority request adds a margin that guarantees its decoding is not disturbed; an instance to be taken offline holds a fake request with infinite usage.
   Each instance reports only one number: (total memory − sum of virtual usage) / batch size, that is, how many more steps it can run. The global scheduler uses only this number to dispatch new requests and to pair migration sources and destinations; the choice of which request to migrate is made locally by the instance. So the global scheduler does not track individual requests, and avoids the stalls of centralized scheduling.

Other design: KV is sent with Gloo on a separate CUDA stream; small blocks are packed into a contiguous buffer before sending; if the global scheduler fails, the system falls back to direct dispatch.

## Evidence
- End to end: 4 VMs with 16 A10s in total, 16 LLaMA-7B instances, all based on vLLM. On real data (ShareGPT, BurstGPT), end-to-end latency mean/P99 is up to 2×/2.9× faster than the two baselines; on generated long-tail length distributions, prefill mean/P99 is up to 7.7×/14.8× faster than INFaaS++; P99 decoding up to 2× faster, and preemption loss down 70.4% on average.
- Novelty 1 → The migration stall is a constant 20–30 ms, shorter than one decoding step; recomputation and blocking copy take up to 111× as long. Decoding slows by no more than 1% during migration, and instances spend about 10% of their time migrating.
- Novelty 2 → Defragmentation: under M-M load, fragmented memory is 0.7% versus 7.9% for INFaaS++. Priority: with 10% of requests set to high priority, versus Llumnix-base without priorities, high-priority mean latency is 1.2–1.5× faster and P99 prefill 3.6–10× faster, while normal requests slow down by at most 4.5%/13%/2% (end to end/prefill/decoding). Autoscaling: at the same P99 prefill of about 5 s, 36% fewer instances. Scalability: near-zero stalls with 64 instances (GPUs simulated with sleep).
- Gaps: No ablation of "same dispatch policy, with/without migration", and INFaaS++ and Llumnix also use different load metrics, so the gain cannot be split between migration and policy. Original LLaMA goes only to 2k, generated lengths reach at most 6k, and only A10s were used.

## When it applies
Instances need enough bandwidth between them to move KV, and load must be uneven: total free memory is enough, it is just in the wrong places. When the whole cluster is full, migration does not help, and only scaling out does.
