---
id: df-001
type: derived
status: active
created_at: "2026-05-22T00:00:00Z"

question: "What is the combined prefill and decode latency in the demo?"
claim: "The demo prefill and decode latencies sum to 10.6 ms."
tldr: "Core latency is 10.6 ms from prefill plus decode."

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

# df-001 - Total Core Latency

## Observation

- Claim: The demo prefill and decode latencies sum to 10.6 ms.
- Metric: core_latency_ms = 10.6 ms.
- Scope: Derived from `if-001` and `if-002`.

## Inputs

| Fact | Used Field | Value | Purpose |
|---|---|---:|---|
| `if-001` | `metric.value` | 3.4 | Prefill latency |
| `if-002` | `metric.value` | 7.2 | Decode latency |

## Derivation

```text
3.4 + 7.2 = 10.6
```

- Method: Add prefill latency and decode latency from the two internal facts.
- No new run was performed for this fact.

## Checks

- Input facts exist.
- Input metrics use compatible units.
- Formula result matches frontmatter metric value.

## Limitations

- This fact only combines the two referenced demo facts.

## Links

- Derived from: `if-001`, `if-002`
- Gap addressed: none
