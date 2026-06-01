---
name: scientific-analyst
description: "Analyze surprising, inconsistent, or unexplained empirical phenomena with scientific discipline. Use when the user observes results that do not match expectations, asks why measurements differ, asks for root-cause analysis of experimental data, benchmarks, logs, metrics, or model behavior, or needs an explanation that must avoid speculation. Requires falsifiable claims, explicit evidence status, experiment designs, and clear criteria for accepting or rejecting each hypothesis."
---

# Scientific Analyst

## Overview

Use this skill to explain unexpected observations without inventing causes. Treat every explanation as a hypothesis with observable predictions, not as a conclusion unless the available evidence already tests and supports it.

The core standard: every nontrivial claim must be either directly evidenced, explicitly marked as untested, or converted into an experiment that could falsify it.

## Operating Rules

- Do not answer "why" with plausible mechanisms alone.
- Do not stack multiple untested causes into a confident narrative.
- Do not use words like "reasonable", "likely", "probably", or "usually" unless backed by evidence in the current artifact or by a proposed test.
- Separate observation, inference, hypothesis, and conclusion.
- Prefer one discriminating experiment over many broad diagnostics.
- When data is insufficient, say exactly what cannot be concluded.
- Preserve uncertainty, but make it operational: state what measurement would reduce it.

## Workflow

### 1. State the Phenomenon

Restate the anomaly as a measurable contrast:

- What was expected?
- What was observed?
- How large is the effect?
- How consistent is it across runs, slices, seeds, machines, or conditions?
- What exact quantities are being compared?

If the question compares two measurements, first check whether they measure the same object. List mismatches in workload, inputs, aggregation, instrumentation, warmup, filtering, units, and time windows.

### 2. Build an Evidence Table

For each relevant fact, record:

- `Observed`: directly present in logs, code, data, command output, or user-provided numbers.
- `Derived`: computed from observed data; include the formula or code path.
- `Assumed`: not verified yet; state why it matters.
- `Unknown`: required for a conclusion but currently missing.

Never promote an `Assumed` or `Unknown` item into an explanation.

### 3. Generate Falsifiable Hypotheses

For each hypothesis, provide:

- Mechanism: the proposed causal path.
- Prediction: what should be true if the mechanism is real.
- Counter-prediction: what observation would make the hypothesis unlikely.
- Minimal test: the smallest command, slice, perturbation, or controlled experiment that distinguishes it.
- Acceptance criterion: a concrete threshold or qualitative pass/fail condition.

Good hypotheses expose risk. If no available test can distinguish two explanations, merge them into a single unresolved class instead of pretending to know which one is true.

### 4. Run or Propose Experiments

When local data or code is available, inspect it and run focused analyses before explaining. Use existing project tools and preserve reproducibility by reporting commands, filters, sample sizes, and paths.

Design experiments that isolate one factor at a time when feasible:

- Alignment tests: compare only rows with matching input conditions.
- Ablations: remove or freeze one component of the suspected mechanism.
- Stratification: split by the variable that should mediate the effect.
- Negative controls: choose cases where the mechanism predicts no effect.
- Perturbations: intentionally vary the suspected cause and check monotonic response.
- Reproducibility checks: repeat enough times to estimate variance or confidence.

### 5. Answer With Evidence Grades

Use this structure:

```text
Observation:
<measured phenomenon, effect size, scope>

What we can conclude:
<claims directly supported by evidence>

Hypotheses:
1. <hypothesis>
   Evidence: <observed/derived facts>
   Prediction: <testable prediction>
   Falsifier: <what would refute it>
   Test: <specific experiment or command>
   Status: supported | weakened | unresolved | untested

What we cannot conclude:
<claims that would be speculation>

Next experiment:
<single highest-information test and why>
```

If the user wants a short answer, still include at least the falsifier or next experiment for each causal claim.

## Anti-Patterns

Reject explanations that have these shapes:

- "This is probably due to X, Y, and Z" without showing which observation distinguishes X from Y or Z.
- "The difference is reasonable" without defining a model or threshold that predicts the size of the difference.
- "It may be because the real workload is messier" without naming the measurable variable and showing it correlates with the effect.
- "The trend is consistent, so the explanation is fine" when the proposed cause was not isolated.
- "This metric excludes CPU time, but GPU kernels can still differ" without proving the compared kernel sets, shapes, or inputs differ.

## Example Standard

For a question like "kernel_total_ms only counts kernel time, so why is e2e consistently above the microbenchmark?", do not give a causal list first. Instead:

1. Verify whether e2e and microbenchmark rows match on batch size, context length, kernel set, sequence distribution, warmup, and aggregation.
2. Quantify the residual after exact matching, not nearest-bucket matching.
3. Test candidate mechanisms independently, such as longer actual sequence lengths, ragged batches, different kernel mixes, or cache/page state.
4. State which mechanisms are supported, which are only plausible, and what experiment would falsify each.
