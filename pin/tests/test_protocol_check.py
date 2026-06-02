"""Unit tests for protocol_check (snippet-anchored lineage)."""
import os

import protocol_check

HERE = os.path.dirname(__file__)
DEMO = os.path.join(HERE, "..", "examples", "demo")

_FRONTMATTER = (
    "---\n"
    "task: t\n"
    "script: 'run.py'\n"
    "parameters:\n"
    "  - {name: '--gpu', purpose: 'gpu index', required: true}\n"
    "artifacts: [{path: 'x.yaml'}]\n"
    "---\n\n# x\n\n"
)

_VALID_ELEMENT = (
    "## Element: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n"
)


def _write(tmp_path, code: str, element_block: str, frontmatter: str = _FRONTMATTER) -> str:
    """Write code.py + an arg-only run.py + a one-element protocol; return its path."""
    (tmp_path / "code.py").write_text(code)
    (tmp_path / "run.py").write_text("import argparse\n")
    proto = tmp_path / "x-protocol.md"
    proto.write_text(frontmatter + element_block)
    return str(proto)


def test_check_demo_protocol():
    report = protocol_check.check_protocol(
        os.path.join(DEMO, "protocols", "demo-latency-protocol.md"), DEMO)
    assert report["ok"]
    assert report["summary"]["elements"] == 3
    assert report["summary"]["elements_ok"] == 3


def test_valid_element_passes(tmp_path):
    proto = _write(
        tmp_path, "y = 1\n",
        "## Element: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n")
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert report["ok"]


def test_derived_element_without_formula_is_invalid(tmp_path):
    proto = _write(
        tmp_path, "y = total - a - b\n",
        "## Element: foo\n- nature: DERIVED\n- file: code.py\n"
        "```python\ny = total - a - b\n```\n")
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert not report["ok"]
    assert any("formula" in p for p in report["problems"])


def test_snippet_not_in_file_is_invalid(tmp_path):
    proto = _write(
        tmp_path, "a = 1\n",
        "## Element: foo\n- nature: MEASURED\n- file: code.py\n"
        "```python\nnonexistent = 42\n```\n")
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert not report["ok"]
    assert any("not found" in p for p in report["problems"])


def test_missing_snippet_is_invalid(tmp_path):
    proto = _write(
        tmp_path, "a = 1\n",
        "## Element: foo\n- nature: MEASURED\n- file: code.py\n")
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert not report["ok"]
    assert any("snippet" in p for p in report["problems"])


def test_snippet_too_long_is_invalid(tmp_path):
    code = "l1\nl2\nl3\nl4\nl5\nl6\n"
    proto = _write(
        tmp_path, code,
        "## Element: foo\n- nature: MEASURED\n- file: code.py\n"
        "```\nl1\nl2\nl3\nl4\nl5\nl6\n```\n")
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert not report["ok"]
    assert any("lines" in p for p in report["problems"])


def test_bad_nature_tag_is_invalid(tmp_path):
    proto = _write(
        tmp_path, "a = 1\n",
        "## Element: foo\n- nature: GUESSED\n- file: code.py\n"
        "```python\na = 1\n```\n")
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert not report["ok"]


def test_missing_script_is_invalid(tmp_path):
    fm = ("---\ntask: t\nparameters: [{name: '--gpu'}]\n"
          "artifacts: [{path: 'x.yaml'}]\n---\n\n# x\n\n")
    proto = _write(tmp_path, "y = 1\n", _VALID_ELEMENT, frontmatter=fm)
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert not report["ok"]
    assert any("script" in p for p in report["problems"])


def test_missing_parameters_is_invalid(tmp_path):
    fm = ("---\ntask: t\nscript: 'run.py'\n"
          "artifacts: [{path: 'x.yaml'}]\n---\n\n# x\n\n")
    proto = _write(tmp_path, "y = 1\n", _VALID_ELEMENT, frontmatter=fm)
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert not report["ok"]
    assert any("parameters" in p for p in report["problems"])


def test_script_not_on_disk_is_invalid(tmp_path):
    fm = ("---\ntask: t\nscript: 'nope.py'\nparameters: [{name: '--gpu'}]\n"
          "artifacts: [{path: 'x.yaml'}]\n---\n\n# x\n\n")
    proto = _write(tmp_path, "y = 1\n", _VALID_ELEMENT, frontmatter=fm)
    report = protocol_check.check_protocol(proto, str(tmp_path))
    assert not report["ok"]
    assert any("not found" in p for p in report["problems"])


def test_script_reading_env_is_invalid(tmp_path):
    (tmp_path / "code.py").write_text("y = 1\n")
    (tmp_path / "run.py").write_text("import os\ngpu = os.getenv('GPU')\n")
    proto = tmp_path / "x-protocol.md"
    proto.write_text(_FRONTMATTER + _VALID_ELEMENT)
    report = protocol_check.check_protocol(str(proto), str(tmp_path))
    assert not report["ok"]
    assert any("environment" in p for p in report["problems"])


