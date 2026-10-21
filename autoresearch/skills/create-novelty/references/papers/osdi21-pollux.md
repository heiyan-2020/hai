# Pollux: Co-adaptive Cluster Scheduling for Goodput-Optimized Deep Learning
OSDI'21 · Aurick Qiao et al. / Petuum, CMU · Full text: https://www.usenix.org/system/files/osdi21-qiao.pdf (camera-ready) · Selected: Best Paper

**One sentence**: More GPUs only help with a larger batch, and the training value per sample of a large batch can be measured online, so GPU count and batch size should be scheduled together.

## Problem
For DL training jobs in a shared GPU cluster, users must set the GPU count, batch size, and learning rate themselves. The three are linked: with more GPUs, an unchanged batch cannot keep them busy; with a larger batch, the training progress per sample (statistical efficiency) drops.
The best values also change with cluster load and training progress. Even when hand-tuned well, they are only static values fixed at submission.

## Strawman / Baseline
- **User fixes the GPU count (Tiresias, Gandiva)**: A job uses one configuration for its whole life. → GPUs sit idle when load is low, and jobs queue when load is high. Submitting with the original GPU counts from the Microsoft trace gives an average JCT (job completion time) of 2.8 h.
- **Auto-scale GPU count with a throughput model (Optimus, Gavel, AntMan)**: Tunes only the GPU count, not the batch. → The per-GPU batch gets smaller while the gradient sync time per step stays the same, so by Amdahl's law the gain from adding GPUs quickly caps out. With the same job configurations, Optimus+Oracle (2.7 h) is only slightly better than Tiresias.
- **Keep growing the batch to chase throughput (cloud auto-scaling by Or et al.)**: Throughput does not change with training progress, so it scales to the most nodes and the largest batch from the start. → Early in training, large batches are very inefficient, so money is spent without buying progress.

## Novelty
1. **"Training value per sample" can be measured online and extrapolated to batch sizes not yet tried**
   Insight: How much efficiency a large batch loses is set by the gradient noise scale (GNS, the noise-to-signal ratio of the stochastic gradient). It can be estimated cheaply from the local gradients each GPU computes anyway, and it predicts efficiency at other batch sizes without running them. GNS also grows by more than 10× as training proceeds, so late training can tolerate much larger batches.
   So: Define goodput = throughput × statistical efficiency. Throughput comes from a 7-parameter iteration-time model fitted at runtime, and efficiency comes from GNS. "More GPUs + large batch" and "fewer GPUs + small batch" can then be compared on one scale.
   This fills exactly the blind spot of the last two baselines: looking only at throughput, they cannot see that progress from a larger batch is discounted, nor that the discount changes with the training phase.
2. **When allocating GPUs, account for the job re-tuning its batch after it gets the GPUs**
   Insight: What an allocation is worth depends on how large a batch the job will use once it gets it. So an allocation should be valued at the best goodput over batch sizes under that allocation, not at throughput with a fixed batch.
   So: An agent beside each job picks the batch size and gradient-accumulation steps under the current allocation, scales the learning rate by rule, and reports the fitted goodput function to the scheduler. The scheduler searches allocations to maximize the power mean of each job's "goodput speedup relative to a 1/J fair share"; the exponent p is the fairness knob.
   So the cluster gives more GPUs and large batches when it is idle, and fewer GPUs and small batches to keep efficiency when it is crowded; Optimus, which tunes only GPU count, cannot do this.

Other design: The prior assumes perfect scaling to drive exploration; frequent reallocation is penalized (each checkpoint-restart takes 15–120 s); jobs that span nodes do not share machines.

## Evidence
- End to end: 16 AWS nodes with 64 T4s in total, 160 jobs sampled from the Microsoft trace, 6 model types. When the competitors use hand-tuned configurations, average JCT is 50% / 37% shorter than Optimus+Oracle / Tiresias, p99 is 27% shorter for both, and makespan is 20% / 33% shorter. When the competitors use the trace's original configurations, average JCT is 72% / 73% shorter.
- Novelty 1 → The predicted efficiency curves match measurements across many batch sizes (Figure 2); the throughput model's average error on 64 GPUs is at most 10%. ImageNet cloud auto-scaling is 25% cheaper than the throughput-driven approach of Or et al., and only 6% slower.
- Novelty 2 → Figure 5 shows many GPUs at low efficiency under low load, and few GPUs at high efficiency under high load. No direct ablation: Optimus uses Pollux's throughput model, but its allocation algorithm also differs, so the gains cannot be separated. At p=−1, 99% of jobs have finish-time fairness (shared JCT ÷ JCT with an exclusive 1/J of the cluster) <2.
- Gaps: The competitors' TunedJobs and the exact-iteration-count Oracle both favor the competitors. Reallocation happens on average every 7 minutes and adds 8% runtime overhead. Final accuracy differs by ±1% across batch sizes (DeepSpeech2 ±4%); a user-set batch cap is the safety net.

## When it applies
Jobs are synchronous data-parallel on homogeneous GPUs, and the learning-rate scaling rule (AdaScale, square root) keeps accuracy over the batch range used. When the GNS estimate is inaccurate, or the model is sensitive to large batches, goodput overestimates the value of large batches.
