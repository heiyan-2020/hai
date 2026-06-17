# Protocol artifact/field model — design

**Date:** 2026-06-17
**Status:** approved (brainstorming), ready for implementation plan

## Problem

A protocol is the contract for one code-produced artifact: it declares the run
contract (one script + parameters + fixed choices) and traces every
conclusion-bearing component to the code that produces it. Today that lineage
layer is a flat list of `## Element:` blocks, and the output shape is a separate
`artifacts:` list in frontmatter. The two lists are never linked, and the
checker only requires "≥1 element OR ≥1 delegated artifact" for the whole
protocol. Consequences:

- **Symptom 1 — uncovered conclusion-bearing artifacts.** A protocol can declare
  many artifacts and write an element for only one of them; the rest carry zero
  lineage and still pass `protocol_check.py`. There is no per-artifact coverage
  rule.
- **Symptom 2 — floating elements.** An element has `source_field` (free text)
  and `file`, but nothing structurally ties it to a declared artifact. The
  checker never verifies `source_field` points at a real artifact, so elements
  drift loose from the shape.

The root cause is that "output shape" and "lineage" are two parallel,
unlinked lists, joined only by a human reading the prose. The delegation
mechanism (`lineage_protocol`) already gives rich artifacts a clean 1:1 binding
to a child protocol; inline lineage has no equivalent binding.

The fix must avoid the opposite failure too: requiring an element for *every*
field of every artifact is too redundant. The granularity must be chosen
deliberately, not forced.

## Decisions (from brainstorming)

1. **Coverage comes from interactive selection, recorded in the protocol.** At
   skill-run time the agent first enumerates the full run-root shape, then the
   user selects which artifacts bear conclusions. The same pattern recurses: for
   each conclusion-bearing inline artifact, the agent lists its fields and the
   user selects which are important. Selection is recorded in the protocol so the
   checker can enforce coverage mechanically.
2. **Artifact becomes a first-class node; lineage nests under it.** Each artifact
   is one of three states: `shape-only` (no lineage), `inline` (lists all its
   fields, important ones carry a `### Field:` block), or `delegated` (carries
   `lineage_protocol`, no inline fields). This is symmetric with delegation: an
   artifact either inlines its fields or delegates.
3. **List all fields of a conclusion-bearing artifact, marking which are
   important.** A `fields:` list under each inline artifact names every field;
   each is tagged `important` (gets a `### Field:` block) or `shape-only`. So
   "deliberately not traced" and "forgotten" are visibly distinct in the file.
4. **Rename `element` → `field`.** The lineage block is `### Field:`. The term
   "important field" generalizes across JSON fields, table columns, and figure
   bars — each a named, conclusion-bearing component of an artifact.
5. **Declare the whole run-root shape first.** A `## Run root shape` section at
   the top of the body lists the entire produced directory tree, marking which
   nodes bear conclusions. Shape-only nodes stop there; conclusion-bearing nodes
   are elaborated below.
6. **Hard cut, one-time migration.** The checker accepts only the new format; all
   existing protocols (and the fact lineage references that cite them) are
   migrated in the same change. No dual-format transition period.

## File format

The run contract stays in frontmatter (`task`, `script`, `parameters`,
`fixed`). The artifact tree moves entirely into the markdown body — `### Field:`
blocks carry fenced code snippets, which do not belong in YAML, and the body is
where nesting reads naturally. `side_effects` is removed; those files become
`shape-only` nodes in the run-root shape.

````markdown
---
task: streaming-pairwise-overall
script: "scripts/streaming_spec/summarize_pairwise_overall.py"
parameters:
  - name: "--run-root"
    purpose: "the run directory to summarize"
    required: true
fixed:
  - "hit-round detection uses first correct inducer request"
---

# streaming-pairwise-overall protocol — one-line description

## Run root shape
```text
<run_root>/
  tables/rounds.csv          [bears conclusions]
  timeline/<case>.png        [bears conclusions, delegated]
  raw_trace.jsonl            [shape-only]
```

## Artifact: tables/rounds.csv
contains: per-round overlap timing
git_tracked: false
fields:
  - round_idx            (shape-only)
  - generator_return_ts  (shape-only)
  - overlap_window_ms    (important)

### Field: overlap_window_ms
- nature: DERIVED
- source_field: `overlap_window_ms`
- file: scripts/streaming_spec/summarize_pairwise_overall.py
- formula: in a hit round, generator return timestamp minus the same round's first correct inducer request return timestamp
```python
overlap = gen.return_ts - ind.return_ts
```

## Artifact: timeline/<case>.png
contains: per-case timeline
lineage_protocol: "agent-timeline-protocol.md"
````

