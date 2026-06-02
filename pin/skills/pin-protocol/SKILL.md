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
before creating or modifying a protocol — it defines the exact fields and what
`protocol_check.py` enforces. This skill is the *workflow and the judgment*: how
to make the one script honest, how to trace each component to infra, and when to
delegate an artifact to a child protocol instead of cramming it into one element.

## Required layout

One file per artifact-producer, named `{task-id}-protocol.md`. A per-task
protocol lives under `.claude-research/channels/{channel}/`. A *reusable*
artifact protocol that several experiments share — a figure kind, a standard
table — lives under `.claude-research/general_protocols/` and is referenced by
path from each experiment that produces it.

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

## A run produces a tree of artifacts — let the lineage recurse

An experiment rarely produces a single number. It produces a **directory** — a
run root — and that directory is a tree of artifacts, each carrying its own
conclusions. A typical e2e run root:

```text
<run_root>/
  summary.json              # the headline comparison numbers
  baseline/  spec/          # per-case trace JSON, one tree per mode
  agent_timeline_checked/   # profile-clock timeline figures
  kernel/                   # joined kernel-profile outputs
```

The protocol describes `summary.json`'s numbers inline, with elements. But the
other nodes are not numbers — they are *sub-artifacts that are themselves
produced and themselves cited*: a timeline figure shows a conclusion, a joined
kernel profile is its own derived dataset. Collapsing such a node into one
element of the parent is the mistake most protocols made — it leaves the node's
internals invisible and unverifiable.

So when a node has its own internal structure, **don't inline it; delegate it.**
The artifact entry names a `lineage_protocol` — a child protocol that explains
that node as its own first-class artifact, with its own one script (the thing
that produces *it* — the plotting script, the kernel-join script) and its own
elements:

```yaml
artifacts:
  - path: "<run_root>/summary.json"
    contains: "the headline comparison numbers"          # described inline, below
  - path: "<run_root>/agent_timeline_checked/<case>.png"
    contains: "per-case profile-clock timeline"
    lineage_protocol: "agent-timeline-protocol.md"        # ← delegated to its own protocol
```

Recursion mirrors the tree: verifiability reaches every node, not just the root
summary. When you delegate a node, **delete any inline element for it** — the
child is now the single source of truth, and two descriptions of one thing drift
apart. A reusable node (the same timeline figure rendered by many experiments)
becomes one child protocol that every parent references, instead of being
re-explained each time.

Delegation nests to any depth and bottoms out at leaves whose elements point at
infra. A `lineage_protocol` path resolves **relative to the referencing
protocol's own directory** (absolute paths work too), so the protocol graph stays
self-contained. `protocol_check.py` follows every reference: the child must exist,
be itself valid, declare the artifact the parent delegates to it, and the graph
must have no cycle.

## Authoring workflow

1. **Consolidate to one script.** Identify or create the single entry-point
   script that produces this artifact end to end. Drive every configurable choice
   from its arguments; hard-code the rest.
2. **Write the contract frontmatter.** `task`; the `script` path; `parameters`
   (name, purpose, required/default/choices); `fixed` (the hard-coded choices
   that define the artifact); `artifacts` (the output shape — each file a run
   writes, what it contains, `git_tracked`); `side_effects` for the rest.
3. **For each artifact, decide leaf or delegate.** A simple value goes inline as
   an element. A rich artifact (a figure, a nested pipeline output) gets a
   `lineage_protocol` pointing at a child protocol you author the same way — and
   no inline element.
4. **Trace each conclusion-bearing component to its producing code.** One
   `## Element:` block per component — a summary field, a table cell, a bar of a
   figure — with a `nature` tag, the `source_field` where it is read, the `file`
   that produces it, a `formula` if `DERIVED`, and a fenced **snippet** of the
   core producing lines (≤5, verbatim).
5. **Run `protocol_check.py`** and fix every structural problem, in the parent
   and every child.

## Lineage points at the producing code, not the script

