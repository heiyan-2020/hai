# Maelstrom: Mitigating Datacenter-level Disasters by Draining Interdependent Traffic Safely and Efficiently
OSDI'18 · Kaushik Veeraraghavan, Justin Meza et al. / Facebook, UIUC · Full text: https://www.usenix.org/system/files/osdi18-veeraraghavan.pdf (USENIX camera-ready) · Selected: Community favorite (3 sources: Morning Paper, Papers We Love, UIUC CS598 2018)

**One sentence**: The emergency steps of hundreds of services are really the same few primitives, and the only thing to respect is dependency order. Dependency knowledge goes stale, and the only way to keep it fresh is to rehearse on real traffic every week.

## Problem
A power outage, a cut fiber or a bad configuration can bring down a whole datacenter, and redundancy within the same datacenter fails with it.
The fastest way to stop the damage is to drain: move user traffic and service-to-service traffic headed for the failed datacenter to healthy datacenters, and move it back after the repair.
But Facebook has hundreds of interdependent services. Traffic falls into four kinds, stateless, sticky sessions, replication, and primary-secondary stateful, and each kind is drained differently.

## Strawman / Baseline
- **Each service's own drain script, run one by one**: the scripts are incompatible with each other, cannot be composed, and cannot be sped up or slowed down by urgency. Running them in sequence is about 6 times slower.
- **Drain everything at once**: this violates dependencies. For example, draining cache invalidation traffic before read traffic leads to stale reads. Restoring web before the backends makes errors rise with web traffic (in one test this lasted about 5 hours). Moving all traffic in one step makes downstream caches start cold. When replication traffic is restored, it syncs at 10 times the steady-state rate and saturates the backbone.
- **One big drill a year (Google DiRT, Amazon GameDay)**: between drills, systems and dependencies change, and tools and scripts silently break. Facebook's earliest drain tests covered only web services, took more than 10 hours each, and kept being interrupted by unknown dependencies.
- **Diagnose first, then fix (roll back or repair)**: finding the root cause takes time, and users are affected the whole time. Existing tools such as TrafficShift can only drain the stateless traffic of a single service.

## Novelty
1. **Procedures differ, primitives are the same; order is decided only by dependencies**
   Insight: Each service's runbook (emergency operations manual) looks different, but they are all made of a few kinds of operations (change load balancer weights, move data shards, stop and start jobs, change configuration), and the procedures are all "move traffic away while staying healthy". The only real ordering constraints are the dependencies between services.
   So: A runbook is written as a task DAG. Tasks are instantiated from templates and carry preconditions, postconditions and health metrics. The scheduler orders tasks only by dependency and runs all others in parallel. Each team writes only its own policy, and the framework provides the execution mechanism for everyone. After each drill, critical path analysis pushes dependencies off the critical path. This solves scripts that cannot be composed and sequential execution that is too slow.
2. **Dependencies show up only when traffic is really drained**
   Insight: Dependencies keep changing, and surveys, logs and tracing all give incomplete pictures. Draining a datacenter's traffic while it is healthy is reversible: if something goes wrong, traffic can be moved back at once.
   So: Several times a week, use the same runbooks used for real disasters to automatically drain, on production traffic, the datacenter that has gone longest without a test. Humans are called only on anomalies. A failed test is a newly found dependency, which is added to the DAG. This solves tools going stale between yearly drills.
3. **Drain speed is set by health feedback**
   Insight: Overload comes from "draining too fast", not from "draining" itself.
   So: Each task runs in several steps. Step size and wait time come from past drills, then speed up or slow down by health metrics. If a condition is not met, it stops and waits for a human instead of pushing on. In a real disaster, operators can override weak dependencies to go faster. This solves one-step drains crushing downstream services.

## Evidence
- End to end: in production for over 4 years, it handled more than 100 datacenter-level failures. One fiber incident lost over 85% of backbone bandwidth: most user traffic was drained in about 17 minutes and all traffic in about 1.5 hours. One bad configuration crashed all search aggregators: found in 2 minutes, drained in 7 minutes, while diagnosis took 20 minutes. Impact time was cut by about 60%.
- Novelty 1 → one real disaster: user traffic was drained in 40 minutes, all services in 110 minutes. The one-by-one time was computed by adding up each service's time, about 6.6× and 6.3×, and was not actually run. This datacenter's drain runbook has 79 tasks and 109 dependencies, with only 8 on the critical path.
- Novelty 2 → only an anecdote: in one test, a wrong restore order revealed an unknown dependency. No quantitative comparison with dependencies inferred by tracing.
- Novelty 3 → no direct ablation. Stopping to wait for a human happens about once every few dozen tests.
- Gaps: all of it is one company's operational experience, with no controlled comparison.

## When it applies
The disaster affects only some datacenters, and the rest have headroom to absorb the traffic. If the failure is caused by malicious or poisonous requests, draining spreads the failure. For failures caused by software bugs, rollback may be faster.
