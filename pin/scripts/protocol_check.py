#!/usr/bin/env python3
"""protocol_check.py — validate a *-protocol.md data-lineage spec.

A protocol is valid when every conclusion-bearing component of its artifact is
accounted for: each `## Element` names its `file`, carries a short verbatim code
`snippet` that still appears in that file, and is tagged with a nature; and each
artifact that is itself a rich artifact (a figure, a sub-pipeline) either gives
that lineage inline as elements or *delegates* it to a child protocol via
`lineage_protocol:`. This is the machine layer; pin-codex-audit then checks that
the lineage descriptions are actually *true*.

Usage:
    protocol_check.py <protocol.md> [--base DIR] [--json]

--base is the directory that element `file` paths and the entry `script`
resolve against; defaults to the current working directory. A `lineage_protocol`
reference resolves relative to the *referencing* protocol's own directory, so a
graph of protocols stays self-contained and movable.

Exit code 0 iff the protocol — and every protocol it delegates to — is
structurally valid and every snippet locates.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pinlib import VALID_NATURE, PinError, load_protocol, locate_snippet  # noqa: E402

# A lineage snippet must be the *core* lines, not a whole function dump.
MAX_SNIPPET_LINES = 5

# The entry script must be configured by its arguments alone — reading config
# from the environment breaks the "script <args> fully determines the run"
# contract. This is a shallow scan of the entry .py file, not its imports.
_ENV_READ_RE = re.compile(r"\bos\.(?:getenv|environ)\b")

# A `<...>` token in an artifact path is a per-run placeholder (run id, case id).
_PLACEHOLDER_RE = re.compile(r"<[^>]*>")


def _script_env_reads(script_abs: str) -> list[str]:
    """Lines in a .py entry script that read configuration from the environment."""
    if not script_abs.endswith(".py") or not os.path.isfile(script_abs):
        return []
    hits: list[str] = []
    with open(script_abs, "r", encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if _ENV_READ_RE.search(line):
                hits.append(f"line {n}: {line.strip()}")
    return hits


def _resolve_lineage_path(ref: str, parent_protocol_path: str) -> str:
    """A `lineage_protocol` reference resolves relative to the referrer's dir."""
    if os.path.isabs(ref):
        return os.path.normpath(ref)
    parent_dir = os.path.dirname(os.path.abspath(parent_protocol_path))
    return os.path.normpath(os.path.join(parent_dir, ref))


def _norm_pattern(path: str) -> str:
    """Normalise an artifact path for comparison: placeholders -> '*'."""
    p = _PLACEHOLDER_RE.sub("*", str(path))
    p = re.sub(r"/+", "/", p).rstrip("/")
    return p


def _paths_agree(parent_path: str, child_paths: list[str]) -> tuple[bool, str | None]:
    """Does the parent's delegated artifact match something the child produces?

    A *consistency* check, not byte-equality (that is the human/Codex job). With
    `<...>` placeholders treated as wildcards, the parent artifact agrees with a
    child artifact when their basenames are fnmatch-compatible in either
    direction; for a directory artifact (a basename with no extension), it also
    agrees when that name appears as a literal path component of the other.
    """
    p_norm = _norm_pattern(parent_path)
    p_base = os.path.basename(p_norm)
    for cp in child_paths:
        c_norm = _norm_pattern(cp)
        c_base = os.path.basename(c_norm)
        if fnmatch.fnmatch(c_base, p_base) or fnmatch.fnmatch(p_base, c_base):
            return True, cp
        if "." not in p_base and "*" not in p_base and p_base in c_norm.split("/"):
            return True, cp
        if "." not in c_base and "*" not in c_base and c_base in p_norm.split("/"):
            return True, cp
    return False, None


