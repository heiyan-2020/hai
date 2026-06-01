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
  frontmatter `tldr`), then `- Claim: <claim>`, then a `- Metric:` bullet. That
  bullet must carry the machine slug (`- Metric: <metric.name> = ...` — the fact
  check cross-references it), but pair the slug with its plain meaning in the same
  breath: `- Metric: original_spec_gpu1_over_gpu1_synth_mean = 0.9989 (GPU1 kernels
  ÷ a GPU1-only baseline) — no real slowdown`. The slug lives here and nowhere
  else; everywhere else in the body, use the plain words. A leading bold verdict
  (`**Proven for the checked runs.**`) helps the reader confirm at a glance. No
  paths here.
- **Key evidence** — the proof, as a small table that *compares* the measured
  value to the expected one so the match is visible, not asserted. Show only the
  few rows that carry the claim; the full file list is already in frontmatter
  `data`. Every repo path you cite in backticks must exist.
- **Scope & limits** — at least one bullet naming what this does *not* prove
  (this is where caveats from the claim go).
- **Lineage** — trace protocol element → measured field → data file in prose, so
  a reader sees how a number became a claim. This is the static map of where each
  number lives; the runnable version is Reproduction.
- **Reproduction** — two stages, because "reproduce" means two things at two very
  different costs:
  - **Recompute the number — cheap, runs now.** A command that reads the raw files
    under `data/<fact-id>/` and *recomputes* the headline metric from them: reads
    the rows, does the arithmetic, prints the number. It must recompute, not
    reprint — a script that loads `summary.json` and echoes a stored field proves
    nothing, since that field is the very thing in question. Recomputing from the
    inputs is what shows the number is real. This is the `repro.command`.
  - **Regenerate the raw data — expensive, points elsewhere.** One line naming the
    protocol that declares how each raw artifact was produced (`see <protocol-path>,
    artifacts <names>`). The protocol already carries the exact `run` command and
    source file per artifact, so don't copy them here. If the raw data came from a
    long sweep or specific hardware, say so in a few words, so the reader knows the
    recompute is cheap but the regeneration is not.
  - Close with commit / hardware / a short `Verified:` note of the checks that
    passed — and have that note confirm the recompute matched the stored value.

### Write so someone who wasn't there can follow it

The worst readability failure is invisible to the author. A fact is written by the
person who just did the run, in the names that run invented — `synthetic
reference`, `spec run`, `joined decode rows`, a script's variable names. To that
author every term is obvious. To the reader — a teammate who wasn't there, or you
in a month with the context gone — they are opaque, and the fact fails at its one
job: handing the conclusion to someone who lacks your context.

So write for a competent colleague who did **not** do this run and has not read
your code. Two habits carry most of it:

- **Ground every coined term the first time it appears, in one clause.** Not "the
  original GPU1 spec rows are divided by an interpolated GPU1 synthetic reference"
  — but "we divided GPU1's measured kernel times by a *GPU1-only baseline* (the
  same kernels re-run on GPU1 alone)." If a term can't be pinned down in a clause,
  it's too deep for the body — leave it to the protocol or the data files.
- **In prose, say what a number means, not its slug.** A bare `...synth_mean =
  0.9989` makes the reader reverse-engineer the point. The slug belongs only in the
  `- Metric:` bullet, paired with its meaning; in prose, state the point: "0.999× —
  GPU1 is on the money against its own baseline."

The test, before you stop: could a colleague who wasn't on this run read only
**Bottom line** and **Key evidence** and correctly say what you concluded and why?
If a sentence leans on something that lives only in your head or your code,
rewrite it.

### Worked example (the shape to imitate)

The GPU-clock fact, written the right way: every coined term grounded on first use,
the metric in plain words, and Reproduction splitting the cheap recompute from the
expensive regeneration.

````markdown
## Bottom line

