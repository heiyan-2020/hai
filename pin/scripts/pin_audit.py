#!/usr/bin/env python3
"""pin_audit.py — run every enforced pin's assertion and report.

The machine-audit layer of the pin plugin. Non-interactive. Used by the git
pre-commit hook, by the pin-audit / pin-aware-agent skills, and by humans.

Usage:
    pin_audit.py <pins.yaml> [--only id1,id2] [--branch BR] [--json]

Exit code 0 iff every enforced pin passes and no pin is structurally invalid.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pinlib import Pin, PinError, load_pins  # noqa: E402


def detect_branch(project_root: str) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_root, capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "no-branch"


def _run(cmd: list[str] | str, cwd: str, shell: bool = False) -> tuple[int, str]:
    """Run a command, return (exit_code, combined_output trimmed)."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return 124, "timed out after 300s"
    except OSError as exc:
        return 127, f"could not execute: {exc}"
    output = (proc.stdout + proc.stderr).strip()
    if len(output) > 1200:
        output = output[:600] + "\n  ... (truncated) ...\n" + output[-600:]
    return proc.returncode, output


def run_assertion(pin: Pin, project_root: str) -> tuple[bool, str]:
    """Execute one pin's assertion. Returns (passed, detail)."""
    a = pin.assertion
    atype = a.get("type")

    if atype == "pytest":
        code, out = _run(
            [sys.executable, "-m", "pytest", str(a["target"]), "-q", "--no-header"],
            project_root,
        )
        return code == 0, out or f"pytest exit {code}"

    if atype == "python":
        code, out = _run([sys.executable, str(a["target"])], project_root)
        return code == 0, out or f"python exit {code}"

    if atype == "command":
        code, out = _run(str(a["target"]), project_root, shell=True)
        return code == 0, out or f"command exit {code}"

    if atype in {"grep", "grep_absent"}:
        return _run_grep(pin, project_root, want_present=(atype == "grep"))

    return False, f"unknown assertion type '{atype}'"


def _run_grep(pin: Pin, project_root: str, want_present: bool) -> tuple[bool, str]:
    pattern = pin.assertion["pattern"]
    missing, offending = [], []
    for rel in pin.code_locations:
        full = os.path.join(project_root, rel)
        if not os.path.isfile(full):
            return False, f"code_location not found: {rel}"
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            present = pattern in fh.read()
        if want_present and not present:
            missing.append(rel)
        if not want_present and present:
            offending.append(rel)
    if want_present and missing:
        return False, f"pattern absent from: {', '.join(missing)}"
    if not want_present and offending:
        return False, f"pattern present in (should be absent): {', '.join(offending)}"
    return True, "pattern check ok"


def check_anchors(pin: Pin, project_root: str) -> list[str]:
    """Advisory: each code_location should carry a `# PIN: <id>` breadcrumb."""
    warnings: list[str] = []
    needle = f"PIN: {pin.id}"
    for rel in pin.code_locations:
        full = os.path.join(project_root, rel)
        if not os.path.isfile(full):
            continue  # missing file is already an assertion-level concern
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            if needle not in fh.read():
                warnings.append(f"no `# PIN: {pin.id}` anchor in {rel}")
    return warnings


def audit(pins_path: str, only: set[str] | None, branch: str | None) -> dict:
    project_root = os.path.dirname(os.path.abspath(pins_path)) or "."
    pins = load_pins(pins_path)
    branch = branch or detect_branch(project_root)

    structural: list[str] = []
    for pin in pins:
        structural.extend(pin.validate())

    results = []
    for pin in pins:
        if only and pin.id not in only:
            continue
        if not pin.is_enforced(branch):
            results.append({"id": pin.id, "outcome": "SKIP",
                            "detail": f"status={pin.status}", "warnings": []})
            continue
        if pin.validate():
            results.append({"id": pin.id, "outcome": "FAIL",
                            "detail": "structurally invalid", "warnings": []})
            continue
        passed, detail = run_assertion(pin, project_root)
        results.append({
            "id": pin.id,
            "outcome": "PASS" if passed else "FAIL",
            "detail": detail,
            "warnings": check_anchors(pin, project_root),
        })

    failed = [r for r in results if r["outcome"] == "FAIL"]
    ok = not failed and not structural
    return {
        "pins_path": pins_path,
        "branch": branch,
        "ok": ok,
        "structural_errors": structural,
        "results": results,
        "summary": {
            "total": len(results),
            "passed": sum(r["outcome"] == "PASS" for r in results),
            "failed": len(failed),
            "skipped": sum(r["outcome"] == "SKIP" for r in results),
        },
    }


def print_human(report: dict) -> None:
    print(f"pin-audit  ({report['pins_path']}, branch: {report['branch']})")
    print("-" * 64)
    for err in report["structural_errors"]:
        print(f"  STRUCTURAL ERROR  {err}")
    if report["structural_errors"]:
        print("-" * 64)
    for r in report["results"]:
        mark = {"PASS": "ok  ", "FAIL": "FAIL", "SKIP": "skip"}[r["outcome"]]
        print(f"  [{mark}] {r['id']}")
        if r["outcome"] != "PASS" or r["warnings"]:
            if r["detail"]:
                first = r["detail"].splitlines()[0]
                print(f"         {first}")
            for w in r["warnings"]:
                print(f"         warning: {w}")
    s = report["summary"]
    print("-" * 64)
    print(f"  {s['passed']} passed, {s['failed']} failed, {s['skipped']} skipped")
    print(f"  RESULT: {'OK' if report['ok'] else 'BLOCKED'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run all enforced pin assertions.")
    ap.add_argument("pins_path", help="path to pins.yaml")
    ap.add_argument("--only", default="", help="comma-separated pin ids to check")
    ap.add_argument("--branch", default=None, help="branch override")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args(argv)

    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    try:
        report = audit(args.pins_path, only, args.branch)
    except PinError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"pin-audit: ERROR  {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
