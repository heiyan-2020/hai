# Serving DNNs like Clockwork: Performance Predictability from the Bottom Up
OSDI'20 · Gujarati, Karimi et al. / MPI-SWS, Emory · Full text: https://www.usenix.org/system/files/osdi20-gujarati.pdf (camera-ready) · Selected: Highly cited (472 citations)

**One sentence**: DNN inference has no branches and takes a fixed time; all jitter comes from choices the lower layers make on their own. Move those choices to the center, and the system can compute in advance exactly when each request will finish.

## Problem
An inference service must respond within an SLO of tens of ms. It must also let many models with low request rates (personalization, A/B tests) share GPUs, instead of giving each model its own GPU.
The hard part is tail latency: uncertainty at each layer (worker, GPU, OS) amplifies layer by layer.

## Strawman / Baseline
- **A thread pool runs inference concurrently to fill the GPU**: Throughput is up to 25% higher, but when several kernels run at once the GPU allocates resources with an undisclosed policy, and the OS also schedules threads on its own → tail latency rises 100×.
- **Overprovisioning / sending redundant requests**: Trades utilization for tail latency, which is expensive.
- **Clipper, INFaaS**: Wrap around TensorFlow/TensorRT, with scheduling and memory management sealed inside the framework. The SLO is only a long-term target adjusted reactively (Clipper only manages average latency) → goodput collapses when the SLO is below 100 ms. In experiments, Clipper hits the memory limit at 15 ResNet50 instances and INFaaS at 64.

## Novelty
1. **Latency jitter comes from "lower layers having choices", not from inference itself**
   Insight: DNN inference is a fixed sequence of operators on fixed-size input, with no conditional branches. Running ResNet50 alone 11 million times, p99.99 differs from the median by only 0.03%. Jitter appears only where lower layers have choices: the GPU chooses how to run kernels concurrently, the OS chooses which thread to run, the cache chooses what to evict.
   So: Each GPU runs only one inference at a time. GPU memory is preallocated and cut into 16 MB pages, and model load/unload becomes explicit LOAD/UNLOAD actions. JIT and kernel caches are removed. Workers no longer make any choices on their own, so latency is predictable. This removes the 100× tail latency of the first strawman, giving up only the small throughput gain from concurrency.
2. **With predictable latency, scheduling can change from "reactive repair" to "planned in advance"**
   Insight: When the duration of every action is known, the controller can compute the earliest time each request will finish.
   So: All decisions are made in a central controller. It executes only requests that can finish within the SLO; requests bound to time out are not put on the GPU and are cancelled at once. Each worker has only about 5 ms of work queued in advance; the later the decision, the larger the batch it can form. Each action carries an [earliest, latest] time window. If the window is missed, the action is dropped instead of being done late on a best-effort basis, so one unexpected delay does not pass on to later requests. This directly targets the root cause of Clipper/INFaaS adjusting the SLO reactively.
3. **LOAD is also predictable, so GPU memory can be a centrally managed model cache**
   Insight: Copying weights from host to GPU takes a fixed time (about 8 ms for ResNet50, versus about 2.9 ms for inference), so the cost of a cold start can be counted into the SLO in advance together with inference.
   So: All models stay resident in host memory. The controller decides which model to LOAD onto which GPU based on "unmet demand", and unloads with LRU. One GPU can therefore serve thousands of models.

## Evidence
- End to end: 12 workers, 61 kinds of models copied into 4026 instances, replaying a 6-hour Azure Functions trace. Average 9638 r/s. Of 208 million requests, only 58 failed due to misprediction, and no request exceeded the 100 ms SLO. Compared with Clipper/INFaaS (15 ResNet50): with SLOs below 100 ms, only Clockwork still has goodput.
- Novelty 1 → Concurrent vs serial (Fig. 2b): concurrency gives at most 25% more throughput, and serial execution has two orders of magnitude lower latency variation. Prediction error: INFER p99 overestimates by 144 μs and underestimates by 55 μs; LOAD is 431/348 μs.
- Novelty 2 → On 6 workers, 600/1200 r/s can meet 10/22 ms SLOs, and 2400 r/s gets 74 ms. Mixing in batch clients with no SLO does not affect the satisfaction rate of latency-sensitive requests. Centralization itself has no direct ablation.
- Novelty 3 → One worker with 3600 models: with cold starts at 70%, maximum latency still stays within the 100 ms SLO.
- Gaps: INFaaS runs on EC2, not the same hardware as the other systems, and the authors also say only a qualitative comparison is possible. The gap to Clipper/INFaaS mixes in differences in the execution framework. The controller becomes the bottleneck at 110 simulated workers and 103,387 r/s. No fault tolerance.

## When it applies
Workers must have exclusive use of their machine and GPU, and network latency must be mostly stable. Models must have no data-dependent control flow. With dynamic branches, or when sharing GPUs with other tenants, predictions become inaccurate.
