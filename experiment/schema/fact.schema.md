# Internal Fact schema

An internal Fact materializes one concrete Protocol run as structured evidence. Store Facts under `.claude-research/facts/internal/` and evidence under `.claude-research/data/<fact-id>/`.

## Template

````markdown
---
id: if-001
type: internal
status: active
created_at: "2026-08-12T00:00:00Z"
question: "Did the new method reduce mean latency?"
claim: "The new method reduced mean latency by 12.4% on the checked cases."
tldr: "Mean latency fell by 12.4% on the checked cases; other workloads were not tested."

metric:
  name: mean_latency_reduction
  value: 12.4
  unit: "%"

data:
  primary_path: data/if-001/summary.json
  supporting_paths:
    - data/if-001/raw.jsonl

protocol:
  path: protocols/latency-eval-protocol.md
  fields:
    - artifact: summary.json
      field: mean_ms

repro:
  command: "python3 experiments/run_latency.py --out-dir .claude-research/data/if-001"
  commit: "0123456789abcdef"
  branch: "main"
  environment: "Python 3.12, package lock at the recorded commit"
  hardware: "NVIDIA H20 GPU 0"
---

# if-001 - Mean latency reduction

## Bottom line

- Answer: Mean latency fell by 12.4% on the checked cases; other workloads were not tested.
- Claim: The new method reduced mean latency by 12.4% on the checked cases.
- Metric: mean_latency_reduction = 12.4%

## Key evidence

Show the smallest comparison that proves the claim and link concrete files such as `data/if-001/summary.json`.

## Scope & limits

- State at least one thing this Fact does not establish.

## Lineage

Map each cited Protocol field to its concrete file, for example `data/if-001/summary.json`.

## Reproduction

Give a cheap command that recomputes the metric from raw evidence:

```bash
python3 scripts/recompute_latency.py .claude-research/data/if-001/raw.jsonl
```

Verified: the recomputation returned 12.4%. Then give the exact `repro.command` that regenerates the run and state the revision, environment, hardware, and checks performed.
````

## Rules

- `id` matches `if-NNN`; the filename starts with the ID and lives under `facts/internal/`.
- `type` is `internal`.
- `claim` is one observational sentence. Do not use causal language such as “because”, “caused by”, or “therefore”.
- `metric` contains `name`, `value`, and `unit`.
- All data paths are relative, resolve without symlink escape, and stay under `.claude-research/data/<fact-id>/`.
- `protocol.path` exists and every `(artifact, field)` exists in that Protocol.
- `repro.command` invokes the Protocol's entry script and records commit, branch, environment, and hardware.
- Body sections appear exactly in the template order.
- `Bottom line` repeats `tldr`, `claim`, and the metric name.
- `Scope & limits` contains at least one bullet.
- Concrete paths cited in `Key evidence` and `Lineage` exist.
- `Reproduction` contains a fenced raw-evidence recomputation command and a `Verified:` result that the author actually checked against `metric.value`.
