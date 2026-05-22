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
3. Write frontmatter first. The `claim` must be a pure observation, not a
   causal explanation.
4. Fill the required body sections in the exact order for the type.
5. For internal facts, copy supporting artifacts under
   `.claude-research/data/<fact-id>/` before referencing them.
6. For internal facts, reference a protocol and element names. Do not create a
   citeable internal fact whose data lineage is undeclared.
7. Run `fact_check.py` and fix every structural or reference problem.

## Internal fact body

Use exactly:

```text
# <id> - <short title>
## Observation
## Evidence
## Lineage
## Reproduction
## Checks
## Limitations
## Links
```

`Observation` must be bullets and must repeat frontmatter `claim` as
`- Claim: ...`. `Evidence` must be a table. `Limitations` must have at least
one bullet.

## External fact body

Use exactly:

```text
# <id> - <short title>
## Observation
## Evidence
## Source Quote
## Lineage
## Checks
## Limitations
## Links
```

The claim may only state what the source reports. The direct quote should be
short and should support the claim.

## Derived fact body

Use exactly:

```text
# <id> - <short title>
## Observation
## Inputs
## Derivation
## Checks
## Limitations
## Links
```

Derived facts must name `derived_from` input fact IDs and a `derivation.formula`
or `derivation.method`. They must not introduce new measurements.

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
