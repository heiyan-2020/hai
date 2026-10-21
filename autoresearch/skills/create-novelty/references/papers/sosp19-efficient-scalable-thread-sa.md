# Efficient Scalable Thread-Safety-Violation Detection
SOSP'19 · Guangpu Li, Shan Lu et al. / UChicago, Microsoft Research, UC Berkeley · Full text: https://6826.csail.mit.edu/2020/papers/tsvd.pdf (camera-ready, copy on the MIT 6.826 course website) · Selected: Best Paper

**One sentence**: Watch only calls to thread-unsafe objects. Conflicting calls that narrowly miss each other in time are the candidates, and whether an injected delay passes to the other thread tells you whether the two are ordered.

## Problem
A TSV (thread-safety violation) is when two threads concurrently call methods of the same thread-unsafe object and at least one is a write, for example both calling Add on a Dictionary at the same time.
Microsoft's integrated build and test environment runs unit tests for thousands of teams and tens of thousands of modules, and the code makes heavy use of async/await. A detection tool must have zero false positives, low overhead, and give results in one or two runs.

## Strawman / Baseline
- **Happens-before (HB, the order between two operations determined by synchronization) analysis**: must recognize every synchronization operation: locks, fork/join, volatile, async/await, custom synchronization. Missing one edge causes false positives; one extra edge causes misses. Tasks can be joined arbitrarily, and there are more synchronization operations than calls being checked. The authors' HB variant (TSVD-HB) has 310% overhead, of which HB analysis is 270%.
- **Random delay injection (DataCollider, DynamicRandom)**: most delays land in single-threaded phases or on accesses already under a lock, slowing tests for nothing; one bug often needs dozens of runs to trigger. DataCollider overhead 378%, DynamicRandom 178%.
- **Analyze first, then inject (RaceFuzzer, CTrigger)**: at least two runs, and the analysis also depends on modeling synchronization.

## Novelty
1. **Only conflicting calls that "almost collided" are worth delaying**
   Insight: If two conflicting call sites never come close in time during intensive testing, program semantics or synchronization most likely keeps them apart. Conversely, conflicting calls on the same object from different threads less than δ apart (default 100 ms), called near misses, are just short of overlapping.
   So: Instrument only the API calls of thread-unsafe classes (14 classes, 123 APIs), and ignore synchronization operations. After a near miss is found, set a trap at this pair of locations and inject a delay. If another thread runs into it during the trap, the stacks of both threads are captured on the spot, so there are no false positives.
   This avoids both the modeling cost of HB analysis and random injection's "delays in the wrong place".
2. **Use the injected delay itself to probe ordering**
   Insight: Many near misses are actually protected by the same lock. If loc1 happens-before loc2, then a delay before loc1 also holds back the thread at loc2 by the same amount.
   So: Watch whether the other thread shows a long pause during the delay (≥0.5× the delay and overlapping it). If it does, infer that the two are ordered and prune this pair of locations. Without modeling any synchronization mechanism, this removes the false candidates of item 1.
3. **Bug locations execute repeatedly, so discovery and injection can happen in the same run**
   Insight: The same bug location occurs 35.6 times on average (median 4), so after a near miss there are more chances for it to happen again.
   So: Start injecting as soon as a near miss is found, instead of using two separate runs as RaceFuzzer does. Remaining candidates are written to a file for a second run, to cover points that execute only once. Injection probability decays with failures, to avoid waiting in vain at hot spots.

Other design: Detecting concurrent phases only reduces overhead (without it: 54 bugs, 61% overhead).

## Evidence
- End to end: 1,134 bugs found across 1,657 projects, about 43K modules and 122K tests (1,009 from TSVD itself). All 80 checked by four teams were real, 77 were previously unknown, and 38 were high priority. For one team, TSVD found 15 in 3 months while regular testing found none. Comparison on 1000 modules (two runs): TSVD found 53 bugs at 33% overhead; TSVD-HB 41 at 310%; DataCollider 25 at 378%; DynamicRandom 13 at 178%.
- Novelty 1 → removing the time window (any past conflict counts as a near miss): bugs drop from 53 to 46, overhead rises from 33% to 143%.
- Novelty 2 → removing HB inference: bugs drop to 45, overhead rises to 84%; see also the TSVD-HB comparison.
- Novelty 3 → the first run found 42/53, about 80% of the total found by all tools; the 11 new ones in the second run were all at points that execute only once. No same-setting comparison with "two separate runs": no direct ablation.
- Gaps: Ground truth is only the union of 79 bugs found by 4 tools over 200 runs. TSVD missed 26 in two runs: 19 because the two calls rarely come close, 2 because of wrong HB inference, 5 because the delay was too short.

## When it applies
Conflicting calls must occasionally come close (within a hundred milliseconds) in ordinary tests, and the object's thread-safety contract must be expressible as sets of read/write APIs. Timing bugs on persistent data are out of scope.
