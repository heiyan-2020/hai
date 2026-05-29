---
name: pin-fact
description: >-
  Create and validate structured markdown research facts. Use whenever a task
  produces or records a citeable observation: internal measurements, external
  reported results, or derived facts computed from existing facts. Facts are
  constrained markdown evidence cards with yaml frontmatter, fixed sections,
  local evidence links, and protocol lineage for internal facts.
type: flow
user-invocable: true
---

# pin-fact

Facts are the human-facing evidence layer of the pin plugin. A fact is not a
lab notebook entry and not a paper paragraph. It is a constrained markdown
record: the frontmatter is the machine-readable source of truth, and the body is
a fixed-shape evidence card that a researcher can inspect quickly.

A reader of a fact wants two things, in order: *what did we conclude?* and *why
should I believe it?* So the body is ordered for progressive disclosure — the
conclusion first, then the proof and its boundary, then the audit trail. Write
it so a busy person can stop after the first section and still be correct, while
a skeptic can keep reading down to the reproduction command. The frontmatter is
plumbing the reader skips; never re-list its paths as body prose — interpret the
evidence instead of dumping fields.

Three fact types exist:

- `internal` — an observation from your own run or measurement.
- `external` — an observation reported by an outside source.
- `derived` — a second-order fact derived only from existing facts.

Negative results are `internal` facts. They are observations.

## Required layout

Facts live under `.claude-research/facts/`:

```text
internal/if-001-short-title.md
external/ef-001-short-title.md
derived/df-001-short-title.md
```

The canonical schema is `<PLUGIN_ROOT>/schema/facts.schema.md`. Read it before
creating or modifying a fact.

## Creation workflow

1. Decide the type:
   - `internal` if the project produced the observation.
   - `external` if a paper, dataset, blog, or other source reported it.
   - `derived` if it is computed only from existing facts.
2. Allocate the next ID for that type by scanning the matching directory.
3. Write frontmatter first. The `claim` must be a pure observation in **one
   short sentence** — no causal language, and no trailing caveats (those are
   scope). Write `tldr` as the plain-English answer plus the one caveat that
   matters; it is echoed verbatim into `Bottom line`.
4. Fill the required body sections in the exact order for the type.
5. For internal facts, copy supporting artifacts under
   `.claude-research/data/<fact-id>/` before referencing them.
6. For internal facts, reference a protocol and element names. Do not create a
   citeable internal fact whose data lineage is undeclared.
7. Run `fact_check.py` and fix every structural or reference problem.

## Internal fact body

Use exactly these sections, in order — conclusion, then proof and its boundary,
then audit trail:

```text
# <id> - <short title>
## Bottom line
## Key evidence
## Scope & limits
## Lineage
## Reproduction
```

- **Bottom line** — bullets only. Open with `- Answer: <tldr>` (verbatim copy of
  frontmatter `tldr`), then `- Claim: <claim>`, then `- Metric: <name> = ...`. A
  leading bold verdict (`**Proven for the checked runs.**`) helps the reader
  confirm at a glance. No paths here.
- **Key evidence** — the proof, as a small table that *compares* the measured
  value to the expected one so the match is visible, not asserted. Show only the
  few rows that carry the claim; the full file list is already in frontmatter
  `data`. Every repo path you cite in backticks must exist.
- **Scope & limits** — at least one bullet naming what this does *not* prove
  (this is where caveats from the claim go).
- **Lineage** — trace protocol element → measured field → data file in prose, so
  a reader sees how a number became a claim.
- **Reproduction** — the exact command in a code block, then commit / hardware /
  a short `Verified:` note of the checks that passed.

### Worked example (the shape to imitate)

```markdown
## Bottom line

- **Proven for the checked runs.**
- Answer: Decode, extend, and mixed marker injection all wrote the markers into exactly the reserved KV slots. This proves laydown + slot mapping, not KV-vector readback.
- Claim: Each of decode, extend, and mixed marker injection wrote its marker tokens into the slots reserved by the req_to_token map.
- Metric: marker_slot_validator_pass_rate = 1.0 (3/3 modes).

## Key evidence

The proof is a slot match — the slot the model wrote into equals the slot the map reserved.

| Mode   | Marker tokens       | Slot written | Slot reserved | Match |
|--------|---------------------|--------------|---------------|:-----:|
| Decode | `[154842, 154843]`  | 629 (last)   | [628, 629]    | ✅    |
| Extend | `[154842, 154843]`  | [628, 629]   | [628, 629]    | ✅    |
| Mixed  | `[154842, 154843]`  | [628, 629]   | [628, 629]    | ✅    |

Record of all three: `data/if-009-glm-fork-marker-slot-lineage/summary.json`.

## Scope & limits

- Covers the sid8 / GPU7 slot-proof runs only.
- Proves token laydown + request→slot mapping; does **not** read back KV vectors from GPU memory.
- All runs used `generator.max_steps=1` — lineage checks, not end-to-end success.
```

Contrast with the old shape, which led with a 60-word run-on `claim`, repeated it
verbatim under `Observation`, then dumped raw fields (`batch_out_cache_loc=629`)
as undifferentiated bullets and re-listed the same paths under Evidence, Lineage,
and Links. The reader could not find the conclusion or the one number that
mattered. The redesign surfaces both immediately.

## External fact body

Use exactly:

```text
# <id> - <short title>
## Bottom line
## Source quote
## Scope & limits
```

`Bottom line` follows the same `- Answer:` / `- Claim:` / `- Metric:` shape.
`Source quote` is the short verbatim text that backs the claim, attributed to
the citation. The claim may only state what the source reports; say so in
`Scope & limits`.

## Derived fact body

Use exactly:

```text
# <id> - <short title>
## Bottom line
## Inputs
## Derivation
## Scope & limits
```

Derived facts must name `derived_from` input fact IDs and a `derivation.formula`
or `derivation.method`. `Inputs` is a table of source facts and the fields used.
They must not introduce new measurements.

## Validation

Run:

```bash
python3 <PLUGIN_ROOT>/scripts/fact_check.py .claude-research/facts \
  --research-root .claude-research
```

Exit code `0` means every structured markdown fact is valid. Nonzero means the
fact layer is not acceptable yet.

`fact_check.py` verifies structure and references. It does not prove a metric
value equals a JSON field; that belongs to the adversarial audit, which reads
the data, protocol, and code together.
