# AntMan: Dynamic Scaling on GPU Clusters for Deep Learning
OSDI'20 · Wencong Xiao, Shiru Ren et al. / Alibaba Group · Full text: https://www.usenix.org/system/files/osdi20-xiao.pdf (USENIX camera-ready) · Selected: Highly cited (308 citations)

**One sentence**: A training job repeats the same computation every mini-batch, and its GPU memory is allocated and freed within a batch. So its GPU resources can be shrunk or grown at any batch boundary, and other jobs can be packed in safely.

## Problem
Alibaba's multi-tenant GPU cluster has many jobs queued, yet only 20% of GPUs use more than half their memory, and only 10% of GPUs have utilization above 80%.
There are two reasons. Job demand changes by phase (ESPnet uses 3.6 GB for training and 19 GB for decoding), but scheduling reserves the peak exclusively. Multi-GPU jobs need gang scheduling (they start only when all GPUs are available), so GPUs that arrive first sit idle.

## Strawman / Baseline
- **Exclusive allocation (YARN capacity scheduler)**: Reserves the peak exclusively, so GPUs are idle in valleys and during gang waits. Allowing preemption protects resource-guaranteed jobs, but the preempted jobs lose their work.
- **Pack jobs onto the same GPU (Gandiva packing)**:
  → Memory: The framework's caching allocator only grows and never returns used memory, so the real free memory is invisible. When a resource-guaranteed job grows, it fails with OOM.
  → Compute: GPUs have no isolation like cgroups, and a job with many kernels crowds out the other. With ESPnet and ResNet-50 on the same GPU, ESPnet goes from 20.1 minutes to 105.2 minutes.
- **Run other jobs directly on GPUs idling in a gang reservation**: When the large job is ready, it cannot get the resources back, or it starves.
- **NVIDIA MPS**: Limits cannot be changed at run time, and an error in one client brings down all clients.

## Novelty
1. **Most GPU memory lives only one mini-batch → the memory cap can be shrunk or raised at any batch boundary**
   Insight: 90% of models have parameters under 500 MB. Most memory is allocated and freed within the same mini-batch. Each batch creates the same tensors, and 80% of jobs take under 600 ms per batch.
   So: Add an adjustable cap to the TF/PyTorch allocator, and clear the cache or raise the cap at batch boundaries. Tensors beyond the cap go to host memory ("universal memory"), so the job slows down but does not OOM. The next batch creates its tensors again and they return to the GPU naturally, without copying data as paging would.
   When a resource-guaranteed job's memory jumps, it first spills over instead of failing. Then the coordinator shrinks the opportunistic jobs on the same GPU and raises its cap. This solves OOM under packing and lost work under preemption.
2. **Mini-batch time is a ready-made progress meter → compute can be yielded by feedback**
   Insight: Each batch does the same computation, so mini-batch time is stable and directly shows whether there is interference.
   So: Add a GpuOpManager to the framework that delays the issue of opportunistic jobs' GPU operators according to a quota (dependencies unchanged). The local coordinator raises the opportunistic job's share step by step, and backs off as soon as the resource-guaranteed job's mini-batch time slows down. This fills the gap left by GPUs lacking cgroups.
3. **With instant reclamation, idle GPUs can be lent out without preemption**
   Insight: Memory can be reclaimed in 17 ms and compute can be throttled at any time, so lent resources need not wait for the job to end to be taken back.
   So: Resource-guaranteed jobs are gang-scheduled as usual. Opportunistic jobs (no quota, no SLA) are placed on GPUs waiting idle in gang reservations and on GPUs below 80% utilization. Everything gives priority to the resource-guaranteed job on the same GPU. When resources are enough, opportunistic jobs are upgraded directly without restart.

## Evidence
- End to end (64 V100s, traces of 9 models): Average JCT is 2.05× better than YARN-CS and 1.84× better than Gandiva. Makespan is 1.76× and 1.67× better respectively. Production cluster (5000+ GPUs), before vs after deployment: memory usage +42%, GPU utilization +34%, average queueing time down 2.05×.
- Novelty 1 → Two jobs on the same GPU: preemption makes the opportunistic job fail; FIFO makes the resource-guaranteed job wait 17.1 more minutes; under packing it OOMs; universal memory alone without coordination takes more than 500 minutes; AntMan takes 91.8 minutes (91.1 exclusive). Shrinking ResNet-50's memory from 17.6 GB to 1.3 GB takes 17 ms, and growing it back takes 115 ms more.
- Novelty 2 → ESPnet + ResNet-50 on the same GPU: under AntMan ESPnet takes 20.8 minutes (20.1 exclusive), and ResNet-50 keeps 57% of its speed. In a production sample of 10,000 jobs, 99% saw no mini-batch slowdown when sharing a GPU.
- Novelty 3 → JCT of resource-guaranteed jobs matches preemptive YARN-CS (which preempts 46% of jobs). The policy has no separate ablation.
- Gaps: Production data compares different jobs before and after deployment, so JCT is not comparable. Only Gandiva's packing was used, and the profiles it depends on were not available. Cutting ResNet's memory by 10% makes it more than 60% slower, so universal memory is only a fallback.

## When it applies
Jobs must iterate by mini-batch with the same tensors every batch, and must use the modified framework. Opportunistic jobs have no performance guarantee at all. For a synchronous multi-GPU job, if one GPU is under pressure, the whole job slows down.
