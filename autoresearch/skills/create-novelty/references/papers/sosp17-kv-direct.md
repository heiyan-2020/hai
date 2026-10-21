# KV-Direct: High-Performance In-Memory Key-Value Store with Programmable NIC
SOSP'17 · Bojie Li, Zhenyuan Ruan et al. / Microsoft Research, USTC · Full text: https://01.me/files/KV-Direct/kv-direct-paper.pdf (first author's homepage, ACM camera-ready) · Selected: Highly cited (289 citations)

**One sentence**: Once KV processing moves to an FPGA NIC, the bottleneck becomes PCIe, so every design choice is about "issue fewer DMAs and hide DMA latency".

## Problem
KVS are turning from object caches into shared data structures for distributed computing (graphs, parameter servers, counters): KVs are small (8–16 B), writes are frequent, and there are atomic operations on a few hot keys.
Networks have reached 40 Gbps, so the bottleneck is now the server CPU. Data centers have already deployed FPGA NICs at scale.

## Strawman / Baseline
- **CPU processing (MICA, HERD)**: one KV operation takes about 500 instructions, and memory accesses cannot overlap → only 5.5 Mops per core (7.9 with batching), while one core can do 29.3 M random 64 B memory accesses.
- **One-sided RDMA (FaRM, Pilaf, DrTM)**: clients read server memory directly → GET is fast. PUT needs several round trips and synchronization between clients, so most systems send PUT back to the CPU. RDMA single-key atomics reach only 2.24 Mops.
- **Naively move KV processing to the NIC**: the theoretical limit for 64 B DMA is 87 Mops, measured 60 Mops. A round trip is about 1 µs, so about 256 operations must be in flight to saturate it. A later operation on the same key must wait for the earlier one to be written back to host memory, so the pipeline stalls; single-key atomics drop to 0.94 Mops.
- **Two naive uses of on-board DRAM (4 GiB, 12.8 GB/s)**: use it as a cache of host memory, so all accesses go through DRAM first; but DRAM bandwidth is slightly lower than PCIe (13.2 GB/s), so throughput is capped by DRAM instead. Or store a fixed part of the data only in DRAM; it holds only about 6% of 64 GiB.

## Novelty
1. **Server-side execution removes client synchronization, and KVs are small enough to fit in one DMA**
   Insight: When the NIC executes GET/PUT/atomics, consistency is handled on the server side. After that, the cost is the number of DMAs, and the target KVs are small enough to fit directly in a 64 B hash bucket.
   So: A 64 B hash bucket holds 10 slots of 5 B, and small KVs are inlined. Collisions use chaining, avoiding the PUT memory-access thrashing of cuckoo/hopscotch under write-heavy loads. The slab allocator's free lists are cached on the NIC and synchronized in batches. The result: about 1 DMA per GET and about 2 per PUT.
2. **Every operation passes through the one NIC pipeline, so the latest value of a key can stay on chip**
   Insight: KVs in host memory are accessed only by the NIC, so every operation on a key passes through it. The target workloads repeatedly access a few hot keys, so same-key dependencies are common.
   So: An on-chip table records all in-flight operations and the latest value of their keys (borrowed from the reservation station of out-of-order CPUs), indexed by key hash. When an earlier operation completes, queued operations on the same key execute directly on the on-chip value, with only one final write-back, instead of each waiting for a PCIe round trip.
3. **Cache only a hash-selected slice of host memory, and DRAM becomes a second channel instead of a mandatory stop**
   Insight: All data still lives in host memory. As long as the fraction that is "cacheable" is limited, the accesses DRAM serves will not exceed its bandwidth.
   So: Select part of host memory by hashing 64 B addresses (this part can be larger than DRAM). Only accesses to this part go through the DRAM cache; the rest go straight over PCIe. Tune the fraction so the two channels carry similar load. Under skewed loads, hot keys in this slice hit the cache.

## Evidence
- End to end (YCSB, 10 B KV, Zipf 0.99): one NIC does 180 Mops GET and 114 Mops PUT, comparable to 24-core MICA (137 Mops). Energy efficiency 1487 Kops/W, about 3× CPU systems. Tail latency without batching 3–9 µs. 10 NICs reach 1.22 Gops GET.
- Novelty 1 → memory accesses compared with the hash tables of MemC3 and FaRM: with inlined KVs, GET is close to 1 and PUT close to 2; the others cannot exceed 55% utilization at 10 B KV. The allocator takes at most 5% of PCIe throughput.
- Novelty 2 → with/without the out-of-order engine: single-key atomics 180 vs 0.94 Mops (191×).
- Novelty 3 → compared with PCIe only: under long-tail loads about 30% of accesses are served by DRAM, and 95%/100% GET reaches the 180 Mops clock limit; no gain under uniform loads. No measured comparison with the "pure cache" scheme.
- Gaps: Some system numbers in the comparison table are simulated estimates. Throughput depends on client batching (up to 4×). Parameters were tuned per workload. No real applications. Persistence and fault tolerance are not discussed.

## When it applies
KVs must be small enough to inline in one DMA, and the load must be sendable in batches. Only skew makes on-chip forwarding and DRAM offload useful; uniform loads with large values are limited by network or PCIe bandwidth.
