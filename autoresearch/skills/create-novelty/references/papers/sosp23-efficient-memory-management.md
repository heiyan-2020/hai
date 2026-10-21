# Efficient Memory Management for Large Language Model Serving with PagedAttention
SOSP'23 · Woosuk Kwon, Zhuohan Li et al. / UC Berkeley, Stanford, UCSD · Full text: https://arxiv.org/abs/2309.06180 (arXiv v1, with the SOSP'23 copyright page; content is the camera-ready) · Selected: Highly cited (9250 citations)

**One sentence**: Attention does not care where the KV is stored, and the KV cache is only appended at the end, so it can be allocated block by block on demand and shared across sequences, like OS paging.

## Problem
LLM decoding is memory-bound. Throughput needs large batches, and batch size is limited by the GPU memory for the KV cache (the key/value vectors of each generated token).
For OPT-13B, the KV of one token takes 800 KB, and one request takes up to 1.6 GB; on an A100-40GB only about 30% of GPU memory is left for it.
In existing systems, only 20.4–38.2% of KV memory actually holds tokens.

## Strawman / Baseline
- **Reserve contiguous space for the maximum length (FasterTransformer, Orca)**: the framework requires tensors to be contiguous and the output length is unknown, so space is reserved once for the upper limit (e.g. 2048). → Three kinds of waste: the unused tail (internal fragmentation), slots held for tokens not yet generated, and external fragmentation from the buddy allocator. Even when the length is known (Orca Oracle), the whole chunk is held for the entire request.
- **Multi-sequence decoding (parallel sampling, beam search)**: each sequence has its own contiguous space. → The common prompt is stored several times; when beam search switches candidates, the whole KV segment must be copied.
- **Allocate on demand**: without reservation, memory runs out midway through generation and preemption is needed.

## Novelty
1. **Attention is a sum over past tokens and does not depend on physical location**
   Insight: the KV cache is only appended at the end, and attention can be computed block by block and then combined, so it need not be stored contiguously.
   So: cut the KV into fixed-size blocks (16 tokens by default). Each request uses a block table that maps logical blocks to arbitrary physical blocks; the next block is allocated only when the current one is full. The attention kernel is rewritten to read the KV through the block table (PagedAttention).
   Waste is limited to the last block of each sequence. This removes the reservation and both kinds of fragmentation, and needs no compaction (the KV is too large to move online). The obstacle was "tensors must be contiguous", and the new kernel gets around it.
2. **Tokens with the same prefix have the same KV, and it never changes**
   Insight: a token's KV depends only on the tokens before it.
   So: the shared prefix of several sequences maps to the same set of physical blocks, with reference counts; only a shared last block that is about to be written gets block-level copy-on-write. The prompt is stored once, and beam search no longer copies when switching candidates.
3. **A sequence uses all its blocks at every step, and the KV can be recomputed from the tokens**
   Insight: page-by-page replacement is meaningless for this access pattern, and dropped KV need not be written back.
   So: when memory runs out, a whole sequence (for beam search, a whole group) is swapped out together. To resume, it can be swapped back from CPU memory, or the prompt and the generated tokens can be joined into a new prompt and recomputed in one prefill. This answers the midway exhaustion caused by on-demand allocation; the second option is something OS paging cannot do.

## Evidence
- End to end: OPT-13B/66B/175B (1/4/8 A100s), ShareGPT/Alpaca. At similar latency, the sustainable request rate is 1.7–2.7× Orca (Oracle), 2.7–8× Orca (Max), and up to 22× FasterTransformer.
- Novelty 1 → effective KV memory utilization 96.3%, vs. 20.4–38.2%; for OPT-13B, the number of requests batched at once is 2.2× Oracle. Cost: the attention kernel is 20–26% slower than FasterTransformer's. Block size was only tuned as a knob (16–128 is best on ShareGPT).
- Novelty 2 → memory saved by block sharing (two datasets): parallel sampling 6.1–30.5%, beam search 37.6–66.3%. The advantage over Oracle grows from 1.3× for basic sampling to 2.3× for beam=6. On a translation task with a shared prefix: 1.67×/3.58×.
- Novelty 3 → only swap vs. recompute is compared: with small blocks, swap is held back by small PCIe transfers, and recompute overhead stays within 20% of swap. Whole-sequence swap-out is not compared with per-block replacement: no direct ablation.
- Gaps: Orca is not open source; the authors reimplemented it under a buddy allocator assumption. In the Alpaca + OPT-175B setting, memory is ample and the system becomes compute-bound, so the advantage shrinks.

## When it applies
The workload must be limited by GPU memory, not compute, and sequence lengths must be dynamic and unknown. For static shapes such as training, or compute-bound inference, paging only adds the overhead of indirect addressing.