- **Proven for the checked runs.**
- Answer: GPU1's kernels only *looked* ~5% slower than GPU4 — GPU1 was clocked lower (1830 vs 1980 MHz). Against a GPU1-only baseline GPU1 is on the money, so there is no real GPU1 regression.
- Claim: In the checked runs GPU1's SM clock held 1830 MHz and GPU4's held 1980 MHz.
- Metric: original_spec_gpu1_over_gpu1_synth_mean = 0.9989 (GPU1's measured kernels ÷ a GPU1-only baseline, mean over 1950 decode rows) — no slowdown once the clock is held fixed.

## Key evidence

The question is whether GPU1 is slow *on its own terms* or only *next to GPU4*. So
we re-ran the same kernels on GPU1 alone and on GPU4 alone — the GPU1-only and
GPU4-only baselines — and divided the original GPU1 measurements by each.

| GPU1 measured ÷    | Asks                   | Rows | Mean ratio  |
|--------------------|------------------------|-----:|------------:|
| GPU1-only baseline | slow on its own terms? | 1950 | 0.999 → no  |
| GPU4-only baseline | slow next to GPU4?     | 1950 | 1.051 → yes |

The clock log explains the gap — GPU1 simply ran slower:

| Run                              | GPU1 clock | GPU4 clock | GPU4/GPU1 speed |
|----------------------------------|-----------:|-----------:|----------------:|
| GLM FlashMLA kernels             |   1830 MHz |   1980 MHz |           1.05× |
| BF16 matmul stress (independent) |   1830 MHz |   1980 MHz |           1.09× |

Full record: `data/if-010-gpu-clock-calibration/summary.json`.

## Scope & limits

- Covers the GPU1/GPU4 GLM FlashMLA cells, the original GPU1 decode rows, and the matmul stress run — nothing older.
- Shows the apparent GPU1 slowdown vanishes against a same-GPU baseline; does **not** establish *why* GPU1 clocked down (`nvidia-smi` showed no power cap or thermal throttle in the checked run).
- Does not retroactively fix every past multi-GPU number — it flags which cross-GPU comparisons need a clock correction.

## Lineage

Protocol `channels/main/gpu-clock-protocol.md`, element `gpu_clock_calibration`. The
headline ratio is each original GPU1 decode row's `kernel_total_ms` divided by the
GPU1-only baseline's `kernel_total_ms` at the same point, averaged over the 1950
rows — stored row-by-row in `data/if-010-gpu-clock-calibration/rootcause_ratios.csv`,
summarized in `data/if-010-gpu-clock-calibration/summary.json`.

## Reproduction

**Recompute the headline ratio from the stored rows** — cheap, runs now:

```bash
.venv-sglang/bin/python - <<'PY'
import csv, statistics
from pathlib import Path
rows = list(csv.DictReader(
    Path(".claude-research/data/if-010-gpu-clock-calibration/rootcause_ratios.csv").open()))
ratios = [float(r["gpu1_measured_ms"]) / float(r["gpu1_baseline_ms"]) for r in rows]
print(f"{len(ratios)} rows, mean = {statistics.fmean(ratios):.4f}")  # -> 1950 rows, mean = 0.9989
PY
```

This reads the per-row times and recomputes the 0.999 mean; it does not read a
stored mean back out.

**Regenerate the raw data** — expensive (six runs on H20 GPUs 1 and 4, ~1 h): see
`channels/main/gpu-clock-protocol.md`, artifacts `spec_e2e`, `gpu1_synth`,
`gpu4_synth`, `matmul_stress` — each carries its exact `run` command and source.

- Commit `96bfedb` · NVIDIA H20 GPUs 1 and 4 · `.venv-sglang` Python.
- Verified: `rootcause_ratios.csv` and `summary.json` present; the recomputed mean (0.9989) matches the stored `summary.json` field; `gpu_clock_calibration` declared in the protocol.
````

Contrast with the version this replaces, whose Lineage read "the original GPU1 spec
joined decode rows are divided by an interpolated GPU1 synthetic reference and by an
interpolated GPU4 synthetic reference," quoted the metric as the bare slug
`original_spec_gpu1_over_gpu1_synth_mean = 0.9989`, and whose Reproduction merely
`print`ed fields back out of `summary.json`. Every noun assumed you had done the
run, the number was never put in plain words, and nothing was actually recomputed —
the three failures this shape fixes.

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
