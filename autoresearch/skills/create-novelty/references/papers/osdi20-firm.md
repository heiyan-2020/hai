# FIRM: An Intelligent Fine-grained Resource Management Framework for SLO-Oriented Microservices
OSDI'20 · Haoran Qiu, Subho S. Banerjee et al. / UIUC · Full text: https://www.usenix.org/system/files/osdi20-qiu.pdf (USENIX camera-ready) · Selected: Highly cited (412 citations)

**One sentence**: Contention makes the critical path drift and makes the culprit's tail latency far exceed its median. Locate the culprit with these two signals first, then learn per instance how to adjust resources.

## Problem
When microservices share machines, contention on low-level resources such as memory bandwidth, LLC, and network causes latency spikes that violate end-to-end SLOs.
A request's latency is set by its critical path (CP, the longest chain in the call graph). The authors injected contention and collected 41 million traces: whichever service is under contention, the CP switches to it. Across different CPs, median latency differs by 1.6× and p99 by 2.5×.

## Strawman / Baseline
- **Kubernetes autoscaling**: Adds replicas based only on CPU utilization. Under memory bandwidth contention, CPU utilization barely changes, and spikes continue.
- **AIMD on resource limits / static rules based on historical profiles**: The best action depends on load, resource type, and application. At 500 req/s, scaling up a single container is better. At 1500 req/s, CPU contention calls for adding replicas (scale-out), while memory contention still calls for scale-up, and the turning point differs by application. Fixed rules cannot cover this. The CP from a static profile also goes stale.
- **"Scale whoever has the highest latency"**: composePost has the highest median latency but is not under contention, so scaling it does not help. text, which has higher variance, is the one to scale.
- **Performance models (queueing models, etc.)**: Need expert modeling, and must be rebuilt whenever a service is updated.
- **One large model that takes the state of all microservices as input**: The state and action spaces grow with the number of services, training is slow, and it is tied to one application topology.

## Novelty
1. **The fingerprint of contention is "variance", not utilization or average latency**
   Insight: Requests to a contended instance pile up in its queue, so its tail latency stretches relative to its median, and its jitter directly sets the jitter of the whole CP. A service with high but stable latency is just slow by nature.
   So: Compute each request's CP from distributed traces in real time. For each instance on the CP, compute two features: the correlation between its latency and the total CP latency, and p99/p50. An incremental SVM decides whether it is the culprit.
   This answers three failures: Kubernetes cannot see low-level contention, "scale the slowest" scales the wrong target, and a static CP goes stale.
2. **Locate first, then learn the policy on a single instance**
   Insight: Once the culprit is known, "how to adjust" depends only on that instance: the utilization of five kinds of resources, load changes, request mix, and distance from the SLO. This state does not depend on application size.
   So: Each culprit is handed to an RL agent (DDPG, 8-dimensional input, 5-dimensional output) that directly sets CPU quota, memory bandwidth (Intel MBA), LLC (CAT), disk bandwidth, and network bandwidth. When resources hit the ceiling, it adds replicas instead. The reward considers both SLO and utilization. RL learns from feedback the turning points that depend on load and resource type, replacing AIMD rules. The input has a fixed size, which avoids the state explosion of a large model. One general agent can be used across applications, then fine-tuned to a specific service with transfer learning.

Other design: a contention injector (7 kinds) creates contention during training, which gives the SVM labeled culprits and lets RL explore fully; actions are executed through cgroups and tc, taking 2.1–45.7 ms.

## Evidence
- End to end (15 x86/Power machines, 3 DeathStarBench applications + Train-Ticket, random contention injected): Compared with Kubernetes autoscaling and AIMD, SLO violations are 16× and 9× fewer, and p99 is 11× and 6× lower. Requested CPU limits are 29–62% lower, and dropped requests are up to 8× fewer. RL is trained only on Train-Ticket and validated on DeathStarBench.
- Novelty 1 → Single-contention localization has AUC 0.978; multi-contention accuracy is 92–94%. There is no end-to-end comparison with "scale the slowest" or other localization methods; only one example is shown in the characterization experiment.
- Novelty 2 → After convergence, violations are removed in 1.7 s on average, 9× faster than AIMD and 30× faster than Kubernetes. The general agent converges in about 15000 episodes, with 6% lower reward than a dedicated agent. Transfer learning converges in about 2000 episodes. "Two-level split vs one large model" has no direct ablation.
- Gaps: Test contention and training come from the same injector. The baselines are only two rule-based methods, with no comparison to ML methods such as Seer. Power machines do not support MBA/CAT.

## When it applies
SLO violations must come from resource contention and last longer than the time for an action to take effect (milliseconds). Violations caused by application bugs, memory leaks, or global resources such as switches cannot be fixed by adding resources.
