# Experiment playbook: how top-venue papers prove their novelties

Source: the "experiment evidence structure" and "weaknesses reviewers will attack" parts of the breakdown of 100 OSDI/SOSP papers. `<id>` maps to `papers/<id>.md`.
Core principle: each novelty needs its own piece of evidence that shows "the gain comes from it, not from something else". A big end-to-end number only shows that the system is good. It does not show that the insight is right.

## 1. Evidence ladder

Design the experiments in this order. Each level answers one reviewer question.

### Level 1: Motivation measurement. Are the root cause and the fact real?
- **What to do**: quantify the baseline's root cause (where the time goes). Then quantify the fact the insight depends on (degree of skew, event frequency, source of variance, cost ratio).
- **What reviewers expect**: real workloads or real traces, not the workloads used for evaluation; numbers, not adjectives; and a statement of how widely the fact holds.
- **Good examples**: `osdi22-xrp` breaks out the file system at 32% and user/kernel switching at only 5.6%, and measures that an extent changes only once every 159 s on average. `osdi18-legoos` measures that 90% of memory accesses fall in 0.06% of memory. `osdi18-gandiva` measures a 77× gap between peak and trough memory. `osdi24-servicelab` uses ANOVA to show that 3 factors explain R² 0.87, close to the upper bound of 0.89 given by the full hardware model. `osdi16-fasst` measures zero packet loss under heavy traffic over a long time.
- **Common gaps**: the breakdown uses numbers from the literature, not measurements (`osdi16-network-requirements-for`); only the side where the fact holds is measured, not the cases where it changes (XRP does not measure behavior when the layout changes).

### Level 2: End to end. Compare with the strongest, fairest baseline
- **What to do**: on the same hardware, run real applications or standard workloads against the strongest open-source, tuned competitor. Report the real target metric (goodput, time-to-accuracy, capacity under an SLO, not just throughput).
- **What reviewers expect**: the baseline is the one widely accepted as strongest; hardware, transport layer, kernel version and dataset size are all the same; the baseline gets equal tuning; results are also reported in the region where the baseline is strong.
- **Bracket both ends**: besides the strongest competitor, add a naive end point and an ideal upper bound, and show how close you get to the upper bound. Examples: `osdi21-mage` compares with OS paging and with unlimited memory; `osdi20-performance-optimal-read-onl` uses the same store without transactions as the cost upper bound; `sosp17-resource-central` compares with no oversubscription and with blind oversubscription. Note: bracketing only shows where you stand. It does not replace the ablation in level 3.
- **Good examples**: `osdi24-distserve` reports the request rate per GPU that meets the SLO; `sosp19-pipedream` reports the time to reach the target accuracy; `osdi21-oort` splits time-to-accuracy into "number of rounds × time per round".
- **Counterexample**: `osdi16-tensorflow` reports only throughput. It does not quantify the cost of weak consistency.

### Level 3: Ablation of each novelty. Does the gain really come from this design?
From most to least convincing:
1. **Swap in the strawman in the same system**: replace only this design with the baseline's approach and keep everything else the same. This puts the root cause back into your own system and measures again. Examples: `sosp19-nexus` swaps in batch-oblivious scheduling; `sosp21-kangaroo` replaces RRIP with FIFO; `osdi23-enso` uses a Chaotic variant that shuffles the gaps between messages; `osdi16-gemini` swaps in hash partitioning; `osdi20-serving-dnns-like-clockwork` compares concurrent and serial execution; `osdi16-scone` compares sync and async; `sosp25-cortenmm` compares a reader-writer lock version with a lock-free traversal version.
2. **Give the baseline the same unrelated optimizations, then compare**. This rules out "the gain comes from tuning or add-on parts". Examples: `osdi24-distserve` also enumerates the best parallelism for colocated serving in simulation (vLLM++); `sosp17-pebblesdb` adds the same filters to the baseline; `osdi22-memliner` still gains after the prefetcher is replaced with the stronger Leap.
3. **Add one at a time**: start from the baseline, turn on each mechanism in turn, and look at the gain of each step. Examples: `sosp24-powerinfer` (sparsity only → random placement → placement by hotness); `osdi24-taming-throughput-latency-tr` (hybrid only / chunking only / both); `sosp19-splitfs`; `sosp17-my-vm-is`; `osdi20-sundial`; `osdi18-orca` even shows a side effect (adding derived graphs raises recall but lowers MRR; adding risk ranking then brings MRR back up).
4. **Split the total gain into factors you can explain**: `osdi21-oort` (number of rounds × time per round); `sosp19-pipedream` (bytes communicated); `osdi18-the-benefits-and` (accounting for each check the compiler inserts).

