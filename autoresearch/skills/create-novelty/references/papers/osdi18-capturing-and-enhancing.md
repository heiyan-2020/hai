# Capturing and Enhancing In Situ System Observability for Failure Detection
OSDI'18 · Peng Huang et al. / Johns Hopkins University, Microsoft Research, ByteDance · Full text: https://www.usenix.org/system/files/osdi18-huang.pdf (USENIX camera-ready, system name Panorama) · Selected: Community favorite (3 sources: Morning Paper, UIUC CS591 2019, UIUC CS598 2018)

**One sentence**: When a component is half broken, the components that call it have already hit errors on their own execution paths, but they handled them and did not report them. Collect these errors and you can detect the failure.

## Problem
Gray failures in distributed systems (partial failures: a key thread is stuck or all write requests fail, but the process is still alive) often escape detection.
For example, in one ZooKeeper incident the leader did blocking I/O inside a critical section, and the whole cluster could not accept writes. But heartbeats between the leader and followers stayed normal, so no recovery was triggered.

## Strawman / Baseline
- **Heartbeat/crash detectors (built into each system, Falcon, φ accrual)**: define failure as the process stopping, and probe through a dedicated detection path that does not go through the faulty code → of 15 reproduced real gray failures, only 1 was found within 300 s (at 86 s).
- **Monitor multidimensional "vital sign" metrics with thresholds**: it is hard to choose metrics and set thresholds. In one AWS cascading failure caused by a memory leak, memory monitoring did not alarm because the threshold was hard to set.
- **Log errors and analyze them centrally after the fact**: callers usually retry, close the connection or just exit; they only log and do not report. Logs are correlated only during later investigation, which is too late.
- **Insert reporting hooks directly at call boundaries**: fails when there is an indirection layer. ZooKeeper puts a request in a queue and returns at once. After the processing thread exits on OOM, the caller still "succeeds" every time (queue capacity is Integer.MAX_VALUE), and there is not a single negative observation.

## Novelty
1. **What the requester sees is the failure itself**
   Insight: Components interact often. When one component has a problem, it shows up as timeouts, exceptions or bad responses on the execution paths of the components that call it. This is first-hand evidence, not an indirect metric.
   So: Every component becomes an observer of the components it calls. At cross-process/cross-thread calls it reports "healthy/unhealthy" plus context (which kind of operation it was doing). Observations are exchanged only among nodes that care about the same subject. Because the evidence is strong, a simple majority vote per observer and per context is enough, with no thresholds to tune. The context can also point to which thread or which kind of operation is broken.
2. **Observation points can be found statically, so developers need not instrument by hand**
   Insight: Cross-component calls (RPC, sockets, library APIs, public methods of Thread subclasses) have fixed shapes in code. An error related to the other side is either an exception thrown by such a call or a check that depends on its returned data.
   So: Static analysis inserts hooks automatically. Exceptions thrown at a boundary are tagged with "who the subject is", so they are recognized no matter which layer catches them. The dataflow analysis is conservative: it would rather miss a point than blame the wrong subject.
3. **Under an indirection layer, a call returning does not mean success; wait for the completion signal**
   Insight: An interaction through a queue or callback is split into two places: issue (origin) and completion (sink). Only completion is real evidence.
   So: Record PENDING at issue, and confirm at the callback, the return of a blocking wait, a completion flag or the next hop. Too many PENDINGs downgrade to UNHEALTHY. A blocking call that never returns is also found, because it leaves a stale PENDING. This covers the ZooKeeper case that direct hooks miss.

## Evidence
- End to end (ZooKeeper, Cassandra, HDFS, HBase; 15 real gray failures reproduced): all detected, in 0.2–7 s, most under 3 s. The built-in detectors, Falcon and φ accrual detected only one case, at 86 s. Crash failures were all detected within 10 s, for example HBase master 1.5 s vs 11 s, HDFS datanode 6 s vs 30 s (declaring it dead takes 12 min).
- Novelty 1 → false positives: ZooKeeper ran for 25 h; of 797K verdicts, 705 (0.08%) were unhealthy, all within the first 22 s after startup. Localization: f1's negative observations point to the leader's serialization thread. The decision algorithm is not compared with other algorithms.
- Novelty 2 → each system needs only 16–65 annotations, and analysis finishes within 10 s. Overhead is under 3%, or 18% if positive hooks are not merged. How many observation points the analyzer misses is not measured.
- Novelty 3 → only the motivating case (missed by the original method). On the 15 cases there is no comparison with indirection handling on/off: no direct ablation.
- Gaps: failures were reproduced, not measured in production. The baselines compared are all detectors designed for crashes. Only Java is supported. It does not track causality, so cascading failures may point to the wrong subject. When many followers are themselves overloaded, they can wrongly judge a healthy leader as unhealthy.

## When it applies
The monitored component must have enough callers that call it often enough, and the failure must show up on their call paths. Failures that affect only internal state and are not noticed by callers, and components with no callers, cannot be seen.
