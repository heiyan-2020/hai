# Early Detection of Configuration Errors to Reduce Failure Damage
OSDI'16 · Tianyin Xu et al. / UCSD, UChicago, NetApp · Full text: https://www.usenix.org/system/files/conference/osdi16/osdi16-xu.pdf (camera-ready) · Selected: Best Paper

**One sentence**: The code that later uses a configuration value is itself the most complete check, but it comes too late. Rehearse it safely at startup.

## Problem
Configurations for fail-over, error handling and similar are read only when something goes wrong, and are not checked at startup. Errors stay latent (LC error, latent configuration error) and show up only when a fail-over is really needed, and then they bring down the whole service.
Among one storage company's customer issues, LC errors are 75% of high-severity configuration issues. Of 182 reliability-related parameters in 6 systems, 37 (20.3%) can have latent errors.

## Strawman / Baseline
- **Let developers write startup checks by hand**: tedious and incomplete. Apache checks that CoreDumpDirectory exists and is a directory, but not its permissions, so chdir still fails. When the same path is used by chdir and by open(O_CREAT), the constraints also differ.
- **Learn "normal values" from many configurations**: this needs many independent configurations, but a data center pushes the same configuration to all nodes. Values that differ by machine by nature, such as paths and IPs, also cannot be learned.
- **Type inference (conf spellchecker)**: it only knows that a value "is a file", and reports an error only when the file is neither readable nor writable. It misses errors like "the file is read-only but the system needs to write it" and out-of-range numbers.
- **Run the code that uses the configuration early, at startup**: the use points are deep in error-handling paths, and the trigger condition (a real NameNode crash) cannot be created at startup. Also, this code calls exec, creates and deletes files, and closes streams, so running it early damages system state.

## Novelty
1. **Use is the check: it needs only the use point, not the trigger condition**
   Insight: A configuration value is finally consumed by operations such as open, chdir and parseInt. If these operations fail, the value is wrong. What the operation requires of the value is exactly the constraint the program really needs. Whether an error shows up depends only on "the value reaching these operations", not on "when and why execution gets there".
   So: Start from the getter that reads the configuration and do static taint tracking (mark variables derived from the value along the data flow). Extract only the instructions that propagate and use the value, and ignore the enclosing branch conditions. For missing dependent variables, trace backward to compute a static value (for example, freopen's mode="a"). If it cannot be computed, cut the slice there. Wrap the slice as a checker and run it at the end of initialization. To judge errors, use the failure signals the program already has: exceptions, errno, branches that must lead to exit/error logs. Drop checkers that have no failure signal.
   Both the constraints and the error judgments come from the code itself, with nothing written by hand. Running on the local machine's environment finds environment-related errors, such as a missing path or an unreachable IP, which learning methods and type inference cannot see.
2. **Check the arguments by the call's semantics instead of making the real call, so the rehearsal has no side effects**
   Insight: To decide whether a file or network call will fail, it is usually enough to check metadata. The call does not need to run.
   So: Rewrite calls with side effects into check utilities, for example freopen into access/stat, and test only reachability for the network. Copy global variables into local variables before changing them. Delete unknown library calls (such as system()) together with the instructions after them. This solves the side-effect problem of the last strawman, and needs no sandbox or VM.

Other design: checkers for multiple paths are merged and deduplicated; use points already executed before startup get no checker; checkers can run periodically to catch errors caused by environment changes after the check.

## Evidence
- End to end: of 37 LC errors newly found by the authors, it detects 29 (78.4%). Of 21 historical LC errors, it detects 15 (71.4%). That is 11 and 7 more than conf spellchecker. Applied to 830 real configuration files, it reports 282 true errors. False positives involve only 3 parameters (at most 1.7%, in YARN), all caused by missing control dependencies. Checkers run in <1 s. Most systems need fewer than 10 lines of interface annotation.
- Novelty 1 → in the 830 configurations, 37.5%–87.8% of errors can be found only with the local machine's environment. The comparison with conf spellchecker is an overall comparison; no direct ablation.
- Novelty 2 → only a manual check of the checker IR, no side-effect test: no direct ablation.
- Gaps: the 37 new errors come from the same study that inspired the design, so the evaluation is biased (21 historical errors serve as a control). Misses come mainly from values that go into shell commands or are concatenated with runtime request content. Errors in file contents cannot be found.

## When it applies
Configuration values must pass through standard APIs with clear failure signals, and the use context must be statically determinable. Out of scope: errors that depend only on application semantics (email addresses, internal error codes) or on the runtime workload, and values that are "legal but unsuitable" (such as a heap that is too small).
