# Protocol schema  (annotated reference)

A protocol is the **contract for one experiment**: it fixes the shape of what a
run produces and how it is produced, so that the agent and the human agree on
the same object. One file per task, named `{task-id}-protocol.md`, under
`.claude-research/channels/{channel}/`.

It is markdown — not yaml — because the lineage layer needs logical description a
flat key/value file cannot carry. But it is **not** free prose: every produced
number traces to the infra code that computes it, and the experiment runs
through exactly one script.

## The contract, in one picture

A protocol is **run-agnostic** — it describes the experiment, not any single
execution of it. The split that makes protocol and fact orthogonal:

| The protocol fixes (the contract) | A fact records (one run of it) |
|---|---|
| the one script that runs the experiment | the exact argument values passed |
| the parameter interface + the fixed choices | the `commit` and `branch` it ran at |
| the output shape (which files, what's in them) | the hardware, the resulting numbers |
| each number → the infra that computes it | the recompute from the stored output |

So a protocol never carries a commit, a branch, or concrete argument values —
those belong to the fact, because they identify *an instance*, not *the
experiment*.

## One script, parameters only

Every protocol corresponds to **exactly one script**, and that script is the
*only* entry point: real runs and reproductions both go through it. The contract
on that script is strict, because it is what makes a run identifiable from its
arguments alone:

- **Everything configurable is a parameter.** Each knob a run might vary is
  exposed as a command-line argument and listed under `parameters`.
- **Everything else is fixed in the script** and listed under `fixed`, because a
  hard-coded choice (which model, which kernel) is part of the experiment's
  identity even though no run changes it.
- **No configuration outside the arguments** — no environment variables, no
  edited globals, no "first set `X=...`". Running `script <args>` with nothing
  else set must fully determine the run. If the script needs more than its
  arguments today, fixing that is part of authoring the protocol.

## Structure

````markdown
---
task: <task-id>
script: "<path to the single entry-point script>"   # the only way to run it
parameters:
  - name: "--gpu"
    purpose: "which physical GPU to run on"
    required: true
  - name: "--tool-latency-s"
    purpose: "simulated tool-call latency, seconds"
    required: false
    default: 1.0
    choices: [0.0, 1.0, 5.0]
fixed:                                  # hard-coded choices that define the experiment
  - "model GLM-4.7-Flash, FlashMLA, CUDA graph enabled"
  - "embedding validation runs locally"
artifacts:                              # the output shape — what one run writes
  - path: "outputs/<run-id>/seg_00_24/summary.json"
    contains: "per-case status, elapsed_time, eval.valid, speculation counters"
    git_tracked: false
  - path: ".claude-research/data/<fact-id>/summary.json"
    contains: "the copied, git-tracked aggregate a fact cites"
    git_tracked: true
side_effects:
  - path: "<extra file the run writes>"
    git_tracked: false
---

# <task-id> protocol — one-line description

## Element: <name>
- nature: MEASURED | DERIVED | SYNTHETIC | EXTERNAL
- source_field: <where the value is read in the OUTPUT file>
- file: <the INFRA source file that computes it>     # not the script, not the output
- formula: <expression>                              # REQUIRED iff nature == DERIVED
```python
<the core infra lines that produce this element — at most 5, verbatim>
```

## Element: <name>
...
````

## Lineage points at the infra, not the script

The `## Element` blocks are where each conclusion-bearing number earns its
trust. The crucial rule: an element's `file` and `snippet` name the **infra code
that actually computes the value**, not the entry-point script (which only
orchestrates) and not the output file (which only stores the result).

- `source_field` says *where the value is read* in the output (e.g.
  `common_completed.speedup` in `summary.json`).
- `file` + `snippet` say *what code produced it* — the real function in the
  codebase, with the core lines copied verbatim.

The snippet is the anchor: it survives line-number drift, and a reader (or
Codex) sees the lineage logic without opening the file. Keep it to the core — 5
lines at most, not a whole function. Pointing the snippet at the wrapper script,
or quoting the output JSON back at itself, both defeat the purpose: neither shows
how the number came to be.

## Nature tags

| Tag | Meaning |
|---|---|
| `MEASURED`  | Read from a real measurement (wall clock, counter, eval score). |
| `DERIVED`   | Computed from other elements. `formula:` is mandatory. |
| `SYNTHETIC` | Produced by a model/heuristic/assumption, not measured. |
| `EXTERNAL`  | Taken from a paper, dataset, or third-party source. |

The nature tag is the integrity signal: a reader instantly knows whether a bar
in a chart is real or fabricated. A `SYNTHETIC` value mislabeled `MEASURED` is
exactly what `pin-codex-audit` exists to catch.

## Field consumers

`protocol_check.py` enforces:

- `task` is present.
- `script` is present and the file exists on disk.
- If the script is a `.py` file, it does not read configuration from the
  environment (`os.getenv` / `os.environ`) — a run must be determined by its
  arguments alone. This is a shallow scan of the entry file only, not its
  imports.
- `parameters` is a non-empty list, each entry a mapping with a `name`.
- Every `artifacts[]` entry is a mapping with a non-empty `path`.
- At least one `## Element:` block exists.
- Every element has a `nature:` with one of the 4 valid values, a `file:`, and a
  fenced code `snippet`.
- The snippet is at most 5 (non-blank) lines and appears verbatim in `file`
  (matched line-by-line with surrounding whitespace stripped; the line number is
  *derived* from the match, never stored).
- Every `DERIVED` element carries a `formula:`.

`pin-audit.py` (artifact accounting, Phase 5) additionally checks the produced
files against `artifacts[].path` ∪ `side_effects[].path`.

> The machine check is necessary, not sufficient: it cannot tell whether the
> `fixed` choices are complete, whether a parameter's stated default is the real
> one, or whether config leaks in through an *imported* module rather than the
> entry file. Those remain the job of the human confirmation (pin-aware-agent
> Phase 2b) and the adversarial Codex audit (Phase 6).