**Things that are not ablations** (reviewers will point these out):
- A knob sweep (k, number of lanes, number of backups, threshold) is not a with-and-without comparison, unless the sweep includes the point "0 = design removed" (Δ=0 in `osdi16-ec-cache`).
- Attribution inferred by subtracting the other parts from the total (`osdi18-gandiva`).
- Turning designs off one by one cumulatively, so each contribution depends on the order (`sosp19-nexus`).
- Turning two mechanisms on and off together (`osdi18-noria` and `sosp19-scaling-symbolic-evaluation` have only an all-or-nothing switch).
- A static metric in place of a runtime metric (most ablations in `osdi20-hxdp` look only at static instruction count).
- Similar code taken from another project, rather than the same code with the design removed (`sosp25-atmosphere`).

### Level 4: Sensitivity and breaking point. Where does it stop working?
- **What to do**: sweep the strength of the fact the insight depends on (skew, write ratio, how far readers lag, local memory ratio, load, scale). Plot the point where the gain drops to zero or turns negative. For designs that relax a guarantee, also test the failure path on its own.
- **What reviewers expect**: report the ranges where you lose, without being asked. The knee of the curve should match the insight's premise exactly. This makes the conclusion more credible, not less.
- **Good examples**: `sosp17-netcache` reports that the gain disappears when the write ratio exceeds 0.2; `sosp25-rearchitecting-the-thread` reports almost no gain with a hash index and uniform load; `sosp24-lazylog` reports that reads get slower when readers do not lag; `osdi16-coordinated-and-efficient` reports a slowdown when there is no fragmentation; `osdi16-gemini` reports losing to Ligra on BFS; `sosp23-efficient-memory-management` reports that the new kernel is 20–26% slower; `sosp21-linefs` reports that latency doubles when the system is idle; `osdi18-the-benefits-and` uses a sweep to give the conditions under which GC gets expensive.
- **Failure path**: `sosp21-linefs` injects host crashes; `osdi18-the-benefits-and` has a malicious process exhaust the kernel heap again and again for 25 minutes; `sosp23-enabling-high-performance-an` designs 134 attack and corruption scenarios.

### Level 5: Applicability. Is the idea general?
- **What to do**: show it across several platforms, workloads or systems under test. Quantify the cost of generality (person-days to port, extra work for each new target or platform).
- **Good examples**: `osdi18-tvm` covers 4 kinds of hardware; `sosp19-a-generic-communication` covers 5 framework × architecture × transport combinations; `sosp23-validating-jit-compilers` tests 3 real systems; the optimizations of `sosp19-scaling-symbolic-evaluation` are reused directly on a second system; `osdi24-anvil` takes 2 person-months for the first controller, then 2 person-weeks for each one after that.
- **Common gaps**: the only evidence of generality is lines changed, or the porting experience of a single person (`sosp21-the-demikernel-datapath`).

## 2. Evidence for each kind of paper

### Systems / performance papers
The main evidence is level 2 plus level 3. Minimum: the strongest baseline on the same hardware, plus one "swap in the strawman" or add-one-at-a-time control for each novelty. If you use a simulator, report the error between simulation and real machines (`osdi24-distserve` reports <2%), and reproduce at least one key conclusion on real machines. ML systems must report a quality metric (time-to-accuracy, accuracy, perplexity), not only throughput (counterexample: `osdi16-tensorflow`; if there is an accuracy loss, report it, as `sosp24-powerinfer` does).

### Bug-finding / testing papers
- Main evidence: the number of new bugs, and how many are confirmed and fixed (`sosp24-ozz`, `osdi26-valscope`, `sosp23-validating-jit-compilers`).
- Show that the mechanism works: revert historical patches and reproduce the known bugs (`sosp24-ozz`); rewrite the bugs found into the test form of each baseline, and see which ones only your tool catches (`osdi26-valscope`).
- Compare with existing tools on the number of **deduplicated bugs** under the **same budget**. Artemis counts "seeds with inconsistencies" (154 vs 21) and does not compare with fuzzers under the same budget. Reviewers attack this.
- Must report: the false positive rate (ValScope lacks it); where the ground truth comes from (the ground truth of `sosp19-efficient-scalable-thread-sa` is the union of several tools; the "errors" of `sosp17-deepxplore` are not confirmed by hand); an ablation of each search heuristic (TSVD removes the time window and removes delay inference; this is a good example).
- The bug set must not come from the same source as the bugs that inspired the design (`osdi16-early-detection-of`).

