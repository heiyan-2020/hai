---
name: dev-loop
description: Run a lightweight, user-gated development workflow with selectable fast, normal, or verbose detail. Use when Codex is asked to implement, change, refactor, or fix code and the user wants planning, requirements grilling, persistent progress, or an independent Codex review without the heavier pins, protocols, facts, audits, and grounding of pin-aware-agent.
---

# Dev Loop

Run only the phases selected below. Keep the workflow proportional to the task.

## Choose detail

Ask the user to choose before doing task work, unless they already selected a level:

- `fast`: develop and verify only.
- `normal`: plan, obtain approval, develop, and review.
- `verbose`: plan, grill unresolved decisions, obtain approval, develop, and review.

Wait for the answer. Persist the selected level only when a plan exists; `fast` creates no workflow artifact.

## Persist state

For `normal` and `verbose`, create `.claude-research/plans/<task-slug>.md`. Reuse the file when resuming the same task. Keep it concise and update it after every phase with:

- detail level and status;
- goal, scope, design, development steps, and verification;
- decisions and user approval;
- implementation progress;
- review rounds, findings, dispositions, and remaining risks.

Do not create another state format or directory. Preserve unrelated contents already under `.claude-research`.

## Generate the plan

Inspect the relevant repository context before planning. Write a concrete design and development plan to the plan file, present it in plain language, and request approval.

For `normal`, resolve only choices that materially change the result. Ask the user when such a choice cannot be safely inferred. Update the plan from their response and wait for explicit approval before development.

## Grill unresolved decisions

Run this phase only for `verbose`, after drafting the plan and before approval.

Map unsettled decisions as a dependency tree. In each round, ask the whole current frontier: every question whose prerequisites are already settled. Defer dependent questions to later rounds. Number each question and recommend an answer using exactly this shape:

```text
❓ **Q1** - **<title>**: <question and choices>

➡️ <recommended answer>
```

Recompute the frontier after every response. Find repository or environment facts yourself; when useful and available, delegate independent fact-finding without blocking unrelated frontier questions. Never ask the user for discoverable facts.

Finish only when the frontier is empty. Update the persisted plan with every settled decision, tell the user shared understanding has been reached, and obtain explicit approval. Do not develop earlier.

## Develop

Implement the smallest complete change that satisfies the approved plan, or the request itself in `fast`. Follow repository instructions and existing patterns. Test the changed behavior with the smallest meaningful checks. Update progress and deviations in the plan when one exists; stop for approval if a discovered deviation materially changes the agreed design or scope.

## Review

Run this phase for `normal` and `verbose` after development and verification. Use an independent Codex reviewer, not the implementing context.

Prefer `codex review --uncommitted <prompt>` for a Git worktree with local changes. Tell it to read the persisted plan and inspect both the plan and implementation for correctness, scope compliance, regressions, security, missing tests, and needless complexity. Use `--base` or `--commit` when that is the actual review scope. If `codex review` is unavailable or there is no suitable Git diff, invoke an available independent Codex/ask-Codex capability with the plan, changed artifacts, and verification results.

Accept only specific, reproducible findings. Fix valid issues, rerun relevant checks, record the disposition in the plan, and review again. Stop when no actionable findings remain or after three total review rounds. Do not loop beyond three; report any remaining risk to the user.

## Finish

Report the selected level, delivered change, verification result, review outcome when applicable, and the plan path. Do not add pins, protocols, facts, grounding quizzes, or extra workflow files unless the user separately requests them.
