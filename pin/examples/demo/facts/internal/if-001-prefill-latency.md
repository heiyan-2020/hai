---
id: if-001
type: internal
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What prefill latency does the demo runner report?"
claim: "The demo runner reports 3.4 ms prefill latency across 5 samples."
tldr: "Prefill latency is 3.4 ms in the demo summary."

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

# if-001 - Prefill Latency

## Observation

- Claim: The demo runner reports 3.4 ms prefill latency across 5 samples.
- Metric: prefill_ms = 3.4 ms.
- Scope: Demo latency summary across 5 samples.

## Evidence

| Artifact | Path | Purpose |
|---|---|---|
| Summary | `data/if-001/summary.yaml` | Source of the prefill latency value |
| Run log | `data/if-001/run.log` | Confirms the demo run completed |

## Lineage

- Protocol: `protocols/demo-latency-protocol.md`
- Elements used: `prefill_ms`

## Reproduction

```bash
python src/summarize.py data/run.yaml data/summary.yaml
```

- Commit: `0000000`
- Hardware: local CPU
- Software: Python 3.x

## Checks

- Sample count matched expected 5.
- Summary file was recorded.
- Run log was recorded.

## Limitations

- This fact only covers the demo runner and sample data.

## Links

- Related facts: `if-002`
- Gap addressed: none
