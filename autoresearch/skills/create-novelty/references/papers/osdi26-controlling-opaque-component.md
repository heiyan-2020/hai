# Controlling Opaque-Component Effects with Semisolates and Try
OSDI'26 · Evangelos Lamprou, Tianyu Zhu et al. / Brown, Stevens, Columbia, UCLA · Full text: https://www.usenix.org/system/files/osdi26-lamprou.pdf (camera-ready) · Selected: Best Paper

**One sentence**: The side effects of an opaque command land mostly on the file system. Put a copy-on-write view over it, and those effects become one piece of data that you can inspect, pick from and stack.

## Problem
Developers and AI agents run commands every day whose internals they do not understand: LLM-generated scripts, npm packages, repositories with pre-commit hooks.
The side effects of these commands are often irreversible. One LLM-suggested line, `rm -fr "$(cd ...)"/*`, deletes everything the user can write on some paths. node-ipc once rewrote /etc/passwd.
What the user wants: run the command as usual in the **current** environment, but see the side effects first and then decide which ones to apply.

## Strawman / Baseline
- **Container / VM (Docker)**: build a fresh environment and isolate everything → it is not the user's current environment, data must be copied in and out, and side effects can only be kept or dropped as a whole.
- **The command's own --dry-run**: only some commands have it (find does not). It is also a different code path and can disagree with the real run: with --log-file, rsync's dry-run misses side effects.
- **bubblewrap, system-call interposition (MBOX), language-level effect wrappers**: the view must be configured in advance. Side effects are either stopped on the spot (the component halts midway) or go straight to the host. Several uncommitted results cannot be stacked. Language-level schemes also require code changes.
- **Mount OverlayFS directly on /**: needs root. OverlayFS does not allow the upper and lower directories to overlap. Submounts in the lower layer are ignored, so content that should be hidden shows through.

## Novelty
1. **The "diff" of side effects can itself be a first-class object**
   Insight: A Unix program's persistent effect on its environment is written mostly to the file system (it is like the program's heap). A copy-on-write union file system (union FS) automatically collects all changes and deletions into an upper directory, and the lower layer is the live host file system.
   So: The command runs in a private view on top of the host file system (called a semisolate, a "semi-isolate"). It reads the real environment, and its writes go only to the upper directory. When it ends, that directory is the list of side effects. You can inspect it, apply it selectively by path, drop it whole, or save it.
   Unlike a container, it builds no new environment and copies no data. Unlike dry-run, it runs the real code path and works for any command.
2. **An uncommitted diff can serve as the lower layer of the next run**
   Insight: A union file system supports stacking several lower layers, so the previous run's upper directory can directly become the next layer.
   So: A later command can run under the illusion that the earlier command's result is already in effect, and the whole chain of commands can be undone together. This is exactly what out-of-order/speculative execution needs to check read-after-write dependencies. Neither bubblewrap nor MBOX can do it.
3. **User namespaces let unprivileged users mount overlays**
   Obstacles: mounting needs root, overlay does not allow overlapping layers, and submounts leak hidden content.
   So: Get local root in a new user/mount namespace. Mount a separate overlay per top-level directory (/usr, /home…) to avoid overlap. Flatten submounts with mergerfs first. When the order of side effects is needed, trace only system calls with path arguments via seccomp-BPF, not read/write.

## Evidence
- End to end: 25 benchmarks in 5 kinds of scenarios; all side effects were captured. After applying, the file system matched a run without try, checksum for checksum, file by file. 1.0–8.3× slower than running directly, 1.1–225.7× faster than Docker.
- Novelty 1 → comparison with dry-run: for 3 of 5 commands the report matched the native dry-run exactly. For rsync the native dry-run missed effects and try reported them all; for rename only the representation differed. The cost is 4.9–82.6× slower than native dry-run (0.26 s vs 0.03 s).
- Novelty 2 → 5 Koala scripts chained with -L: manual checks confirmed that all real dependencies were found, at 1.0–1.7× overhead. Downstream, hS and Incr used it to get 9.3× and 373.3× speedups (numbers from their own papers).
- Novelty 3 → no direct ablation; only an overhead breakdown: of the 165 ms for an empty command, building the overlay takes 25% and creating directories 22%. When creating 10,000 files, walking the upper directory at exit takes 6.3 s.
- Gaps: The Docker benchmark creates a container and copies data in and out every time, which is biased against Docker. No quantitative comparison with bubblewrap/MBOX. "All side effects captured" rests on manual checks and checksums. Partial application can give inconsistent updates (for example, applying a file but not the directory it is in); try only warns.

## When it applies
Side effects must land mostly on the file system. The network can only be switched off as a whole, and cross-user operations (switching UID) are not supported. It guards only against mistakes, not against malicious code built to bypass try.
