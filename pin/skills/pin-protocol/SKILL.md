---
name: pin-protocol
description: >-
  Author and validate a data-lineage protocol — the contract for one
  code-produced artifact: a summary, a derived table, a figure, or a number. It
  fixes the single script that produces the artifact, the parameters it exposes,
  the output shape, and the code behind every conclusion-bearing component; it is
  run-agnostic, so commit/branch/argument values live in the fact. A run produces
  a tree of artifacts, so a rich node delegates its internal lineage to a child
  protocol via `lineage_protocol`, and verifiability composes all the way down.
  Use whenever a task is about to produce data a fact or figure will cite, before
  producing it; when an artifact's internals aren't yet traceable to code; or
  when a protocol needs a new parameter, output, or delegated child. Authoring
  home invoked by pin-aware-agent Phase 2b. Trigger on "declare the protocol",
  "write the data lineage", "make this experiment or figure reproducible", or any
  time an artifact is produced without one runnable, traceable entry point.
type: flow
user-invocable: true
---

# pin-protocol

A protocol is the **contract for one code-produced artifact** — the object the
agent and the human both point at when they say "this output." An *artifact* is
anything a run emits that something downstream trusts: a summary JSON, a derived
table, a figure, a single number. It is read by three people who were not at
the keyboard: the human deciding whether to trust the result, the Codex auditor
checking the lineage isn't fiction, and you in a month with the context gone. If
any of them cannot reproduce the artifact or trace a part of it to its code from
the protocol plus its one script, the protocol has failed.

The defining idea: a protocol is **run-agnostic**. It describes the artifact,
never a single execution of it. That is what keeps it orthogonal to a fact:

| The protocol fixes (the contract) | A fact records (one run of it) |
|---|---|
| the one script that produces the artifact | the exact argument values passed |
| the parameter interface + the fixed choices | the `commit` and `branch` it ran at |
| the output shape (which files, what's in them) | the hardware, the resulting numbers |
| each component → the infra that computes it | the recompute from the stored output |

So a protocol never carries a commit, a branch, or concrete argument values.
Those identify an *instance*, and the instance is the fact's job (see
`pin-fact`).

The goal is that **every artifact is verifiable, all the way down.** A run
produces not one number but a *tree* of artifacts — a run-root directory holding
a summary, per-case traces, figures, derived datasets. Verifiability has to reach
every node of that tree, not just the top summary, and it does so by
**recursion** — a rich node delegates its internals to its own protocol (see
below).

The canonical structure is `<PLUGIN_ROOT>/schema/protocol.schema.md`. Read it
before creating or modifying a protocol — it defines the exact format and what
`protocol_check.py` enforces. This skill is the *workflow and the judgment*: how
to make the one script honest, how to trace each field to infra, and when to
delegate an artifact to a child protocol instead of cramming its internals into
one field.

## Required layout

One file per artifact-producer, named `{task-id}-protocol.md`. Every protocol
lives under `.claude-research/protocols/` — never inside a channel directory. A
protocol is a durable contract, not run scratch; keeping all of them in one
dedicated directory keeps them findable next to each other instead of buried
among a channel's raw outputs and per-run files, and makes `lineage_protocol`
references plain same-directory paths. A *reusable* artifact protocol that
several experiments share — a figure kind, a standard table — is simply another
file in the same directory, referenced by path from each parent that delegates
to it.

## One script is the only entry point — and you own it

Every protocol corresponds to **exactly one script**, and that script is the
only way the artifact gets produced: every real run and every reproduction goes
through it. For a figure that script is the *plotting* script; for an experiment
it is the run script. Making that script exist and obey the contract is *part of
authoring the protocol*, not a precondition you assume — if the artifact is
currently produced by a pile of ad-hoc commands or notebook cells, you
consolidate it into one entry-point script first.

The contract on the script, which is what lets a run be identified from its
arguments alone:

