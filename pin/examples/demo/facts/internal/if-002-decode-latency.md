---
id: if-002
type: internal
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What decode latency does the demo runner report?"
tldr: "Decode latency is 7.2 ms, the mean of 5 demo samples."
claim: "The demo runner reports 7.2 ms decode latency across 5 samples."

metric:
  name: decode_ms
  value: 7.2
  unit: "ms"
  direction: lower_is_better

data:
  primary_path: data/if-002/summary.yaml
  supporting_paths:
    - data/if-002/run.log

protocol:
  path: protocols/demo-latency-protocol.md
  elements:
    - decode_ms

repro:
  command: "python src/summarize.py data/run.yaml data/summary.yaml"
  commit: "0000000"
  hardware: "local CPU"
  software:
    python: "3.x"

tags: [demo, latency]
---

# if-002 — Decode latency

## Bottom line

- **Measured on the demo runner.**
- Answer: Decode latency is 7.2 ms, the mean of 5 demo samples.
- Claim: The demo runner reports 7.2 ms decode latency across 5 samples.
- Metric: decode_ms = 7.2 ms (lower is better).

## Key evidence

| What it shows           | Value  | Source                        |
|-------------------------|--------|-------------------------------|
| Reported decode mean    | 7.2 ms | `data/if-002/summary.yaml`    |
| Samples behind the mean | 5      | `data/if-002/run.log`         |

## Scope & limits

- Covers the demo runner and its bundled sample data only.
- A single run — no variance or confidence interval is reported.

## Lineage

- Protocol `protocols/demo-latency-protocol.md`, element `decode_ms` (MEASURED).
- `summary.yaml -> decode_ms` is the per-run `decode_ms` averaged over the 5 samples in `run.yaml`.

## Reproduction

```bash
python src/summarize.py data/run.yaml data/summary.yaml
```

- Commit `0000000` · local CPU · Python 3.x.
- Verified: sample count = 5; summary and run log present.
