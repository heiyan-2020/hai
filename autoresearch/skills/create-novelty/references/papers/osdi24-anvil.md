# Anvil: Verifying Liveness of Cluster Management Controllers
OSDI'24 · Xudong Sun, Tianyin Xu et al. / UIUC, UW-Madison, VMware Research · Full text: https://www.usenix.org/system/files/osdi24-sun-xudong.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Every controller promises "once the desired state stops changing, the cluster will eventually match it and stay matched"; this one liveness spec can be proven by splitting it into "the environment eventually goes quiet" plus "it converges once quiet".

## Problem
A Kubernetes controller loops: it reads the cluster state, compares it with the desired state the user declared, and sends requests to fix the difference.
Crashes, asynchrony, and conflicts with other controllers can keep it from ever reaching the desired state; for example, if it crashes between two steps, after restart the second object is never created.
Of the bugs testing tools found in 16 controllers, 69% (70 bugs) are of the "never matches" kind.

## Strawman / Baseline
- **Testing / fault injection (Acto, Sieve)**: Covers only the timings that actually run; a ZooKeeper scale-up crash bug the authors later found appears only at a specific timing, and Sieve did not catch it.
- **Write safety properties to rule out bugs**: Such as "an unrecoverable intermediate state never appears"; but to write that, you must first know which states are unrecoverable, that is, know the bug first.
- **IronFleet-style liveness verification**: Specs are written for one system (such as "if the network is fair, the reliable transport layer eventually delivers"), so each new controller needs a rewrite. The paper does not quantify its proof cost.
- **Directly prove "after a crash, it converges from any state"**: After a crash, the cluster state can be any interleaving of earlier execution and failures; the controller can also stop at any step (the paper's simplified ZooKeeper step alone has 6 branches). Each starting point needs its own proof, and there is no existing paper proof to follow.
- **Pick one of two fault assumptions**: Assuming "at most one crash" gives too weak a guarantee; allowing "crashes forever" makes liveness impossible.

## Novelty
1. **Controller correctness needs only one generic spec**
   Insight: All controllers follow the reconcile principle, and the shared core of correctness has only two parts: when the desired state stops changing, the cluster eventually matches it (progress), and stays matched from then on (stability). Writing it needs only the desired state, not knowledge of bugs.
   So: Write it as one temporal-logic formula, ESR: "if desired state d stops changing from some moment on, then eventually the cluster always matches d". All three controllers share this one spec, and all 70 bugs above violate it.
2. **Faults can be arbitrarily many, but they eventually stop**
   Insight: Liveness only needs the environment to eventually give the controller a stretch of undisturbed time; it does not need to limit the number of faults. The idea is the same as partial synchrony (delays are eventually bounded).
   So: For crashes and for request failures, add an action that "turns off that fault", and assume it eventually happens under weak fairness (an action that is always enabled eventually happens). Competition from built-in controllers is likewise modeled as eventually yielding.
3. **Level triggering reduces "start from any state" to "start from the initial state"**
   Insight: Controllers are level-triggered (reconcile looks only at the current state and does not depend on history), and after one round of reconcile ends they are always rescheduled and start over from the initial state.
   So: The proof splits into two lemmas: (1) the environment eventually becomes stable; (2) in a stable environment, the current round ends wherever it stopped (only termination is proven, not convergence), a new round starts from the initial state, and from then on it is proven along a single path that each object is set correctly. This removes exactly the burden of "prove convergence separately for each starting point". "First get the object, then create or update it" is written as a parameterized lemma and reused for each object.

Other design: TLA is embedded in Verus (an SMT verifier for Rust, without temporal logic); more than 70 temporal lemmas and 60 environment lemmas are provided (the paper does not quantify how much effort this saves compared with IronFleet).

## Evidence
- End to end: verified three controllers, ZooKeeper, RabbitMQ, and FluentBit, with features matching the reference implementations. Proof/code ratio 4.5–7.4, each verifies in <3 minutes. Reconcile time is similar to the reference implementations. 854 crash tests, no failures.
- Novelty 1 → Verification found 3 liveness bugs and 1 safety bug, 2 of which also exist in the reference implementations. "Rules out the 70 bugs" is a manual analysis.
- Novelty 2 → No direct ablation.
- Novelty 3 → The first controller took 2 person-months (including working out the proof strategy), the next two about 2 person-weeks each; FluentBit added 28 features incrementally, with an average of 47 lines changed per feature (19 of them proof). No direct ablation.
- Gaps: Much trusted code (environment model 1846 lines, Kubernetes integration 5886 lines); the only bug found by functional testing came from an incomplete trusted API spec.

## When it applies
All components it interacts with must be modeled and must eventually stop conflicting; if an unmodeled custom controller competes with it to change objects, the result does not hold.