- **Everything configurable is a parameter.** Each knob a run might vary — which
  GPU, which segment, which case to plot — is exposed as a command-line argument.
  The protocol lists each under `parameters` with its purpose, whether it is
  required, its default, and any allowed values.
- **Everything else is fixed in the script** and listed under `fixed`. A
  hard-coded choice (which model, which colour map, that validation runs locally)
  is part of the artifact's identity even though no run changes it — so the
  reader needs to see it, and it must not silently differ between runs.
- **Nothing outside the arguments configures the run** — no environment
  variables, no edited globals, no "first export `X`". `script <args>` with a
  clean environment must fully determine the output. If the script reads an env
  var or a hard-wired absolute path today, turning that into a parameter (or a
  documented `fixed` default) is the work.

The test for this part: hand someone the script path and the argument list, on a
clean shell. If they need anything you didn't write down to get the same output,
the contract is broken.

## A run produces a tree of artifacts — declare the shape, then the lineage

An experiment rarely produces a single number. It produces a **directory** — a
run root — and that directory is a tree of files, only some of which carry
conclusions. The body of a protocol declares that whole tree first, then traces
the parts that matter. So the body has two layers:

1. **`## Run root shape`** — a fenced tree of *every* path a run writes, each
   node tagged with its state:
   - `[shape-only]` — a produced file that carries no conclusion (a raw trace, a
     log, a run-config dump). Declared so the shape is complete; gets no lineage.
   - `[bears conclusions]` — a file something downstream trusts. Gets a
     `## Artifact:` section that **inlines** its fields.
   - `[bears conclusions, delegated]` — a conclusion-bearing file rich enough to
     be its own first-class object (a figure, a sub-pipeline output). Gets a
     `## Artifact:` section that **delegates** to a child protocol.
2. **One `## Artifact: <path>` section per conclusion-bearing node**, and only
   per conclusion-bearing node. The two sides are a bijection: every
   `[bears conclusions]`/`[bears conclusions, delegated]` path has exactly one
   `## Artifact:` section, and every `## Artifact:` section's path is a node so
   marked. No uncovered conclusion-bearing path, no artifact section for a
   shape-only path.

A typical e2e run-root shape:

```text
<run_root>/
  summary.json              [bears conclusions]
  agent_timeline/<case>.png [bears conclusions, delegated]
  baseline/  spec/          [shape-only]
  run.yaml                  [shape-only]
```

An **inline** artifact carries `contains:` / `git_tracked:` and a `fields:` list
naming *every* field it has, each tagged `(important)` or `(shape-only)`:

- `(important)` — a conclusion-bearing field; it gets one `### Field:` block
  below that traces it to the producing code.
- `(shape-only)` — a field present in the artifact but deliberately not traced.

Listing every field, marked, makes "deliberately not traced" and "forgotten"
visibly distinct in the file. An inline artifact must have **at least one
important field** — a conclusion-bearing artifact with nothing worth tracing is
a contradiction.

## When a node is rich, delegate its lineage to a child protocol

`summary.json` above is described inline, with `### Field:` blocks. But a node
like the timeline figure is not a number — it is a *sub-artifact that is itself
produced and itself cited*: a figure shows a conclusion, a joined kernel profile
is its own derived dataset. Collapsing such a node into one field of the parent
is the mistake the old flat model made — it leaves the node's internals
invisible and unverifiable.

So when a node has its own internal structure, **don't inline it; delegate it.**
Mark it `[bears conclusions, delegated]` in the shape, and its `## Artifact:`
section names a `lineage_protocol` — a child protocol that explains that node as
its own first-class artifact, with its own one script (the thing that produces
*it* — the plotting script, the kernel-join script) and its own `### Field:`
blocks:

```markdown
## Artifact: <run_root>/agent_timeline/<case>.png
contains: per-case profile-clock timeline
git_tracked: false
lineage_protocol: "agent-timeline-protocol.md"   # ← delegated; no fields, no Field blocks
```

