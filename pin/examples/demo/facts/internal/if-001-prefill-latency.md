---
id: if-001
type: internal
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What prefill latency does the demo runner report?"
tldr: "Prefill latency is 3.4 ms, the mean of 5 demo samples."
claim: "The demo runner reports 3.4 ms prefill latency across 5 samples."

metric:
  name: prefill_ms
  value: 3.4
  unit: "ms"
  direction: lower_is_better

data:
  primary_path: data/if-001/summary.yaml
  supporting_paths:
    - data/if-001/run.log

protocol:
  path: protocols/demo-latency-protocol.md
  elements:
    - prefill_ms

repro:
  command: "python src/summarize.py data/run.yaml data/summary.yaml"
  commit: "0000000"
  hardware: "local CPU"
  software:
    python: "3.x"

tags: [demo, latency]
---

# if-001 — Prefill latency

## Bottom line

- **Measured on the demo runner.**
- Answer: Prefill latency is 3.4 ms, the mean of 5 demo samples.
- Claim: The demo runner reports 3.4 ms prefill latency across 5 samples.
- Metric: prefill_ms = 3.4 ms (lower is better).

## Key evidence

| What it shows           | Value  | Source                        |
|-------------------------|--------|-------------------------------|
| Reported prefill mean   | 3.4 ms | `data/if-001/summary.yaml`    |
| Samples behind the mean | 5      | `data/if-001/run.log`         |

## Scope & limits

- Covers the demo runner and its bundled sample data only.
- A single run — no variance or confidence interval is reported.

## Lineage

- Protocol `protocols/demo-latency-protocol.md`, element `prefill_ms` (MEASURED).
- `summary.yaml -> prefill_ms` is the per-run `prefill_ms` averaged over the 5 samples in `run.yaml`.

## Reproduction

```bash
python src/summarize.py data/run.yaml data/summary.yaml
```

- Commit `0000000` · local CPU · Python 3.x.
- Verified: sample count = 5; summary and run log present.
