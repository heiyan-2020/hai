# A Unified Architecture for Accelerating Distributed DNN Training in Heterogeneous GPU/CPU Clusters
OSDI'20 · Yimin Jiang et al. / Tsinghua University, ByteDance, Google · Full text: https://www.usenix.org/system/files/osdi20-jiang.pdf (camera-ready, system name BytePS) · Selected: Highly cited (432 citations)

**One sentence**: Idle CPU machines in a GPU cluster are extra aggregation bandwidth, so split gradients among them by ratio. CPUs only do summation and do not run the optimizer.

## Problem
Data-parallel training must synchronize all gradients every iteration, and communication is the scaling bottleneck. In ByteDance's cluster, peak GPU allocation is nearly 96%, but 20–45% of GPU machines run single-machine jobs and their NICs are idle. Average CPU utilization is only 20–35%. Existing synchronization architectures cannot use these resources.

## Strawman / Baseline
- **All-reduce (Horovod + NCCL)**: A ring among GPU machines only; each machine sends and receives 2(n−1)M/n (M is model size). → Bandwidth-optimal with no extra machines, but cannot use CPU machines.
- **Parameter server (PS, aggregates and updates parameters on separate CPU machines)**: GPU machines send and receive only M. → Optimal only when the number of CPU machines k equals the number of GPU machines n. When k ≤ n/2, the CPU machines' NICs become the bottleneck, and it is slower than all-reduce.
- **PS runs the full optimizer on the CPU**: → The bottleneck is memory bandwidth. Adam needs more than 10 times the memory reads/writes per gradient, and the NIC traffic takes another 200 Gbps; 1024 Gbps of DDR4 cannot keep up. On 32-GPU VGG-16, MXNet PS is still the slowest even with added CPU machines.
- **The framework's intra-machine aggregation**: Direct reduce-scatter across 8 GPUs. → GPU copies across PCIe switches get only about 80 Gbps (105 Gbps within a switch). On NVLink machines, NCCL occupies the PCIe link that is shared with the NIC.

## Novelty
1. **All-reduce and PS are the two endpoints of the same load-allocation problem**
   Insight: The aggregation process on a GPU machine receives the local share of gradients without using the network. A CPU machine only carries the traffic of the part it is responsible for. So communication time is the maximum of the two kinds of machines' loads, and the ratio can be tuned to make them equal.
   So: Every machine (including GPU machines) runs a summation service. A closed-form solution gives the two kinds of machines different shares of the gradients. Tensors are cut into chunks of ≤4 MB and consistently hashed to the services. k=0 is all-reduce, and k=n is PS. In theory, at n=32 and k=16 it is 46% faster than all-reduce and 52% faster than PS.
2. **In the optimizer, only "summation" suits the CPU**
   Insight: Summation is a streaming operation that touches memory once. AVX summation throughput is >200 Gbps, above the NIC. The parameter update is the memory-intensive part.
   So: The CPU only sums (fewer than 3 cores at 100 Gbps), and the parameter update moves back to the GPU. Each GPU repeats the update, which costs less than 0.5% of forward and backward FLOPs. This removes the memory bandwidth bottleneck of PS. Asynchronous training instead pushes parameter deltas, which is proven equivalent to asynchronous PS.
3. **The intra-machine bottleneck is the PCIe link of the NIC, not the links between GPUs**
   Insight: The upper bound on cross-machine communication is the NIC. Intra-machine aggregation only needs to avoid crowding the NIC's link and avoid slow cross-switch copies.
   So: On pure PCIe machines, aggregate inside each switch first, then let the local CPU combine them (analysis shows 23.7% faster than ring, 9% from optimal). On NVLink machines, use reduce/broadcast, with the root chosen as a GPU that does not share a switch with the NIC.

Other design: reuses existing pipelining and priority scheduling; RDMA tuning raises the microbenchmark from 41 Gbps to 89 Gbps.

## Evidence
- End to end: 6 models, 3 frameworks, up to 256 V100s. At 256 GPUs it is 10–84% faster than all-reduce (with CPU machines) or 9–53% (without), and up to 245% faster than native PS. ResNet-50 scaling efficiency is 97.5% (all-reduce 88%).
- Novelty 1 → Communication microbenchmark on 8 single-GPU machines: within 1–9% of the theoretical optimum; all-reduce does not change with k. End to end on 8×8 GPUs, adding CPU machines gives up to 20% more speed, with each using <4 cores.
- Novelty 2 → VGG-16 on 256 GPUs is 52% faster than native PS, broken down as intra-machine communication 19%, summation service 18%, implementation 15%. This breakdown exists for this one model only.
- Novelty 3 → Without CPU machines: on pure PCIe machines it is up to 20% faster than the strawman intra-machine strategy. On NVLink machines, choosing GPU0 as root (equivalent to NCCL) is the worst.
- Gaps: With no CPU machines and no intra-machine optimization, BytePS is still faster than all-reduce. The authors only guess this is "more asynchrony", so this gain cannot be attributed. The baselines did not get the same RDMA optimizations.

## When it applies
The network must be close to full bisection bandwidth, and the cluster must have idle CPUs and NICs. Once CPU machines outnumber GPU machines, there is no further gain. The intra-machine scheme must be designed by hand for each topology.