This is the rule most protocols get wrong, and it is the *same* rule for every
kind of artifact: each conclusion-bearing component traces to the code that
produces **it** — not the entry script (which only orchestrates), and not the
output file (which only stores the result). What a "component" is depends on the
artifact, and so does its producing code: a field in a summary JSON traces to the
function that computes it; a cell of a derived table to the aggregation that
fills it; a bar in a figure to the line that draws it. Same rule, different leaf.
In each case the element's `file`+`snippet` name that code.

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

## Worked example: delegating a node of the tree

Take the `agent_timeline_checked/` node from the run-root tree above. The parent
experiment protocol stops trying to explain it and delegates:

```yaml
# in the experiment protocol's `artifacts:`
- path: "<run_root>/agent_timeline_checked/<case>_profile_clock_compare.png"
  contains: "per-case baseline-vs-spec profile-clock timeline"
  git_tracked: false
  lineage_protocol: "agent-timeline-protocol.md"
```

The child protocol explains that node as its own artifact, one element per
component — here each component happens to be a bar, so the snippet is the line
that draws it. The shape to imitate, from the runnable demo
(`examples/demo/protocols/demo-latency-figure-protocol.md`), whose snippets
`protocol_check.py` locates verbatim:

````markdown
---
task: demo-latency-figure
script: "src/plot.py"
parameters:
  - name: "--summary"
    purpose: "the summary.yaml whose fields this figure draws"
    required: false
    default: "data/summary.yaml"
  - name: "--out"
    purpose: "output PNG path"
    required: false
artifacts:
  - path: "data/latency_breakdown.png"
    contains: "one coloured segment per latency phase"
    git_tracked: true
---

# data/latency_breakdown.png — latency-breakdown figure

## Element: prefill_segment
- nature: MEASURED
- source_field: `prefill_ms` in summary.yaml
- file: src/plot.py
```python
    ax.barh(0, s["prefill_ms"], left=0.0, color=PREFILL, label="prefill")
```

## Element: overhead_segment
- nature: DERIVED
- source_field: `overhead_ms` in summary.yaml; drawn after prefill+decode
- formula: overhead_ms = total_ms - prefill_ms - decode_ms (computed in summarize.py; this segment only draws it)
- file: src/plot.py
```python
    ax.barh(0, s["overhead_ms"], left=s["prefill_ms"] + s["decode_ms"],
            color=OVERHEAD, label="overhead")
```
````

Contrast with the fat-element version this replaces: describing the whole figure
with one element and one snippet collapses every bar and colour into a single line
of lineage, so most of what the picture asserts stays unverifiable. One element
per component — each tracing to the code that produces it — is what makes the
artifact checkable.

## The test before you stop

Could a colleague who was **not** on this run, given only this protocol and the
ones it delegates to:
(a) produce the artifact with `script <args>` on a clean shell, and
(b) trace each conclusion-bearing component — a summary field, a table cell, a
bar of a figure — to the code that produced it?
If a rich artifact is still one fat element, if a snippet points at the script or
the output instead of the producing code, or if a delegated reference is dangling
or points at a child describing a different file, the answer is no — fix it before
validating.

## Validation

```bash
python3 <PLUGIN_ROOT>/scripts/protocol_check.py \
  .claude-research/channels/<channel>/<task-id>-protocol.md
```

Exit `0` means structurally valid, **recursively across the whole delegation
tree**: `task` present; `script` exists and (if a `.py` file) reads nothing from
the environment; `parameters` is a non-empty list with a `name` each; every
`artifacts[]` has a `path`; at least one element *or* one delegated artifact;
every element has a `nature`, a `file`, and a verbatim ≤5-line snippet that
locates in that file (with a `formula` for `DERIVED`); and for every delegated
artifact, the referenced child protocol exists, is itself valid, declares the
artifact the parent delegates to it, and the reference graph has no cycle. Pass
`--base <dir>` if code paths resolve against a directory other than the cwd.

What `protocol_check.py` still can't tell — whether `fixed` is complete, whether a
parameter's default is the real one, whether config leaks in through an *imported*
module, whether a `nature` tag is honest, or whether a delegated child truly
explains the *same* bytes the parent emits — is what the human confirmation
(Phase 2b) and the Codex audit (Phase 6) are for.