# --------------------------------------------------------------------------
# Recursion: an artifact can delegate its lineage to a child protocol.
# --------------------------------------------------------------------------
def _proto(task: str, artifacts: str, *, element: bool = True) -> str:
    """A minimal protocol body; `artifacts` is the inline yaml list."""
    body = (
        f"---\ntask: {task}\nscript: 'run.py'\n"
        "parameters: [{name: '--gpu', purpose: 'gpu index'}]\n"
        f"artifacts: {artifacts}\n---\n\n# {task}\n\n"
    )
    if element:
        body += "## Element: foo\n- nature: MEASURED\n- file: code.py\n```python\ny = 1\n```\n"
    return body


def _scaffold(tmp_path):
    (tmp_path / "code.py").write_text("y = 1\n")
    (tmp_path / "run.py").write_text("import argparse\n")


def test_delegated_artifact_recurses_and_passes(tmp_path):
    _scaffold(tmp_path)
    (tmp_path / "child-protocol.md").write_text(_proto("child", "[{path: 'fig.png'}]"))
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto(
        "parent", "[{path: 'out/fig.png', lineage_protocol: 'child-protocol.md'}]"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert report["ok"], report["problems"]
    assert report["summary"]["delegated"] == 1
    assert report["lineage"][0]["agree"]
    assert report["lineage"][0]["report"]["task"] == "child"


def test_pure_delegation_without_own_elements_is_valid(tmp_path):
    _scaffold(tmp_path)
    (tmp_path / "child-protocol.md").write_text(_proto("child", "[{path: 'fig.png'}]"))
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto(
        "parent", "[{path: 'fig.png', lineage_protocol: 'child-protocol.md'}]",
        element=False))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert report["ok"], report["problems"]


def test_dangling_lineage_reference_is_invalid(tmp_path):
    _scaffold(tmp_path)
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto(
        "parent", "[{path: 'fig.png', lineage_protocol: 'missing-protocol.md'}]"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert not report["ok"]
    assert any("not found" in p for p in report["problems"])


def _all_problems(report) -> list[str]:
    """Flatten a protocol report's problems across the whole delegation tree."""
    out = list(report["problems"])
    for ln in report.get("lineage", []):
        out.extend(_all_problems(ln["report"]))
    return out


def test_lineage_cycle_is_detected(tmp_path):
    _scaffold(tmp_path)
    (tmp_path / "a-protocol.md").write_text(_proto(
        "a", "[{path: 'fig.png', lineage_protocol: 'b-protocol.md'}]"))
    (tmp_path / "b-protocol.md").write_text(_proto(
        "b", "[{path: 'fig.png', lineage_protocol: 'a-protocol.md'}]"))
    report = protocol_check.check_protocol(
        str(tmp_path / "a-protocol.md"), str(tmp_path))
    assert not report["ok"]
    # the 2-cycle is caught when b references a (a is already on the stack)
    assert any("cycle" in p for p in _all_problems(report))


def test_self_reference_cycle_is_detected(tmp_path):
    _scaffold(tmp_path)
    proto = tmp_path / "self-protocol.md"
    proto.write_text(_proto(
        "self", "[{path: 'fig.png', lineage_protocol: 'self-protocol.md'}]"))
    report = protocol_check.check_protocol(str(proto), str(tmp_path))
    assert not report["ok"]
    assert any("cycle" in p for p in report["problems"])


def test_path_mismatch_between_parent_and_child_is_invalid(tmp_path):
    _scaffold(tmp_path)
    (tmp_path / "child-protocol.md").write_text(_proto("child", "[{path: 'fig.png'}]"))
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto(
        "parent", "[{path: 'table.csv', lineage_protocol: 'child-protocol.md'}]"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert not report["ok"]
    assert any("matches no artifact" in p for p in report["problems"])
    assert not report["lineage"][0]["agree"]


def test_invalid_child_propagates_to_parent(tmp_path):
    _scaffold(tmp_path)
    # child's snippet does not appear in code.py
    child = (
        "---\ntask: child\nscript: 'run.py'\n"
        "parameters: [{name: '--gpu', purpose: 'g'}]\n"
        "artifacts: [{path: 'fig.png'}]\n---\n\n# child\n\n"
        "## Element: foo\n- nature: MEASURED\n- file: code.py\n```python\nabsent = 9\n```\n"
    )
    (tmp_path / "child-protocol.md").write_text(child)
    parent = tmp_path / "parent-protocol.md"
    parent.write_text(_proto(
        "parent", "[{path: 'fig.png', lineage_protocol: 'child-protocol.md'}]"))
    report = protocol_check.check_protocol(str(parent), str(tmp_path))
    assert not report["ok"]
    assert any("child protocol is INVALID" in p for p in report["problems"])
    assert not report["lineage"][0]["report"]["ok"]
