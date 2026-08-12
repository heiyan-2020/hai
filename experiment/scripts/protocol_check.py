#!/usr/bin/env python3
"""Validate Protocol structure and data-lineage anchors."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re

from protocol_lib import VALID_NATURES, ValidationError, load_protocol, locate_snippet

MAX_SNIPPET_LINES = 5
_ENV_READ_RE = re.compile(r"\bos\.(?:getenv|environ)\b")
_PLACEHOLDER_RE = re.compile(r"<[^>]*>")


def _environment_reads(path: str) -> list[str]:
    if not path.endswith(".py") or not os.path.isfile(path):
        return []
    hits = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if _ENV_READ_RE.search(line):
                hits.append(f"line {number}: {line.strip()}")
    return hits


def _lineage_path(reference: str, protocol_path: str, protocol_root: str) -> str | None:
    if os.path.isabs(reference):
        return None
    path = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(protocol_path)), reference))
    try:
        return path if os.path.commonpath((protocol_root, path)) == protocol_root else None
    except ValueError:
        return None


def _normal_pattern(path: str) -> str:
    return re.sub(r"/+", "/", _PLACEHOLDER_RE.sub("*", path)).rstrip("/")


def _paths_agree(parent: str, children: list[str]) -> tuple[bool, str | None]:
    parent_normal = _normal_pattern(parent)
    parent_name = os.path.basename(parent_normal)
    for child in children:
        child_normal = _normal_pattern(child)
        child_name = os.path.basename(child_normal)
        if fnmatch.fnmatch(child_name, parent_name) or fnmatch.fnmatch(parent_name, child_name):
            return True, child
        if "." not in parent_name and "*" not in parent_name and parent_name in child_normal.split("/"):
            return True, child
        if "." not in child_name and "*" not in child_name and child_name in parent_normal.split("/"):
            return True, child
    return False, None


def check_protocol(
    protocol_path: str,
    base_dir: str,
    stack: list[str] | None = None,
    cache: dict[str, dict] | None = None,
    protocol_root: str | None = None,
) -> dict:
    stack = stack or []
    cache = cache if cache is not None else {}
    protocol_abs = os.path.abspath(protocol_path)
    protocol_root = protocol_root or os.path.realpath(os.path.dirname(protocol_abs))
    protocol = load_protocol(protocol_path)
    problems: list[str] = []

    if not protocol.task:
        problems.append("frontmatter: task is missing")
    if not protocol.script:
        problems.append("frontmatter: script is missing")
    else:
        script_path = os.path.realpath(os.path.join(base_dir, protocol.script))
        try:
            script_inside = (not os.path.isabs(protocol.script)
                             and os.path.commonpath((os.path.realpath(base_dir), script_path))
                             == os.path.realpath(base_dir))
        except ValueError:
            script_inside = False
        if not script_inside:
            problems.append(f"frontmatter: script escapes project root: {protocol.script}")
        elif not os.path.isfile(script_path):
            problems.append(f"frontmatter: script not found: {protocol.script}")
        for hit in _environment_reads(script_path) if script_inside else []:
            problems.append(f"script reads environment configuration ({hit}); expose it as an argument")
    if not isinstance(protocol.parameters, list) or not protocol.parameters:
        problems.append("frontmatter: parameters must be a non-empty list")
    else:
        for index, parameter in enumerate(protocol.parameters):
            if not isinstance(parameter, dict) or not str(parameter.get("name", "")).strip():
                problems.append(f"frontmatter: parameters[{index}] has no name")
    if not isinstance(protocol.fixed, list):
        problems.append("frontmatter: fixed must be a list")

    bearing_nodes = [node for node in protocol.run_root_shape if node.bears_conclusions]
    if not protocol.run_root_shape:
        problems.append("body: Run root shape is missing or empty")
    elif not bearing_nodes:
        problems.append("body: at least one path must bear conclusions")
    allowed_markers = {
        frozenset({"shape-only"}),
        frozenset({"bears conclusions"}),
        frozenset({"bears conclusions", "delegated"}),
    }
    shape_paths = [node.path for node in protocol.run_root_shape]
    if len(set(shape_paths)) != len(shape_paths):
        problems.append("body: Run root shape contains duplicate paths")
    for node in protocol.run_root_shape:
        if node.marker_count != 1 or node.tags not in allowed_markers:
            problems.append(f"shape path {node.path!r} has an invalid marker")

    artifact_paths = [artifact.path for artifact in protocol.artifacts]
    if len(set(artifact_paths)) != len(artifact_paths):
        problems.append("body: duplicate Artifact sections")
    artifact_by_path = {artifact.path: artifact for artifact in protocol.artifacts}
    bearing_paths = {node.path for node in bearing_nodes}
    for artifact in protocol.artifacts:
        if artifact.path not in bearing_paths:
            problems.append(f"artifact {artifact.path!r} is not marked [bears conclusions]")
    for node in bearing_nodes:
        artifact = artifact_by_path.get(node.path)
        if not artifact:
            problems.append(f"shape path {node.path!r} has no Artifact section")
            continue
        if node.delegated != bool(artifact.lineage_protocol):
            problems.append(f"artifact {node.path!r}: delegated marker and lineage_protocol disagree")

    field_reports: list[dict] = []
    delegations: list[tuple[str, str]] = []
    for artifact in protocol.artifacts:
        if artifact.lineage_protocol:
            delegations.append((artifact.path, artifact.lineage_protocol))
            if artifact.fields or artifact.field_blocks:
                problems.append(f"artifact {artifact.path!r}: delegated artifacts cannot define fields")
            continue
        for item in artifact.fields:
            if item["important"] is None:
                problems.append(f"artifact {artifact.path!r}: field {item['name']!r} needs an importance tag")
        important = [item["name"] for item in artifact.fields if item["important"]]
        block_names = [block.name for block in artifact.field_blocks]
        if not important:
            problems.append(f"artifact {artifact.path!r}: no important field")
        for name in important:
            if block_names.count(name) != 1:
                problems.append(f"artifact {artifact.path!r}: important field {name!r} needs exactly one Field block")
        for name in block_names:
            if name not in important:
                problems.append(f"artifact {artifact.path!r}: Field block {name!r} is not an important field")
        for lineage in artifact.field_blocks:
            field_problems: list[str] = []
            located_at = None
            if lineage.nature not in VALID_NATURES:
                field_problems.append(f"invalid nature {lineage.nature!r}")
            if not lineage.source_field:
                field_problems.append("missing source_field")
            if not lineage.file:
                field_problems.append("missing file")
            lines = [line for line in lineage.snippet.splitlines() if line.strip()]
            if not lines:
                field_problems.append("missing code snippet")
            elif len(lines) > MAX_SNIPPET_LINES:
                field_problems.append(f"snippet exceeds {MAX_SNIPPET_LINES} lines")
            if lineage.file and lines:
                ok, detail, located_at = locate_snippet(lineage.snippet, lineage.file, base_dir)
                if not ok:
                    field_problems.append(detail)
            if lineage.nature == "DERIVED" and not lineage.formula:
                field_problems.append("DERIVED field needs formula")
            field_reports.append({
                "artifact": artifact.path,
                "name": lineage.name,
                "nature": lineage.nature,
                "file": lineage.file,
                "located_at": located_at,
                "ok": not field_problems,
                "problems": field_problems,
            })
            problems.extend(f"field {artifact.path}#{lineage.name}: {item}" for item in field_problems)

    lineage_reports: list[dict] = []
    for artifact_path, reference in delegations:
        child_path = _lineage_path(reference, protocol_path, protocol_root)
        if child_path is None:
            problems.append(f"artifact {artifact_path!r}: child Protocol escapes Protocol root")
            continue
        if child_path == protocol_abs or child_path in stack:
            problems.append(f"artifact {artifact_path!r}: lineage reference cycle")
            continue
        if not os.path.isfile(child_path):
            problems.append(f"artifact {artifact_path!r}: child Protocol not found: {reference}")
            continue
        try:
            child_report = cache.get(child_path)
            if child_report is None:
                child_report = check_protocol(
                    child_path, base_dir, stack + [protocol_abs], cache, protocol_root
                )
                cache[child_path] = child_report
        except ValidationError as exc:
            problems.append(f"artifact {artifact_path!r}: child Protocol invalid: {exc}")
            continue
        agrees, matched = _paths_agree(artifact_path, child_report["artifact_paths"])
        lineage_reports.append({
            "artifact": artifact_path,
            "reference": reference,
            "matched_artifact": matched,
            "agrees": agrees,
            "report": child_report,
        })
        if not child_report["ok"]:
            problems.append(f"artifact {artifact_path!r}: child Protocol has errors")
        if not agrees:
            problems.append(f"artifact {artifact_path!r}: child Protocol describes another artifact")

    return {
        "protocol_path": protocol_path,
        "base_dir": base_dir,
        "task": protocol.task,
        "ok": not problems,
        "problems": problems,
        "fields": field_reports,
        "artifact_paths": artifact_paths,
        "lineage": lineage_reports,
        "summary": {
            "artifacts": len(protocol.artifacts),
            "bearing": len(bearing_nodes),
            "fields": len(field_reports),
            "fields_ok": sum(field["ok"] for field in field_reports),
            "delegated": len(delegations),
        },
    }


def print_report(report: dict, indent: int = 0) -> None:
    pad = "  " * indent
    if not indent:
        print(f"protocol-check ({report['protocol_path']})")
    else:
        print(f"{pad}delegated {report['protocol_path']}")
    for field in report["fields"]:
        marker = "ok" if field["ok"] else "FAIL"
        print(f"{pad}  [{marker}] {field['artifact']}#{field['name']}")
        for problem in field["problems"]:
            print(f"{pad}         {problem}")
    for child in report["lineage"]:
        print_report(child["report"], indent + 1)
    for problem in report["problems"]:
        if not problem.startswith("field "):
            print(f"{pad}  PROBLEM {problem}")
    print(f"{pad}RESULT: {'OK' if report['ok'] else 'INVALID'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a data-lineage Protocol")
    parser.add_argument("protocol_path")
    parser.add_argument("--base", default=os.getcwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = check_protocol(args.protocol_path, os.path.abspath(args.base))
    except ValidationError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"protocol-check: ERROR {exc}")
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
