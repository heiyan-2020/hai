# Protocol schema  (annotated reference)

A protocol is the **contract for one code-produced artifact**: it fixes how the
artifact is produced and how every conclusion-bearing part of it traces to the
code, so the agent and the human agree on the same object. An *artifact* is
anything a run emits that something downstream trusts — a summary JSON, a
derived table, a figure, a single number. An experiment is just the artifact
at the top (a run root + its summary); a figure rendered from that run is
another artifact one level down. The goal is that **every artifact is
verifiable**, all the way down.

One file per artifact-producer, named `{task-id}-protocol.md`. Every protocol —
per-task or reusable (a figure kind, a standard table, shared across
experiments) — lives under `.claude-research/protocols/`, referenced by path.
Protocols are durable contracts, so they get their own directory rather than
sitting inside `.claude-research/channels/{channel}/` among per-run files.

It is markdown — not yaml — because the lineage layer needs logical description
a flat key/value file cannot carry, and the `### Field:` blocks carry fenced
code snippets that do not belong in yaml. But it is **not** free prose: every
conclusion-bearing field traces to the infra code that computes it, and the
artifact is produced through exactly one script.

## The contract, in one picture

A protocol is **run-agnostic** — it describes the artifact, not any single
execution that produced it. The split that makes protocol and fact orthogonal:

