---
id: if-002
type: internal
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What decode latency does the demo runner report?"
claim: "The demo runner reports 7.2 ms decode latency across 5 samples."
tldr: "Decode latency is 7.2 ms in the demo summary."

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

# if-002 - Decode Latency

## Observation

- Claim: The demo runner reports 7.2 ms decode latency across 5 samples.
- Metric: decode_ms = 7.2 ms.
- Scope: Demo latency summary across 5 samples.

## Evidence

| Artifact | Path | Purpose |
|---|---|---|
| Summary | `data/if-002/summary.yaml` | Source of the decode latency value |
| Run log | `data/if-002/run.log` | Confirms the demo run completed |

## Lineage

- Protocol: `protocols/demo-latency-protocol.md`
- Elements used: `decode_ms`

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

- Related facts: `if-001`
- Gap addressed: none
