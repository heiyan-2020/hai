"""Unit tests for pinlib parsing."""
import os

import pytest

import pinlib

HERE = os.path.dirname(__file__)
DEMO = os.path.join(HERE, "..", "examples", "demo")


def test_load_pins_demo():
    pins = pinlib.load_pins(os.path.join(DEMO, "pins.yaml"))
    assert {p.id for p in pins} == {"enforce-tool-call-marker", "decode-time-is-measured"}


def test_demo_pins_are_structurally_valid():
    for p in pinlib.load_pins(os.path.join(DEMO, "pins.yaml")):
        assert p.validate() == []


def test_pin_validate_flags_bad_status():
    p = pinlib.Pin("x", "c", "main", "0", "bogus",
                   {"type": "command", "target": "true"})
    assert any("status" in problem for problem in p.validate())


def test_pin_validate_flags_grep_without_pattern():
    p = pinlib.Pin("x", "c", "main", "0", "active",
                   {"type": "grep"}, code_locations=["a.py"])
    assert any("pattern" in problem for problem in p.validate())


def test_is_enforced_by_status_and_branch():
    base = dict(id="a", claim="c", branch="main", born_at="0",
                assertion={"type": "command", "target": "true"})
    assert pinlib.Pin(status="active", **base).is_enforced("main")
    assert not pinlib.Pin(status="retired", retire_reason="done", **base).is_enforced("main")
    disabled = pinlib.Pin(status="disabled", disabled_on=["exp"], **base)
    assert disabled.is_enforced("main")
    assert not disabled.is_enforced("exp")


def test_load_pins_rejects_duplicate_ids(tmp_path):
    f = tmp_path / "pins.yaml"
    f.write_text(
        "pins:\n"
        "  - {id: x, claim: a, assertion: {type: command, target: 'true'}}\n"
        "  - {id: x, claim: b, assertion: {type: command, target: 'true'}}\n"
    )
    with pytest.raises(pinlib.PinError):
        pinlib.load_pins(str(f))


NEW_PROTO = """---
task: demo-task
script: "src/run.py"
parameters:
  - name: "--gpu"
    purpose: "gpu index"
    required: true
fixed:
  - "kernels fixed in runner.py"
---

# demo-task protocol — one-liner

## Run root shape
```text
<run_root>/
  data/summary.yaml          [bears conclusions]
  data/fig.png               [bears conclusions, delegated]
  data/run.yaml              [shape-only]
```

## Artifact: data/summary.yaml
contains: mean prefill_ms and derived overhead_ms
git_tracked: true
fields:
  - prefill_ms    (important)
  - n_runs        (shape-only)
  - overhead_ms   (important)

### Field: prefill_ms
- nature: MEASURED
- source_field: summary.yaml -> prefill_ms
- file: src/runner.py
```python
    start = time.perf_counter()
```

### Field: overhead_ms
- nature: DERIVED
- source_field: summary.yaml -> overhead_ms
- file: src/summarize.py
- formula: overhead_ms = total_ms - prefill_ms - decode_ms
```python
    overhead_ms = total_ms - prefill_ms - decode_ms
```

## Artifact: data/fig.png
contains: the latency figure
git_tracked: true
lineage_protocol: "fig-protocol.md"
"""


def test_load_protocol_parses_frontmatter(tmp_path):
    p = tmp_path / "x-protocol.md"
    p.write_text(NEW_PROTO)
    proto = pinlib.load_protocol(str(p))
    assert proto.task == "demo-task"
    assert proto.script == "src/run.py"
    assert proto.parameters[0]["name"] == "--gpu"


def test_load_protocol_parses_run_root_shape(tmp_path):
    p = tmp_path / "x-protocol.md"
    p.write_text(NEW_PROTO)
    proto = pinlib.load_protocol(str(p))
    nodes = {n.path: n for n in proto.run_root_shape}
    assert nodes["data/summary.yaml"].bears_conclusions
    assert not nodes["data/summary.yaml"].delegated
    assert nodes["data/fig.png"].bears_conclusions
    assert nodes["data/fig.png"].delegated
    assert not nodes["data/run.yaml"].bears_conclusions


def test_load_protocol_parses_artifacts_and_fields(tmp_path):
    p = tmp_path / "x-protocol.md"
    p.write_text(NEW_PROTO)
    proto = pinlib.load_protocol(str(p))
    arts = {a.path: a for a in proto.artifacts}
    summ = arts["data/summary.yaml"]
    assert summ.contains == "mean prefill_ms and derived overhead_ms"
    assert summ.git_tracked is True
    assert summ.lineage_protocol == ""
    fields = {f["name"]: f["important"] for f in summ.fields}
    assert fields == {"prefill_ms": True, "n_runs": False, "overhead_ms": True}
    blocks = {b.name: b for b in summ.field_blocks}
    assert set(blocks) == {"prefill_ms", "overhead_ms"}
    assert blocks["prefill_ms"].nature == "MEASURED"
    assert blocks["prefill_ms"].file == "src/runner.py"
    assert "perf_counter" in blocks["prefill_ms"].snippet
    assert blocks["overhead_ms"].formula.startswith("overhead_ms =")


def test_load_protocol_parses_delegated_artifact(tmp_path):
    p = tmp_path / "x-protocol.md"
    p.write_text(NEW_PROTO)
    proto = pinlib.load_protocol(str(p))
    fig = next(a for a in proto.artifacts if a.path == "data/fig.png")
    assert fig.lineage_protocol == "fig-protocol.md"
    assert fig.field_blocks == []
    assert fig.fields == []


def test_locate_snippet():
    # a real snippet locates and reports a start line
    ok, _, line = pinlib.locate_snippet(
        "_ = sum(i for i in range(140_000))", "src/runner.py", DEMO)
    assert ok and line

    # indentation differences are ignored
    indented = "        return (time.perf_counter() - start) * 1000.0"
    ok2, _, _ = pinlib.locate_snippet(indented, "src/runner.py", DEMO)
    assert ok2

    # a snippet that is not in the file fails
    missing, _, _ = pinlib.locate_snippet("xyz = 999", "src/runner.py", DEMO)
    assert not missing

    # a missing file fails
    no_file, _, _ = pinlib.locate_snippet("a = 1", "src/nope.py", DEMO)
    assert not no_file

    # an empty snippet fails
    empty, _, _ = pinlib.locate_snippet("   \n  \n", "src/runner.py", DEMO)
    assert not empty
