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


def test_load_protocol_demo():
    proto = pinlib.load_protocol(
        os.path.join(DEMO, "protocols", "demo-latency-protocol.md"))
    assert proto.task == "demo-latency-baseline"
    assert len(proto.elements) == 3
    natures = {e.name: e.nature for e in proto.elements}
    assert natures["overhead_ms"] == "DERIVED"
    assert natures["prefill_ms"] == "MEASURED"
    # each element carries a file and a verbatim code snippet
    prefill = next(e for e in proto.elements if e.name == "prefill_ms")
    assert prefill.file == "src/runner.py"
    assert "perf_counter" in prefill.snippet


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
