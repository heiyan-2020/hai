# Kraken: Leveraging Live Traffic Tests to Identify and Resolve Resource Utilization Bottlenecks in Large Scale Web Services
OSDI'16 · Kaushik Veeraraghavan, Justin Meza et al. / Facebook · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-veeraraghavan.pdf (camera-ready) · Selected: Community favorite (3 sources: Morning Paper, The Paper Trail, UIUC CS598 2018)

**One sentence**: The web tier is stateless and routing weights are programmable. So real user traffic can be steered onto one cluster as a load test, with two top-level metrics guarding user experience.

## Problem
Facebook has hundreds of systems spread across data centers in several locations. Code changes several times a day, there are several hardware generations, and bottlenecks keep shifting.
To push utilization up, you must know how many requests a cluster or a region (1–3 nearby data centers) can really handle, and where it gets stuck.

## Strawman / Baseline
- **Capacity models / queueing models (Muse and others)**: → load and code change every day, so models go stale fast. Interactions between systems produce behavior that exists only as a whole, which models cannot compute.
- **Synthetic load tests (JMeter, TPC-C, YCSB)**: → cover only a narrow set of use cases. JMeter does not even run JavaScript.
- **Shadow traffic replay (JustRunIt)**: → web requests have write side effects, so they must be stubbed. Logic changes often, so stubbing never finishes, and downstream dependencies are not really stressed.
- **Single-machine capacity × machine count**: → at large scale, complex system effects dominate, and the estimate is sometimes far off.
- **Watch every system's metrics during the test**: thousands of systems, each exporting dozens of counters → all effort goes into tuning individual subsystems, and the bottleneck that really limits total capacity is not found.

## Novelty
1. **A stateless web tier plus layered routing weights lets real traffic itself serve as the test load**
   Insight: Web servers are stateless, so any one can serve any request. From POP (edge point of presence) to region, from region to clusters, and from cluster to machines, traffic is split by programmable weights.
   So: Raise the weight of a cluster or region to concentrate real user traffic there and run a load test in production. The load naturally includes read/write mixes, non-uniform arrivals and bursts, and is always current. No model, no synthetic load, and no stubbing of side effects is needed.
2. **User experience can be guarded by just two top-level metrics, and every step can be undone within 2 minutes**
   Insight: For users, a cluster under load test carries the same kind of risk as an operational incident. Web-tier p99 response time and the HTTP fatal error rate are enough to represent user experience; there is no need to watch every system.
   So: Build a feedback loop: after each weight change, read monitoring before the next change. Start with steps of about 15%. When any metric is within 10% of its threshold, drop to 1%. Stop when a threshold is crossed. On a failure, abort the test and send traffic back to healthy clusters. Later, metrics were added for only 23 key systems.
3. **The gap between "theoretical capacity" and "measured capacity" points to bottlenecks that appear only at scale**
   Insight: Single-machine capacity can be measured accurately with real traffic on 32 machines. Multiply by machine count to get theoretical capacity. When a cluster cannot reach the theoretical value, the missing part is cross-system bottlenecks.
   So: Iterate "measure → break down latency to find the bottleneck → fix → measure again". The target is 93% of theoretical value for a cluster and 90% for a region.

## Evidence
- End to end: 3 years in production, serving 1.7 billion users, with thousands of cluster tests and more than 50 region tests. Region tests used to stop at about 70% of theoretical capacity (75.7% in one test in May 2015). Later they routinely reached 90%, and service capacity on the same hardware rose by more than 20%.
- Novelty 1 → only a demonstration of the process: 32 machines hit the queueing threshold at about 175 RPS; one cluster test stopped at 75%. No comparison with modeling or shadow traffic: no direct ablation.
- Novelty 2 → changing a weight and confirming its effect takes about 120 s; recovery after a failure takes about 2 minutes; a region held about 90% load for about an hour. How much the tested users were actually affected is not quantified.
- Novelty 3 → case: the share of latency from the cache (TAO) under load rose from 15% to 40% because of hot shards. After switching to hashing weighted by access frequency, the CPU p95–p10 spread dropped from 10–15% to below 5%. Other cases: a rack switch hit about 12 Gbps (limit 10) with a 3% error rate; load imbalance gave one service a 1.75% error rate; connection-count settings were too low; the monitoring system Gorilla itself lacked capacity.
- Gaps: the 20% is a before/after comparison, during which systems kept changing, so it cannot be attributed to any specific fix.

## When it applies
Servers must be stateless, and load must be controllable by changing routing. Global systems such as batch processing, message queues and storage are not affected by where ingress traffic lands, so this method cannot test them.