| The protocol fixes (the contract) | A fact records (one run of it) |
|---|---|
| the one script that produces the artifact | the exact argument values passed |
| the parameter interface + the fixed choices | the `commit` and `branch` it ran at |
| the output shape (which files, what's in them) | the hardware, the resulting numbers |
| each field → the infra that computes it | the recompute from the stored output |

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

## The artifact tree: shape first, then lineage

A run does not produce one file; it produces a *tree* of files, only some of
which bear conclusions. The body of a protocol declares that tree, then traces
the parts that matter:

1. **`## Run root shape`** — a fenced tree of *every* path the run writes, each
   node tagged with its state:
   - `[shape-only]` — a produced file that carries no conclusion (a raw trace, a
     log). It is declared so the shape is complete, but gets no lineage.
   - `[bears conclusions]` — a file something downstream trusts. It gets a
     `## Artifact:` section that inlines its fields.
   - `[bears conclusions, delegated]` — a conclusion-bearing file rich enough to
     be its own first-class object (a figure, a sub-pipeline output). It gets a
     `## Artifact:` section that delegates to a child protocol.
2. **One `## Artifact: <path>` section per conclusion-bearing node** — and only
   per conclusion-bearing node. Each `[bears conclusions]` / `[bears
   conclusions, delegated]` path in the shape has exactly one section, and every
   `## Artifact:` section's path is a node so marked. The two sides are a
   bijection: no uncovered conclusion-bearing path, no artifact section for a
   shape-only path.

An **inline** artifact carries `contains:` / `git_tracked:` and a `fields:`
list naming *every* field it has, each tagged `(important)` or `(shape-only)`:

- `(important)` — a conclusion-bearing field; it gets one `### Field:` block
  below that traces it to the producing code.
- `(shape-only)` — a field present in the artifact but deliberately not traced.

Listing every field, marked, makes "deliberately not traced" and "forgotten"
visibly distinct in the file. An inline artifact must have **at least one
important field** — a conclusion-bearing artifact with nothing worth tracing is
a contradiction.

A **delegated** artifact carries `lineage_protocol:` and *no* `fields:` list and
*no* `### Field:` blocks — the child protocol is its single source of truth (see
below).

## Recursion: an artifact can delegate its lineage to a child protocol

A rich artifact — a figure, or a sub-pipeline output — has internal structure
that its parent protocol should not try to cram into one field. Instead the
parent **delegates**: the artifact section names a `lineage_protocol`, a child
protocol that fully explains that artifact as its own first-class object.

```markdown
## Artifact: data/latency_breakdown.png
contains: the latency-breakdown figure rendered from summary.yaml
git_tracked: true
lineage_protocol: "demo-latency-figure-protocol.md"   # ← delegate the image's lineage
```

The child (`demo-latency-figure-protocol.md`) is a normal protocol whose
`script` is the artifact's producer (the plotting script) and whose `### Field:`
blocks are the artifact's own components. When an artifact delegates, the parent
does **not** also inline-describe it — the child is the single source of truth,
so the delegated artifact carries no fields and no field blocks. Delegation
nests to any depth and bottoms out at leaves whose fields point at infra.

A `lineage_protocol` path resolves **relative to the referencing protocol's own
directory** (absolute paths are allowed too), so the protocol graph is
self-contained and survives being moved.

A protocol may have only delegated artifacts and **no own `### Field:` blocks** —
a pure-composition protocol (everything rich is delegated) is valid. What is
*not* valid is a protocol where nothing bears conclusions at all.

## Structure

````markdown
---
task: <task-id>
script: "<path to the single entry-point script>"   # the only way to produce it
parameters:
  - name: "--out-dir"
    purpose: "directory for the per-run and summary files"
    required: false
    default: "data"
  - name: "--figure-out"
    purpose: "if set, also render the figure to this path"
    required: false
    default: ""
fixed:                                  # hard-coded choices that define the artifact
  - "the measured kernels (a fixed prefill pass and decode loop in src/runner.py)"
---

# <task-id> protocol — one-line description

## Run root shape
```text
<run_root>/
  data/summary.yaml             [bears conclusions]
  data/latency_breakdown.png    [bears conclusions, delegated]
  data/run.yaml                 [shape-only]
```

## Artifact: data/summary.yaml
contains: mean prefill_ms, decode_ms, and the derived overhead_ms
git_tracked: true
fields:
  - prefill_ms    (important)
  - decode_ms     (important)
  - overhead_ms   (important)
  - n_runs        (shape-only)

### Field: prefill_ms
- nature: MEASURED | DERIVED | SYNTHETIC | EXTERNAL
- source_field: <where the value is read in the OUTPUT file>
- file: <the INFRA source file that computes it>     # not the script, not the output
- formula: <expression>                              # REQUIRED iff nature == DERIVED
```python
<the core infra lines that produce this field — at most 5, verbatim>
```

### Field: <name>
...

## Artifact: data/latency_breakdown.png             # a delegated artifact
contains: the latency-breakdown figure rendered from summary.yaml
git_tracked: true
lineage_protocol: "demo-latency-figure-protocol.md"  # no fields, no `### Field:` blocks
````

## Lineage points at the producing code, not the script

The `### Field:` blocks are where each conclusion-bearing field earns its
trust, and the rule is the same for every kind of artifact: a field's `file`
and snippet name the **code that actually produces that field**, not the
entry-point script (which only orchestrates) and not the output file (which only
stores the result). What a field is, and what its producing code is, vary by
artifact — a field in a summary JSON traces to the function that computes it, a
cell of a derived table to the aggregation that fills it, a bar in a figure to
the draw call that turns the number into geometry — but the rule does not.

- `source_field` says *where the value is read* in the output (e.g.
  `overhead_ms` in `summary.yaml`).
- `file` + snippet say *what code produced it* — the real function in the
  codebase, with the core lines copied verbatim.

For a presentational artifact (a figure, a formatted table) the value a field
shows is usually computed upstream; the block does not re-derive it. The
`nature` still reflects that datum — `MEASURED` or `DERIVED` (with `formula` even
though the computation lives upstream) — `source_field` names it, and the snippet
is the line that renders it.

The snippet is the anchor: it survives line-number drift, and a reader (or
Codex) sees the lineage logic without opening the file. Keep it to the core — 5
lines at most, not a whole function. Pointing the snippet at the wrapper script,
or quoting the output back at itself, both defeat the purpose: neither shows how
the field came to be.

## Nature tags

| Tag | Meaning |
|---|---|
| `MEASURED`  | Read from a real measurement (wall clock, counter, eval score). |
| `DERIVED`   | Computed from other fields. `formula:` is mandatory. |
| `SYNTHETIC` | Produced by a model/heuristic/assumption, not measured. |
| `EXTERNAL`  | Taken from a paper, dataset, or third-party source. |

The nature tag is the integrity signal: a reader instantly knows whether a bar
in a chart is real or fabricated. A `SYNTHETIC` value mislabeled `MEASURED` is
exactly what `pin-codex-audit` exists to catch.

## Field consumers (what the checker enforces)

`protocol_check.py` enforces, recursively across the whole delegation tree:

- `task` is present.
- `script` is present and the file exists on disk.
- If the script is a `.py` file, it does not read configuration from the
  environment (`os.getenv` / `os.environ`) — a run must be determined by its
  arguments alone. This is a shallow scan of the entry file only, not its
  imports.
- `parameters` is a non-empty list, each entry a mapping with a `name`.
- A `## Run root shape` section is present with at least one node marked
  `[bears conclusions]` (or `[bears conclusions, delegated]`) — something must
  bear conclusions.
- **Artifact ↔ shape bijection.** Every `[bears conclusions]` node has a
  matching `## Artifact:` section, and every `## Artifact:` section's path is a
  bears-conclusions node — both directions. A shape-only node with an artifact
  section, or a bears-conclusions node without one, is an error.
- **Delegation marker agreement.** A node marked delegated has a
  `lineage_protocol:`, and an artifact with a `lineage_protocol:` is marked
  delegated — both directions.
- **Inline artifact coverage.** An inline (non-delegated) artifact has at least
  one `(important)` field.
- **Important-field ↔ `### Field:`-block bijection.** Each important field has
  exactly one `### Field:` block; each `### Field:` block names an important
  field of its artifact. No uncovered important field, no orphan block, no
  duplicate block.
- **Field-block contract.** Each `### Field:` block has a `nature:` that is one
  of the 4 valid values, a `file:`, and a fenced code snippet that is at most 5
  (non-blank) lines and appears verbatim in `file` (matched line-by-line with
  surrounding whitespace stripped; the line number is *derived* from the match,
  never stored). A `DERIVED` field carries a `formula:`; a non-`DERIVED` field
  need not.
- **No inline lineage on a delegated artifact.** A delegated artifact has no
  `fields:` list and no `### Field:` blocks.
- **Delegation resolution.** For every artifact with a `lineage_protocol`: the
  referenced file exists (resolved relative to this protocol's directory), the
  child protocol is itself structurally valid (checked recursively), the parent
  artifact's path matches an artifact the child declares (a placeholder-aware
  consistency check, not byte-equality), and the reference graph has no cycle.

Artifact accounting (pin-aware-agent Phase 5) additionally reconciles the
produced files against the `## Run root shape` tree — across the whole
delegation tree, so a child protocol's declared shape counts too. Shape-only
nodes count, which is why they are declared.

> The machine check is necessary, not sufficient: it cannot tell whether the
> `fixed` choices are complete, whether a parameter's stated default is the real
> one, whether a field's snippet truly *computes* the value rather than merely
> looking it up, whether config leaks in through an *imported* module rather than
> the entry file, or whether a delegated child truly explains the *same* bytes
> the parent emits. Those remain the job of the human confirmation
> (pin-aware-agent Phase 2b) and the adversarial Codex audit (Phase 6).
