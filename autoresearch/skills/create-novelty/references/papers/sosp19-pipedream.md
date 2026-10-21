# PipeDream: Generalized Pipeline Parallelism for DNN Training
SOSP'19 · Deepak Narayanan, Aaron Harlap et al. / Microsoft Research, CMU, Stanford · Full text: https://people.eecs.berkeley.edu/~matei/papers/2019/sosp_pipedream.pdf (camera-ready from Matei Zaharia's homepage) · Selected: Highly cited (1328 citations)

**One sentence**: Activations between layers are often smaller than the whole model's weights, and training tolerates bounded staleness. As long as one minibatch uses the same weight version in its forward and backward passes, the pipeline needs no flush.

## Problem
Multi-GPU training mainly uses data parallelism (DP): each GPU holds a full model copy, and all gradients are all_reduced after each minibatch.
On public clouds beyond 32 GPUs, communication stalls can take 90% of training time. It is worst for models with dense weights such as LSTMs and fully connected layers, and the faster the GPU, the higher the share.

## Strawman / Baseline
- **DP (BSP synchronous)**: per-step communication is proportional to the whole model → the same number of bytes crosses slow inter-machine links.
- **Asynchronous DP (ASP) / large batch + LARS (per-layer learning rate)**: less synchronization → stale gradients hurt convergence; VGG-16 reaches 48% accuracy 7.4× slower than PipeDream; batch 4096/8192 does not reach target accuracy.
- **Model parallelism**: split layers across GPUs → only one GPU computes at a time; partitioning is manual or uses expensive reinforcement-learning search.
- **Naive pipeline**: inject minibatches continuously → a stage's forward pass uses old weights, but by the backward pass the weights have been updated by later minibatches, so the gradient is invalid and training may not converge.
- **GPipe**: flush after every m microbatches and update together → the pipeline drains often, and activations must be recomputed.
- **OWT, FlexFlow (hybrid intra-batch parallelism)**: no pipelining, so computation and communication do not overlap.

## Novelty
1. **After splitting by layer, only activations between adjacent stages need to be sent, and this can overlap with computation of other minibatches**
   Insight: For many models, layer outputs are much smaller than weights, and different minibatches have no dependencies on each other.
   So: Consecutive layers form a stage. Stages send activations/gradients point to point asynchronously while computing the next minibatch. Communication drops by more than 85% for VGG-16 and AWD LM and is hidden by computation. This is exactly where DP's root cause lies.
2. **Training tolerates bounded staleness, but a single minibatch must be internally consistent**
   Insight: Weights change slowly, so a forward pass can still learn without seeing the updates of in-flight minibatches. Only using different weights in the forward and backward passes makes a gradient invalid.
   So: Each stage's forward pass uses the latest weights and stores them (weight stashing); the backward pass retrieves the same version. The steady state can then strictly alternate "one forward, one backward" (1F1B), with no flush and no wait for global synchronization. This fixes both the wrong gradients of the naive pipeline and GPipe's draining. Each stage stores only 1/n of the weights, in n versions, so peak memory is similar to DP.
3. **The pipeline is a chain of consecutive layers, and each layer's time hardly varies with input**
   Insight: Short profiling accurately estimates each layer's cost, and the chain structure gives "minimize the slowest stage" optimal substructure.
   So: Use dynamic programming over the layer topology to find the split points and the number of replicas per stage (a stage can use DP, rotating by minibatch ID so the forward and backward passes land on the same replica). This replaces manual partitioning, and for models with large activations and small weights such as ResNet-50 it automatically falls back to pure DP.

## Evidence
- End to end (Azure 4×V100 per machine, AWS 8×V100 per machine, to target accuracy): VGG-16 5.28× faster than DP (16 GPUs); GNMT-16 3.14×; AWD LM 4.25×; S2VT 3.01×; ResNet-50 picks DP, 1×. Each model needs about as many epochs as DP to reach accuracy.
- Novelty 1 → byte counts: communication drops 88% for AWD LM and 85% for S2VT. With the same bytes, adding pipelining alone is up to 80% faster than hybrid parallelism and 1.9× faster than FlexFlow.
- Novelty 2 → compared with the authors' own GPipe under the same split: GPipe throughput is 55%/71% lower (same depth) or 35%/42% lower (maximum depth). Whether removing weight stashing prevents convergence: no direct ablation.
- Novelty 3 → optimizer runs in <8 seconds; predicted and measured throughput are linearly correlated, and it picks the best of the tested configurations. Pipelining with replicas is 14.9×/6.5× faster than model parallelism.
- Gaps: Baselines are on public cloud in fp32; DP there is 1.94–3.29× slower than on MLPerf dedicated clusters, so part of the speedup comes from the slow network.

## When it applies
Activations between layers must be clearly smaller than weights. Convolution-heavy models with large activations (ResNet-50) gain nothing. Non-BSP staleness semantics must be acceptable.
