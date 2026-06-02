---
name: pin-protocol
description: >-
  Author and validate a per-task data-lineage protocol — the contract for one
  experiment. A protocol fixes the single script that runs the experiment, the
  parameters it exposes, the shape of its output, and the infra code that
  computes each number; it is run-agnostic, so commit/branch/argument-values
  live in the fact, not here. Use whenever a research task is about to produce
  data a fact or figure will cite, before producing it, or when an existing
  protocol needs a new parameter or output. This is the authoring home invoked
  by pin-aware-agent Phase 2b. Trigger on "declare the protocol", "write the
  data lineage", "make this experiment reproducible", or any time data is
  produced without one runnable entry point.
type: flow
user-invocable: true
---

# pin-protocol

A protocol is the **contract for one experiment** — the object the agent and the
human both point at when they say "this run." It is read by three people who
were not at the keyboard: the human deciding whether to trust the result, the
Codex auditor checking the lineage isn't fiction, and you in a month with the
context gone. If any of them cannot reproduce the experiment or trace a number
to its code from the protocol plus its one script, the protocol has failed.

The defining idea: a protocol is **run-agnostic**. It describes the experiment,
never a single execution of it. That is what keeps it orthogonal to a fact:

| The protocol fixes (the contract) | A fact records (one run of it) |
|---|---|
| the one script that runs the experiment | the exact argument values passed |
| the parameter interface + the fixed choices | the `commit` and `branch` it ran at |
| the output shape (which files, what's in them) | the hardware, the resulting numbers |
| each number → the infra that computes it | the recompute from the stored output |

So a protocol never carries a commit, a branch, or concrete argument values.
Those identify an *instance*, and the instance is the fact's job (see
`pin-fact`).

The canonical structure is `<PLUGIN_ROOT>/schema/protocol.schema.md`. Read it
before creating or modifying a protocol — it defines the exact fields and what
`protocol_check.py` enforces. This skill is the *workflow and the judgment*: how
to make the one script honest, and how to trace each number to infra.

## Required layout

One file per task, named `{task-id}-protocol.md`, under
`.claude-research/channels/{channel}/`.

## One script is the only entry point — and you own it

Every protocol corresponds to **exactly one script**, and that script is the
only way the experiment runs: every real run and every reproduction goes through
it. Making that script exist and obey the contract is *part of authoring the
protocol*, not a precondition you assume — if the experiment is currently run by
a pile of ad-hoc commands or notebook cells, you consolidate it into one
entry-point script first.

The contract on the script, which is what lets a run be identified from its
arguments alone:

- **Everything configurable is a parameter.** Each knob a run might vary —
  which GPU, which segment, the tool latency — is exposed as a command-line
  argument. The protocol lists each under `parameters` with its purpose, whether
  it is required, its default, and any allowed values.
- **Everything else is fixed in the script** and listed under `fixed`. A
  hard-coded choice (which model, which kernel, that validation runs locally) is
  part of the experiment's identity even though no run changes it — so the
  reader needs to see it, and it must not silently differ between runs.
- **Nothing outside the arguments configures the run** — no environment
  variables, no edited globals, no "first export `X`". `script <args>` with a
  clean environment must fully determine the run. If the script reads an env var
  or a hard-wired absolute path today, turning that into a parameter (or a
  documented `fixed` default) is the work.

The test for this part: hand someone the script path and the argument list, on a
clean shell. If they need anything you didn't write down to get the same run,
the contract is broken.

## Authoring workflow

1. **Consolidate to one script.** Identify or create the single entry-point
   script that runs this experiment end to end. Drive every configurable choice
   from its arguments; hard-code the rest.
2. **Write the contract frontmatter.** `task`; the `script` path; `parameters`
   (name, purpose, required/default/choices); `fixed` (the hard-coded choices
   that define the experiment); `artifacts` (the output shape — each file a run
   writes, what it contains, `git_tracked`); `side_effects` for the rest.
3. **Trace each conclusion-bearing number to infra.** One `## Element:` block
   per number, with a `nature` tag, the `source_field` where it is read in the
   output, the `file` — *the infra source that computes it* — a `formula` if
   `DERIVED`, and a fenced **snippet** of the core infra lines (≤5, verbatim).
