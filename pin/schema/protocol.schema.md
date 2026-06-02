# Protocol schema  (annotated reference)

A protocol is the **contract for one code-produced artifact**: it fixes how the
artifact is produced and how every conclusion-bearing part of it traces to the
code, so the agent and the human agree on the same object. An *artifact* is
anything a run emits that something downstream trusts — a summary JSON, a
derived table, a figure, a single number. An experiment is just the artifact
at the top (a run root + its summary); a figure rendered from that run is
another artifact one level down. The goal is that **every artifact is
verifiable**, all the way down.

One file per artifact-producer, named `{task-id}-protocol.md`. A per-task
protocol lives under `.claude-research/channels/{channel}/`; a *reusable*
artifact protocol that several experiments share (a figure kind, a standard
table) lives under `.claude-research/general_protocols/` and is referenced by
path.

It is markdown — not yaml — because the lineage layer needs logical description
a flat key/value file cannot carry. But it is **not** free prose: every produced
component traces to the infra code that computes it, and the artifact is
produced through exactly one script.

## The contract, in one picture

A protocol is **run-agnostic** — it describes the artifact, not any single
execution that produced it. The split that makes protocol and fact orthogonal:

| The protocol fixes (the contract) | A fact records (one run of it) |
|---|---|
| the one script that produces the artifact | the exact argument values passed |
| the parameter interface + the fixed choices | the `commit` and `branch` it ran at |
| the output shape (which files, what's in them) | the hardware, the resulting numbers |
| each component → the infra that computes it | the recompute from the stored output |

So a protocol never carries a commit, a branch, or concrete argument values —
those belong to the fact, because they identify *an instance*, not *the
artifact*.

## One script, parameters only

Every protocol corresponds to **exactly one script**, and that script is the
*only* entry point: real runs and reproductions both go through it. For a figure
that one script is the *plotting* script; for an experiment it is the run
script. The contract on that script is strict, because it is what makes a run
identifiable from its arguments alone:

- **Everything configurable is a parameter.** Each knob a run might vary is
  exposed as a command-line argument and listed under `parameters`.
- **Everything else is fixed in the script** and listed under `fixed`, because a
  hard-coded choice (which model, which colour map) is part of the artifact's
  identity even though no run changes it.
- **No configuration outside the arguments** — no environment variables, no
  edited globals, no "first set `X=...`". Running `script <args>` with nothing
  else set must fully determine the output. If the script needs more than its
  arguments today, fixing that is part of authoring the protocol.

## Recursion: an artifact can delegate its lineage to a child protocol

A rich artifact — a figure, or a sub-pipeline output — has internal structure
that its parent protocol should not try to cram into one element. Instead the
parent **delegates**: the artifact entry names a `lineage_protocol`, a child
protocol that fully explains that artifact as its own first-class object.

```yaml
artifacts:
  - path: "<run_root>/agent_timeline_checked/<case>_profile_clock_compare.png"
    contains: "per-case baseline-vs-spec profile-clock timeline"
    git_tracked: false
    lineage_protocol: "agent-timeline-protocol.md"   # ← delegate the image's lineage
```

The child (`agent-timeline-protocol.md`) is a normal protocol whose `script` is
the artifact's producer (the plotting script) and whose `## Element` blocks are
the artifact's own components. When an artifact delegates, the parent does **not**
also inline-describe it — the child is the single source of truth. Delegation
nests to any depth and bottoms out at leaves whose elements point at infra.

A `lineage_protocol` path resolves **relative to the referencing protocol's own
directory** (absolute paths are allowed too), so the protocol graph is
self-contained and survives being moved.

## Structure

````markdown
---
task: <task-id>
script: "<path to the single entry-point script>"   # the only way to produce it
parameters:
  - name: "--gpu"
    purpose: "which physical GPU to run on"
    required: true
  - name: "--tool-latency-s"
    purpose: "simulated tool-call latency, seconds"
    required: false
    default: 1.0
    choices: [0.0, 1.0, 5.0]
fixed:                                  # hard-coded choices that define the artifact
  - "model GLM-4.7-Flash, FlashMLA, CUDA graph enabled"
  - "embedding validation runs locally"
artifacts:                              # the output shape — what one run writes
  - path: "outputs/<run-id>/seg_00_24/summary.json"
    contains: "per-case status, elapsed_time, eval.valid, speculation counters"
    git_tracked: false
  - path: "outputs/<run-id>/agent_timeline_checked/<case>.png"
    contains: "per-case profile-clock timeline"
    git_tracked: false
    lineage_protocol: "agent-timeline-protocol.md"   # delegated artifact
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

A protocol may have only delegated artifacts and **no own `## Element` blocks** —
a pure-composition protocol (everything rich is delegated) is valid. Otherwise it
needs at least one element.

## Lineage points at the producing code, not the script

The `## Element` blocks are where each conclusion-bearing component earns its
trust, and the rule is the same for every kind of artifact: an element's `file`
and `snippet` name the **code that actually produces that component**, not the
entry-point script (which only orchestrates) and not the output file (which only
stores the result). What a component is, and what its producing code is, vary by
artifact — a field in a summary JSON traces to the function that computes it, a
cell of a derived table to the aggregation that fills it, a bar in a figure to
the line that draws it — but the rule does not.

- `source_field` says *where the value is read* in the output (e.g.
  `common_completed.speedup` in `summary.json`).
- `file` + `snippet` say *what code produced it* — the real function in the
  codebase, with the core lines copied verbatim.

For a presentational artifact (a figure, a formatted table) the value a component
shows is usually computed upstream; the element does not re-derive it. The
`nature` still reflects that datum — `MEASURED` or `DERIVED` (with `formula` even
though the computation lives upstream) — `source_field` names it, and the snippet
is the line that renders it.

The snippet is the anchor: it survives line-number drift, and a reader (or
Codex) sees the lineage logic without opening the file. Keep it to the core — 5
lines at most, not a whole function. Pointing the snippet at the wrapper script,
or quoting the output back at itself, both defeat the purpose: neither shows how
the component came to be.

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

`protocol_check.py` enforces, recursively across the whole delegation tree:

- `task` is present.
- `script` is present and the file exists on disk.
- If the script is a `.py` file, it does not read configuration from the
  environment (`os.getenv` / `os.environ`) — a run must be determined by its
  arguments alone. This is a shallow scan of the entry file only, not its
  imports.
- `parameters` is a non-empty list, each entry a mapping with a `name`.
- Every `artifacts[]` entry is a mapping with a non-empty `path`.
- At least one `## Element:` block **or** at least one delegated artifact exists.
- Every element has a `nature:` with one of the 4 valid values, a `file:`, and a
  fenced code `snippet`.
- The snippet is at most 5 (non-blank) lines and appears verbatim in `file`
  (matched line-by-line with surrounding whitespace stripped; the line number is
  *derived* from the match, never stored).
- Every `DERIVED` element carries a `formula:`.
- For every artifact with a `lineage_protocol`: the referenced file exists
  (resolved relative to this protocol's directory), the child protocol is itself
  structurally valid (checked recursively), the parent artifact's path matches an
  artifact the child declares (a placeholder-aware consistency check, not
  byte-equality), and the reference graph has no cycle.

Artifact accounting (pin-aware-agent Phase 5) additionally reconciles the
produced files against `artifacts[].path` ∪ `side_effects[].path` — across the
whole delegation tree, so a child protocol's declared artifacts count too.

> The machine check is necessary, not sufficient: it cannot tell whether the
> `fixed` choices are complete, whether a parameter's stated default is the real
> one, whether config leaks in through an *imported* module rather than the
> entry file, or whether a delegated child truly explains the *same* bytes the
> parent emits. Those remain the job of the human confirmation (pin-aware-agent
> Phase 2b) and the adversarial Codex audit (Phase 6).
