# Facts schema  (structured markdown)

A fact is a constrained markdown evidence card. Markdown gives the human a
readable record with figures and tables; yaml frontmatter gives tools a stable
machine interface. The body is not free prose.

Facts live under:

```text
.claude-research/facts/
├── internal/
├── external/
└── derived/
```

## Types

| Type | ID prefix | Meaning |
|---|---|---|
| `internal` | `if-` | An observation from your own run or measurement. |
| `external` | `ef-` | An observation reported by a paper, dataset, blog, or other outside source. |
| `derived` | `df-` | A second-order fact derived only from existing facts. |

Failures and negative results are `internal` facts. They are observations, not
a separate type.

## Shared frontmatter

Every fact has:

```yaml
---
id: if-001
type: internal
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What question does this fact answer?"
claim: "The pure observation this fact records."
tldr: "Short plain-English summary."

metric:
  name: accuracy
  value: 65.3
  unit: "%"
  direction: higher_is_better

tags: [evaluation]
---
```

The `claim` is canonical. It must be observational: no "because", "due to",
"causes", "therefore", "explains", or similar causal language.

## Internal fact

Internal facts must additionally carry local evidence, protocol lineage, and
reproduction fields:

```yaml
data:
  primary_path: data/if-001/results.json
  supporting_paths:
    - data/if-001/run.log
    - data/if-001/config.yaml
    - data/if-001/figure.png

protocol:
  path: channels/main/eval-1-protocol.md
  elements:
    - accuracy
    - sample_count

repro:
  command: "uv run python -m run.eval --config configs/a.yaml"
  commit: "abc1234"
  hardware: "8x H20 96GB"
  software:
    python: "3.12"
```

Required body sections, in this exact order:

```text
# <id> — <short title>
## Observation
## Evidence
## Lineage
## Reproduction
## Checks
## Limitations
## Links
```

`Observation` must be bullets and repeat the frontmatter claim as
`- Claim: ...`. `Evidence` must be a table. `Limitations` must contain at
least one bullet.

## External fact

External facts must carry source metadata:

```yaml
source:
  url: "https://arxiv.org/abs/2302.01318"
  citation: "Leviathan et al., 2023"
  quote: "Short source quote."
  accessed_at: "2026-05-22"
```

Required body sections, in this exact order:

```text
# <id> — <short title>
## Observation
## Evidence
## Source Quote
## Lineage
## Checks
## Limitations
## Links
```

The claim may only state what the source reports. It is not an independent
verification of the source.

## Derived fact

Derived facts must name their inputs and derivation:

```yaml
derived_from:
  - if-001
  - if-002

derivation:
  formula: "65.3 - 52.4"
  method: "Subtract baseline accuracy from Method A accuracy."
```

Required body sections, in this exact order:

```text
# <id> — <short title>
## Observation
## Inputs
## Derivation
## Checks
## Limitations
## Links
```

Derived facts must not introduce new measurements. They can only use existing
fact fields and must not cite raw data as their primary evidence.

## Machine checks

`fact_check.py` enforces:

- files live under the directory matching their type;
- IDs use the correct prefix;
- required frontmatter fields exist;
- body sections exist in the exact required order;
- `Observation` repeats the canonical `claim` and contains a metric bullet;
- `Observation` and `claim` do not contain obvious causal language;
- `Limitations` is non-empty;
- internal data paths and protocol paths exist;
- internal protocol elements exist in the referenced protocol;
- external source fields exist;
- derived input facts exist;
- markdown image paths and Evidence table paths exist.