4. **Run `protocol_check.py`** and fix every structural problem.

## Lineage points at the infra, not the script

This is the rule most protocols get wrong. The script is a thin runner; the
*truth* of a number lives in the infra function that computes it. So an
element's `file` and `snippet` must name that infra code — not the entry-point
script (which only orchestrates), and not the output file (which only stores the
result).

- `source_field` → where the value is read in the output (`common_completed.speedup`).
- `file` + `snippet` → the real function that produced it, core lines verbatim.

Quoting the output JSON back at itself proves nothing — it restates the number
in question. Pointing at the script shows what was launched, not how the value
was computed. Point at the infra.

The `nature` tag is the integrity signal: `MEASURED` (read from a real
measurement), `DERIVED` (computed — `formula` mandatory), `SYNTHETIC` (a
model/heuristic/assumption), `EXTERNAL` (a third-party source). A `SYNTHETIC`
value dressed as `MEASURED` turns a fabricated chart bar into a "real" one — the
exact thing `pin-codex-audit` looks for.

## Worked example (the shape to imitate)

````markdown
---
task: streaming-spec-tool1s-segmented
script: "scripts/streaming_spec/run_segmented_e2e.py"
parameters:
  - name: "--gpu"
    purpose: "physical GPU index to run on"
    required: true
  - name: "--segment"
    purpose: "case range, e.g. 0-24"
    required: false
    default: "0-24"
  - name: "--tool-latency-s"
    purpose: "simulated tool-call latency in seconds"
    required: false
    default: 1.0
fixed:
  - "model GLM-4.7-Flash, FlashMLA, CUDA graph enabled"
  - "embedding validation runs locally; max_concurrent_inducers=3"
artifacts:
  - path: "outputs/<run-id>/seg_00_24/summary.json"
    contains: "per-case status, elapsed_time, eval.valid, speculation counters"
    git_tracked: false
  - path: ".claude-research/data/<fact-id>/summary.json"
    contains: "the git-tracked aggregate a fact cites"
    git_tracked: true
---

# streaming-spec-tool1s-segmented protocol

## Element: common_completed_speedup
- nature: DERIVED
- source_field: `common_completed.speedup` in summary.json
- file: src/streaming_spec/metrics.py
- formula: sum(baseline elapsed) / sum(spec elapsed) over cases both runs completed
```python
both = [c for c in cases if c.baseline.done and c.spec.done]
speedup = sum(c.baseline.elapsed for c in both) / sum(c.spec.elapsed for c in both)
```
````

Contrast with the version this replaces: it had a `run` field of prose
(*"Segmented BFCL … ran on physical GPU1 with tool latency 1s …"*) instead of a
script, a `source` of two bare filenames, and elements whose `file` pointed at
`summary.json` with the output JSON quoted back as the "snippet." Nobody could
run it from its arguments, and no number traced to the code that made it.

## The test before you stop

Could a colleague who was **not** on this run, given only this protocol:
(a) run the experiment with `script <args>` on a clean shell and get a
well-formed output, and (b) trace each element's number to the infra file and
lines that compute it? If the script needs hidden config, or a snippet points at
the script or the output instead of the infra, the answer is no — fix it before
validating.

## Validation

```bash
python3 <PLUGIN_ROOT>/scripts/protocol_check.py \
  .claude-research/channels/<channel>/<task-id>-protocol.md
```

Exit `0` means structurally valid: `task` present; `script` exists and (if a
`.py` file) reads nothing from the environment; `parameters` is a non-empty list
with a `name` each; every `artifacts[]` has a `path`; and every element has a
`nature`, a `file`, and a verbatim ≤5-line snippet that locates in that file
(with a `formula` for `DERIVED`). Pass `--base <dir>` if paths resolve against a
directory other than the cwd.

What `protocol_check.py` still can't tell — whether `fixed` is complete, whether
a parameter's default is the real one, whether config leaks in through an
*imported* module rather than the entry script, or whether a `nature` tag is
honest — is what the human confirmation (Phase 2b) and the Codex audit (Phase 6)
are for.
