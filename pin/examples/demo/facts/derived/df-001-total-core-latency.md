---
id: df-001
type: derived
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What is the combined prefill and decode latency in the demo?"
tldr: "Prefill and decode latency sum to 10.6 ms in the demo."
claim: "The demo prefill and decode latencies sum to 10.6 ms."

metric:
  name: core_latency_ms
  value: 10.6
  unit: "ms"
  direction: lower_is_better

derived_from:
  - if-001
  - if-002

derivation:
  formula: "3.4 + 7.2"
  method: "Add prefill latency and decode latency from the two internal facts."

tags: [demo, latency, derived]
---

# df-001 — Total core latency

## Bottom line

- **Derived from `if-001` and `if-002` — no new measurement.**
- Answer: Prefill and decode latency sum to 10.6 ms in the demo.
- Claim: The demo prefill and decode latencies sum to 10.6 ms.
- Metric: core_latency_ms = 10.6 ms (lower is better).

## Inputs

| Fact     | Field used     | Value           |
|----------|----------------|-----------------|
| `if-001` | `metric.value` | 3.4 ms (prefill)|
| `if-002` | `metric.value` | 7.2 ms (decode) |

## Derivation

```text
3.4 + 7.2 = 10.6
```

- Method: add prefill and decode latency from the two internal facts. No new run was performed.

## Scope & limits

- Combines only the two referenced demo facts and inherits their limitations.
- Ignores any latency outside prefill and decode (e.g. overhead).
