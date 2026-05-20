"""Unit tests for the pin_audit engine."""
import os

import pin_audit

HERE = os.path.dirname(__file__)
DEMO = os.path.join(HERE, "..", "examples", "demo")


def _write_pins(tmp_path, body: str) -> str:
    f = tmp_path / "pins.yaml"
    f.write_text(body)
    return str(f)


def test_audit_clean_demo():
    report = pin_audit.audit(os.path.join(DEMO, "pins.yaml"), None, "main")
    assert report["ok"]
    assert report["summary"]["passed"] == 2
    assert report["summary"]["failed"] == 0


def test_audit_catches_failing_command_pin(tmp_path):
    path = _write_pins(tmp_path,
        "pins:\n"
        "  - id: bad\n"
        "    claim: always fails\n"
        "    branch: main\n"
        "    born_at: '0'\n"
        "    status: active\n"
        "    assertion: {type: command, target: 'exit 1'}\n")
    report = pin_audit.audit(path, None, "main")
    assert not report["ok"]
    assert report["summary"]["failed"] == 1


def test_audit_skips_retired_pin(tmp_path):
    path = _write_pins(tmp_path,
        "pins:\n"
        "  - id: old\n"
        "    claim: a retired decision\n"
        "    branch: main\n"
        "    born_at: '0'\n"
        "    status: retired\n"
        "    retire_reason: superseded by new approach\n"
        "    assertion: {type: command, target: 'exit 1'}\n")
    report = pin_audit.audit(path, None, "main")
    assert report["ok"]  # retired pin not enforced, so audit is clean
    assert report["summary"]["skipped"] == 1


def test_grep_absent_fails_when_pattern_present(tmp_path):
    (tmp_path / "code.py").write_text("decode = ms_per_token * n_tokens\n")
    path = _write_pins(tmp_path,
        "pins:\n"
        "  - id: no-synthetic-decode\n"
        "    claim: decode time must not be synthetic\n"
        "    branch: main\n"
        "    born_at: '0'\n"
        "    status: active\n"
        "    assertion: {type: grep_absent, pattern: 'ms_per_token'}\n"
        "    code_locations: ['code.py']\n")
    report = pin_audit.audit(path, None, "main")
    assert not report["ok"]


def test_disabled_pin_skipped_on_its_branch(tmp_path):
    path = _write_pins(tmp_path,
        "pins:\n"
        "  - id: relaxed\n"
        "    claim: temporarily off on the experiment branch\n"
        "    branch: main\n"
        "    born_at: '0'\n"
        "    status: disabled\n"
        "    disabled_on: ['fork-exp']\n"
        "    assertion: {type: command, target: 'exit 1'}\n")
    on_exp = pin_audit.audit(path, None, "fork-exp")
    assert on_exp["ok"] and on_exp["summary"]["skipped"] == 1
    on_main = pin_audit.audit(path, None, "main")
    assert not on_main["ok"]  # enforced again on main