### Verification papers
- Main evidence: proof/code ratio, person-months, verification time, and performance on par with the unverified version (`osdi24-anvil`, `sosp25-atmosphere`, `osdi24-verismo`).
- Extra credit: real bugs found during verification and then fixed (the vulnerabilities `osdi24-verismo` found have been fixed by the vendor; `osdi24-anvil`); the effort for later increments (Anvil drops from 2 person-months to 2 person-weeks).
- Reviewers will always ask:
  (1) Is the spec strong enough? Do mutation testing to show that the verifier rejects wrong code. `osdi16-push-button-verification-of`, `sosp17-komodo`, `sosp25-atmosphere`, `sosp25-cortenmm` and `osdi24-verismo` all lack this.
  (2) How large is the trusted base (spec, solver, environment model, hardware model, integration code)?
  (3) Is the verified code the real code, not a ported copy (CortenMM verifies a copy)?
  (4) Compare effort with other verification methods: use the same target, and record the human effort spent on trial and error, not just the final line counts (`osdi25-basilisk`).
  (5) Is there a held-out set? Basilisk was developed on the first 6 protocols, and its held-out set has only 10.

### Measurement studies
- Main evidence: distributions and correlations on large-scale, unsampled data (`osdi20-a-large-scale`), or a controlled comparison that differs in only one variable (`osdi18-the-benefits-and` changes the critical paths of the two systems until they match line by line).
- Must do: test at least one implication in an experiment or a simulation. Twitter did not simulate "how much timely expiry would save"; the software overhead breakdown in `osdi16-network-requirements-for` uses numbers from the literature.
- Data should come from several sources (a single company is a standing weakness). The numbers in the text must match those in the figures and tables (`osdi16-network-requirements-for` and `osdi23-triangulating-python-perform` were both caught with mismatches).
- Incident studies: others must be able to check the classification criteria, and reproduction must go beyond small programs on one machine (`osdi22-metastable-failures-in`).

### Security papers
- Main evidence: attack or injection experiments that show "it really blocks the bad thing". Good examples: all 134 scenarios in `sosp23-enabling-high-performance-an` are detected; the adversarial stress test in `osdi18-the-benefits-and`.
- The common gap is having only arguments or proofs: `osdi16-ryoan`, `osdi25-building-bridges`, `sosp17-the-efficient-server`, `osdi20-byzantine-ordered-consensus` and `osdi18-graviton` have no attack experiments; `sosp17-my-vm-is` claims "more secure" in its title but argues only from interface size.
- The hardware must really provide isolation. The prototype hardware of `sosp17-komodo` does not provide real isolation; `osdi16-ryoan` uses an emulated SGX v2.
- State the gaps in the threat model (side channels, DoS, Sybil, poisoning), and where the extra overhead comes from.

### Production / experience papers
- Main evidence: multi-year deployment statistics (`osdi24-servicelab` 5 years, `sosp24-fbdetect` 7 years), before-and-after comparisons (`osdi20-virtual-consensus-in` p99 drops 5–10×, `osdi16-kraken`), timelines of real incidents (`osdi18-maelstrom`).
- Standing weaknesses: no with-and-without control for the core design; true and false positives rely on developer labels, and false negatives are estimated indirectly; the jobs in the before and after periods differ and the system keeps changing, so the two cannot be compared (`osdi20-antman`, `osdi16-kraken`); the "control" is computed, not actually run (`osdi18-maelstrom` adds up the time of each service to estimate how much slower serial execution would be).
- Remedies: run a controlled A/B test on at least one key design, or use trace-driven simulation for a with-and-without comparison (the core gain of `sosp24-fbdetect` is validated only in simulation; this also gets attacked, but it is better than nothing); build ground truth with A/A experiments and injected known effects (`osdi24-servicelab`).

## 3. Weaknesses reviewers will attack, and how to guard against them in advance

