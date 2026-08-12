---
name: experiment-loop
description: Run a lightweight, user-gated experiment workflow with selectable fast, normal, or verbose detail. Use when Codex must design, implement, execute, or analyze an experiment whose outputs need reproducible data lineage and must be materialized as a structured internal Fact.
---

# Experiment Loop

Treat a Protocol as the reusable contract and a Fact as one concrete materialization:

```text
Protocol + arguments + code revision + environment -> artifacts -> Fact
```

An experiment is incomplete until its Protocol and Fact both validate.

## Choose detail

Ask the user to choose unless they already selected a level:

- `fast`: Protocol, implementation, smoke run, formal run, Fact.
- `normal`: approved plan, then the fast flow plus independent review.
- `verbose`: normal plus design-tree grilling before approval.

Wait for the answer. Never let `fast` skip Protocol or Fact validation.

## Persist the plan

For `normal` and `verbose`, write `.claude-research/plans/<task-slug>.md`. Record the question or hypothesis, variables, controls, baseline, metrics, repetitions and seeds, resources, stopping conditions, expected artifacts, implementation, verification, approval, progress, review findings, and remaining limits.

Inspect the repository before proposing the plan. Present it plainly and wait for explicit approval.

## Grill unresolved decisions

Run only for `verbose`. Map unsettled decisions as a dependency tree. Ask the whole current frontier in each round; defer questions that depend on an unsettled answer. Use:

```text
❓ **Q1** - **<title>**: <question and choices>

➡️ <recommended answer>
```

Find repository and environment facts yourself. Recompute the frontier after each response. Persist settled decisions and obtain approval only when the frontier is empty.

## Establish the Protocol

Invoke the `protocol` skill before a formal run. Reuse a matching file under `.claude-research/protocols/`; otherwise create or update one. Confirm that it declares:

- one argument-driven entry script;
- parameters and fixed choices;
- the complete output tree;
- every conclusion-bearing artifact and important field;
- field lineage to the code that produces it.

Run `protocol_check.py`. Do not execute a formal run while it fails. In `normal` and `verbose`, include the proposed conclusion-bearing artifacts and fields in the approved plan. In `fast`, infer them from the request and stop only when a material ambiguity remains.

## Implement and smoke-test

Implement the smallest complete entry script and supporting code. Every configurable choice must be an argument; do not rely on edited globals or environment variables. Run the smallest cheap invocation that checks arguments, output shape, failure handling, and metric computation. A smoke run is not the Fact unless it answers the actual experiment question.

## Run and materialize the Fact

Allocate the next `if-NNN` ID. Execute only the Protocol entry script and place durable evidence under `.claude-research/data/<fact-id>/`. Then invoke the `fact` skill to write `.claude-research/facts/internal/<fact-id>-<slug>.md`.

The Fact must bind the Protocol to the actual command, commit, branch, environment, hardware, concrete data, artifact fields, claim, headline metric, and limits. A failed execution is a Fact only when the failure itself answers the experiment question; otherwise report the failure without inventing a claim.

Run the cheap recomputation command recorded in `Reproduction` at every detail level. Confirm its output matches the Fact metric and record the result as `Verified:`; never treat structural validation as evidence that the number is true. Then run `fact_check.py` against the newly created Fact file. Stop only when the Fact validates or report the blocker.

## Review the completed run

Run only for `normal` and `verbose`, after the formal run has produced a validated Fact. Do not use review as a pre-run gate.

Use an independent Codex reviewer in a fresh, read-only context. Invoke `codex exec --ephemeral --sandbox read-only -C <project-root> <prompt>`, or use an equivalent available independent Codex call. Ask it to inspect the persisted plan, Protocol, implementation, formal-run artifacts, and Fact for design validity, controls, comparable samples, data leakage, metric correctness, reproducibility, lineage coverage, unsupported claims, cherry-picking, missing checks, and needless complexity.

Accept only specific reproducible findings. Fix valid findings and rerun checks. If a fix changes the Protocol, implementation, data, metric, or claim, rerun the formal experiment and rematerialize the Fact before reviewing again. Spend at most three review rounds across the whole task.

## Finish

Report the level, Protocol path, exact formal-run command, Fact path, data path, validation and review outcomes, main observation, and limits.
