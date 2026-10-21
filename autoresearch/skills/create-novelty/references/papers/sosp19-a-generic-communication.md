# A Generic Communication Scheduler for Distributed DNN Training Acceleration
SOSP'19 · Yanghua Peng, Yibo Zhu et al. / HKU, ByteDance · Full text: https://i.cs.hku.hk/~cwu/papers/yhpeng-sosp19.pdf (camera-ready from author homepage, with ACM copyright page; system name ByteScheduler) · Selected: Highly cited (425 citations)

**One sentence**: Backpropagation emits gradients starting from the last layer, but the next forward pass needs parameters starting from the first layer, so earlier layers should be sent first, and this holds for every framework.

## Problem
In data-parallel training, each iteration must aggregate gradients from all workers, using a parameter server (PS: workers push gradients and pull parameters) or all-reduce.
Communication often takes most of the training time. Frameworks send FIFO in the order tensors are produced, and backpropagation produces the last layer's gradients first.

## Strawman / Baseline
- **Framework default FIFO**: layer 0's parameters arrive last, and the next forward pass just waits. Once a large tensor (the largest in VGG16 exceeds 400 MB) is queued, it blocks all higher-priority tensors behind it. Under PS, a pull can start only after the whole tensor is pushed, wasting half of the duplex bandwidth.
- **P3 (MXNet PS), TicTac (TensorFlow PS)**: schedule by layer priority, but deeply modify their own engine and PS; switching frameworks or moving to all-reduce means redoing the work. P3 uses fixed 160 KB slices and waits for one ACK per slice sent, which cannot fill bandwidth above 10 Gbps. TicTac speeds up by less than 20%.
- **The global barrier between iterations in TensorFlow and PyTorch**: the next iteration waits until all communication of this one completes, so no reordering helps (the authors think this is why TicTac's gains are small).
- **Schedule in the communication library or the transport layer**: RPC/MPI implementations vary widely; and at the TCP/RDMA layer, layer priority is no longer visible.

## Novelty
1. **Every framework runs the same layer-by-layer DAG**
   Insight: Regardless of framework, PS or all-reduce, TCP or RDMA, the forward pass consumes layers in order 0…N, and the backward pass produces them in order N…0. Under the assumption of "infinitely small slices and free preemption", one can prove that "lower layer number first" is optimal.
   So: Put scheduling at the framework's Python API layer, independent of the engine. The obstacle is that each engine decides its own execution order. The solution is to insert a Dependency Proxy into the engine: a placeholder operator that depends on the operator producing the gradient, runs before the communication operator, and finishes only when the scheduler releases it. Declarative engines can already declare dependencies, and imperative engines can use hooks, so the engine need not be modified.
2. **The real dependency is per layer; the global barrier is just how the code is written**
   Insight: The forward pass of layer i in the next iteration needs only layer i's communication to be complete.
   So: Make communication asynchronous so the barrier passes immediately; then put a Proxy before each layer's forward pass that waits for that layer's communication to finish. Reordering communication becomes effective again.
3. **Slicing and preemption have fixed costs, and the best granularity changes with the environment**
   Insight: Each message has about 300 µs of overhead. The best slice size varies with model, bandwidth and PS/all-reduce, and iteration time is a non-smooth function of slice size.
   So: Replace send-one-wait-one with credit (the number of bytes allowed in flight, like a sliding window). Slice size and credit are searched by measurement with Bayesian Optimization at the start of training. This answers exactly the fixed slices and stop-and-wait sending of P3.

## Evidence
- End to end: up to 64 V100s (8 per machine, 100 Gbps), VGG16/ResNet50/Transformer, 5 framework × architecture × transport combinations, compared with native frameworks: speedup 1%–196%, the highest for VGG16 on TensorFlow PS TCP. 28–43% faster than P3 on MXNet PS TCP.
- Novelty 1 → no direct ablation. Evidence of generality: it works on 3 frameworks, users change 2 lines of code, and only the TensorFlow engine needed 13 changed lines.
- Novelty 2 → no direct ablation. TensorFlow PS with its barrier gains the most (VGG16 170–196%), but the barrier's contribution is not separated.
- Novelty 3 → fixing the parameters tuned at 1 Gbps and using them at 1–100 Gbps: the tuned version is faster in every case, and fixed parameters are sometimes worse than the native framework. BO needs 28–51% fewer trials than SGD-momentum, usually under 10.
- Gaps: Under PS, the gains are mixed with load balancing. Native frameworks assign tensors to PSs round-robin; after slicing, load becomes naturally even, and part of Transformer's 171% comes from this.

## When it applies
Training must be limited by communication, and layer computation must proceed in chain order. ResNet50 at 100 Gbps is only 9.6% faster. Multiple jobs sharing the network or PS are outside the model.
