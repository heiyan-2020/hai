---
task: demo-latency-figure
script: "src/plot.py"
parameters:
  - name: "--summary"
    purpose: "the summary.yaml whose fields this figure draws"
    required: false
    default: "data/summary.yaml"
  - name: "--out"
    purpose: "output PNG path"
    required: false
    default: "data/latency_breakdown.png"
fixed:
  - "a single stacked horizontal bar, three segments left-to-right: prefill | decode | overhead"
  - "x-axis is absolute milliseconds from 0"
---

# demo-latency-figure protocol — latency-breakdown figure

This is the protocol for the *figure*. The experiment protocol
(`demo-latency-protocol.md`) names this image as a delegated artifact and points
here. Each important field below is a visual channel — a coloured segment — and
traces to the line that turns a number into geometry.

## Run root shape
```text
<run_root>/
  data/latency_breakdown.png    [bears conclusions]
```

## Artifact: data/latency_breakdown.png
contains: the latency-breakdown bar — one coloured segment per latency phase
git_tracked: true
fields:
  - prefill_segment    (important)
  - decode_segment     (important)
  - overhead_segment   (important)

### Field: prefill_segment
- nature: MEASURED
- source_field: `prefill_ms` in summary.yaml
- file: src/plot.py
```python
    ax.barh(0, s["prefill_ms"], left=0.0, color=PREFILL, label="prefill")
```

### Field: decode_segment
- nature: MEASURED
- source_field: `decode_ms` in summary.yaml; its left edge encodes the prefill end time
- file: src/plot.py
```python
    ax.barh(0, s["decode_ms"], left=s["prefill_ms"], color=DECODE, label="decode")
```

### Field: overhead_segment
- nature: DERIVED
- source_field: `overhead_ms` in summary.yaml; drawn after prefill+decode
- formula: overhead_ms = total_ms - prefill_ms - decode_ms (computed in summarize.py; this segment only draws it)
- file: src/plot.py
```python
    ax.barh(0, s["overhead_ms"], left=s["prefill_ms"] + s["decode_ms"],
            color=OVERHEAD, label="overhead")
```
