---
id: ef-001
type: external
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What target latency does the demo reference use?"
tldr: "The external demo reference sets a 12 ms target latency budget."
claim: "The demo reference reports a 12 ms target latency budget."

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

# ef-001 — Reported target latency

## Bottom line

- **Reported by an external source (not independently verified).**
- Answer: The external demo reference sets a 12 ms target latency budget.
- Claim: The demo reference reports a 12 ms target latency budget.
- Metric: target_latency_ms = 12 ms (lower is better).

## Source quote

> The target latency budget is 12 ms.

— Demo Reference, 2026 · https://example.com/demo-latency · accessed 2026-05-22.

## Scope & limits

- Records what the external reference reports; this fact does not independently verify the budget.
- Applies to the demo reference's setup, which may differ from ours.