def check_protocol(
    protocol_path: str,
    base_dir: str,
    _stack: list[str] | None = None,
    _cache: dict[str, dict] | None = None,
) -> dict:
    """Validate one protocol, recursing into any `lineage_protocol` children.

    `_stack` is the chain of protocol files currently being checked (cycle
    detection); `_cache` memoises child reports so a shared child protocol
    (e.g. a reusable figure protocol referenced by many experiments) is checked
    once per run.
    """
    _stack = _stack or []
    _cache = _cache if _cache is not None else {}
    proto_abs = os.path.abspath(protocol_path)

    proto = load_protocol(protocol_path)
    problems: list[str] = []

    if not proto.task:
        problems.append("frontmatter: 'task' is missing or empty")

    # The contract: one entry-point script, configured by arguments alone.
    if not proto.script.strip():
        problems.append(
            "frontmatter: 'script' is missing — a protocol needs one entry-point "
            "script that produces the artifact")
    else:
        script_abs = os.path.join(base_dir, proto.script)
        if not os.path.isfile(script_abs):
            problems.append(f"frontmatter: script not found on disk: {proto.script}")
        else:
            for hit in _script_env_reads(script_abs):
                problems.append(
                    f"script reads the environment ({hit}) — expose it as a "
                    "parameter; the run must be determined by its arguments alone")

    if not isinstance(proto.parameters, list) or not proto.parameters:
        problems.append(
            "frontmatter: 'parameters' must be a non-empty list — every "
            "configurable option the script exposes")
    else:
        for i, par in enumerate(proto.parameters):
            if not isinstance(par, dict) or not str(par.get("name", "")).strip():
                problems.append(f"frontmatter: parameters[{i}] has no 'name'")

    artifact_paths: list[str] = []
    delegations: list[tuple[int, str, str]] = []  # (index, ref, parent_artifact_path)
    for i, art in enumerate(proto.artifacts):
        if not isinstance(art, dict):
            problems.append(f"frontmatter: artifacts[{i}] is not a mapping")
            continue
        path = str(art.get("path", "")).strip()
        if not path:
            problems.append(f"frontmatter: artifacts[{i}] has no 'path'")
        else:
            artifact_paths.append(path)
        ref = str(art.get("lineage_protocol", "") or "").strip()
        if ref:
            delegations.append((i, ref, path))

    # A protocol earns its keep with at least one own element OR at least one
    # delegated artifact — a pure-composition protocol (all rich artifacts
    # delegated) is valid even with no number elements of its own.
    if not proto.elements and not delegations:
        problems.append(
            "body: no `## Element:` lineage blocks and no delegated artifacts — "
            "nothing in this protocol is verifiable")

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

    # Recurse into delegated child protocols.
    lineage_reports = []
    for i, ref, parent_art_path in delegations:
        child_abs = _resolve_lineage_path(ref, protocol_path)

        if child_abs == proto_abs or child_abs in _stack:
            chain = " -> ".join(
                os.path.basename(p) for p in (_stack + [proto_abs, child_abs])
            )
            problems.append(
                f"artifacts[{i}] lineage_protocol '{ref}': reference cycle ({chain})")
            continue
        if not os.path.isfile(child_abs):
            problems.append(
                f"artifacts[{i}] lineage_protocol '{ref}': child protocol not "
                f"found ({child_abs})")
            continue

        if child_abs in _cache:
            child_report = _cache[child_abs]
        else:
            try:
                child_report = check_protocol(
                    child_abs, base_dir, _stack + [proto_abs], _cache)
            except PinError as exc:
                problems.append(
                    f"artifacts[{i}] lineage_protocol '{ref}': {exc}")
                continue
            _cache[child_abs] = child_report

        agree, matched = _paths_agree(parent_art_path, child_report["artifact_paths"])
        lineage_reports.append({
            "artifact_index": i,
            "ref": ref,
            "child_path": child_abs,
            "agree": agree,
            "matched_artifact": matched,
            "report": child_report,
        })
        if not child_report["ok"]:
            problems.append(
                f"artifacts[{i}] lineage_protocol '{ref}': child protocol is "
                f"INVALID ({len(child_report['problems'])} problem(s) — see below)")
        if not agree:
            problems.append(
                f"artifacts[{i}] '{parent_art_path}' matches no artifact declared "
                f"by child protocol '{ref}' — the child should declare the artifact "
                "it explains, so the delegation points at the right thing")

    return {
        "protocol_path": protocol_path,
        "base_dir": base_dir,
        "task": proto.task,
        "ok": not problems,
        "problems": problems,
        "elements": element_reports,
        "artifact_paths": artifact_paths,
        "lineage": lineage_reports,
        "summary": {
            "elements": len(proto.elements),
            "elements_ok": sum(e["ok"] for e in element_reports),
            "artifacts": len(proto.artifacts),
            "delegated": len(delegations),
        },
    }


def print_human(report: dict, indent: int = 0) -> None:
    pad = "  " * indent
    if indent == 0:
        print(f"protocol-check  ({report['protocol_path']})")
        print(f"  task: {report['task']}   base: {report['base_dir']}")
        print("-" * 64)
    else:
        print(f"{pad}└─ delegated: {report['task']}  ({report['protocol_path']})")

    for el in report["elements"]:
        mark = "ok  " if el["ok"] else "FAIL"
        where = f"{el['file']}:{el['located_at']}" if el["located_at"] else el["file"]
        print(f"{pad}  [{mark}] {el['name']}  ({el['nature'] or 'no-nature'}  {where})")
        for p in el["problems"]:
            print(f"{pad}         {p}")

    for ln in report.get("lineage", []):
        amark = "ok" if ln["agree"] else "PATH-MISMATCH"
        print(f"{pad}  → lineage_protocol '{ln['ref']}'  [{amark}]")
        print_human(ln["report"], indent + 2)

    # Element problems already print under each element; everything else —
    # structural frontmatter problems and artifact/delegation problems (dangling
    # reference, cycle, path mismatch, invalid child) — must stay visible.
    for p in report["problems"]:
        if p.startswith("element "):
            continue
        print(f"{pad}  PROBLEM  {p}")

    if indent == 0:
        s = report["summary"]
        print("-" * 64)
        print(f"  {s['elements_ok']}/{s['elements']} elements valid, "
              f"{s['artifacts']} artifact(s) declared, "
              f"{s['delegated']} delegated")
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
