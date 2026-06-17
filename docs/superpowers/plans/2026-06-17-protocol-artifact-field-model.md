# Protocol artifact/field model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure protocols so each produced artifact is a first-class body node with its lineage (`### Field:` blocks) nested under it, replacing the flat `## Element:` list, and make per-artifact / per-field coverage mechanically checkable.

**Architecture:** The run contract (`task`, `script`, `parameters`, `fixed`) stays in YAML frontmatter. The artifact tree moves into the markdown body: a `## Run root shape` fenced tree lists every produced path and marks which bear conclusions; each conclusion-bearing path gets a `## Artifact:` section that either lists its `fields:` (important ones carrying `### Field:` blocks) or delegates via `lineage_protocol:`. `pinlib` parses this; `protocol_check.py` enforces coverage and the field↔artifact bijection. Facts cite an `(artifact, field)` pair instead of a bare element name. Hard cut — no dual-format support.

**Tech Stack:** Python 3 stdlib + PyYAML, pytest. Files under `pin/scripts/`, `pin/schema/`, `pin/skills/`, `pin/examples/demo/`, `pin/tests/`.

**Working dir:** `/mnt/nvme2/zyx/projects/hai`. Run tests from `pin/`: `cd pin && python3 -m pytest tests/ -q` (tests `sys.path`-insert `scripts/`; confirm with `cat pin/tests/conftest.py` if present, else they import `protocol_check`/`pinlib` directly because pytest adds the test dir's parent — run from `pin/tests` or with `PYTHONPATH=scripts`). Verify the exact invocation in Task 0.

---

## File structure

- `pin/scripts/pinlib.py` — parsing. Replace `LineageElement`/`Protocol` with `LineageField`, `Artifact`, `ShapeNode`, new `Protocol`; rewrite `load_protocol` + body parser. `locate_snippet` unchanged.
- `pin/scripts/protocol_check.py` — validation. Rewrite the artifact/element block into shape+artifact+field enforcement. Keep delegation recursion, cycle detection, `_paths_agree`, env-scan.
- `pin/scripts/factlib.py` — `_check_internal` block: `protocol.elements` → `protocol.fields` of `(artifact, field)`.
- `pin/schema/protocol.schema.md` — rewrite to new structure.
- `pin/schema/facts.schema.md` — `protocol.elements` → `protocol.fields`.
- `pin/skills/pin-protocol/SKILL.md` — rewrite workflow + format.
- `pin/skills/pin-fact/SKILL.md`, `pin/skills/pin-codex-audit/SKILL.md`, `pin/skills/pin-codex-audit/references/codex-briefing.md`, `pin/skills/pin-grounding/SKILL.md`, `pin/skills/pin-aware-agent/SKILL.md`, `pin/README.md` — rename element→field, update citation wording.
- `pin/examples/demo/protocols/demo-latency-protocol.md`, `demo-latency-figure-protocol.md` — migrate to new format.
- `pin/examples/demo/facts/internal/if-001-prefill-latency.md`, `if-002-decode-latency.md` — migrate `protocol.elements` → `protocol.fields`.
- `pin/tests/test_pinlib.py`, `test_protocol_check.py`, `test_fact_check.py` — rewrite for new model.

---

## Task 0: Confirm test harness

**Files:** none (investigation)

- [ ] **Step 1: Find how tests import modules**

Run: `cd /mnt/nvme2/zyx/projects/hai/pin && ls tests/conftest.py 2>/dev/null; head -10 tests/test_pinlib.py`
Then run the baseline suite to see the current green state:
Run: `cd /mnt/nvme2/zyx/projects/hai/pin && PYTHONPATH=scripts python3 -m pytest tests/ -q`
Expected: all tests pass. Record the exact working command — use it verbatim in every later "run tests" step. If `PYTHONPATH=scripts` is needed, prefix it everywhere below.

---

## Task 1: pinlib — new data model + body parser

**Files:**
- Modify: `pin/scripts/pinlib.py:115-206` (dataclasses + `load_protocol` + `_parse_elements`)
- Test: `pin/tests/test_pinlib.py`

- [ ] **Step 1: Write failing tests for the new parser**

Replace the protocol section of `pin/tests/test_pinlib.py` (the `test_load_protocol_demo` test and add new ones). Add at top if missing: `import os`, `import pinlib`, and `DEMO = os.path.join(os.path.dirname(__file__), "..", "examples", "demo")`.

```python
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
```

Delete the old `test_load_protocol_demo` (it asserts `proto.elements`, which no longer exists; the migrated-demo assertion is re-added in Task 3). Keep `test_locate_snippet` and any pin tests untouched.

- [ ] **Step 2: Run the new tests, verify they fail**

Run: `cd pin && PYTHONPATH=scripts python3 -m pytest tests/test_pinlib.py -q`
Expected: FAIL — `Protocol` has no `run_root_shape`/`artifacts[].fields`, `AttributeError` or parse errors.

- [ ] **Step 3: Rewrite the dataclasses and parser**

In `pin/scripts/pinlib.py`, replace the block from `@dataclass class LineageElement` through the end of `_parse_elements` (lines ~115-206) with:

```python
@dataclass
class LineageField:
    name: str
    nature: str = ""
    source_field: str = ""
    file: str = ""
    snippet: str = ""
    formula: str = ""


@dataclass
class Artifact:
    path: str
    contains: str = ""
    git_tracked: bool | None = None
    lineage_protocol: str = ""
    fields: list[dict[str, Any]] = field(default_factory=list)   # {name, important}
    field_blocks: list[LineageField] = field(default_factory=list)


@dataclass
class ShapeNode:
    path: str
    bears_conclusions: bool = False
    delegated: bool = False


@dataclass
class Protocol:
    task: str
    script: str = ""
    parameters: list[dict[str, Any]] = field(default_factory=list)
    run_root_shape: list[ShapeNode] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    path: str = ""


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_FIELD_HEADER_RE = re.compile(r"^###\s+Field:\s*(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^-\s*([A-Za-z_]+)\s*:\s*(.*)$")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)
_SHAPE_MARKER_RE = re.compile(r"\[([^\]]*)\]")
_FIELD_LIST_RE = re.compile(r"^-\s*(\S+)\s*\((important|shape-only)\)\s*$")


def load_protocol(path: str) -> Protocol:
    """Parse a *-protocol.md file: yaml frontmatter + a body of a `## Run root
    shape` section and one `## Artifact:` section per produced artifact, each
    with nested `### Field:` lineage blocks."""
    if not os.path.isfile(path):
        raise PinError(f"protocol file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    fm_match = _FRONTMATTER_RE.match(text)
    if not fm_match:
        raise PinError(f"{path}: missing yaml frontmatter (--- ... ---)")
    try:
        fm = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise PinError(f"{path}: frontmatter is not valid yaml: {exc}") from exc
    if not isinstance(fm, dict):
        raise PinError(f"{path}: frontmatter must be a mapping")

    body = text[fm_match.end():]
    run_root_shape, artifacts = _parse_body(body)

    return Protocol(
        task=fm.get("task", ""),
        script=str(fm.get("script", "") or ""),
        parameters=list(fm.get("parameters", []) or []),
        run_root_shape=run_root_shape,
        artifacts=artifacts,
        path=path,
    )


def _parse_body(body: str) -> tuple[list[ShapeNode], list[Artifact]]:
    """Split the body on top-level `## ` headers into the run-root-shape section
    and the per-artifact sections."""
    headers = list(_SECTION_RE.finditer(body))
    shape: list[ShapeNode] = []
    artifacts: list[Artifact] = []
    for idx, hdr in enumerate(headers):
        title = hdr.group(1).strip()
        start = hdr.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(body)
        block = body[start:end]
        if title.lower().startswith("run root shape"):
            shape = _parse_shape(block)
        elif title.lower().startswith("artifact:"):
            path = title.split(":", 1)[1].strip()
            artifacts.append(_parse_artifact(path, block))
    return shape, artifacts


def _parse_shape(block: str) -> list[ShapeNode]:
    """Read the fenced tree; a line bearing a `[...]` marker is one node."""
    fence = _FENCE_RE.search(block)
    region = fence.group(1) if fence else block
    nodes: list[ShapeNode] = []
    for line in region.splitlines():
        m = _SHAPE_MARKER_RE.search(line)
        if not m:
            continue
        path = line[:m.start()].strip()
        if not path:
            continue
        markers = [x.strip().lower() for x in m.group(1).split(",")]
        nodes.append(ShapeNode(
            path=path,
            bears_conclusions="bears conclusions" in markers,
            delegated="delegated" in markers,
        ))
    return nodes


def _parse_artifact(path: str, block: str) -> Artifact:
    """Parse one `## Artifact:` section: its `contains`/`git_tracked`/
    `lineage_protocol`/`fields:` preamble plus nested `### Field:` blocks."""
    art = Artifact(path=path)
    field_headers = list(_FIELD_HEADER_RE.finditer(block))
    preamble_end = field_headers[0].start() if field_headers else len(block)
    preamble = block[:preamble_end]

    in_fields = False
    for raw in preamble.splitlines():
        line = raw.strip()
        if line.startswith("contains:"):
            art.contains = line[len("contains:"):].strip()
            in_fields = False
        elif line.startswith("git_tracked:"):
            art.git_tracked = line[len("git_tracked:"):].strip().lower() == "true"
            in_fields = False
        elif line.startswith("lineage_protocol:"):
            art.lineage_protocol = line[len("lineage_protocol:"):].strip().strip('"\'')
            in_fields = False
        elif line.startswith("fields:"):
            in_fields = True
        elif in_fields:
            fm = _FIELD_LIST_RE.match(line)
            if fm:
                art.fields.append({"name": fm.group(1), "important": fm.group(2) == "important"})

    for i, fh in enumerate(field_headers):
        name = fh.group(1).strip()
        fstart = fh.end()
        fend = field_headers[i + 1].start() if i + 1 < len(field_headers) else len(block)
        art.field_blocks.append(_parse_field_block(name, block[fstart:fend]))
    return art


def _parse_field_block(name: str, block: str) -> LineageField:
    """The `- key: value` bullets before the fence, plus the first fenced
    block captured verbatim as the snippet."""
    lf = LineageField(name=name)
    fence = _FENCE_RE.search(block)
    if fence:
        lf.snippet = fence.group(1)
        bullet_region = block[:fence.start()]
    else:
        bullet_region = block
    for line in bullet_region.splitlines():
        m = _BULLET_RE.match(line.strip())
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2).strip()
        if key in {"nature", "source_field", "file", "formula"}:
            setattr(lf, key, val)
    return lf
```

Note: the `fields:` list lines use the indented form `  - name   (important)`; `line.strip()` removes the indent so `_FIELD_LIST_RE` matches `- name (important)`. The `### Field:` markdown headers do not match `_FIELD_LIST_RE`, and `_SECTION_RE` matches only `## ` (two hashes, with the trailing space) so `### Field:` is not mistaken for a section.

- [ ] **Step 4: Run the new tests, verify they pass**

Run: `cd pin && PYTHONPATH=scripts python3 -m pytest tests/test_pinlib.py -q`
Expected: PASS (the migrated-demo assertion comes in Task 3; `test_load_protocol_demo` was deleted).

- [ ] **Step 5: Commit**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add pin/scripts/pinlib.py pin/tests/test_pinlib.py
git commit -m "pinlib: parse artifact/field protocol model"
```

---

## Task 2: protocol_check — shape/artifact/field enforcement

**Files:**
- Modify: `pin/scripts/protocol_check.py:33` (import), `:144-202` (artifact+element block), `:253-306` (report + print)
- Test: `pin/tests/test_protocol_check.py`

- [ ] **Step 1: Write failing tests for the new enforcement**

Rewrite `pin/tests/test_protocol_check.py`. Replace the frontmatter/element helpers and per-element tests with helpers that build the new format, keeping the delegation tests (which only need the helper updated). Use this top section:

```python
"""Unit tests for protocol_check (artifact/field lineage model)."""
import os

import protocol_check

HERE = os.path.dirname(__file__)
DEMO = os.path.join(HERE, "..", "examples", "demo")

_FM = (
    "---\n"
    "task: t\n"
    "script: 'run.py'\n"
    "parameters:\n"
    "  - {name: '--gpu', purpose: 'gpu index', required: true}\n"
    "---\n\n# t protocol\n\n"
)


def _shape(*lines: str) -> str:
    body = "## Run root shape\n```text\n<run_root>/\n"
    body += "".join(f"  {ln}\n" for ln in lines)
    body += "```\n\n"
    return body


def _artifact(path, fields_block, field_blocks):
    return f"## Artifact: {path}\ncontains: c\n{fields_block}\n{field_blocks}\n"


_INLINE_OK = (
    _FM
    + _shape("x.yaml   [bears conclusions]")
    + "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n  - bar (shape-only)\n\n"
    + "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n"
)


def _scaffold(tmp_path):
    (tmp_path / "code.py").write_text("y = 1\n")
    (tmp_path / "run.py").write_text("import argparse\n")


def _write(tmp_path, body, code="y = 1\n"):
    (tmp_path / "code.py").write_text(code)
    (tmp_path / "run.py").write_text("import argparse\n")
    p = tmp_path / "x-protocol.md"
    p.write_text(body)
    return str(p)


def test_valid_inline_artifact_passes(tmp_path):
    report = protocol_check.check_protocol(_write(tmp_path, _INLINE_OK), str(tmp_path))
    assert report["ok"], report["problems"]


def test_bears_conclusions_node_without_artifact_section_is_invalid(tmp_path):
    body = _FM + _shape("x.yaml   [bears conclusions]")  # no ## Artifact section
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("no `## Artifact:` section" in p for p in report["problems"])


def test_inline_artifact_without_important_field_is_invalid(tmp_path):
    body = (_FM + _shape("x.yaml   [bears conclusions]")
            + "## Artifact: x.yaml\ncontains: c\nfields:\n  - bar (shape-only)\n\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("no important field" in p for p in report["problems"])


def test_important_field_without_block_is_invalid(tmp_path):
    body = (_FM + _shape("x.yaml   [bears conclusions]")
            + "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("no `### Field:` block" in p for p in report["problems"])


def test_orphan_field_block_is_invalid(tmp_path):
    body = (_FM + _shape("x.yaml   [bears conclusions]")
            + "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
            + "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n"
            + "### Field: ghost\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("not an important field" in p for p in report["problems"])


def test_derived_field_without_formula_is_invalid(tmp_path):
    body = (_FM + _shape("x.yaml   [bears conclusions]")
            + "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
            + "### Field: foo\n- nature: DERIVED\n- file: code.py\n```python\ny = 1\n```\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("formula" in p for p in report["problems"])


def test_snippet_not_in_file_is_invalid(tmp_path):
    body = (_FM + _shape("x.yaml   [bears conclusions]")
            + "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
            + "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\nabsent = 9\n```\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("not found" in p for p in report["problems"])


def test_bad_nature_is_invalid(tmp_path):
    body = (_FM + _shape("x.yaml   [bears conclusions]")
            + "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
            + "### Field: foo\n- nature: GUESSED\n- file: code.py\n```python\ny = 1\n```\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]


def test_no_bears_conclusions_node_is_invalid(tmp_path):
    body = _FM + _shape("x.yaml   [shape-only]")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("nothing in this protocol bears conclusions" in p for p in report["problems"])


def test_missing_script_is_invalid(tmp_path):
    fm = ("---\ntask: t\nparameters: [{name: '--gpu'}]\n---\n\n# t\n\n")
    body = fm + _shape("x.yaml   [bears conclusions]") + (
        "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
        "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("script" in p for p in report["problems"])


def test_script_reading_env_is_invalid(tmp_path):
    (tmp_path / "code.py").write_text("y = 1\n")
    (tmp_path / "run.py").write_text("import os\ngpu = os.getenv('GPU')\n")
    p = tmp_path / "x-protocol.md"
    p.write_text(_INLINE_OK)
    report = protocol_check.check_protocol(str(p), str(tmp_path))
    assert not report["ok"]
    assert any("environment" in p for p in report["problems"])
```

Then update the delegation-test helper `_proto` to emit the new format (these tests stay otherwise identical in intent):

```python
def _proto(task: str, art_path: str, *, delegate: str = "", inline: bool = True) -> str:
    body = (
        f"---\ntask: {task}\nscript: 'run.py'\n"
        "parameters: [{name: '--gpu', purpose: 'gpu index'}]\n"
        f"---\n\n# {task}\n\n"
    )
    marker = "[bears conclusions, delegated]" if delegate else "[bears conclusions]"
    body += f"## Run root shape\n```text\n<run_root>/\n  {art_path}   {marker}\n```\n\n"
    if delegate:
        body += f"## Artifact: {art_path}\ncontains: c\nlineage_protocol: \"{delegate}\"\n"
    elif inline:
        body += (f"## Artifact: {art_path}\ncontains: c\nfields:\n  - foo (important)\n\n"
                 "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n")
    else:
        body += f"## Artifact: {art_path}\ncontains: c\nlineage_protocol: \"\"\n"
    return body
```

Rewrite the delegation tests to use the new signature. Each delegated parent uses `_proto("parent", "out/fig.png", delegate="child-protocol.md")`; each child uses `_proto("child", "fig.png")`. Keep these test names and assertions (update calls only):

```python
def test_delegated_artifact_recurses_and_passes(tmp_path):
    _scaffold(tmp_path)
    (tmp_path / "child-protocol.md").write_text(_proto("child", "fig.png"))
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto("parent", "out/fig.png", delegate="child-protocol.md"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert report["ok"], report["problems"]
    assert report["summary"]["delegated"] == 1
    assert report["lineage"][0]["agree"]
    assert report["lineage"][0]["report"]["task"] == "child"


def test_pure_delegation_is_valid(tmp_path):
    _scaffold(tmp_path)
    (tmp_path / "child-protocol.md").write_text(_proto("child", "fig.png"))
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto("parent", "fig.png", delegate="child-protocol.md"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert report["ok"], report["problems"]


def test_dangling_lineage_reference_is_invalid(tmp_path):
    _scaffold(tmp_path)
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto("parent", "fig.png", delegate="missing-protocol.md"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert not report["ok"]
    assert any("not found" in p for p in report["problems"])


def _all_problems(report):
    out = list(report["problems"])
    for ln in report.get("lineage", []):
        out.extend(_all_problems(ln["report"]))
    return out


def test_lineage_cycle_is_detected(tmp_path):
    _scaffold(tmp_path)
    (tmp_path / "a-protocol.md").write_text(_proto("a", "fig.png", delegate="b-protocol.md"))
    (tmp_path / "b-protocol.md").write_text(_proto("b", "fig.png", delegate="a-protocol.md"))
    report = protocol_check.check_protocol(str(tmp_path / "a-protocol.md"), str(tmp_path))
    assert not report["ok"]
    assert any("cycle" in p for p in _all_problems(report))


def test_self_reference_cycle_is_detected(tmp_path):
    _scaffold(tmp_path)
    p = tmp_path / "self-protocol.md"
    p.write_text(_proto("self", "fig.png", delegate="self-protocol.md"))
    report = protocol_check.check_protocol(str(p), str(tmp_path))
    assert not report["ok"]
    assert any("cycle" in p for p in report["problems"])


def test_path_mismatch_between_parent_and_child_is_invalid(tmp_path):
    _scaffold(tmp_path)
    (tmp_path / "child-protocol.md").write_text(_proto("child", "fig.png"))
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto("parent", "table.csv", delegate="child-protocol.md"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert not report["ok"]
    assert any("matches no artifact" in p for p in report["problems"])


def test_invalid_child_propagates_to_parent(tmp_path):
    _scaffold(tmp_path)
    child = _proto("child", "fig.png").replace("y = 1\n```", "absent = 9\n```")
    (tmp_path / "child-protocol.md").write_text(child)
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto("parent", "fig.png", delegate="child-protocol.md"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert not report["ok"]
    assert any("child protocol is INVALID" in p for p in report["problems"])


def test_check_demo_protocol(tmp_path):
    report = protocol_check.check_protocol(
        os.path.join(DEMO, "protocols", "demo-latency-protocol.md"), DEMO)
    assert report["ok"], report["problems"]
```

- [ ] **Step 2: Run, verify failures**

Run: `cd pin && PYTHONPATH=scripts python3 -m pytest tests/test_protocol_check.py -q`
Expected: many FAIL (new problem strings / report keys not produced yet; `test_check_demo_protocol` fails until Task 3).

- [ ] **Step 3: Rewrite the checker core**

In `pin/scripts/protocol_check.py`:

(a) Change the import on line 33 to:
```python
from pinlib import VALID_NATURE, PinError, load_protocol, locate_snippet  # noqa: E402
```
(unchanged — `locate_snippet`/`VALID_NATURE` still used; `load_protocol` now returns the new shape).

(b) Replace the block from `artifact_paths: list[str] = []` (line ~144) through the end of the element loop `problems.extend(... for p in el_problems)` (line ~202) with:

```python
    # ---- Run-root shape: every produced path, which bear conclusions --------
    shape_by_path = {n.path: n for n in proto.run_root_shape}
    bears = [n for n in proto.run_root_shape if n.bears_conclusions]
    if not proto.run_root_shape:
        problems.append(
            "body: no `## Run root shape` section — declare every produced path "
            "and mark which bear conclusions")
    elif not bears:
        problems.append(
            "body: nothing in this protocol bears conclusions — at least one "
            "run-root-shape node must be marked [bears conclusions]")

    # ---- Artifacts: one `## Artifact:` section per bears-conclusions node ----
    artifact_paths: list[str] = [a.path for a in proto.artifacts]
    art_by_path = {a.path: a for a in proto.artifacts}
    for node in bears:
        art = art_by_path.get(node.path)
        if art is None:
            problems.append(
                f"shape node '{node.path}' bears conclusions but has no "
                "`## Artifact:` section")
            continue
        if node.delegated and not art.lineage_protocol:
            problems.append(
                f"artifact '{node.path}' is marked delegated in the shape but has "
                "no 'lineage_protocol:'")
        if art.lineage_protocol and not node.delegated:
            problems.append(
                f"artifact '{node.path}' has a 'lineage_protocol:' but is not "
                "marked delegated in the shape")

    # ---- Field bijection + field-block contract for inline artifacts --------
    delegations: list[tuple[str, str, str]] = []  # (artifact_path, ref, artifact_path)
    field_reports = []
    for art in proto.artifacts:
        if art.lineage_protocol:
            delegations.append((art.path, art.lineage_protocol, art.path))
            if art.fields or art.field_blocks:
                problems.append(
                    f"artifact '{art.path}' delegates via lineage_protocol but also "
                    "lists inline fields/`### Field:` blocks — a delegated artifact "
                    "has neither")
            continue
        important = [f["name"] for f in art.fields if f.get("important")]
        block_names = [b.name for b in art.field_blocks]
        if not important:
            problems.append(
                f"artifact '{art.path}' bears conclusions but lists no important "
                "field — mark at least one field (important)")
        for name in important:
            if block_names.count(name) == 0:
                problems.append(
                    f"artifact '{art.path}': important field '{name}' has no "
                    "`### Field:` block")
            elif block_names.count(name) > 1:
                problems.append(
                    f"artifact '{art.path}': important field '{name}' has "
                    f"{block_names.count(name)} `### Field:` blocks (expected one)")
        for name in block_names:
            if name not in important:
                problems.append(
                    f"artifact '{art.path}': `### Field:` block '{name}' is not an "
                    "important field of this artifact")
        for lf in art.field_blocks:
            fp: list[str] = []
            located_at = None
            if lf.nature not in VALID_NATURE:
                fp.append(f"nature '{lf.nature}' not in {sorted(VALID_NATURE)}")
            if not lf.file:
                fp.append("missing 'file'")
            if not lf.snippet.strip():
                fp.append("missing code snippet (fenced ``` block)")
            else:
                snippet_lines = [ln for ln in lf.snippet.splitlines() if ln.strip()]
                if len(snippet_lines) > MAX_SNIPPET_LINES:
                    fp.append(
                        f"snippet is {len(snippet_lines)} lines — keep it to the "
                        f"core {MAX_SNIPPET_LINES} or fewer")
            if lf.file and lf.snippet.strip():
                ok, detail, located_at = locate_snippet(lf.snippet, lf.file, base_dir)
                if not ok:
                    fp.append(detail)
            if lf.nature == "DERIVED" and not lf.formula:
                fp.append("nature is DERIVED but no 'formula' given")
            field_reports.append({
                "artifact": art.path,
                "name": lf.name,
                "nature": lf.nature,
                "file": lf.file,
                "located_at": located_at,
                "ok": not fp,
                "problems": fp,
            })
            problems.extend(f"field '{art.path}#{lf.name}': {p}" for p in fp)
```

(c) The delegation-recursion loop (lines ~204-251) iterates `for i, ref, parent_art_path in delegations`. Change the unpack to `for art_path, ref, parent_art_path in delegations`, and replace every `artifacts[{i}]` message prefix with `artifact '{art_path}'`, and `_resolve_lineage_path(ref, protocol_path)` stays. The `lineage_reports.append({"artifact_index": i, ...})` becomes `{"artifact": art_path, ...}`.

(d) Replace the `return {...}` (lines ~253-268) with:

```python
    return {
        "protocol_path": protocol_path,
        "base_dir": base_dir,
        "task": proto.task,
        "ok": not problems,
        "problems": problems,
        "fields": field_reports,
        "artifact_paths": artifact_paths,
        "lineage": lineage_reports,
        "summary": {
            "fields": len(field_reports),
            "fields_ok": sum(f["ok"] for f in field_reports),
            "artifacts": len(proto.artifacts),
            "bears_conclusions": len(bears),
            "delegated": len(delegations),
        },
    }
```

(e) In `print_human` (lines ~280-306): rename the element loop to iterate `report["fields"]`, label each `f"{el['artifact']}#{el['name']}"`, change the problem-skip prefix from `"element "` to `"field "`, and update the summary line to:
```python
        print(f"  {s['fields_ok']}/{s['fields']} fields valid, "
              f"{s['artifacts']} artifact(s), {s['bears_conclusions']} bearing "
              f"conclusions, {s['delegated']} delegated")
```

- [ ] **Step 4: Run, verify pass (except demo until Task 3)**

Run: `cd pin && PYTHONPATH=scripts python3 -m pytest tests/test_protocol_check.py -q -k "not demo"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add pin/scripts/protocol_check.py pin/tests/test_protocol_check.py
git commit -m "protocol_check: enforce artifact/field coverage and bijection"
```

---

## Task 3: Migrate the demo protocols

**Files:**
- Modify: `pin/examples/demo/protocols/demo-latency-protocol.md`, `demo-latency-figure-protocol.md`
- Test: `pin/tests/test_pinlib.py`, `test_protocol_check.py` (re-add demo assertions)

- [ ] **Step 1: Rewrite `demo-latency-protocol.md`**

```markdown
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
```

Note: `data/run.yaml` (the old `side_effects` entry) is now a `[shape-only]` node.

- [ ] **Step 2: Rewrite `demo-latency-figure-protocol.md`**

```markdown
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
```

- [ ] **Step 3: Re-add demo assertions to test_pinlib**

Add to `pin/tests/test_pinlib.py`:

```python
def test_load_protocol_demo():
    proto = pinlib.load_protocol(
        os.path.join(DEMO, "protocols", "demo-latency-protocol.md"))
    assert proto.task == "demo-latency-baseline"
    summ = next(a for a in proto.artifacts if a.path == "data/summary.yaml")
    blocks = {b.name: b for b in summ.field_blocks}
    assert blocks["overhead_ms"].nature == "DERIVED"
    assert blocks["prefill_ms"].nature == "MEASURED"
    assert blocks["prefill_ms"].file == "src/runner.py"
    assert "perf_counter" in blocks["prefill_ms"].snippet
    fig = next(a for a in proto.artifacts if a.path == "data/latency_breakdown.png")
    assert fig.lineage_protocol == "demo-latency-figure-protocol.md"
```

- [ ] **Step 4: Verify checker + parser pass on the demo**

Run: `cd pin && PYTHONPATH=scripts python3 -m pytest tests/test_pinlib.py tests/test_protocol_check.py -q`
Expected: PASS (including `test_check_demo_protocol` and `test_load_protocol_demo`).
Also run the CLI for a human-readable confirmation:
Run: `cd pin && PYTHONPATH=scripts python3 scripts/protocol_check.py examples/demo/protocols/demo-latency-protocol.md --base examples/demo`
Expected: `RESULT: OK`, with the figure protocol shown as a delegated child.

- [ ] **Step 5: Commit**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add pin/examples/demo/protocols/ pin/tests/test_pinlib.py
git commit -m "demo: migrate protocols to artifact/field model"
```

---

## Task 4: factlib — cite (artifact, field) instead of element

**Files:**
- Modify: `pin/scripts/factlib.py:309-333`
- Test: `pin/tests/test_fact_check.py`

- [ ] **Step 1: Write/adjust failing tests**

In `pin/tests/test_fact_check.py`: update `_write_protocol` to emit the new format, and change `_write_internal_fact` to cite `protocol.fields`. Replace the protocol writer and the element parameter:

```python
def _write_protocol(tmp_path):
    (tmp_path / "code.py").write_text("acc = 1\n")
    (tmp_path / "run.py").write_text("import argparse\n")
    (tmp_path / "protocol.md").write_text(
        "---\ntask: t\nscript: 'run.py'\n"
        "parameters: [{name: '--gpu', purpose: 'g'}]\n---\n\n# t\n\n"
        "## Run root shape\n```text\n<run_root>/\n"
        "  data/if-001/result.json   [bears conclusions]\n```\n\n"
        "## Artifact: data/if-001/result.json\ncontains: c\n"
        "fields:\n  - accuracy (important)\n\n"
        "### Field: accuracy\n- nature: MEASURED\n- file: code.py\n```python\nacc = 1\n```\n"
    )
```

Change `_write_internal_fact(tmp_path, claim=None, protocol_field=("data/if-001/result.json", "accuracy"))` to emit:

```python
        "protocol:\n"
        "  path: protocol.md\n"
        "  fields:\n"
        f"    - {{artifact: '{protocol_field[0]}', field: '{protocol_field[1]}'}}\n"
```

And the bad-reference test:

```python
def test_internal_fact_rejects_missing_protocol_field(tmp_path):
    _write_internal_fact(tmp_path, protocol_field=("data/if-001/result.json", "missing"))
    report = fact_check.check_fact(...)  # keep existing call shape
    assert not report["ok"]
    assert any("protocol field" in problem for problem in report["problems"])
```

Update the prose-lineage line in the fact body helper from
`"- Protocol `protocol.md`, element `accuracy`.\n\n"` to
`"- Protocol `protocol.md`, artifact `data/if-001/result.json` field `accuracy`.\n\n"`.

- [ ] **Step 2: Run, verify failure**

Run: `cd pin && PYTHONPATH=scripts python3 -m pytest tests/test_fact_check.py -q`
Expected: FAIL — factlib still reads `protocol.elements` / `proto.elements`.

- [ ] **Step 3: Rewrite the factlib internal-fact protocol check**

Replace `pin/scripts/factlib.py:309-333` with:

```python
    protocol = fact.meta.get("protocol")
    if not isinstance(protocol, dict):
        problems.append("internal fact needs frontmatter protocol mapping")
    else:
        proto_path = protocol.get("path")
        fields = protocol.get("fields")
        if not proto_path:
            problems.append("internal fact needs protocol.path")
        if not isinstance(fields, list) or not fields:
            problems.append("internal fact needs non-empty protocol.fields")
        if proto_path and isinstance(fields, list):
            full = _resolve_research_path(str(proto_path), research_root)
            if not os.path.isfile(full):
                problems.append(f"protocol.path does not exist: {proto_path}")
            else:
                try:
                    proto = load_protocol(full)
                    known = {
                        (a.path, b.name)
                        for a in proto.artifacts
                        for b in a.field_blocks
                    }
                    for ref in fields:
                        if not isinstance(ref, dict):
                            problems.append(
                                "protocol.fields entries must be {artifact, field} mappings")
                            continue
                        key = (ref.get("artifact"), ref.get("field"))
                        if key not in known:
                            problems.append(
                                f"protocol field {key[1]!r} of artifact {key[0]!r} "
                                f"not found in {proto_path}")
                except PinError as exc:
                    problems.append(f"protocol.path invalid: {exc}")
```

- [ ] **Step 4: Run, verify pass**

Run: `cd pin && PYTHONPATH=scripts python3 -m pytest tests/test_fact_check.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add pin/scripts/factlib.py pin/tests/test_fact_check.py
git commit -m "factlib: internal facts cite (artifact, field) lineage"
```

---

## Task 5: Migrate demo facts

**Files:**
- Modify: `pin/examples/demo/facts/internal/if-001-prefill-latency.md`, `if-002-decode-latency.md`

- [ ] **Step 1: Read both facts**

Run: `cd /mnt/nvme2/zyx/projects/hai && sed -n '20,30p;55,65p' pin/examples/demo/facts/internal/if-001-prefill-latency.md`
Identify the `protocol:` frontmatter block and the prose `- Protocol ... element ...` lineage line.

- [ ] **Step 2: Edit if-001**

In `pin/examples/demo/facts/internal/if-001-prefill-latency.md`, replace the frontmatter block
```yaml
protocol:
  path: protocols/demo-latency-protocol.md
  elements:
    - prefill_ms
```
with
```yaml
protocol:
  path: protocols/demo-latency-protocol.md
  fields:
    - {artifact: data/summary.yaml, field: prefill_ms}
```
and the prose line
`- Protocol `protocols/demo-latency-protocol.md`, element `prefill_ms` (MEASURED).`
with
`- Protocol `protocols/demo-latency-protocol.md`, artifact `data/summary.yaml` field `prefill_ms` (MEASURED).`

- [ ] **Step 3: Edit if-002 the same way**

Apply the identical transform to `if-002-decode-latency.md`, using `field: decode_ms`. Confirm its current element name first: `grep -n "elements:\|element \`" pin/examples/demo/facts/internal/if-002-decode-latency.md`.

- [ ] **Step 4: Verify fact_check passes on the demo facts**

Run: `cd pin && PYTHONPATH=scripts python3 scripts/fact_check.py examples/demo/facts/internal/if-001-prefill-latency.md --base examples/demo`
Expected: OK / no problems. Repeat for if-002.

- [ ] **Step 5: Commit**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add pin/examples/demo/facts/internal/
git commit -m "demo: cite (artifact, field) in internal facts"
```

---

## Task 6: Rewrite the protocol schema

**Files:**
- Modify: `pin/schema/protocol.schema.md`

- [ ] **Step 1: Rewrite the Structure and Field-consumers sections**

Replace the `## Structure` fenced example with the new format (the canonical block from the design spec, `docs/superpowers/specs/2026-06-17-protocol-artifact-field-model-design.md` § "File format"). Replace the old "## Lineage points at the producing code" element references with `### Field:` wording. Rewrite the `## Field consumers` enforcement list to match Task 2's checker:

- `task`, `script` (exists, `.py` reads no env), `parameters` (non-empty, each named) — unchanged.
- `## Run root shape` present and ≥1 node marked `[bears conclusions]`.
- Each `[bears conclusions]` node has a matching `## Artifact:` section; `[... delegated]` ⟺ the section carries `lineage_protocol:`.
- An inline artifact has ≥1 `important` field; important fields ↔ `### Field:` blocks is a bijection (no orphan blocks, no uncovered important field).
- Each `### Field:` block: `nature` ∈ the 4 values, `file`, fenced snippet ≤5 lines located verbatim, `formula` iff `DERIVED`.
- A delegated artifact has no inline fields/blocks; child resolves, is valid, declares the delegated path, graph acyclic.

Keep the closing "machine check is necessary, not sufficient" note, updated to reference fields.

- [ ] **Step 2: Sanity-check the schema example parses**

Extract the schema's fenced protocol example into a temp file and run the checker against the demo `src/` to confirm the documented format is the one the checker accepts (or visually diff it against the migrated `demo-latency-protocol.md`). No automated test; verify by eye that headings, `fields:` syntax, and markers match Task 1/2.

- [ ] **Step 3: Commit**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add pin/schema/protocol.schema.md
git commit -m "schema: rewrite protocol schema for artifact/field model"
```

---

## Task 7: Rewrite the pin-protocol skill

**Files:**
- Modify: `pin/skills/pin-protocol/SKILL.md`

- [ ] **Step 1: Rewrite the format + workflow**

Update SKILL.md to describe:
- The new body structure (`## Run root shape`, `## Artifact:`, `fields:`, `### Field:`), replacing all `## Element:` references and the worked example with the migrated demo format.
- The interactive authoring workflow from the design spec § "Authoring workflow": (1) one script, (2) frontmatter, (3) enumerate run-root shape from the producing code, (4) user selects conclusion-bearing artifacts, (5) per artifact inline-vs-delegate; for inline, list fields and user selects important ones, (6) author each `### Field:` block, (7) run checker.
- The "test before you stop" and validation sections, updated to fields/artifacts.

Keep the skill under any length limit it already respects (check the frontmatter `description`). Do not change the YAML frontmatter `name`/`description` semantics beyond wording.

- [ ] **Step 2: Verify no stale `## Element` references remain**

Run: `grep -n "## Element\|element" pin/skills/pin-protocol/SKILL.md`
Expected: no `## Element`; remaining "element" only if intentional (prefer "field").

- [ ] **Step 3: Commit**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add pin/skills/pin-protocol/SKILL.md
git commit -m "pin-protocol: rewrite workflow + format for artifact/field model"
```

---

## Task 8: Update cross-referencing docs

**Files:**
- Modify: `pin/schema/facts.schema.md`, `pin/skills/pin-fact/SKILL.md`, `pin/skills/pin-codex-audit/SKILL.md`, `pin/skills/pin-codex-audit/references/codex-briefing.md`, `pin/skills/pin-grounding/SKILL.md`, `pin/skills/pin-aware-agent/SKILL.md`, `pin/README.md`

- [ ] **Step 1: facts.schema.md**

Replace the `protocol.elements` example (lines ~112-116) with:
```yaml
protocol:
  path: channels/main/eval-1-protocol.md
  fields:
    - {artifact: summary.json, field: accuracy}
    - {artifact: summary.json, field: sample_count}
```
Update surrounding prose that says "element" to "artifact field".

- [ ] **Step 2: pin-fact/SKILL.md**

Update the lineage instructions (lines ~63-66, ~100, and the worked example ~226, ~257) from "protocol element names" / "element `X`" to "the protocol's `(artifact, field)` pairs" and prose `artifact `…` field `…``. Keep the delegation note (cite the child protocol for a delegated artifact's field).

- [ ] **Step 3: codex-briefing.md + pin-codex-audit/SKILL.md**

Replace "protocol element" / "data element" with "artifact field" throughout (codex-briefing lines ~14,41,44,49,69; codex-audit lines ~80,88,89). The Q3 FALSE LINEAGE prompt should say "for each important field of each artifact in `<protocol path(s)>`".

- [ ] **Step 4: pin-grounding/SKILL.md + pin-aware-agent/SKILL.md + README.md**

Replace "data element" / "lineage element" / "element names" with "artifact field" / "the `(artifact, field)` pairs". In pin-aware-agent lines ~158-159 update "each element's code snippet must still appear" to "each field's code snippet". README: update any element wording.

- [ ] **Step 5: Grep for stragglers across the plugin**

Run: `cd pin && grep -rn "## Element\|protocol element\|data element\|lineage element\|\.elements\b" --include='*.md' --include='*.py' . | grep -v tests/`
Expected: empty (or only intentional historical mentions). Fix any remaining.

- [ ] **Step 6: Commit**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add pin/schema/facts.schema.md pin/skills/ pin/README.md
git commit -m "docs: rename element->field, cite (artifact, field) across pin skills"
```

---

## Task 9: Full verification

**Files:** none (verification)

- [ ] **Step 1: Run the whole suite**

Run: `cd pin && PYTHONPATH=scripts python3 -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 2: Run both checkers on the demo end to end**

Run:
```bash
cd pin
PYTHONPATH=scripts python3 scripts/protocol_check.py examples/demo/protocols/demo-latency-protocol.md --base examples/demo
PYTHONPATH=scripts python3 scripts/protocol_check.py examples/demo/protocols/demo-latency-figure-protocol.md --base examples/demo
for f in examples/demo/facts/internal/*.md; do PYTHONPATH=scripts python3 scripts/fact_check.py "$f" --base examples/demo; done
```
Expected: every protocol `RESULT: OK`; every internal fact OK.

- [ ] **Step 3: Confirm no old-format remnants**

Run: `cd pin && grep -rn "## Element\|side_effects\|\.elements" --include='*.md' --include='*.py' . | grep -v docs/`
Expected: empty. (`side_effects` is fully replaced by `[shape-only]` shape nodes.)

- [ ] **Step 4: Final commit if anything was fixed**

```bash
cd /mnt/nvme2/zyx/projects/hai
git add -A && git commit -m "protocol artifact/field model: final verification fixes" || echo "nothing to commit"
```

---

## Self-review notes

- **Spec coverage:** decisions 1-6 map to Tasks 1-2 (coverage/bijection mechanics), 3/5 (migration), 7 (interactive workflow), 6/8 (schema+docs), 4/8 (fact citation breaking change). Hard cut: no dual-format code path exists in Task 1/2.
- **`side_effects` removal:** old `side_effects[]` entries become `[shape-only]` shape nodes (Task 3 demo, Task 6 schema, Task 9 grep gate).
- **Type consistency:** `LineageField`/`Artifact`/`ShapeNode`/`Protocol` names and fields are identical across Tasks 1, 2, 4. Report keys (`fields`, `artifact_paths`, `lineage`, `summary.{fields,fields_ok,artifacts,bears_conclusions,delegated}`) are produced in Task 2 and asserted in Tasks 2-3.
- **Open risk to verify in Task 0:** the exact pytest invocation (`PYTHONPATH=scripts`). Adjust all run-steps if the repo already adds `scripts/` to the path via conftest.
- **Not in scope:** semantic snippet-correctness checking (still human + Codex), per spec § "Out of scope".
```
