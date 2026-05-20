#!/usr/bin/env python3
"""protocol_check.py — validate a *-protocol.md data-lineage spec.

A protocol is valid when every conclusion-bearing data element names its
`file`, carries a short verbatim code `snippet` that still appears in that
file, and is tagged with a nature. This is the machine layer; pin-codex-audit
then checks that the snippet's lineage description is actually *true*.

Usage:
    protocol_check.py <protocol.md> [--base DIR] [--json]

--base is the directory that element `file` paths resolve against; defaults to
the current working directory.

Exit code 0 iff the protocol is structurally valid and every snippet locates.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pinlib import VALID_NATURE, PinError, load_protocol, locate_snippet  # noqa: E402

# A lineage snippet must be the *core* lines, not a whole function dump.
MAX_SNIPPET_LINES = 5


def check_protocol(protocol_path: str, base_dir: str) -> dict:
    proto = load_protocol(protocol_path)
    problems: list[str] = []

    if not proto.task:
        problems.append("frontmatter: 'task' is missing or empty")

    for i, art in enumerate(proto.artifacts):
        if not isinstance(art, dict):
            problems.append(f"frontmatter: artifacts[{i}] is not a mapping")
            continue
        if not str(art.get("path", "")).strip():
            problems.append(f"frontmatter: artifacts[{i}] has no 'path'")

    if not proto.elements:
        problems.append("body: no `## Element:` lineage blocks found")

    element_reports = []
    for el in proto.elements:
        el_problems: list[str] = []
        located_at = None

        if el.nature not in VALID_NATURE:
            el_problems.append(
                f"nature '{el.nature}' not in {sorted(VALID_NATURE)}"
            )
        if not el.file:
            el_problems.append("missing 'file'")
        if not el.snippet.strip():
            el_problems.append("missing code snippet (fenced ``` block)")
        else:
            snippet_lines = [ln for ln in el.snippet.splitlines() if ln.strip()]
            if len(snippet_lines) > MAX_SNIPPET_LINES:
                el_problems.append(
                    f"snippet is {len(snippet_lines)} lines — keep it to the "
                    f"core {MAX_SNIPPET_LINES} or fewer"
                )
        if el.file and el.snippet.strip():
            ok, detail, located_at = locate_snippet(el.snippet, el.file, base_dir)
            if not ok:
                el_problems.append(detail)
        if el.nature == "DERIVED" and not el.formula:
            el_problems.append("nature is DERIVED but no 'formula' given")

        element_reports.append({
            "name": el.name,
            "nature": el.nature,
            "file": el.file,
            "located_at": located_at,
            "ok": not el_problems,
            "problems": el_problems,
        })
        problems.extend(f"element '{el.name}': {p}" for p in el_problems)

    return {
        "protocol_path": protocol_path,
        "base_dir": base_dir,
        "task": proto.task,
        "ok": not problems,
        "problems": problems,
        "elements": element_reports,
        "summary": {
            "elements": len(proto.elements),
            "elements_ok": sum(e["ok"] for e in element_reports),
            "artifacts": len(proto.artifacts),
        },
    }


def print_human(report: dict) -> None:
    print(f"protocol-check  ({report['protocol_path']})")
    print(f"  task: {report['task']}   base: {report['base_dir']}")
    print("-" * 64)
    for el in report["elements"]:
        mark = "ok  " if el["ok"] else "FAIL"
        where = f"{el['file']}:{el['located_at']}" if el["located_at"] else el["file"]
        print(f"  [{mark}] {el['name']}  ({el['nature'] or 'no-nature'}  {where})")
        for p in el["problems"]:
            print(f"         {p}")
    structural = [p for p in report["problems"] if not p.startswith("element ")]
    for p in structural:
        print(f"  STRUCTURAL  {p}")
    s = report["summary"]
    print("-" * 64)
    print(f"  {s['elements_ok']}/{s['elements']} elements valid, "
          f"{s['artifacts']} artifact(s) declared")
    print(f"  RESULT: {'OK' if report['ok'] else 'INVALID'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a protocol data-lineage spec.")
    ap.add_argument("protocol_path", help="path to a *-protocol.md file")
    ap.add_argument("--base", default=os.getcwd(),
                    help="dir that element file paths resolve against (default: cwd)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args(argv)

    try:
        report = check_protocol(args.protocol_path, os.path.abspath(args.base))
    except PinError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"protocol-check: ERROR  {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
