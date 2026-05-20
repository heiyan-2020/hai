"""Unit tests for protocol_check (snippet-anchored lineage)."""
import os

import protocol_check

HERE = os.path.dirname(__file__)
DEMO = os.path.join(HERE, "..", "examples", "demo")

_FRONTMATTER = "---\ntask: t\nartifacts: [{path: 'x.yaml'}]\n---\n\n# x\n\n"


def _write(tmp_path, code: str, element_block: str) -> str:
    """Write a code.py + a one-element protocol; return the protocol path."""
    (tmp_path / "code.py").write_text(code)
    proto = tmp_path / "x-protocol.md"
    proto.write_text(_FRONTMATTER + element_block)
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