| Weakness | Examples | How to guard against it in the design |
|---|---|---|
| The baseline is reimplemented or simulated by the authors, or is an "optimistic version" | `sosp21-kangaroo`, `osdi18-the-fuzzylog`, `sosp19-nexus`, `sosp23-efficient-memory-management`, `osdi20-caladan` (it also fitted the competitor with its own components), `sosp21-linefs`, `osdi24-taming-throughput-latency-tr`, `sosp24-lazylog`, `sosp19-pipedream`, `osdi24-infinigen`, `sosp19-efficient-scalable-thread-sa` | Prefer open-source competitors. If you must rewrite one, calibrate your implementation against the numbers in the competitor's paper, release the code, and state where your version favors the competitor |
| Citing published numbers, or comparing on different hardware | `osdi16-fasst`, `osdi18-ray`, `osdi23-enso` (FPGA vs ASIC), `osdi20-serving-dnns-like-clockwork`, `sosp17-komodo` (compares with SGX across platforms and clock speeds), `osdi20-virtual-consensus-in`, `sosp21-ghost` (different kernel versions) | Same machine, same kernel, same transport layer. If you cannot, downgrade it to a "qualitative comparison" and use the same-hardware ablation as the main evidence |
| Different comparison conditions: transport layer, RPC stack, billing basis | `osdi20-aifm` (TCP vs RDMA), `sosp24-lazylog` (RPC stack), `osdi18-pocket` (billing basis), `osdi20-a-unified-architecture` (the baseline did not get equal RDMA tuning) | Unify the shared layers; or give the baseline the same low-level optimizations, then compare |
| Only simulation or emulation; key hardware is not available | `osdi18-legoos`, `osdi16-ryoan`, `sosp17-strata`, `osdi18-graviton`, `osdi16-just-say-no-to-paxos-overhea`, `osdi21-oort` (even the clock is simulated), `sosp17-resource-central`, `sosp21-faster-and-cheaper`, `sosp17-netcache` (rotates a few machines to emulate a large scale) | Report the error between simulation and real machines; mark which paths are emulated; reproduce at least one key conclusion on real machines; do not present "computed" as "measured" (the MTTF of LegoOS) |
| Treating a knob sweep as an ablation | `osdi20-hxdp` (number of lanes), `osdi16-ec-cache` (k), `osdi16-tensorflow` (number of backups), `osdi18-legoos` (cache size), `osdi24-infinigen` (α and column ratio) | The sweep must include the "design removed" point; also do a separate strawman swap |
| The gain is mixed with unrelated engineering optimizations | `sosp19-nexus` (CPU/GPU overlap alone gives 7.4×), `osdi20-ansor` (weight layout rewrite), `sosp19-a-generic-communication` (load balances naturally after sharding), `sosp21-ghost` (topology-aware placement), `sosp19-snap` (protocol, MTU, copies), `osdi20-byzantine-ordered-consensus` (implicit batching), `sosp23-enabling-high-performance-an` (borrowed delegation threads), `osdi16-netbricks`, `osdi18-noria`, `osdi20-hxdp` (no PCIe crossing) | First list all optimizations that are not novelties. Turn each on and off separately, or add them to the baseline too. State their share explicitly in the text |
| No with-and-without control for the core design | `osdi24-servicelab`, `sosp17-canopy`, `sosp21-the-demikernel-datapath`, `osdi21-mage`, `osdi18-ray`, `sosp24-lazylog`; later novelties lack it most often (the mapping cache of `osdi22-xrp`, the static locks of `osdi25-building-bridges`, the weight stashing of `sosp19-pipedream`) | In the experiment plan, give each novelty one row: "expected result after removing it or swapping in the strawman". This includes the 2nd and 3rd novelties added to deal with new costs |
| Confounders in production before-and-after comparisons | `osdi20-antman`, `osdi16-kraken`, `osdi20-virtual-consensus-in` (the gain is mixed with machine and hardware upgrades), `osdi26-teaching-the-old-dog-new-tri`, `osdi18-maelstrom` | Use a concurrent control (turn it on in some clusters and not in others), or use trace replay for a with-and-without comparison. Write down what else changed during that period |
| Evaluating on the data that inspired the design, or selection bias | `osdi16-early-detection-of` (the bug set comes from the same source as the study), `osdi25-basilisk` (development and evaluation sets overlap), `osdi20-firm` (training and testing use the same injector), `osdi18-orca` (evaluates only the subset where the root cause can be filled in by hand) | Set aside a held-out set from the start. Take test workloads or faults from a different source |
| The workload is tailored to the method, or is synthetic | `osdi22-xrp` (BPF-KV), `osdi16-coordinated-and-efficient` (workload modified to highlight the effect), `osdi24-distserve` (Poisson arrivals, self-chosen SLOs), `osdi18-gandiva`, `osdi16-ec-cache` (synthetic Zipf) | Use accepted workloads and real traces for the main results. Use tailored workloads only to show the mechanism |
| The baseline is a hypothetical lower bound or an estimate | `sosp17-the-efficient-server` ("run it again"), `osdi18-orca` (estimated engineer effort), `osdi20-sundial` (uncertainty filled in by a formula) | Find a competitor that really runs. If none exists, implement the most naive version that really runs |
| The competitor is too weak, or not designed for the same problem | `osdi18-capturing-and-enhancing` (the competitor is designed for crash faults), `sosp17-netcache` (compares only with no cache), `osdi21-oort` (compares only with random selection), `osdi20-firm` (compares only with rule-based methods), `osdi26-controlling-opaque-component` (the Docker setup is biased against Docker) | Include at least one method of the same kind (also learning-based, also a cache). Have people from the competitor's field approve the baseline settings |
| The failure paths of relaxed guarantees are not tested | `osdi18-legoos` (no failure recovery experiment), `sosp23-treesls` (no systematic crash injection), `osdi22-xrp`, `osdi18-pocket`, `sosp21-ghost`, `osdi16-fasst`, `sosp19-pipedream`, `osdi18-noria` | Failure injection: crashes, packet loss, layout changes, concurrent writes, adversarial inputs. Report the cost and frequency of the fallback path |
| Security or correctness rests only on arguments; the strength of the spec is not checked | `osdi16-push-button-verification-of`, `sosp17-komodo`, `osdi25-building-bridges`, `osdi24-verismo`, `sosp25-atmosphere`, `sosp19-taso` (if an axiom is wrong, the guarantee fails) | Mutation testing, attack demos, fault injection: do at least one of the three |
| Unreliable ground truth | `sosp17-deepxplore` (not confirmed), `sosp19-efficient-scalable-thread-sa` (union of tools), `sosp24-fbdetect` (assumes its own false negatives are 0), `osdi24-servicelab` (relies on developer labels) | Confirm a random sample by hand. Build ground truth from injected known effects |
| Inconsistent numbers | `sosp19-nexus`, `sosp17-zygos`, `osdi16-network-requirements-for`, `osdi23-triangulating-python-perform`, `osdi20-ansor` | Generate all tables and all numbers in the text from the raw data with scripts |
| The ablation is done at only one point | `osdi20-ansor` (one operator, two networks), `sosp19-taso` (joint optimization tested only on BERT), `osdi20-a-unified-architecture` (gain breakdown for only one model) | Ablations cover at least two kinds of workload from the main results |

