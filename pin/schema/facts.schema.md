# Facts schema  (structured markdown)

A fact is a constrained markdown evidence card. Markdown gives the human a
readable record with figures and tables; yaml frontmatter gives tools a stable
machine interface. The body is not free prose.

## Read it like a human reads it

A fact is written for someone who wants two things, in this order: *what did we
conclude?* and *why should I believe it?* The body is therefore ordered for
**progressive disclosure** — three tiers a reader can stop at the moment they
are satisfied:

1. **The conclusion** — `Bottom line`. The plain answer, the exact claim, the
   headline number. The only section a busy reader must read.
2. **The proof and its boundary** — `Key evidence` then `Scope & limits`. The
   two or three numbers that, if true, force the conclusion, shown as a
   comparison you can check at a glance; then, immediately, what this does *not*
   prove. Over-reading scope is the most common fast-reading mistake, so the
   boundary sits right next to the proof.
3. **The audit trail** — `Lineage`, `Reproduction`. Where the numbers came from
   and how to regenerate them. For the skeptic.

The frontmatter is machine plumbing; humans skip it. So the body must never be a
prose re-listing of frontmatter paths. It interprets the evidence ("the run
wrote marker 154843 into KV slot 629, the exact slot the map reserved"), it does
not dump fields.

Two rules carry most of the readability:

- **`claim` is one short observational sentence.** Caveats, scope, and hedges do
  not belong in the claim — they go in `Scope & limits`. A claim that needs the
  word "while" is two facts.
- **`tldr` is the plain answer plus the one caveat that matters**, and it is
  echoed verbatim into `Bottom line` as `- Answer:`. The human takeaway and the
  machine record stay locked together.

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

The `claim` is canonical. It must be observational (no "because", "due to",
"causes", "therefore", "explains") and it must be **one short sentence**. If you
are tempted to add "while", "although", or a trailing qualifier, that qualifier
is scope — put it in `Scope & limits`, not the claim. `tldr` is the plain-English
answer to `question`, plus the single caveat a reader most needs.

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
## Bottom line
## Key evidence
## Scope & limits
## Lineage
## Reproduction
```

- `Bottom line` is bullets. It must open with `- Answer: <tldr>` (echoing the
  frontmatter `tldr` verbatim), then `- Claim: <claim>`, then a `- Metric:`
  bullet. A leading bold verdict such as `**Proven for the checked runs.**` is
  encouraged — it is what lets a reader confirm in one glance.
- `Key evidence` is the decisive proof, ideally a small table that *compares*
  the measured value against the expected one (the reader should be able to see
  the match, not take it on faith). Keep it to the few rows that actually carry
  the claim; the full artifact list already lives in frontmatter `data`.
- `Scope & limits` must contain at least one bullet stating what the fact does
  *not* establish.
- `Lineage` traces protocol element → measured field → data file in prose, so a
  reader can follow how a number became a claim.
- `Reproduction` carries the exact command, commit, hardware, and a short
  "Verified:" note recording the checks that were run.

Every repo-relative path cited in backticks under `Key evidence` or `Lineage`
must exist on disk.

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
## Bottom line
## Source quote
## Scope & limits
```

`Bottom line` follows the same `- Answer:` / `- Claim:` / `- Metric:` shape as
internal facts. `Source quote` is the verbatim text that backs the claim,
attributed to the citation. The claim may only state what the source reports;
`Scope & limits` should note that this fact records the source, it does not
independently verify it.

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
## Bottom line
## Inputs
## Derivation
## Scope & limits
```

`Bottom line` follows the same `- Answer:` / `- Claim:` / `- Metric:` shape.
`Inputs` is a table of the source facts and the fields used. `Derivation` shows
the formula or method. Derived facts must not introduce new measurements; they
use existing fact fields only and must not cite raw data as primary evidence.

## Machine checks

`fact_check.py` enforces:

- files live under the directory matching their type;
- IDs use the correct prefix;
- required frontmatter fields exist;
- body sections exist in the exact required order;
- `Bottom line` echoes `tldr` (`- Answer:`) and `claim` (`- Claim:`) and
  contains a `- Metric:` bullet;
- `Bottom line` and `claim` do not contain obvious causal language;
- `Scope & limits` is non-empty;
- internal data paths and protocol paths exist;
- internal protocol elements exist in the referenced protocol;
- external source fields exist;
- derived input facts exist;
- markdown image paths resolve, and every repo-relative path cited in
  `Key evidence` or `Lineage` exists on disk.
