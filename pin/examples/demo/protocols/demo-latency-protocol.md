---
task: demo-latency-baseline
script: "src/run_demo.py"
parameters:
  - name: "--n-runs"
    purpose: "how many measured runs to average"
    required: false
    default: 5
  - name: "--out-dir"
    purpose: "directory for the per-run and summary yaml files"
    required: false
    default: "data"
  - name: "--figure-out"
    purpose: "if set, also render the latency-breakdown figure to this path"
    required: false
    default: ""
fixed:
  - "the measured kernels (a fixed prefill pass and decode loop in src/runner.py)"
---

# demo-latency-baseline protocol — latency summary + figure

## Run root shape
```text
<run_root>/
  data/summary.yaml             [bears conclusions]
  data/latency_breakdown.png    [bears conclusions, delegated]
  data/run.yaml                 [shape-only]
```

## Artifact: data/summary.yaml
contains: mean prefill_ms, decode_ms, and the derived overhead_ms
git_tracked: true
fields:
  - prefill_ms    (important)
  - decode_ms     (important)
  - overhead_ms   (important)
  - n_runs        (shape-only)

### Field: prefill_ms
- nature: MEASURED
- source_field: summary.yaml -> prefill_ms (averaged from run.yaml -> prefill_ms)
- file: src/runner.py
```python
    start = time.perf_counter()
    _ = sum(i * i for i in range(60_000))
    return (time.perf_counter() - start) * 1000.0
```

### Field: decode_ms
- nature: MEASURED
- source_field: summary.yaml -> decode_ms (averaged from run.yaml -> decode_ms)
- file: src/runner.py
```python
    start = time.perf_counter()
    _ = sum(i for i in range(140_000))
    return (time.perf_counter() - start) * 1000.0
```

### Field: overhead_ms
- nature: DERIVED
- source_field: summary.yaml -> overhead_ms
- file: src/summarize.py
- formula: overhead_ms = total_ms - prefill_ms - decode_ms
```python
    overhead_ms = total_ms - prefill_ms - decode_ms
```

## Artifact: data/latency_breakdown.png
contains: the latency-breakdown figure rendered from summary.yaml
git_tracked: true
lineage_protocol: "demo-latency-figure-protocol.md"
