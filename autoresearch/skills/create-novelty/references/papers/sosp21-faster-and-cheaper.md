# Faster and Cheaper Serverless Computing on Harvested Resources
SOSP'21 · Yanqi Zhang, Íñigo Goiri et al. / Cornell, Microsoft Research · Full text: https://www.csl.cornell.edu/~delimitrou/papers/2021.sosp.harvest.pdf (author lab home page, camera-ready) · Selected: Highly cited (227 citations)

**One sentence**: Almost all functions are short, and Harvest VMs are rarely evicted, so the chance that the two collide is tiny; the whole FaaS platform can therefore run on cheap VMs that get evicted.

## Problem
FaaS users pay for the actual run time of functions, but the platform has to rent VMs from IaaS and reserve a lot of capacity to create the illusion of "unlimited elasticity".
Harvest VMs are cheap: a Harvest VM has a minimum size and takes all unallocated cores on its host (priced lower than the minimum size). But it has two problems: it can be evicted with only 30 s notice, and its core count can change at any time, by 12 cores per change on average.

## Strawman / Baseline
- **Use only regular VMs**: reliable but expensive; for the same budget, Harvest VMs buy 1.9–9.7× the CPU.
- **Put long applications (any invocation over 30 s) on regular VMs and the rest on Harvest VMs**: no eviction failures. → Long applications take 99.7% of execution time, so only 12% of compute can go to Harvest; yet 94% of invocations on regular VMs are actually short. Relaxing it to "regular VM only if P99 exceeds 30 s", with the failure rate held below 0.1%, still gives only 28%.
- **OpenWhisk default load balancing**: packs by memory, filling one invoker before moving to the next. → It ignores CPU, so VMs with few cores or that just shrank saturate first.
- **CPU-aware JSQ (join-the-shortest-queue)**: always pick the VM with the lowest load. → Invocations of one function are spread over all N VMs, so the inter-arrival time on each VM becomes N times longer and often exceeds the 10-minute keep-alive (how long a function container is kept after it goes idle); cold starts go up.
- **Spot VMs**: fixed size, evicted per VM → more fragmentation; the same idle resources can only be 91.67% used (Harvest: 99.62%), and the failure rate is at least 23.2× higher.

## Novelty
1. **An eviction failure needs two unlikely events at the same time**
   Insight (Azure trace): Harvest VMs live 61.5 days on average, and 90% live longer than 1 day. Only 4.1% of invocations exceed 30 s; long applications are "long" only because of a few tail invocations. 70% of the intervals between core-count changes are longer than the longest invocation (578.6 s).
   So: do not split long and short; put all functions on Harvest VMs. After an eviction notice, send no new invocations; running invocations mostly finish within 30 s. This directly overturns the conservative "long applications on regular VMs" approach.
2. **Slight imbalance is harmless when not overloaded, but spreading destroys warm starts**
   Insight: cold starts depend on the inter-arrival time of one function on one VM, and when resources are not saturated, slight load imbalance causes no queueing.
   So (MWS): consistent hashing gives each function a starting VM. VMs are added along the ring until the sum of their currently available cores covers the function's estimated demand (arrival rate × average CPU × average duration). Then the VM with the lowest CPU/memory weighted utilization in this small set is chosen. Each VM reports its available cores every second, so core changes and evictions show up in the set at once. Consistent hashing ensures only a few functions move when VMs are added or removed.
   This fixes both the default balancer ignoring CPU and JSQ's many cold starts.

## Evidence
- End to end: with a budget equal to 2 regular 16-core VMs, 6–21 Harvest VMs can be bought under different discount assumptions, giving 2.2–9.0× throughput. For the same resources, 49–89% cheaper than regular VMs and 0–45% cheaper than Spot. Replaying the trace on real Harvest VMs, P99 latency is 62% lower than a regular VM cluster.
- Novelty 1 → trace-driven simulation (1000 runs per period): failure rate 0.0015% in the period with the most evictions, 3.68×10⁻⁸ in a typical period; cold start rate rises by at most 0.13 percentage points.
- Novelty 2 → 10 heterogeneous VMs with 5–28 cores: MWS throughput is 22.6× OpenWhisk default and 1.6× JSQ, with 56–76% fewer cold starts than JSQ. Under an extreme trace where core counts change every 3.6 minutes on average, MWS throughput is 73.1% of a stable Harvest cluster; the default balancer reaches only 39.0% of a dedicated cluster. No separate ablation of consistent hashing.
- Gaps: reliability rests only on simulation, which assumes all functions use the same CPU. Prices are computed from assumed discounts. The SLO is P99 50 s, which is loose. The real-VM experiments use CPU spin loops instead of real functions.

## When it applies
The vast majority of functions must be shorter than the eviction notice period (30 s), and Harvest VMs must live far longer than functions. For workloads dominated by long tasks, Novelty 1 does not hold.
