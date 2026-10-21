# TensorFlow: A System for Large-Scale Machine Learning
OSDI'16 · Martín Abadi et al. / Google Brain · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-abadi.pdf (camera-ready) · Selected: Highly cited (16018 citations)

**One sentence**: SGD tolerates stale and lost updates, so mutable state can go into the dataflow graph, and the parameter server becomes an ordinary user-programmable subgraph.

## Problem
Google's previous system, DistBelief, trained neural networks with a parameter server (PS, a stateful process that stores model parameters and receives gradients from workers).
Researchers who wanted to try new optimizers, new layers, or RNNs/GANs had to change the PS or layers written in C++.

## Strawman / Baseline
- **PS architecture (DistBelief, Project Adam and others)**: workers always run "read parameters → forward → backward → write gradients", the update rule is hard-coded in the PS, and the interface is only get/put. → Momentum requires changing the PS's data representation. Related parameters cannot be updated atomically. Computation cannot be offloaded to the PS to save traffic. RNNs with loops and GANs with alternating training do not fit this pattern.
- **Batch dataflow (Spark, DryadLINQ)**: data is immutable and subcomputations are deterministic; on failure, recompute from lineage (the record of how data was produced). → Updating the model requires broadcasting it whole. SparkNet takes 20 s to broadcast weights to 5 workers and collect updates, so only large batches work, and convergence slows.
- **Keep loops in the client language**: Python launches one graph execution per iteration. → The runtime cannot see the whole loop, so it cannot issue GPU kernels back to back without waiting for intermediate results. To stay in the graph, you must unroll to the longest sequence. The paper gives no numbers.
- **Synchronous SGD**: each step waits for the slowest worker. → The median step time is only about 10% more than asynchronous, but above the 90th percentile it gets sharply worse. Asynchronous SGD uses stale parameters.

## Novelty
1. **Training does not need to recover every write exactly, so mutable state can go into the dataflow graph**
   Insight: Batch dataflow requires immutability so it can recompute exactly after a failure. Training does not need this: after a failure, restart from the latest checkpoint, and the few lost update steps are made up by training on input data again. SGD itself also tolerates stale and lost updates.
   So: Variable and Queue are graph vertices with mutable state. Fault tolerance relies only on user-level periodic checkpoints (Save/Restore are also graph nodes), which need not be consistent.
   The PS is just a subgraph placed on certain tasks: optimizers, sparse embedding updates and computing softmax on the PS can all be written as scripts. This avoids the broadcast cost and the hard-coded update rule.
2. **Each worker's batch is a random sample, so losing any one does not matter**
   Insight: Synchronous SGD needs only "enough" gradients, not the gradients of particular workers.
   So: Implement the synchronization barrier and gradient accumulation with queues. Then deliberately run a few extra backup workers, and each step takes the first m gradients to arrive. Unlike MapReduce, there is no need to detect stragglers first. This cuts off the long tail of synchronous SGD.
3. **Make conditionals and loops into operators in the graph, so dynamic models also get whole-graph execution**
   Insight: Classic dynamic dataflow machines already had Switch/Merge: the branch not taken outputs a special dead value, which propagates all the way to Merge, so downstream operators still "complete" instead of waiting forever.
   So: Use them to implement conditionals and while loops in the graph. During partitioning, add coordination at the start and end of each iteration for each device, so the loop body can span devices. Automatic differentiation records which branch the forward pass took and replays it in the backward pass. Variable-length sequences need no unrolling and no return to Python. This also solves DistBelief's inability to fit RNNs. The paper does not explain why earlier systems did not do this.

Other design: single operators as nodes, which eases automatic differentiation; a unified device abstraction, so the same program runs on CPU/GPU/TPU/phones.

## Evidence
- End to end: on a single GPU, step times for four CNNs are shorter than Caffe and within 6% of Torch; Neon is faster on 3 models. Asynchronous training of Inception-v3 is slightly faster than MXNet. 200 workers reach 2,300 images/s, with diminishing returns.
- Novelty 1 → null-model microbenchmark: with 16 PS tasks, synchronous step time grows from 1.8 ms with 1 worker to 8.8 ms with 100. Sparse reads of a 1 GB or 16 GB embedding both take 5–20 ms. Placing softmax on more PS tasks raises throughput. Sampled softmax cuts transfer and computation to 1/78. No comparison with DistBelief: no direct ablation.
- Novelty 2 → 50 workers plus backups: step time is shortest with 4 (1.93 s); the speedup normalized by resources is highest with 3 (9.5%); a 5th instead slows things down.
- Novelty 3 → no direct ablation; the paper has no performance experiment on control flow.
- Gaps: all results are system throughput, with no time-to-accuracy. The benefit of a programmable PS side is not quantified.

## When it applies
The algorithm must tolerate weak consistency and lost updates; otherwise users must build synchronization on the graph themselves. The computation must be writable as a static graph in advance. Algorithms whose structure unfolds only at run time (such as deep reinforcement learning) are awkward to use.
