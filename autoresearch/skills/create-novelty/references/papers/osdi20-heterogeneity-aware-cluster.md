# Heterogeneity-Aware Cluster Scheduling Policies for Deep Learning Workloads
OSDI'20 · Narayanan, Santhanam et al. / Stanford, Microsoft Research · Full text: https://www.usenix.org/system/files/osdi20-narayanan_deepak.pdf (USENIX camera-ready, system name Gavel) · Selected: Highly cited (338 citations)

**One sentence**: Common scheduling policies are all just functions of job throughput. Replace throughput with the time-weighted average throughput across GPU types, and all these policies become heterogeneity-aware.

## Problem
A GPU cluster mixes several generations of GPUs: K80, P100, V100. Different models get very different speedups on newer GPUs: ResNet-50 is nearly 10× faster on V100 than on K80, while A3C is only 2× faster. Per dollar, P100 is the better deal for many models.
Operators have different goals: fairness, makespan (the time for a batch of jobs to all finish), cost, and hierarchical fairness.

## Strawman / Baseline
- **Heterogeneity-agnostic policies (Tiresias's LAS, i.e. max-min fairness that rotates by GPU time used; Themis; Gandiva)**: Treat one K80 and one V100 as the same share. → Shares are "equal" but speeds differ several times. Jobs that are not sensitive to GPU type occupy V100s, which is waste.
- **Heterogeneity-aware but serving only one goal (AlloX, Gandiva_fair)**: The mechanism is tied to the goal, so they can only optimize average JCT or max-min fairness, and cannot do hierarchical policies. AlloX favors short jobs, so long jobs starve under high load.
- **Gandiva's random co-location**: Randomly tries pairs of jobs on the same GPU until there is a gain. → Co-location gains differ hugely between pairs (Figure 4), and random trials often pick wrong.
- **Place jobs directly by the optimal allocation**: Distributed jobs need several GPUs at once, and with co-location added, exact solving is a multiple-choice knapsack problem, which is NP-hard. Waiting to gather 8 GPUs leaves resources idle, and letting small jobs jump the queue starves large jobs.

## Novelty
1. **Policies look only at throughput, so replacing "throughput" with "effective throughput" makes them heterogeneity-aware**
   Insight: The objectives of policies such as LAS, FIFO, makespan, finish-time fairness, and cost plus SLO can all be written as functions of each job's throughput. DNN training proceeds in iterations and can be paused and migrated cheaply at iteration boundaries (saving and loading a checkpoint takes under 5 seconds). So a job can be split across several GPU types by time fraction.
   So: The allocation is a matrix X giving the fraction of time each job runs on each GPU type. Effective throughput is the X-weighted average throughput. Replace the throughput in the original policy with it, add validity constraints, and get an LP (or a sequence of LPs) for an off-the-shelf solver.
   Co-location and placement sensitivity just add rows and columns to the matrix for "job pairs" and "consolidated/spread placement", using measured pair throughputs instead of random trials.
   One formulation covers all goals. This solves two root causes: "counting shares but not speed" and "mechanism tied to a single goal". With only one GPU type, it reduces to the original policy.
2. **Only the long-run average needs to match, so each round can be greedy**
   Insight: A policy gives fractions over a period of time and does not require any single round to be exact. A wrong choice in one round can be made up in later rounds.
   So: Each round is 6 minutes. Priority is "target fraction ÷ fraction received". Each round greedily picks job combinations that fit, in priority order, and the same job does not appear twice in a round. A job that is not scheduled keeps rising in priority, so it does not starve. This avoids NP-hard exact placement.

Other design: estimate co-location throughput with Quasar-style matrix completion; solve hierarchical policies with water filling; lease renewal reduces checkpoints.

## Evidence
- End to end (physical cluster: 8 V100 + 16 P100 + 24 K80): heterogeneity-aware LAS lowers average JCT from 5.1 h to 3.4 h (1.5×). Makespan drops from Gandiva's 21.3 h to 17.7 h (1.2×). Simulation and measurement differ by less than 8%.
- Novelty 1 → Simulated cluster (36 of each GPU type), compared with the heterogeneity-agnostic version under the same round-based mechanism: LAS lowers average JCT under high load by 3.5× (single-GPU jobs) and 2.2× (including multi-GPU jobs). The FTF policy lowers JCT by 3×. Makespan is 2.5× lower than FIFO. Also, the minimum-cost policy saves 1.4× over the maximum-throughput policy, but 35% of jobs violate their SLO. With the SLO constraint added, violations are 0 and it still saves 1.2×. Explicit co-location gives 2.2× better JCT than Gandiva's random co-location. It sustains higher load than AlloX.
- Novelty 2 → Compared with an ideal scheduler that follows the allocation exactly: the two nearly overlap (Figure 15b). Preemption overhead is below 3%, and below 0.5% with renewal.
- Gaps: Most conclusions come from simulation, with synthetic job types and durations (uniform sampling over 26 models). Solve time: the hierarchical policy takes under 10 minutes at 2048 jobs, but with co-location it only reaches 512 jobs. The policies do not stop jobs from misreporting throughput (not strategy-proof).

## When it applies
Jobs must be cheap to preempt and migrate at iteration boundaries, and their throughput must be stable and measurable in advance. For jobs that cannot be preempted, or workloads that behave unstably across GPU types, time-fraction allocation cannot be delivered.
