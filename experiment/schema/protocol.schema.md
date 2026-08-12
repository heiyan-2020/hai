# Protocol schema

A Protocol is the run-agnostic contract for one code-produced artifact tree. It fixes the single entry script, its parameter interface, fixed choices, output shape, and the code lineage of every conclusion-bearing field. Concrete arguments and results belong to a Fact.

Store one Protocol per producer at `.claude-research/protocols/<task-id>-protocol.md`.

## Template

````markdown
---
task: latency-eval
script: "experiments/run_latency.py"
parameters:
  - name: "--out-dir"
    purpose: "output directory"
    required: true
fixed:
  - "warmup count is 3"
---

# Latency evaluation Protocol

## Run root shape

```text
<run_root>/
  summary.json          [bears conclusions]
  latency.png           [bears conclusions, delegated]
  raw.jsonl             [shape-only]
```

## Artifact: summary.json
contains: aggregate latency metrics
git_tracked: false
fields:
  - mean_ms (important)
  - sample_count (shape-only)

### Field: mean_ms
- nature: DERIVED
- source_field: summary.json -> mean_ms
- file: experiments/metrics.py
- formula: mean_ms = sum(latencies_ms) / len(latencies_ms)
```python
mean_ms = sum(latencies_ms) / len(latencies_ms)
```

## Artifact: latency.png
contains: latency visualization
git_tracked: false
lineage_protocol: "latency-figure-protocol.md"
````

The delegated file `latency-figure-protocol.md` is a normal child Protocol:

````markdown
---
task: latency-figure
script: "experiments/plot_latency.py"
parameters:
  - name: "--summary"
    purpose: "parent summary.json"
    required: true
  - name: "--out"
    purpose: "output latency.png"
    required: true
fixed:
  - "bar color is teal"
---

# Latency figure Protocol

## Run root shape

```text
latency.png [bears conclusions]
```

## Artifact: latency.png
contains: mean-latency bar
git_tracked: false
fields:
  - mean_bar (important)

### Field: mean_bar
- nature: DERIVED
- source_field: latency.png -> mean bar height
- file: experiments/plot_latency.py
- formula: bar height = summary.json.mean_ms
```python
ax.bar(["mean"], [summary["mean_ms"]])
```
````

## Frontmatter

- `task`: non-empty stable task ID.
- `script`: the only entry point that produces this artifact tree.
- `parameters`: non-empty list; each entry needs `name`. Document purpose, required/default, and choices when applicable.
- `fixed`: list every hard-coded choice that defines the artifact. Use `[]` only when none exist.

The entry script must be determined by its arguments. Python entry scripts may not read `os.getenv` or `os.environ`.

## Run root shape

List every produced path and mark it exactly once:

- `[shape-only]`: produced but not used to support a conclusion.
- `[bears conclusions]`: trusted downstream and described inline.
- `[bears conclusions, delegated]`: rich artifact described by a child Protocol.

Every conclusion-bearing path has exactly one matching `## Artifact:` section. Shape-only paths have none.

## Inline artifacts

List every field as `(important)` or `(shape-only)`. At least one field must be important. Each important field has exactly one `### Field:` block with:

- `nature`: `MEASURED`, `DERIVED`, `SYNTHETIC`, or `EXTERNAL`.
- `source_field`: where the value appears in the output.
- `file`: source file containing the producing code.
- `formula`: required for `DERIVED`.
- fenced snippet: at most five nonblank lines appearing verbatim in `file`.

The snippet points to code that produces the field, not the entry wrapper or stored output.

## Delegated artifacts

A delegated artifact has `lineage_protocol` and no inline `fields` or `### Field:` blocks. The child path is relative to the parent Protocol and must stay inside the top-level Protocol directory. Delegation may recurse but must not cycle, and the child must declare the delegated artifact.