A delegated artifact carries `lineage_protocol:` and **no** `fields:` list and
**no** `### Field:` blocks — the child is the single source of truth, and two
descriptions of one thing drift apart. A reusable node (the same timeline figure
rendered by many experiments) becomes one child protocol that every parent
references, instead of being re-explained each time. A protocol whose
conclusion-bearing nodes are *all* delegated has no own `### Field:` blocks at
all — a pure-composition protocol is valid.

Delegation nests to any depth and bottoms out at leaves whose fields point at
infra. A `lineage_protocol` path resolves **relative to the referencing
protocol's own directory** (absolute paths work too), so the protocol graph stays
self-contained. `protocol_check.py` follows every reference: the child must exist,
be itself valid, declare the artifact the parent delegates to it, and the graph
must have no cycle.

## Authoring workflow

Protocols are **run-agnostic and authored before the run**, so you don't read an
output directory that exists yet — you infer the shape and fields **from the
producing code** (or from an example run if one already happens to exist). The
selection is interactive and recurses: artifact-level first, then field-level.

1. **Consolidate to one script.** Identify or create the single entry-point
   script that produces this artifact end to end. Drive every configurable choice
   from its arguments; hard-code the rest.
2. **Write the contract frontmatter.** `task`; the `script` path; `parameters`
   (name, purpose, required/default/choices); `fixed` (the hard-coded choices
   that define the artifact).
3. **Enumerate the run-root shape from the producing code.** Read the script to
   determine *every* path it writes, and list them as the `## Run root shape`
   tree. This is inference from the code, not observation of a run — the protocol
   is authored before the run exists.
4. **The user selects which artifacts bear conclusions.** Present the enumerated
   tree; the user marks which nodes carry conclusions. Everything else is tagged
   `[shape-only]` and stops there.
5. **Per conclusion-bearing artifact, decide inline vs delegate — and recurse.**
   If the node is rich (a figure, a nested pipeline output), mark it
   `[bears conclusions, delegated]` and delegate to a child protocol that you
   author by running *this same workflow* on the child (its own script, shape,
   field selection) — no inline fields. Otherwise it is inline: **list the
   artifact's fields from the code, and the user selects which are important.**
   The non-selected ones are tagged `(shape-only)`.
6. **Author each `### Field:` block, tracing it to the producing code.** One
   block per important field — a summary field, a table cell, a bar of a figure —
   with a `nature` tag, the `source_field` where it is read, the `file` that
   produces it, a `formula` if `DERIVED`, and a fenced **snippet** of the core
   producing lines (≤5, verbatim).
7. **Run `protocol_check.py`** and fix every structural problem, in the parent
   and every child.

The interactive selection is the core new behavior: first the user picks which
artifacts in the tree bear conclusions, then for each *inline* artifact the user
picks which of its enumerated fields are important. Both levels are recorded in
the protocol (the shape tags and the `(important)`/`(shape-only)` field tags) so
the checker can enforce coverage mechanically rather than trusting prose.

## Lineage points at the producing code, not the script

This is the rule most protocols get wrong, and it is the *same* rule for every
kind of artifact: each important field traces to the code that produces **it** —
not the entry script (which only orchestrates), and not the output file (which
only stores the result). What a "field" is depends on the artifact, and so does
its producing code: a field in a summary JSON traces to the function that
computes it; a cell of a derived table to the aggregation that fills it; a bar in
a figure to the line that draws it. Same rule, different leaf. In each case the
field block's `file`+`snippet` name that code.

- `source_field` → where the value is read in the output (`common_completed.speedup`).
- `file` + `snippet` → the real code that produced it, core lines verbatim.

Quoting the output back at itself proves nothing — it restates the number in
question. Pointing at the script shows what was launched, not how the value was
made. Point at the producing code.

The `nature` tag is the integrity signal: `MEASURED` (read from a real
measurement), `DERIVED` (computed — `formula` mandatory), `SYNTHETIC` (a
model/heuristic/assumption), `EXTERNAL` (a third-party source). A `SYNTHETIC`
value dressed as `MEASURED` turns a fabricated chart bar into a "real" one — the
exact thing `pin-codex-audit` looks for.

