# Using Lightweight Formal Methods to Validate a Key-Value Storage Node in Amazon S3
SOSP'21 · James Bornholt, Rajeev Joshi, Vytautas Astrauskas, Brendan Cully, Bernhard Kragl, Seth Markle, Kyle Sauri, Drew Schleit, Grant Slatton, Serdar Tasiran, Jacob Van Geffen, Andrew Warfield / AWS, UT Austin, ETH Zurich, U. Washington · https://doi.org/10.1145/3477132.3483540
Paper type: verification / validation methodology in industry (experience paper)
> Spoiler: this card dissects the paper. Do not read it if you want to train on this paper.

## Dissection
- Background: ShardStore is S3's new storage node: a key-value store (keys are shard IDs, values are shard data) on one disk. It is an LSM tree with values stored outside the tree, on append-only extents, with background reclamation (garbage collection) and LSM compaction. It gets crash consistency from soft updates: writes go to disk in a dependency order, with no journal. A run-time `Dependency` type builds the order graph; every extent append takes and returns one, and `is_persistent()` tells whether an operation reached disk. The code is 44,048 lines of Rust, highly concurrent, changes all the time, is deployed continuously, and already holds hundreds of PB in a gradual rollout.
- Problem: The team wants to check deep properties: functional correctness of API calls, crash consistency of on-disk structures, and correctness of concurrent API calls and background tasks. The checks must keep working while the code and even the spec change, and they must be maintained by engineers with no formal-methods background after the experts leave. Full verification is too costly at this size and rate of change. Ordinary tests miss the bugs that matter.
- Challenges: (1) Proof-based verification costs 3–10× the code (VeriBetrKV: 7 lines of proof per line of code). (2) A spec written by experts in a modeling language (Alloy, SPIN, Yggdrasil-style Python, which the authors used at first) is a second artifact that nobody on the team will keep in sync. (3) The natural check, "model and implementation hold the same key-value map after every call", is too strong: a crash may legally lose recent writes, and concurrent calls overlap, so there is no "after every call". (4) The crash states are too many to list at block level, and exhaustive interleaving search does not scale: a small end-to-end test has tens of thousands of atomic steps, the largest over a million. (5) Random testing only reaches states the harness can reach, and a failing random run is too long to debug.
- Solution:
  1. Insight: specs go stale when only experts touch them. Engineers already must update unit-test mocks when they change code. → Design: for each component, write a reference model in Rust with the same interface but a trivial implementation (the LSM-tree index's model is a hash map; the models total 450 lines, 1% of the code). Use it as the mock in unit tests. → The spec is updated as part of normal work, or the build breaks.
  2. Insight: you do not need to imagine scenarios. Generate them, and let the model be the oracle. → Design: property-based testing. Random sequences of operations from an alphabet (API calls plus background tasks such as reclaim and clean reboot, which are no-ops in the model) run on both model and implementation, and outputs and the key-value map are compared after each step. The implementation runs on an in-memory disk. Arguments are biased only where there is evidence (sizes near the page size). Code coverage shows blind spots. The components are deterministic, so failures shrink automatically (bug #9: 61 operations → 6). IO faults are injected with a "has failed" flag: after a fault a get may return nothing but never wrong data. → Deep bugs are found with no hand-written scenarios, and the failures can be debugged.
  3. Insight: the soft-updates code already records which writes must reach disk before others, and can say if an operation is durable. That is the crash spec. → Design: add `DirtyReboot(RebootType)` to the alphabet. The reboot type chooses per component whether it flushes, and flush operations interleaved in the sequence give partly flushed states. After a dirty reboot: if a dependency says persistent, the data must be readable (persistence). After a clean reboot: every dependency must be persistent (forward progress). → Crash bugs (a missing edge or write in the graph) are caught with no block-level enumeration and no hand-written "what may be lost" model.
  4. Insight: overlapping operations can still be checked against the sequential model by asking whether the result equals some serial order (linearizability). Exhaustive search is only affordable for small code. → Design: Loom (sound, exhaustive, for the release/acquire memory model) checks small custom concurrency primitives. Shuttle (randomized, e.g. PCT; open-sourced by the authors) checks end-to-end harnesses that Loom cannot finish. → Concurrency gets checked at every scale, and the team knowingly trades soundness for scale.
  Also: Miri for undefined behavior in unsafe Rust; Crux proves deserializers cannot panic on any input up to a size bound, plus fuzzing for larger inputs.
- Evidence: 16 issues stopped before production (5 functional, 5 crash consistency, 6 concurrency), most about data integrity, one deadlock (#12). Tens of millions of random sequences run before every deployment. Validation code: models 450 + functional 4,860 + crash 2,661 + concurrency 901 lines, about 20% of the implementation (vs. 3–10× for verified systems). Ordinary unit/integration tests: 19,540 lines. Effort: two experts full time for nine months, a third for three months. Adoption: 18% of harness lines last edited by non-experts (git blame); three engineers wrote over 100 lines each, including crash checks; four engineers wrote their own model-checking harnesses; a harness is now a standard code-review question; engineers asked to make the tests release blockers. Block-level exhaustive crash states found no extra bugs and were much slower. Biasing toward production size and get/put distributions had no effect. Known miss: one cache bug caught in code review, because tests used a cache so large the miss path never ran. Not checked: concurrent crashing executions, resource exhaustion, message parsing, request routing, business logic, parts of the control plane.

## Reveal schedule
| Fact | Earliest stage |
|------|----------------|
| Storage node design (LSM tree, extents, reclamation, compaction), soft updates, Rust, 44K lines, fast change, replication across nodes | 1 |
| Ordinary tests pass, yet crash and race questions go unanswered; proofs cost 3–10×; experts are temporary; perf/availability already covered | 1 |
| The problem is to keep a spec of deep properties in sync with the code and owned by the team | 1 (learner should find this) |
| Spec as a simple same-language model that doubles as the mock | 2 (learner should find this after wall 1) |
| Random operation sequences checked against the model; bias, coverage, determinism, shrinking | 2 |
| Strict state equality fails under crashes and concurrency | 2 (wall) |
| `Dependency` / `is_persistent` as the crash spec; coarse per-component crash states | 2 (hint) |
| Linearizability against the same model; exhaustive for small code, random for large | 2 |
| Names ShardStore, Shuttle, Loom, DirtyReboot; bug catalog; line counts of validation code; adoption numbers | 3 |

Protected terms: "lightweight formal methods" (3), ShardStore (3), "reference model" (2, only after the learner proposes something like it), "property-based testing" (2, after the learner proposes random sequences), "refinement" (2), `Dependency` / `is_persistent` (2, as the hint for idea 3), Shuttle, Loom, DirtyReboot (3).
Safe background: LSM trees, WiscKey-style key/value separation, soft updates vs. journaling in general, append-only zones, garbage collection, mocks and unit tests, fuzzing, QuickCheck as a general idea, model checking and TLA+/Alloy in general, linearizability, Rust's safe/unsafe split and data-race freedom.

## Stage 1: Find the problem
### Background to give
You work on the team building a new storage node for a large cloud object store. A node runs one key-value store per disk: keys are shard IDs, values are shard data. Data sits in chunks on append-only disk regions (extents); an LSM tree maps each shard to its chunks, and is itself stored as chunks. Background reclamation copies live chunks off an extent and resets it; LSM compaction runs at the same time. For crash consistency the node orders its disk writes (soft updates), with no journal. It is about 44,000 lines of Rust. Changes ship continuously, the design is still being iterated, and the node already stores hundreds of petabytes in a gradual rollout. Leadership has lent you two formal-methods experts for nine months.

### Phenomena
1. In a design review of a planned reclamation change, a reviewer asks: "If we crash after page 0 of a chunk is on disk but page 1 is not, and the next chunk is then written starting at page 1, can reclamation later skip the second chunk and reset the extent?" Nobody can answer. The reclamation unit tests all pass. The unit and integration test suite is 19,540 lines.
2. Pre-production load tests and the staggered-deployment dashboards show the node meets its latency and availability targets.
3. A teammate argues that single-node crash bugs cannot lose customer data, since each shard is replicated across several nodes. The on-call lead answers that a node that comes back wrong, or loses its whole disk, triggers large repair traffic and IO across the fleet, and sometimes needs an operator to step in.
4. Your lead reads the verified storage papers (FSCQ, Yggdrasil, VeriBetrKV). They report 3–10× proof overhead over the code; VeriBetrKV reports 7 lines of proof per line of implementation. The interface between the LSM tree and the chunk store changed again this month. None of the engineers has used a proof assistant or any other formal method.
5. The experts start by writing a model of the chunk store in Alloy and SPIN, and plan to build a tool that checks the Rust code against it. At a planning meeting someone asks who updates the model after the experts' nine months end. No engineer volunteers.
6. A code review of an LSM compaction change asks: "What if reclamation runs on an extent after compaction has written a new chunk there, but before compaction has recorded that chunk in the tree's metadata?" The code compiles, Rust rules out data races in safe code, and the concurrent stress test passes on every CI run. The reviewer approves after reading the code twice.

Tutor notes: 1 and 6 are the core ones (the bugs that matter are deep crash and interleaving cases that hand-written tests do not reach). 4 is the constraint that rules out full verification. 5 is the constraint that rules out the "experts write a separate model" fix. 3 says crash consistency matters even with replication. 2 is the distractor: performance and availability are already covered by load tests and staged rollout, and are out of scope.

### Hint ladder
- L1: In phenomena 1 and 6, the tests pass and the reviewer still has no answer. What would you need in hand to answer such questions by machine, not by reading code?
- L2: Phenomena 4 and 5 each rule out one way to get that. What does each cost, and who pays it after the nine months?
- L3: You need something that says what correct means for crashes and interleavings, can be checked against the real code, and is ___ by the people who change the code every week. Fill the gap and state the problem.
- Bottom-out: state the target below.

### Target
The node needs checks of deep properties (functional correctness, crash consistency, concurrency) that hand-written tests do not reach, on 44K lines of code that change all the time. Full verification costs several times the code, and the team cannot sustain it. An expert-written model in a separate language will not be kept in sync once the experts leave. The problem: find a way to specify and check these properties that is automated, cheap enough to keep up with the code, and owned by the engineers themselves.
Checklist:
- [core] The bugs that matter are crash-state and interleaving cases that unit tests miss.
- [core] Proofs are ruled out by cost and the rate of change.
- [core] The spec must stay in sync with the code and be maintained by non-experts after the experts leave.
- [detail] Crash consistency matters even with cross-node replication (repair cost, operator load).
- [detail] Accepting weaker guarantees than proof is acceptable.

### Common wrong turns
- "Write more unit tests for these cases" → Phenomenon 1 needed a page-boundary spill, a specific crash, and a later chunk at the same spot. How many such cases would you have to think of in advance?
- "Prove it anyway, just the core" → Phenomenon 4: the core interface changed this month. Who updates the proof next month?
- "It's a performance or rollout issue" → Phenomenon 2 is green. Is anything in 1 or 6 about speed?
- "Replication makes this moot" → Phenomenon 3: what does a bad recovery cost the fleet?

## Stage 2: Derive the solution
### Seed hint
Think about what engineers already keep up to date without being asked, and why they do it.

### Path
1. Learner proposes a model in TLA+/Alloy, checked by experts. Wall (phenomenon 5, the authors' own first attempt): a second artifact in a second language has no owner after the experts leave. Ask: which test artifacts break the build when the code changes, so engineers must fix them?
2. Learner finds: write the spec as a simple implementation of the same interface, in Rust, in the same code base, and use it as the mock in unit tests. Fork: one model of the node's public API, or one per component? The paper chose per component: it is easier to drive corner cases and fault paths through internal APIs, and easier to debug.
3. Learner proposes hand-written tests that compare the model and the code. Wall: phenomenon 1 needs a combination nobody would write down. Ask: who could choose the scenarios for you? Learner proposes random operation sequences run on both, compared after each step, with background tasks in the alphabet as no-ops in the model. Sub-walls: random keys almost never repeat, so gets rarely hit (bias toward earlier keys); a failing run of 61 operations is hard to debug (shrinking, which needs determinism: even Rust's HashMap iteration order is random); new code such as a cache may be unreachable (coverage). Also ask: should you bias toward production traffic? (The paper tried it: no effect. Bias only with evidence.)
4. Learner proposes the check "same key-value map after every call" for crashes too. Wall: after a crash, recent writes may legally be gone. Which ones? Naive fixes: list every block-level crash state (dramatically slower, and in the paper it found no extra bugs); or teach the model the effect of each IO (fragile, costly to maintain). Ask: which part of the system already decides, at run time, which writes must reach disk first?
5. Learner finds: the write-order graph can say whether an operation is durable. Check that anything it calls durable is readable after a crash, and that after a clean shutdown everything is durable. Then crash states can be coarse: per component, flush or not, plus flush operations mixed into the sequence. Probe: is it circular to take the spec from the implementation? (No: the check catches a graph that is too weak; forward progress catches one that never completes. It does not check that the graph is minimal.)
6. Learner tries the same per-call comparison for concurrency. Wall: calls overlap, so there is no "after the call". Learner proposes linearizability against the same model. Wall: exhaustive interleaving search hits tens of thousands of atomic steps in a small test and over a million in the largest. Learner proposes exhaustive search for small primitives and random schedules for end-to-end tests, and names the price: random search can miss bugs.
Also discuss: injected IO errors make the strict comparison fail, because one call may do three IOs and only one fails. Tracking every possible model state blows up. The paper uses a "has failed" flag: after a fault, a get may return nothing but never wrong data. Run with and without injection.

### Hint ladder
Idea 1 (spec = same-language simple model, reused as mock):
- L1: In phenomenon 5, what is different between the Alloy model and the unit tests, from an engineer's point of view?
- L2: When an engineer changes the LSM tree's interface, what do they have to update before the build passes?
- L3: What is the simplest thing that behaves like the index, if you ignore disks and performance? Where else could that thing be used?
- Bottom-out: write a trivial Rust implementation of each component's interface (the index is a hash map) and use it as the unit-test mock, so engineers must keep it current.
Idea 2 (random sequences against the model):
- L1: In phenomenon 1, who would have had to think of that scenario?
- L2: If you have a second implementation that is obviously right, what can you compare it with, and on which inputs?
- Bottom-out: generate random sequences of API and background operations, run them on both, and compare after each step; add bias, coverage and shrinking.
Idea 3 (the write-order graph is the crash spec):
- L1: After a crash, your model must know which writes may be gone. Who in the system already knows that?
- L2: The soft-updates code passes an object into every disk append and gets one back. What can you ask that object?
- L3: If it says "this put is on disk", what must be true after reboot? And what must be true after a clean shutdown?
- Bottom-out: each mutating call returns a `Dependency`; after a dirty reboot, anything `is_persistent()` must read back correctly; after a clean reboot, all must be persistent. Crash states are chosen per component, with flushes mixed in.
Idea 4 (concurrency by linearizability, tool chosen by scale):
- L1: Two calls overlap. What sequential history could the model compare against?
- L2: Your exhaustive checker does not finish on the end-to-end test. Which code truly needs every interleaving checked?
- Bottom-out: check linearizability against the model; exhaustive search for small primitives, random schedules for end-to-end harnesses, and accept that the second can miss bugs.

### Target
1. Specs drift when only experts own them. Write each component's spec as a trivial Rust implementation of the same interface and reuse it as the unit-test mock, so engineers keep it current as part of normal work.
2. Check conformance with random operation sequences on model and implementation; biased only with evidence; coverage to find blind spots; deterministic code so failures shrink.
3. Equality fails after a crash. The implementation's own write-order objects say what is durable, so check persistence after dirty reboots and forward progress after clean ones, with coarse per-component crash states.
4. Equality has no meaning under overlap. Check linearizability against the same model; exhaustive for small primitives, random for end-to-end tests.
Checklist:
- [core] Spec in the implementation language, simple, reused as mock, so it stays current.
- [core] Generated operation sequences compared against the model, not hand-written scenarios.
- [core] The crash spec comes from the implementation's persistence tracking; why that is not circular.
- [core] Linearizability for concurrency; a soundness-versus-scale choice of tools.
- [detail] Bias, coverage, determinism and shrinking; per-component models; relaxed checks after injected IO faults.

## Stage 3: Design the experiments
### Summary to give
Problem: ShardStore, S3's new storage node (44K lines of Rust, soft updates, heavily concurrent, changing all the time), needs checks of functional correctness, crash consistency and concurrency that outlast the formal-methods experts. Method (lightweight formal methods): each component has an executable reference model in Rust (1% of the code) that is also its unit-test mock. Property-based testing checks that the implementation refines the model on random operation sequences. For crashes, `DirtyReboot` operations are added to the sequences, and the `Dependency` objects returned by soft updates define what must survive. For concurrency, linearizability is checked with Loom (exhaustive, small code) and Shuttle (randomized, end-to-end). There are no speedup plots here. Ask the learner: what evidence would convince a reviewer that a validation method works?

### Key research questions
1. Does it find real, serious bugs that the existing tests missed? Without this, nothing else matters. A reviewer wants bugs that would have shipped, not toy bugs.
2. What does it cost to build and keep running? The whole claim is "cheaper than proof". The cost must be measured against proof and against the existing tests.
3. Does it survive the experts leaving? This is the paper's main bet (idea 1). It needs evidence that non-experts maintain and extend it.
4. What does it miss, and do the design shortcuts lose bugs? Coarse crash states, random schedules and biasing all trade coverage for speed. A reviewer wants their cost shown, plus an honest list of what was missed.

### Key experiments
1. Bugs found. Paper: a catalog of 16 issues stopped before production (5 functional, 5 crash consistency, 6 concurrency), across most components, mostly data integrity, plus one deadlock (#12). Two are walked through: #10, a crash bug that needs a UUID whose tail equals the magic bytes, a chunk that just spills onto a second page, and a crash losing only that page (found locally before code review); and #14, a race between reclamation and compaction that loses index entries (found by Loom before code review). The count covers only bugs blocked in CI; more were caught locally, by anecdote only. Weak designs: counting bugs without saying whether the existing 19,540-line test suite would have caught them; no severity; no baseline tool run on the same code versions. The paper itself has no head-to-head against ordinary testing; push the learner to propose one (e.g. replay old buggy commits against the old test suite).
2. Cost. Paper: lines of code per artifact: models 450, functional checks 4,860, crash checks 2,661, concurrency checks 901, about 20% of the implementation, vs. 3–10× in verified systems. The checks are ordinary Rust unit tests. Initial effort: two experts full time for nine months, plus a third for three months. Weak designs: lines of code only, without person-months; comparing with proof overhead but not with a modeling-language approach (the paper has no such comparison); no CPU cost of running tens of millions of sequences before each deployment.
3. Adoption. Paper: 18% of harness lines last edited by non-experts (git blame, which the authors call crude); three engineers wrote over 100 lines each, including crash checks for new features; four wrote their own model-checking harnesses; a harness is now a standard review question; engineers asked to make the checks release blockers. Weak designs: one snapshot in time instead of a trend; git blame counts edits, not new properties; no survey of how long a new harness takes to write.
4. Limits and ablations. Paper: block-level exhaustive crash states found no extra bugs and were dramatically slower (an ablation for the coarse crash states). Biasing toward production distributions had no effect. Shrinking cut bug #9 from 61 operations (9 crashes, 14 writes, 226 KiB) to 6 (1 crash, 2 writes, 2 B). One known miss: a cache-miss bug caught only in code review, because tests used a huge cache; it led to the coverage metrics. Out of scope: concurrent crashing executions, resource exhaustion (no oracle), message parsing, routing, business logic, some control-plane operations. Shuttle's miss rate is not measured. Weak designs: reporting only successes; no ablation of the random schedules; no seeded-bug study to estimate what the checks miss.

### Reviewer probes
- Is 16 a lot? Out of how many bugs found by all methods in the same period?
- Two of the 16 (#9, #15) are listed as bugs in the reference model itself. What does that say about who checks the spec? (The paper mentions early proofs about the models with Prusti.)
- The crash spec comes from the implementation's own `Dependency` graph. Which bug class does this check never catch? (A dependency stronger than needed passes. Persistence only catches a graph that is too weak.)
- How would you show that random schedules find races that matter, not only easy ones?
- Would this work on a team without a strong mocking culture, or in a language with no ownership types to keep the model simple?

## Stage 4: Apply and extend
### Scenarios
1. A journaled store. Setup: another team's node uses a write-ahead log and fsync, with no per-operation write-order objects. Question: what plays the role of the crash spec now? Good directions: expose the last durable log position as the oracle (every operation acknowledged at or before it must survive, later ones may vanish but only as a suffix); check that recovery yields a prefix of the log; note that this is a weaker, coarser spec than per-operation dependencies, and say which bugs it would miss.
2. Crashes during concurrency. Setup: the paper does not check concurrent crashing executions; it found no effective automated way. Question: design one. Good directions: crash at a random point inside a random schedule; the spec becomes "the recovered state equals some linearization of the operations whose dependencies were persistent, plus any subset of in-flight ones"; discuss why the set of allowed states grows fast and how per-component coarse crash states might keep it small.
3. Resource exhaustion. Setup: running out of disk space is not tested, because there is no oracle: real leaks look like expected overhead from metadata, checksums and alignment. Question: how would you build an oracle? Good directions: a space-accounting reference model with a bound on overhead per byte stored; a differential check that space returns to a baseline after delete-all plus reclaim; ideas from resource analysis, which the paper names as future work. A good answer says which real bug (e.g. a space leak) each check catches and which false alarms it raises.