## 4. Self-check list

Go through your own experiment plan item by item:

1. Has the fact the insight depends on been measured, with numbers, on a real workload? Is the workload used for measurement separate from the evaluation workload?
2. Is the main baseline the strongest one, open source, on the same hardware, and tuned? Has it been given the same optimizations that are unrelated to the novelties?
3. Do you report the real target metric (goodput, time-to-accuracy, capacity under an SLO, deduplicated bug count), or a proxy metric?
4. Does every novelty (including the 2nd and 3rd added to deal with new costs) have a "swap in the strawman in the same system" or add-one-at-a-time control?
5. Is any "ablation" really just a knob sweep, an estimate by subtraction or a bundled switch?
6. List all engineering optimizations that are not novelties. Have their shares been separated out?
7. Is there a curve that sweeps the strength of the insight's premise and marks the point where the gain disappears?
8. Where a guarantee is relaxed or a fallback path is designed, have you injected failures and measured the cost and frequency of the fallback?
9. Do security or correctness claims have an attack demo, mutation testing or fault injection, not just arguments?
10. Is every simulated, emulated or estimated number marked with its source and error, with at least one reproduction on real machines?
11. Does the evaluation set contain samples that inspired the design? Is there a held-out set?
12. If there is production data: is there a concurrent control? Was the "control" actually run, or computed?
13. Are all numbers generated by scripts from the raw data, and do the text and the figures agree?
