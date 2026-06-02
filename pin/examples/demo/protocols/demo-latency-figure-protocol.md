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
artifacts:
  - path: "data/latency_breakdown.png"
    contains: "the latency-breakdown bar: one coloured segment per latency phase"
    git_tracked: true
---

# data/latency_breakdown.png — latency-breakdown figure

This is the protocol for the *figure*, not the experiment. The experiment
protocol (`demo-latency-protocol.md`) names this image as one of its artifacts
and delegates here; this file explains how each thing you can read off the
picture is drawn. The unit of lineage for a figure is a **visual channel** — a
coloured segment, an axis, a series — and each one traces to the line that turns
a number into geometry.

The value each segment *encodes* is computed upstream (in `summarize.py`, traced
by the experiment protocol's number elements). What this protocol pins down is
the part nothing else covers: how that value becomes a bar of a given width at a
given position.

## Element: prefill_segment
- nature: MEASURED
- source_field: `prefill_ms` in summary.yaml
- file: src/plot.py
```python
    ax.barh(0, s["prefill_ms"], left=0.0, color=PREFILL, label="prefill")
```

## Element: decode_segment
- nature: MEASURED
- source_field: `decode_ms` in summary.yaml; its left edge encodes the prefill end time
- file: src/plot.py
```python
    ax.barh(0, s["decode_ms"], left=s["prefill_ms"], color=DECODE, label="decode")
```

## Element: overhead_segment
- nature: DERIVED
- source_field: `overhead_ms` in summary.yaml; drawn after prefill+decode
- formula: overhead_ms = total_ms - prefill_ms - decode_ms (computed in summarize.py; this segment only draws it)
- file: src/plot.py
```python
    ax.barh(0, s["overhead_ms"], left=s["prefill_ms"] + s["decode_ms"],
            color=OVERHEAD, label="overhead")
```