## Worked example: shape, inline artifact, delegated artifact

The runnable demo (`examples/demo/protocols/demo-latency-protocol.md`) is one
script that produces a summary and a figure. Its body shows all three node
states — `[bears conclusions]` inline, `[bears conclusions, delegated]`, and
`[shape-only]` — and the `### Field:` blocks, whose snippets `protocol_check.py`
locates verbatim:

````markdown
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
- nature: MEASURED
- source_field: summary.yaml -> prefill_ms (averaged from run.yaml -> prefill_ms)
- file: src/runner.py
```python
    start = time.perf_counter()
    _ = sum(i * i for i in range(60_000))
    return (time.perf_counter() - start) * 1000.0
```

### Field: overhead_ms
- nature: DERIVED
- source_field: summary.yaml -> overhead_ms
- file: src/summarize.py
- formula: overhead_ms = total_ms - prefill_ms - decode_ms
```python
    overhead_ms = total_ms - prefill_ms - decode_ms
```

## Artifact: data/latency_breakdown.png
contains: the latency-breakdown figure rendered from summary.yaml
git_tracked: true
lineage_protocol: "demo-latency-figure-protocol.md"
````

`summary.yaml` is inline: it lists every field, marks three important and one
shape-only, and each important field gets a `### Field:` block tracing it to the
infra (`runner.py` measures, `summarize.py` derives — neither is the entry
script). The figure is delegated to `demo-latency-figure-protocol.md`, which is a
normal protocol whose `script` is the *plotting* script and whose `### Field:`
blocks are the figure's coloured segments — one per bar, the snippet being the
draw call.

Contrast with the fat-field version this replaces: describing the whole figure
with one field and one snippet collapses every bar and colour into a single line
of lineage, so most of what the picture asserts stays unverifiable. One field per
conclusion-bearing component — each tracing to the code that produces it — is
what makes the artifact checkable.

## The test before you stop

Could a colleague who was **not** on this run, given only this protocol and the
ones it delegates to:
(a) produce the artifact with `script <args>` on a clean shell, and
(b) trace each important field — a summary field, a table cell, a bar of a
figure — to the code that produced it?
If a conclusion-bearing node has no `## Artifact:` section (or a shape-only node
has one), if an inline artifact has no important field, if a snippet points at
the script or the output instead of the producing code, or if a delegated
reference is dangling or points at a child describing a different file, the
answer is no — fix it before validating.

## Validation

```bash
python3 <PLUGIN_ROOT>/scripts/protocol_check.py \
  .claude-research/protocols/<task-id>-protocol.md
```

Exit `0` means structurally valid, **recursively across the whole delegation
tree**: `task` present; `script` exists and (if a `.py` file) reads nothing from
the environment; `parameters` is a non-empty list with a `name` each; a
`## Run root shape` with at least one conclusion-bearing node; the artifact ↔
shape bijection (every bears-conclusions node has one `## Artifact:` section and
vice versa); delegation markers agree (delegated node ↔ `lineage_protocol`);
every inline artifact has ≥1 important field; the important-field ↔ `### Field:`
bijection (no uncovered field, no orphan block, no duplicate); every `### Field:`
block has a valid `nature`, a `file`, and a verbatim ≤5-line snippet that locates
in that file (with a `formula` for `DERIVED`); a delegated artifact has no
`fields:` and no `### Field:` blocks; and for every delegated artifact, the
referenced child protocol exists, is itself valid, declares the artifact the
parent delegates to it, and the reference graph has no cycle. Pass `--base <dir>`
if code paths resolve against a directory other than the cwd.

What `protocol_check.py` still can't tell — whether `fixed` is complete, whether a
parameter's default is the real one, whether config leaks in through an *imported*
module, whether a `nature` tag is honest, or whether a delegated child truly
explains the *same* bytes the parent emits — is what the human confirmation
(Phase 2b) and the Codex audit (Phase 6) are for.
