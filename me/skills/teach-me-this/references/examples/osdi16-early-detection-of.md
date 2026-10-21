# Early Detection of Configuration Errors to Reduce Failure Damage
OSDI'16 · Tianyin Xu, Xinxin Jin, Peng Huang, Yuanyuan Zhou, Shan Lu, Long Jin, Shankar Pasupathy / UCSD, University of Chicago, NetApp · https://www.usenix.org/conference/osdi16/technical-sessions/presentation/xu
Paper type: tool / reliability (study-driven: a code study of six systems, then a tool built on its findings)
> Spoiler: this card dissects the paper. Do not read it if you want to train on this paper.

## Dissection
- Background: Large systems have hundreds of settings (HDFS 164, YARN 116, HBase 125, Apache 97, Squid 216, MySQL 462). Config errors are a major cause of cloud outages; an erroneous fail-over config caused a 2.5-hour Google App Engine outage in 2010. The same config file is pushed to thousands of nodes and persists across reboots, so redundancy and restarts do not help. Sysadmins mostly test configs black-box: start the system, run a small workload, watch.
- Problem: Many settings, especially those for fail-over, error handling, backup and log rotation, are not read or checked at startup. They are read only when the rare path runs. An error in them stays hidden until the system needs that path, and then the safety net itself fails. At one storage company (COMP-A), such errors are 47.6% of config issues but 75% of the high-severity ones, and they take longer to diagnose. The study of 182 reliability-related (RAS) settings in six systems finds 37 (20.3%) exposed to such errors. Goal: detect these errors at startup, automatically, without hand-written rules and without large config datasets.
- Challenges: (1) Hand-written startup checks are missing (14.0%–93.2% of RAS settings have none) or incomplete, and the right constraint depends on how the value is used (chdir vs. open, O_RDONLY vs. O_CREAT). (2) Learning "normal" values needs many independent configs, but data centers copy one config to every node, and paths, IPs and hostnames differ by machine by design. Type inference (conf spellchecker) knows "this is a file" but not how it is used. (3) The code that uses the value sits behind a trigger (a real NameNode crash) that cannot be produced at startup. (4) Running that code early has side effects: exec replaces the process, files get created or deleted, freopen closes the stream it reopens. (5) The extracted code depends on variables that may not exist yet at startup. (6) Running code alone does not say whether the value is wrong.
- Solution:
  1. Insight: the code that consumes a value (open, chdir, parseInt, FileInputStream) is already the most complete check of that value, and whether it fails depends on the value reaching that operation, not on when or why execution gets there. → Design: start from the config getter, do forward static taint tracking along data flow (not control flow), extract only the instructions that transform, propagate and use the value, drop the trigger conditions, and recover the needed context by backtracking (e.g. freopen's mode = "a"); where context is indeterminate (network reads, request content), cut the slice. Run these checkers at the end of initialization, on the real host. → Removes hand-written constraints and the need to produce the trigger; it also catches errors tied to the local environment.
  2. Insight: to know whether a file or network call would fail, checking its arguments against the call's semantics is enough; the call need not run. → Design: rewrite side-effecting calls into check utilities (freopen → access/stat; network → reachability), copy globals into locals, skip file-content reads/writes and send/recv, and remove unknown library calls (e.g. system()) together with the instructions after them. A sandbox or VM was rejected because it needs extra setup from sysadmins. → Makes the early rehearsal safe inside the running process.
  3. Insight: programs already signal failure. → Design: catch Java exceptions, check return values/errno of known C calls, and treat instructions post-dominated by exit/abort/throw/error logging as errors. Drop checkers with no such signal (e.g. booleans used only for branching). → Turns the rehearsal into a verdict with no new rules.
  Also: merge equal or subset checkers; drop checkers whose code already ran before the call site; invoke after the root → nobody user switch, before serving or joining the cluster; optional periodic thread for errors that appear after the check (TOCTTOU).
- Evidence: detects 29 of 37 new errors (78.4%) and 15 of 21 historical ones (71.4%); conf spellchecker detects 11 and 7 fewer. All type/format and option/range errors are found; file-path errors 9/12 and 5/7; "other" 7/13 and 3/6. On 830 real config files from mailing lists and forums: 282 true errors, 3 false alarms; 37.5%–87.8% of the errors per system can only be seen on the local environment. False alarms in 3 parameters (2 YARN, 1 HBase), at most 1.7% (2/116 in YARN), all from missed control dependencies. Checkers run in under 1 s (max 780 ms, HBase HMaster; Apache 0.6 ms). Setup is 4–7 lines per system, 31 for MySQL. Misses come from values passed to shell commands and from paths merged with request content.

## Reveal schedule
| Fact | Earliest stage |
|------|----------------|
| Config errors cause big outages; same config on many nodes; sysadmins test black-box | 1 |
| COMP-A ticket numbers (47.6% / 75% / diagnosis time); Squid, MapReduce, HDFS fail-over, Apache core-dump incidents | 1 |
| Many reliability settings have no startup check and are not read at startup | 1 (learner should find this) |
| Hand-written checks are incomplete; the constraint depends on how the value is used | 1 |
| Learning from many configs fails because configs are copies; type inference is too coarse | 1 (as wrong turns) / 2 (as walls) |
| The using code is itself the complete check | 2 (seed points at it; learner should find it) |
| Failure depends on the value reaching the operation, not on the trigger; drop the conditions | 2 |
| Static data-flow slice from the getter, backward context, cut when indeterminate | 2 |
| Side effects; rewrite calls to semantic checks; sandbox/VM rejected | 2 |
| Existing error signals as the verdict; drop checkers without one | 2 |
| Where to run (end of init, after user switch), periodic re-check | 2 |
| Names PCheck, "LC error", "checker"; all §4 numbers | 3 |
| Limits: shell commands, request-dependent values, legal but unsuitable values, file contents | 3 (probes) / 4 |

Protected terms: "latent configuration error", "LC error" (3); PCheck (3); "emulating late execution", "execution emulation" (3); "checker" as the paper's artifact (2, only after the learner proposes generated check code); "check utility" (2, only after the learner proposes replacing calls); "usage-implied checking" (2, bottom-out only).
Safe background: HDFS HA and fencing, NameNode/DataNode, TaskTracker, Squid log rotation, Apache core dumps, errno and Java exceptions, static taint analysis and program slicing, LLVM and Soot, TOCTTOU, conf spellchecker as a type-inference tool, the idea of learning config rules from many machines.

## Stage 1: Find the problem
### Background to give
You are on the reliability team of a company that runs Hadoop (HDFS, YARN, HBase) and a web tier (Apache, Squid, MySQL) on a few thousand machines. Config changes go through code review, then a rollout tool copies the same file to every node in a role. The pre-rollout test is: start the service on a canary, send it some traffic, watch logs and dashboards for a while. You have been asked to look at last year's config-related incidents and say what the team should build.

### Phenomena
1. Postmortem, Squid proxy. Someone set `diskd_program` to a path that did not exist. Startup log: clean. Traffic: normal for days. At the next log rotation, Squid hung and hogged the CPU for 7+ hours. Diagnosis took 48 hours: 26 rounds of back-and-forth, 5 collections of logs and traces, 2 patches that did not fix it. The final fix added a startup check that the path exists. A reviewer noted it does not look at file type or permissions.
2. A RegionServer died with OutOfMemoryError two days after a deploy. Its heap setting was a valid number that parsed fine at startup; the week's load was simply larger than the person who chose it expected.
3. Ticket statistics shared by a storage vendor you buy from. Config tickets where the system started cleanly and the error showed up later are 47.6% of all config tickets, but 75% of the high-severity ones. Diagnosis time, normalized to the average ticket: mean 1.14 vs. 0.87, median 1.70 vs. 0.41 for errors caught at startup.
4. Staging drill for HDFS high availability. The cluster had been serving normally. The team killed the active NameNode. Fail-over never completed: the fencing step threw IllegalArgumentException parsing `dfs.ha.fencing.ssh.connect-timeout` (a typo), and the whole HDFS was unavailable. A note in the drill report: "We only saw this because we killed the active NameNode. We cannot do that on every config push."
5. A teammate's audit. Apache's startup code for `CoreDumpDirectory` checks that the path exists and is a directory. In the crash handler, Apache calls chdir to it; the process has no permission, chdir fails, and no core dump is written. Elsewhere, one path setting is used by chdir in one place and by open(O_CREAT) in another. Counts from the audit: of 44 reliability-related HDFS settings, 41 have no startup check at all; for MySQL, 6 of 43 have none and 6 more have only a partial one. HDFS has 164 settings, MySQL 462. The teammate's note: "Writing these checks by hand means knowing every use of every value. They also go stale as the code changes."
6. Hadoop issue thread. `mapred.local.dir` pointed to a directory with the wrong owner, on many nodes. "When I ran jobs on a big cluster, some map tasks never got started." TaskTrackers caught the exception, retried, and looped forever; restarting did not help. Request in the thread: "TaskTracker should check whether it can access the local dir at the initialization time, before taking any tasks." A Java developer on your team says their usual quick fix for such bugs is to read the setting in a class constructor, "but this object is only created when the first job runs."

Tutor notes: 1, 4 and 6 are the core pattern (startup looks fine, the value is used only on a rare path, failure lands when that path is needed, and it hits many nodes at once). 3 says these errors are the expensive ones. 5 is the constraint that rules out "just write more startup checks": the right check depends on how the value is used, and there are too many values. 4 also carries a constraint: the rare path cannot be triggered on purpose in production. The last line of 1 and the constructor remark in 6 repeat it: partial fixes keep missing cases. 2 is the distractor: it is late too, but the value is legal; nothing in the code rejects it. It is a sizing problem, outside this paper's scope. Do not let the learner build the problem around resource tuning.

### Hint ladder
- L1: In 1, 4 and 6, when was the bad value first read by the program?
- L2: Your canary test starts the service and sends traffic. Which of these settings does that test ever touch? What do they have in common?
- L3: The fixes in 1, 5 and 6 all try to check at startup by hand and all miss cases. So the problem is "catch errors in settings that startup never uses, at startup, without ___ and without ___". Fill the blanks from 4 and 5.
- Bottom-out: state the target below.

### Target
Settings for fail-over, error handling, log rotation and similar paths are not used or checked at startup, so an error in them passes every startup test and canary. It surfaces only when the rare path runs, often under an existing failure, on every node that got the file. The result is severe outages and long diagnosis. Hand-written startup checks are missing or incomplete, because the correct constraint depends on how each value is used, and there are hundreds of values. The problem: detect these errors at startup, automatically, without hand-written rules and without having to trigger the rare path.
Checklist:
- [core] The bad values are in settings used only on late, rare paths; startup and canaries never touch them.
- [core] Damage is high because the error shows up exactly when the safety net is needed, and on all nodes at once.
- [core] Hand-written checks do not scale and are incomplete; the rare path cannot be triggered on demand.
- [detail] These errors take longer to diagnose and dominate high-severity tickets.
- [detail] Restart and redundancy do not help, because the bad value persists in the file on every node.

### Common wrong turns
- "Test configs better before rollout" → Which test would have touched `diskd_program` or the fencing timeout without killing a NameNode or waiting for log rotation?
- "Learn normal values from all our machines" → Your rollout copies one file to every node. How many independent samples does that give? And what is the "normal" value of a local path or an IP address?
- "Use a type checker for config values" → In 5, the value is a directory that exists. What would a type checker say about it?
- "It is about resource sizing" (from 2) → In 1, 4 and 6, was the value a plausible-but-too-small number, or something an operation flatly rejects?

## Stage 2: Derive the solution
### Seed hint
In every incident you looked at, something in the program did eventually notice the bad value. Look at what noticed it, and how much that piece of code knows about what the value must be.

### Path
1. Learner proposes generating startup checks from types or rules. Wall: the constraint depends on use (chdir needs execute permission, open(O_CREAT) needs write on the parent, freopen with "a" needs append). Rules or types miss these; conf spellchecker only flags a file that is neither readable nor writable. Ask: where in the code is the full constraint already written down?
2. Learner sees that the consuming operation (chdir, open, parseInt) is the complete check, and proposes "run the fail-over code at startup". Wall: that code runs only after a NameNode crash; you cannot cause one. Ask: does chdir fail because a crash happened, or because of the path it got?
3. Learner proposes running only the instructions that carry the value from the getter to the operation, and drops the conditions around them. Wall (missing context): the call also needs other variables (freopen's mode and stream; values read from the network; parts built from request content) that may not exist at startup. Ask: which of these can you compute from the code alone, and what do you do with the rest? Good answer: backtrack to constants where possible; cut the slice where the value is indeterminate, accepting misses over wrong verdicts. Also: following control flow too would pull in everything (over-tainting); follow data flow, but keep simple guards like `if (p != NULL)`.
4. Wall (side effects): the extracted code runs inside the live process. exec would replace the process image; a slice could create or delete files; freopen on the error log closes stderr. Learner may say "run it in a sandbox or VM". Ask: who sets up that VM on every node, at every startup? Good answer: do not make the call; check its arguments by the call's meaning (access/stat for files, reachability for addresses), copy globals to locals, drop calls you do not understand along with what follows.
5. Wall (no verdict): the rehearsal ran. How do you know the value was bad? Good answer: reuse the program's own failure signals (exceptions, errno, branches that lead to exit or error logs); if a slice has none, it cannot tell you anything, so drop it.
6. Where and when to run. Ask: if the process starts as root and switches to nobody during startup, when should the check run? (After the switch, before serving or joining the cluster.) What if someone deletes the directory an hour after startup? (Re-run periodically.)
Also discuss: why does running on the real host matter, compared with checking the config file as text? (Missing paths, unreachable IPs, wrong owners are facts about this machine.)

### Hint ladder
Idea 1 (the using code is the check, and it does not need the trigger):
- L1: In the Apache audit, the startup check passed and chdir failed. Which of the two knew the real constraint?
- L2: For the fencing timeout, what decides whether parseInt throws: the NameNode crash, or the string?
- L3: If you could run just the steps from "read the setting" to "use it", without the "if crashed" around them, what would you need to make them runnable?
- Bottom-out: extract the data-flow slice from the getter to the consuming operations, drop the trigger conditions, fill in context that can be computed statically, cut where it cannot, and run the slice at the end of startup on the real host.
Idea 2 (rehearse without side effects):
- L1: What would happen to the live process if the slice called freopen on stderr, or exec?
- L2: To know whether open(path, O_CREAT) would fail, what do you actually need to look at?
- L3: Could you swap each risky call for a function that answers "would this call fail with these arguments?"
- Bottom-out: rewrite calls into semantic checks (access/stat, reachability), keep state changes local, skip file contents and packets, remove unknown calls and what follows; no VM needed.
Idea 3 (the verdict comes from the program):
- L1: When the real fail-over broke, how did the program show it?
- L2: Which such signals exist in Java and in C?
- Bottom-out: catch exceptions, check return codes/errno, treat paths that must reach exit/abort/error logging as failures; drop slices with no signal.

### Target
1. The operation that consumes a value already encodes its full constraint, and its outcome depends on the value, not on the trigger. So extract the slice from the config getter to the use by static data-flow taint tracking, drop the trigger conditions, recover static context, cut where context is unknown, and run it at the end of startup on the real host.
2. Rehearsal must not change the process or the machine. So replace side-effecting calls with argument checks based on call semantics, keep writes local, and remove unknown calls; this avoids a sandbox that sysadmins would have to set up.
3. The program's own error signals give the verdict; checks with no signal are dropped.
Checklist:
- [core] The code that uses the value is the check; derive checks from it, not from rules.
- [core] Only the use matters, not the trigger, so the rare path need not happen.
- [core] Side effects must be removed by checking arguments, not making calls.
- [core] A verdict needs existing failure signals.
- [detail] Missing context: compute statically or cut; accept misses.
- [detail] Run after the user switch and before serving; re-run periodically; drop checks whose code already ran.

## Stage 3: Design the experiments
### Summary to give
Problem: latent configuration (LC) errors sit in settings that are not used at startup, mostly fail-over and error-handling settings, so they escape testing and break the system when the rare path runs. Method (PCheck, for C via LLVM and Java via Soot): from developer-specified config getters, static taint tracking extracts the instructions that transform, propagate and use each value. It recovers the needed context by backtracking and wraps the result into checkers. Side-effecting calls are rewritten into check utilities; the verdict comes from exceptions, error codes, and exit or error-log paths. Checkers are inserted at a developer-annotated point at the end of initialization, with optional periodic runs.

### Key research questions
1. Does it catch real LC errors, and more than existing tools? This is the headline claim. A reviewer will also ask whether it works beyond the errors that inspired the design.
2. Does it work on real configs in the wild, and does running on the local environment matter? This tests idea 1's claim that use-based checks catch what text-based tools cannot.
3. What does it cost: false alarms, startup time, developer effort? A tool that blocks startup on false alarms, or needs heavy annotation, will not be deployed.

### Key experiments
1. Detection. Benchmarks: 37 new LC errors from the study plus 21 historical errors that caused real failures, collected from prior studies (the control set). Baseline: conf spellchecker. Metric: number detected, split by error type. Result: 29/37 (78.4%) and 15/21 (71.4%), 11 and 7 more than conf spellchecker; type/format and range errors all found; misses are values used in shell commands or combined with request content. Weak designs: using synthetic errors from mutation tools (ConfErr), which are mostly caught by the system's own startup checks and so are not latent; testing only on the study's own errors; reporting one total without per-type breakdown, which hides where it fails.
2. Real config files. 830 files from mailing lists, ServerFault and StackOverflow, for five systems (Squid excluded). Result: 282 true errors, 3 false alarms; 37.5% (HDFS) to 87.8% (Apache) of errors are visible only on the native environment (missing paths, unreachable IPs, undefined environment variables). Weak design: checking the file as strings on a build machine, which loses exactly these errors.
3. Cost. False positives: run checkers on default configs and the 830 files, and inspect the generated IR. Result: 3 parameters with false alarms, at most 1.7% (YARN, 2/116), all from missed control dependencies. Time: under 1 s per process (HBase HMaster 780 ms; Squid 93.8 ms due to a public-IP setting; Apache 0.6 ms). Setup: 4–7 lines per system, 31 for MySQL. Weak designs: measuring runtime throughput instead of startup delay; counting false alarms only on configs known to be broken.

### Reviewer probes
- Side-effect freedom is checked only by reading the generated IR. What test would show that checkers never change files or process state?
- Coverage: checkers exist for all HDFS/YARN/HBase settings, but only 18 of 97 Apache, 45 of 216 Squid, 32 of 462 MySQL settings. How many errors hide in the rest?
- 37 of 58 benchmark errors come from the authors' own study. Is the 21-error control set large enough?
- The check passed at startup; the directory is deleted an hour later. How often does periodic checking run, and what does it cost?
- A value that is valid but unsuitable (small heap, short timeout) is out of scope. How much of the high-severity ticket pool is that?

## Stage 4: Apply and extend
### Scenarios
1. Values that go to a shell. Setup: some settings are concatenated into a shell command string and passed to system(); the tool removes such calls because their effects are unknown, so it misses these errors. Question: how can you check them without running the command? Good directions: model the first token as an executable path and check that it exists and is executable; give known commands their own semantic checks. For values merged with request content, rehearse with representative values (the paper names this as future work), and say how that risks false alarms.
2. Check before rollout, not at startup. Setup: the team wants to reject a bad config in the rollout tool, before it reaches thousands of nodes. Question: what changes if checkers run as a separate program when the config file changes? Good directions: the standalone program no longer has to protect the live process's state, but must still avoid external effects, and it must include the config parsing code (easy when parsing is modular, as in HDFS/YARN/HBase; hard when parsing is mixed with initialization). It must run on, or emulate, each target host's environment, since many errors are host-specific.
3. Legal but wrong (the stage-1 distractor). Setup: heap sizes and timeouts that parse fine but fail under load days later. Question: can the "rehearse the use" idea reach these? Good directions: the use (allocation, waiting) does not fail on its own; you need a model of the workload or resource usage (profiles, past peaks) to rehearse against, so this becomes a dynamic, not a static, check. A good answer says which part of the original insight breaks: there is no failing operation to borrow.
