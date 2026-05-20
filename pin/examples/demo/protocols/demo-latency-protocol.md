---
task: demo-latency-baseline
artifacts:
  - path: "data/summary.yaml"
    run: "python src/summarize.py data/run.yaml data/summary.yaml"
    source: "src/summarize.py"
    validate:
      - "test -f data/summary.yaml"
    provenance_fields: [produced_by]
    git_tracked: true
side_effects:
  - path: "data/run.yaml"
    git_tracked: true
---

# data/summary.yaml — latency summary

A three-row latency breakdown. Each row is one segment of total latency.
Each element names its `file` and carries the core code that produces it —
the snippet is the anchor, robust to line-number drift.

## Element: prefill_ms
- nature: MEASURED
- source_field: summary.yaml -> prefill_ms (averaged from run.yaml -> prefill_ms)
- file: src/runner.py
```python
    start = time.perf_counter()
    _ = sum(i * i for i in range(60_000))
    return (time.perf_counter() - start) * 1000.0
```

## Element: decode_ms
- nature: MEASURED
- source_field: summary.yaml -> decode_ms (averaged from run.yaml -> decode_ms)
- file: src/runner.py
```python
    start = time.perf_counter()
    _ = sum(i for i in range(140_000))
    return (time.perf_counter() - start) * 1000.0
```

## Element: overhead_ms
- nature: DERIVED
- source_field: summary.yaml -> overhead_ms
- file: src/summarize.py
- formula: overhead_ms = total_ms - prefill_ms - decode_ms
```python
    overhead_ms = total_ms - prefill_ms - decode_ms
```
