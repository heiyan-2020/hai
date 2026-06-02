---
name: review-pr
description: "Use when the user wants an interactive, educational review of merging one Git branch into another, especially with a source branch and target branch, branch diff walkthroughs, per-file explanations, comprehension checks, or merge conflict decisions."
---

# Review PR

Guide the user through a source-branch-to-target-branch review. The output is
an interactive understanding session, not an automatic merge.

## Completion Status

End with exactly one state:

- `DONE`: every changed file was reviewed or skipped, and every detected
  conflict was discussed.
- `NEEDS_CONTEXT`: source branch, target branch, or required git refs are
  missing.
- `BLOCKED`: git state or command failures prevent a reliable diff or conflict
  analysis.

## Inputs

Require:

- `SOURCE`: branch or ref to merge.
- `TARGET`: branch or ref to merge into.

If either is missing, ask for only the missing value. Do not infer the target
branch unless the user explicitly asks you to choose one.

## Step 1: Resolve Refs

Run:

```bash
git rev-parse --verify SOURCE^{commit}
git rev-parse --verify TARGET^{commit}
git merge-base TARGET SOURCE
git diff --stat TARGET...SOURCE
git diff --name-status TARGET...SOURCE
git log --oneline --reverse TARGET..SOURCE
```

If a ref is unavailable, stop with `NEEDS_CONTEXT`. If git reports an
ambiguous or invalid revision, ask the user for the exact branch name.

Do not check out branches, modify files, stage changes, or run an actual merge
while reviewing unless the user explicitly asks for that separate operation.

## Step 2: Understand the Diff

Inspect the diff before explaining it:

```bash
git diff --find-renames --find-copies TARGET...SOURCE
```

Build a concise mental model:

- What user-facing behavior, data, workflow, or infrastructure changed.
- Which files are central versus supporting.
- Whether commits and file changes tell the same story.
- Any risky areas, deleted code, generated artifacts, or test gaps.

Then introduce the merge to the user in this shape:

```text
Merging SOURCE into TARGET appears to do:

1. <main change>
2. <supporting change>
3. <risk/test note if relevant>

Changed files:
<status> <path> - <one-line role in the change>

Say "expand" for the current file, or "skip"/"next" to move on.
```

## Step 3: Per-File Interactive Walkthrough

Process files one at a time in diff order. Never advance to the next file
unless the user says `skip` or `next`.

For each file:

1. Announce the current index, path, status, and a one-sentence role.
2. Offer exactly these actions: `expand`, `skip`, `next`.
3. If the user says `skip` or `next`, move to the next file.
4. If the user says `expand`, explain the file in detail:
   - relevant hunks and why they matter;
   - changed APIs, data flow, invariants, tests, or behavior;
   - risks, assumptions, and dependencies;
   - how this file connects to the overall merge.
5. Ask one targeted comprehension question about the expanded file.
6. Wait for the user's answer.
7. Give direct feedback. If the answer misses the core point, explain the gap
   and ask one follow-up question about the same concept.
8. Stay on the same file until the user says `skip` or `next`.

Keep the walkthrough educational but technical. Avoid dumping the raw diff;
quote only the small snippets needed to anchor the explanation.

## Step 4: Conflict Analysis

After all files are reviewed or skipped, detect potential conflicts without
mutating the worktree.

Prefer:

```bash
git merge-tree $(git merge-base TARGET SOURCE) TARGET SOURCE
```

If the local Git version supports a better non-mutating conflict listing, use
it. If non-mutating analysis is unavailable or inconclusive, explain the limit
and stop with `BLOCKED` unless the user explicitly authorizes a temporary
worktree or actual merge attempt.

For each conflict:

1. Identify the conflicted file and conflicting regions.
2. Explain both sides:
   - what `TARGET` is preserving;
   - what `SOURCE` is introducing;
   - why Git cannot combine them automatically.
3. Ask the user what resolution policy they want for that conflict.
4. Record the user's decision before moving to the next conflict.

If no conflicts are detected, say that no merge conflicts were found by the
non-mutating analysis.

## Step 5: Finish

End with:

- reviewed/skipped file counts;
- conflict count and recorded resolution decisions;
- remaining risks or test gaps noticed during review;
- `DONE`, `NEEDS_CONTEXT`, or `BLOCKED`.