### Structural rules

- Every path marked `[bears conclusions]` in `## Run root shape` has a matching
  `## Artifact:` section (inline or delegated). Shape-only paths have no section.
- An inline `## Artifact:` section has a `fields:` list with ≥1 `important` field.
- Each `important` field has exactly one `### Field:` block; each `### Field:`
  block maps back to an `important` field in its artifact's `fields:` list — no
  orphan field blocks.
- A delegated artifact carries `lineage_protocol` and no `fields:` / `### Field:`.
- A `### Field:` block keeps the old element contract: `nature` (one of MEASURED
  / DERIVED / SYNTHETIC / EXTERNAL), `source_field`, `file`, a fenced snippet
  (≤5 non-blank lines, verbatim, locates in `file`), and `formula` iff
  `nature == DERIVED`. The snippet must point at the producing code, not the
  entry script or the output.

## Authoring workflow (pin-protocol skill)

Protocols are run-agnostic and authored before the run, so the agent infers the
shape and fields from the **producing code** (or an example run if one already
exists). Selection is interactive and recursive:

1. Consolidate to one entry-point script (unchanged).
2. Write the contract frontmatter: `task`, `script`, `parameters`, `fixed`.
3. Enumerate the run-root shape — agent reads the script to determine every path
   it writes, lists them as a tree.
4. User selects which artifacts bear conclusions.
5. For each conclusion-bearing artifact: if rich, delegate to a child protocol
   (recurse the whole workflow on the child); otherwise inline — agent lists the
   artifact's fields, user selects which are important.
6. For each important field, author the `### Field:` block tracing it to the
   producing code.
7. Run `protocol_check.py` and fix every structural problem, recursively.

## Checker changes (protocol_check.py + pinlib.py)

- New parser: `## Run root shape` tree, `## Artifact:` sections, per-artifact
  `contains` / `git_tracked` / `fields:` / `lineage_protocol`, and `### Field:`
  blocks. `pinlib.load_protocol` and its dataclasses change shape; `locate_snippet`
  is reused unchanged.
- Enforce the structural rules above: bears-conclusions coverage, inline artifact
  has ≥1 important field, important-field ↔ `### Field:` bijection (no orphans),
  field-block contract (nature/file/snippet/formula), delegation resolution
  (child exists, valid, declares the delegated path, no cycle).
- Artifact accounting (pin-aware-agent Phase 5) reconciles produced files against
  the `## Run root shape` tree across the whole delegation tree; shape-only nodes
  count (replacing the old `artifacts ∪ side_effects` union).
- The script env-scan check (`.py` entry reads nothing from the environment) is
  unchanged.

## Fact lineage citation change (breaking)

Facts cite protocol lineage by element name today (`pin-fact` Lineage section:
"protocol element → measured field → data file"). With nesting, a fact cites an
**artifact + important field** instead of a bare element name — e.g. the
`overlap_window_ms` important field of `tables/rounds.csv`. This is a breaking
change to the citation format; `pin-fact`, `facts.schema.md`, the demo facts,
and any fact-side validation in `factlib.py` are updated accordingly.

## Change surface (one-time migration)

**Core (structure + validation)**
- `pin/schema/protocol.schema.md` — rewrite structure
- `pin/scripts/protocol_check.py` — new parsing + new enforcement
- `pin/scripts/pinlib.py` — `load_protocol`, the Element/Protocol dataclasses
- `pin/skills/pin-protocol/SKILL.md` — rewrite workflow + format

**Rename element→field, update citation form**
- `pin/skills/pin-fact/SKILL.md`, `pin/schema/facts.schema.md`
- `pin/scripts/factlib.py` (if it parses element references)
- `pin/skills/pin-codex-audit/SKILL.md` + `references/codex-briefing.md`
- `pin/skills/pin-grounding/SKILL.md`, `pin/skills/pin-aware-agent/SKILL.md`,
  `pin/README.md`

**Examples + tests**
- `pin/examples/demo/protocols/demo-latency-protocol.md`,
  `demo-latency-figure-protocol.md`
- demo facts citing elements: `if-001-prefill-latency.md`,
  `if-002-decode-latency.md`
- `pin/tests/test_protocol_check.py`, `test_pinlib.py`, `test_fact_check.py`

## Out of scope

- Any *semantic* check that a snippet truly computes the value (still the job of
  human confirmation Phase 2b and the Codex audit Phase 6). The original
  motivating gap — a snippet pointing at lookups instead of the real
  subtraction — remains a judgment call; this design only makes coverage and the
  field↔artifact binding mechanical, plus a possible weak heuristic warning is
  noted but not required.
- Dual-format support / backward compatibility.
