---
id: ef-001
type: external
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What target latency does the demo reference use?"
claim: "The demo reference reports a 12 ms target latency budget."
tldr: "The external reference budget is 12 ms."

metric:
  name: target_latency_ms
  value: 12
  unit: "ms"
  direction: lower_is_better

source:
  url: "https://example.com/demo-latency"
  citation: "Demo Reference, 2026"
  quote: "The target latency budget is 12 ms."
  accessed_at: "2026-05-22"

tags: [demo, latency, external]
---

# ef-001 - Reported Target Latency

## Observation

- Claim: The demo reference reports a 12 ms target latency budget.
- Metric: target_latency_ms = 12 ms.
- Scope: External demo reference.

## Evidence

| Artifact | Path | Purpose |
|---|---|---|
| Reference | `https://example.com/demo-latency` | Source page |

## Source Quote

> The target latency budget is 12 ms.

## Lineage

- Source type: external reference.
- Citation: Demo Reference, 2026.
- Accessed at: 2026-05-22.

## Checks

- Source URL recorded.
- Citation recorded.
- Direct quote recorded.

## Limitations

- This fact records what the external reference reports.

## Links

- Related facts: none
- Gap addressed: none
