# Gandiva: Introspective Cluster Scheduling for Deep Learning
OSDI'18 · Wencong Xiao, Romil Bhardwaj et al. / Microsoft Research, Beihang University · Full text: https://www.usenix.org/system/files/osdi18-xiao.pdf (camera-ready) · Selected: Highly cited (651 citations)

**One sentence**: A training job is a million identical mini-batches. So it can be swapped out and migrated cheaply at iteration boundaries, and iteration speed can be used to try scheduling choices and back out of bad ones.

## Problem
Deep learning training (DLT) jobs today are scheduled by Kubernetes/YARN: they get fixed GPUs once and hold them exclusively until done.
A hyperparameter search submits tens to hundreds of configurations at once (multi-job). It needs accuracy curves for all configurations early, to decide which ones to kill. But other jobs run for hours to days, so multi-jobs can only wait in the queue.
Jobs are also highly heterogeneous: VGG16 on two GPUs across CPU sockets gets only 60% of the best placement; ResNet-50 on two GPUs across machines is slowed by neighbors by up to 47%; the average GPU utilization of the production cluster is about 52%.

## Strawman / Baseline
- **Big-data schedulers (YARN capacity, Kubernetes)**: treat jobs as black boxes, allocate once on arrival and hold exclusively to the end → queueing causes head-of-line blocking, with no early feedback. A wrong placement (poor locality, heavy interference) cannot be corrected later. Small jobs with low utilization hold a whole GPU.
- **General process suspend/migrate (CRIU)**: checkpoint the whole process at any moment → state is GB-scale; migrating a single-GPU job takes 8–10s, and multi-GPU is slower. Suspending at any moment also means moving peak GPU memory.
- **Model first, then decide packing (several jobs sharing one GPU)**: the gain from packing ranges from +412% to −16% depending on the model. It is hard to predict even for jobs of the same kind, and interference across kinds cannot be modeled at all.

## Novelty
1. **The mini-batch boundary is a natural, cheap preemption point**
   Insight: GPU memory rises and falls periodically within each mini-batch. For ResNet-50, peak and trough differ by 77× (23GB vs 0.3GB). At the trough, only a small amount of live state such as model parameters remains.
   So: Delay suspension to the trough (at most one mini-batch late), and copy only live objects. Migration reuses the framework's existing checkpoint, stores only one copy of the model, and warms up the destination.
   Swapping out becomes cheap enough that the scheduling unit changes from "the whole job" to "a 60s stretch of iterations". This allows oversubscription and rotating time slices, and removes CRIU's GB-scale cost and the queueing caused by exclusive allocation.
2. **Iteration speed is a ready-made probe, so scheduling can act first, measure, and undo mistakes**
   Insight: The time between two GPU memory troughs is the time of one mini-batch, and a few iterations measure it accurately. A job runs a million iterations, so the cost of trial and error is amortized.
   So: Build no interference model; just try. If total throughput after packing is worse than time slicing, undo it. For locality-sensitive jobs, migrate them when closer GPUs free up. When the cluster is idle, let jobs that declare they can scale grow to more GPUs.
   This answers two root causes: "model predictions are inaccurate" and "one-time allocation cannot be corrected".

Other design: place jobs grouped by GPU count (jobs with the same GPU count on the same machine); defragmenting migration; grow-shrink; PyTorch detects the trough in its caching allocator.

## Evidence
- End to end: 180-GPU cluster, 1000 synthetic jobs, compared with a scheduler that only does bin-packing without oversubscription: average time to finish the first 100 mini-batches is 498s vs 2203s (−77%), utilization 62.8% vs 50.1% (+26%). Replaying a 9-day Microsoft trace on 100 GPUs (8800 jobs, replaced with 10 open-source models) against YARN capacity: average JCT −26.8%, makespan −17.8%, with AutoML multi-jobs 13.6×/12.9× faster. Hyperparameter search finds a qualifying configuration 3.4–7.0× faster.
- Novelty 1 → 6 single-GPU jobs rotating over 4 GPUs lose <2% total throughput; suspend-resume takes <100ms to 1s; an 8-GPU migration saves 98% of 35s; for 6 of 10 models, migration takes <1s, at most 3.5s. "Suspend at trough vs suspend at any moment": no direct ablation.
- Novelty 2 → in the 180-GPU experiment with migration disabled, the 26% utilization gain comes from packing, and undos are rare. In AutoML, "time slicing alone gives 7×, the rest is due to migration" is derived by subtraction, not by ablation.
- Gaps: the workload is synthetic; trace replay relies on fast-forward (error <1%); no comparison with model-based packing; no cluster-level fairness guarantee.

## When it applies
Jobs consist of many identical iterations, and PyTorch/TensorFlow can be modified. When iterations are very long or irregular, or packing exceeds GPU memory, both preemption latency and the cost of trial and error grow.
