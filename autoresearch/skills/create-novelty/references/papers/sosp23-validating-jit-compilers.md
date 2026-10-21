# Validating JIT Compilers via Compilation Space Exploration
SOSP'23 · Cong Li, Yanyan Jiang, Chang Xu, Zhendong Su / Nanjing University, ETH Zurich · Full text: https://cs.nju.edu.cn/changxu/1_publications/23/SOSP23.pdf (author home page, camera-ready) · Selected: Best Paper

**One sentence**: The same program on the same VM must give the same output no matter which parts get compiled or when it falls back to the interpreter; inserting semantically neutral loops and calls can change these choices.

## Problem
JIT compilers such as HotSpot C1/C2, OpenJ9 and ART have complex optimizations and are a main source of VM bugs. JITs are tiered and warmed up by profiles: code is first interpreted and only compiled after a counter reaches a threshold; they also do OSR (switching a running loop to compiled code) and deopt (falling back to the interpreter when speculation fails).
Deep JIT bugs only appear under a specific interleaving of "which parts are compiled and which are interpreted". Existing tools mostly find shallow bugs in parsers, verifiers and the like.

## Strawman / Baseline
- **Random program generation + cross-VM differential testing (JavaFuzzer, classfuzz, classming, JavaTailor, JAttack)**: compare different JVMs, or fully interpreted vs. fully compiled output. → Only a constant number of compilation choices are compared, which treats the JIT as a static compiler. To make programs finish fast, generators avoid long loops, so many programs never reach the compilation threshold (in the paper's example, the key method is called only 6 times).
- **Fuzz JIT options or thresholds (JOpFuzzer)**: → each VM needs experts to understand its options, and the explored range is limited by the number of options. The authors ran random thresholds for a week and found nothing; developers are also reluctant to fix bugs triggered by obscure options.
- **Modify the VM to directly control whether each call is compiled or interpreted**: → a lot of engineering, and it only works for one VM. Real VMs only allow OSR and deopt at specific points; forcing control breaks their internal assumptions.
- **Coverage-guided JIT fuzzing (JITfuzz)**: → no differential oracle, so it can only find crashes, not miscompilations.

## Novelty
1. **A program's own "compilation space" is a huge test space and comes with its own oracle**
   Insight: for the same program and the same VM, each method call can be interpreted, compiled at some tier, or OSRed or deopted midway. n calls give Ω(2^n) JIT interleavings, and a correct VM must give the same output under all of them.
   So: compare different interleavings of the same program on the same VM against each other (metamorphic testing). No second VM and no reference implementation are needed.
   This fixes exactly the root cause of the differential baselines: they cover only a few points such as fully interpreted and fully compiled, while bugs hide in the partial compilation and deoptimization interleavings in between.
2. **Use the VM's own hotness mechanism to steer interleavings from the source level**
   Insight: the VM decides when to compile from method call counts and loop back-edge counts; deopt is triggered by uncommon traps. All of these are driven by ordinary code, so adding or removing loops or calls can "heat" a piece of code to compilation or even OSR without touching VM internals.
   So: randomly pick methods in a seed program and insert synthesized loops. Three ways to insert: insert directly; wrap a statement in a loop, with a flag ensuring it runs only once; before some call, call the method tens of thousands of times in advance, with a control flag making these pre-calls return early. The synthesized code backs up and restores any reused variables, suppresses output and swallows exceptions, so it is semantically equivalent to the seed. If a variant's output differs from the seed's, that is a JIT bug.
   This avoids the cost of modifying the VM or tuning options: the same tool runs on HotSpot, OpenJ9 and ART without changing any VM.

## Evidence
- End to end: as of 2023-04-10, 85 bugs reported on HotSpot, OpenJ9 and ART (32/37/16); 53 confirmed or fixed (26 fixed), 15 duplicates. 18 are miscompilations, 66 crashes and 1 performance; all appear only with the JIT on. 12 OpenJ9 bugs are marked blocker, 10 HotSpot bugs are ≥P3, and 13 OpenJ9 bugs had been latent for at least 4 major versions.
- Novelty 1 → 7 days on 16 cores on OpenJ9: 42,559 seeds, 340,472 variants. Compilation space exploration found output mismatches on 154 seeds; the traditional "default vs. fully compiled" comparison found them on only 21; 138 of them (89.6%) were found only by the former.
- Novelty 2 → no direct ablation: the separate contributions of the three insertion methods and the synthesized statements were not measured. Generating one variant takes 1.65 s, 0.16 s in batch; throughput ≥0.63 OpenJ9 invocations/s.
- Gaps: the comparison counts "seeds with a mismatch", not deduplicated independent bugs. No comparison of bug counts with tools such as JavaTailor under the same budget, and no measurement of how many interleavings were actually covered. Of the 21 found by the traditional comparison, 5 were not triggered by Artemis, because they involve compilation of built-in library methods. No support for concurrency or floating point.

## When it applies
The VM must be a tiered JIT that triggers compilation from call and loop counts and can fall back to the interpreter. Program output must be deterministic. Bugs that appear only in the compilation of built-in library methods, or that depend on concurrent timing, cannot be triggered by inserting user code to change hotness.
