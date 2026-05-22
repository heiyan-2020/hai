#!/usr/bin/env python3
"""fact_check.py — validate structured markdown research facts.

Usage:
    fact_check.py <facts-dir> [--research-root DIR] [--json]

<facts-dir> should contain internal/, external/, and/or derived/ markdown fact
files. Paths in frontmatter such as data.primary_path and protocol.path resolve
against --research-root, which defaults to the parent directory of <facts-dir>.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factlib import validate_facts  # noqa: E402
from pinlib import PinError  # noqa: E402


def print_human(report: dict) -> None:
    print(f"fact-check  ({report['facts_root']})")
    print(f"  research root: {report['research_root']}")
    print("-" * 64)
    for fact in report["facts"]:
        mark = "ok  " if fact["ok"] else "FAIL"
        rel = os.path.relpath(fact["path"], report["facts_root"])
        print(f"  [{mark}] {fact['id'] or '(no id)'}  ({fact['type'] or 'no-type'}  {rel})")
        for problem in fact["problems"]:
            print(f"         {problem}")
    s = report["summary"]
    print("-" * 64)
    print(
        f"  {s['ok']}/{s['total']} facts valid "
        f"({s['internal']} internal, {s['external']} external, {s['derived']} derived)"
    )
    print(f"  RESULT: {'OK' if report['ok'] else 'INVALID'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate structured markdown facts.")
    ap.add_argument("facts_dir", help="path to .claude-research/facts")
    ap.add_argument(
        "--research-root",
        default=None,
        help="directory that fact data/protocol paths resolve against",
    )
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args(argv)

    try:
        report = validate_facts(args.facts_dir, args.research_root)
    except PinError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"fact-check: ERROR  {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
