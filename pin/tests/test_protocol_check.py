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


def test_artifact_section_for_non_bears_node_is_invalid(tmp_path):
    # x.yaml is marked [shape-only] yet still carries a `## Artifact:` section.
    body = (_FM + _shape("x.yaml   [shape-only]", "y.yaml   [bears conclusions]")
            + "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
            + "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n"
            + "## Artifact: y.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
            + "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("not marked [bears conclusions]" in p for p in report["problems"])


def test_artifact_section_for_path_absent_from_shape_is_invalid(tmp_path):
    # z.yaml has a `## Artifact:` section but never appears in the run root shape.
    body = (_FM + _shape("x.yaml   [bears conclusions]")
            + "## Artifact: x.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
            + "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n"
            + "## Artifact: z.yaml\ncontains: c\nfields:\n  - foo (important)\n\n"
            + "### Field: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n")
    report = protocol_check.check_protocol(_write(tmp_path, body), str(tmp_path))
    assert not report["ok"]
    assert any("not marked [bears conclusions]" in p for p in report["problems"])


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


# --------------------------------------------------------------------------
# Recursion: an artifact can delegate its lineage to a child protocol.
# --------------------------------------------------------------------------
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
