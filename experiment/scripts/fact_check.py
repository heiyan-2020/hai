#!/usr/bin/env python3
"""Validate internal Facts that materialize Protocol runs."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
from dataclasses import dataclass
from typing import Any

import yaml

from protocol_lib import ValidationError, load_protocol
from protocol_check import check_protocol

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_ID_RE = re.compile(r"^if-\d{3,}$")
_CAUSAL_RE = re.compile(r"\b(because|due to|caused by|causes?|therefore|explains?)\b", re.IGNORECASE)
_REQUIRED_SECTIONS = ["Bottom line", "Key evidence", "Scope & limits", "Lineage", "Reproduction"]


@dataclass
class Fact:
    path: str
    meta: dict[str, Any]
    body: str
    sections: dict[str, str]

    @property
    def id(self) -> str:
        return str(self.meta.get("id", "") or "")


def load_fact(path: str) -> Fact:
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValidationError(f"{path}: missing YAML frontmatter")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValidationError(f"{path}: invalid YAML frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValidationError(f"{path}: frontmatter must be a mapping")
    body = text[match.end():]
    headers = list(_H2_RE.finditer(body))
    sections = {}
    for index, header in enumerate(headers):
        start = header.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(body)
        sections[header.group(1).strip()] = body[start:end].strip()
    return Fact(path, meta, body, sections)


def _resolve_inside(path: str, research_root: str, base: str | None = None) -> str | None:
    if os.path.isabs(path):
        return None
    root = os.path.realpath(research_root)
    resolved = os.path.realpath(os.path.join(base or root, path))
    try:
        return resolved if os.path.commonpath((root, resolved)) == root else None
    except ValueError:
        return None


def _command_invokes_script(command: str, script: str) -> bool:
    if "\n" in command or "`" in command:
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return False
    if not tokens or any(token and set(token) <= set("();&|<>") for token in tokens):
        return False
    target = os.path.normpath(script).lstrip("./")
    matches = [index for index, token in enumerate(tokens)
               if os.path.normpath(token).lstrip("./") == target]
    if not matches:
        return False
    safe_options = {
        "python": {"-B", "-E", "-I", "-O", "-OO", "-P", "-S", "-s", "-u", "-x"},
        "python3": {"-B", "-E", "-I", "-O", "-OO", "-P", "-S", "-s", "-u", "-x"},
        "bash": set(), "sh": set(), "node": set(), "ruby": set(), "perl": set(),
        "rscript": set(),
    }
    return any(index == 0 or (
        os.path.basename(tokens[0]).lower() in safe_options
        and all(token in safe_options[os.path.basename(tokens[0]).lower()]
                for token in tokens[1:index])
    )
               for index in matches)


def _is_inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath((os.path.realpath(root), os.path.realpath(path))) == os.path.realpath(root)
    except ValueError:
        return False


def _path_references(fact: Fact, research_root: str) -> list[str]:
    problems = []
    for section_name in ("Key evidence", "Lineage"):
        text = _FENCE_RE.sub("", fact.sections.get(section_name, ""))
        for token in set(_BACKTICK_RE.findall(text)):
            token = token.strip()
            if "/" not in token or token.startswith(("http://", "https://")):
                continue
            if any(character in token for character in "<>{}*…"):
                continue
            resolved = _resolve_inside(token, research_root)
            if resolved is None:
                problems.append(f"path in {section_name} escapes research root: {token}")
            elif not os.path.exists(resolved):
                problems.append(f"path in {section_name} does not exist: {token}")
    for target in _IMAGE_RE.findall(fact.body):
        target = target.split()[0].strip()
        if target.startswith(("http://", "https://")):
            continue
        resolved = _resolve_inside(target, research_root, os.path.dirname(fact.path))
        if resolved is None:
            problems.append(f"image escapes research root: {target}")
        elif not os.path.exists(resolved):
            problems.append(f"image does not exist: {target}")
    return problems


def validate_fact(fact: Fact, facts_root: str, research_root: str) -> list[str]:
    meta = fact.meta
    problems: list[str] = []
    if not _ID_RE.match(fact.id):
        problems.append("id must match if-NNN")
    if not os.path.basename(fact.path).startswith(fact.id + "-"):
        problems.append("filename must start with '<id>-' ")
    if os.path.basename(os.path.dirname(fact.path)) != "internal":
        problems.append("Fact must live under facts/internal/")
    expected_facts_root = os.path.join(research_root, "facts", "internal")
    if os.path.dirname(os.path.realpath(fact.path)) != os.path.realpath(expected_facts_root):
        problems.append("Fact must live directly under <research-root>/facts/internal/")
    if meta.get("type") != "internal":
        problems.append("type must be internal")
    for key in ("id", "type", "status", "created_at", "question", "claim", "tldr"):
        if not meta.get(key):
            problems.append(f"frontmatter missing {key}")

    claim = str(meta.get("claim", "") or "")
    if "\n" in claim or _CAUSAL_RE.search(claim):
        problems.append("claim must be one observational sentence without causal language")
    metric = meta.get("metric")
    if not isinstance(metric, dict):
        problems.append("metric must be a mapping")
        metric = {}
    for key in ("name", "value", "unit"):
        if key not in metric or metric.get(key) in (None, ""):
            problems.append(f"metric missing {key}")

    if list(fact.sections) != _REQUIRED_SECTIONS:
        problems.append(f"sections must be exactly {_REQUIRED_SECTIONS}")
    for section in _REQUIRED_SECTIONS:
        if not fact.sections.get(section, "").strip():
            problems.append(f"section is empty: {section}")
    bottom = fact.sections.get("Bottom line", "")
    if meta.get("tldr") and f"- Answer: {meta['tldr']}" not in bottom:
        problems.append("Bottom line must echo tldr as '- Answer:'")
    if claim and f"- Claim: {claim}" not in bottom:
        problems.append("Bottom line must echo claim as '- Claim:'")
    if metric.get("name") and f"- Metric: {metric['name']}" not in bottom:
        problems.append("Bottom line must include the metric name")
    if not any(line.strip().startswith("- ") for line in fact.sections.get("Scope & limits", "").splitlines()):
        problems.append("Scope & limits needs at least one bullet")

    data = meta.get("data")
    if not isinstance(data, dict):
        problems.append("data must be a mapping")
        data = {}
    primary = data.get("primary_path")
    expected_data_root = os.path.join(research_root, "data", fact.id)
    if not primary:
        problems.append("data.primary_path is required")
    else:
        resolved = _resolve_inside(str(primary), research_root)
        if resolved is None:
            problems.append(f"data.primary_path escapes research root: {primary}")
        elif not _is_inside(resolved, expected_data_root):
            problems.append(f"data.primary_path must live under data/{fact.id}/: {primary}")
        elif not os.path.exists(resolved):
            problems.append(f"data.primary_path does not exist: {primary}")
    supporting = data.get("supporting_paths", [])
    if not isinstance(supporting, list):
        problems.append("data.supporting_paths must be a list")
    else:
        for path in supporting:
            resolved = _resolve_inside(str(path), research_root)
            if resolved is None:
                problems.append(f"supporting data escapes research root: {path}")
            elif not _is_inside(resolved, expected_data_root):
                problems.append(f"supporting data must live under data/{fact.id}/: {path}")
            elif not os.path.exists(resolved):
                problems.append(f"supporting data does not exist: {path}")

    protocol_meta = meta.get("protocol")
    protocol = None
    if not isinstance(protocol_meta, dict):
        problems.append("protocol must be a mapping")
        protocol_meta = {}
    protocol_path = protocol_meta.get("path")
    field_refs = protocol_meta.get("fields")
    if not protocol_path:
        problems.append("protocol.path is required")
    else:
        full_protocol_path = _resolve_inside(str(protocol_path), research_root)
        if full_protocol_path is None:
            problems.append(f"protocol.path escapes research root: {protocol_path}")
        else:
            try:
                protocol = load_protocol(full_protocol_path)
            except ValidationError as exc:
                problems.append(f"protocol.path invalid: {exc}")
            else:
                protocol_report = check_protocol(
                    full_protocol_path, os.path.dirname(research_root)
                )
                if not protocol_report["ok"]:
                    problems.append("protocol.path failed Protocol validation")
    if not isinstance(field_refs, list) or not field_refs:
        problems.append("protocol.fields must be a non-empty list")
    elif protocol:
        known = {(artifact.path, block.name)
                 for artifact in protocol.artifacts for block in artifact.field_blocks}
        for reference in field_refs:
            if not isinstance(reference, dict):
                problems.append("protocol.fields entries must contain artifact and field")
                continue
            key = (reference.get("artifact"), reference.get("field"))
            if key not in known:
                problems.append(f"Protocol field not found: {key[0]}#{key[1]}")

    repro = meta.get("repro")
    if not isinstance(repro, dict):
        problems.append("repro must be a mapping")
        repro = {}
    for key in ("command", "commit", "branch", "environment", "hardware"):
        if not repro.get(key):
            problems.append(f"repro missing {key}")
    if protocol and repro.get("command") and not _command_invokes_script(str(repro["command"]), protocol.script):
        problems.append("repro.command must invoke the Protocol script")
    reproduction = fact.sections.get("Reproduction", "")
    if not _FENCE_RE.search(reproduction):
        problems.append("Reproduction needs a fenced metric recomputation command")
    reproduction_prose = _FENCE_RE.sub("", reproduction)
    if not re.search(r"(?m)^\s*Verified:\s*\S", reproduction_prose):
        problems.append("Reproduction must record the recomputation result as 'Verified:'")

    problems.extend(_path_references(fact, research_root))
    return problems


def validate_facts(facts_path: str, research_root: str | None = None) -> dict:
    facts_path = os.path.abspath(facts_path)
    facts_root = os.path.dirname(os.path.dirname(facts_path)) if os.path.isfile(facts_path) else facts_path
    research_root = os.path.abspath(research_root or os.path.dirname(facts_root))
    internal_root = os.path.join(facts_root, "internal")
    facts: list[Fact] = []
    if os.path.isfile(facts_path):
        facts.append(load_fact(facts_path))
    elif os.path.isdir(internal_root):
        for name in sorted(os.listdir(internal_root)):
            if name.endswith(".md"):
                facts.append(load_fact(os.path.join(internal_root, name)))
    ids = [fact.id for fact in facts]
    duplicate_ids = {fact_id for fact_id in ids if fact_id and ids.count(fact_id) > 1}
    reports = []
    for fact in facts:
        problems = validate_fact(fact, facts_root, research_root)
        if fact.id in duplicate_ids:
            problems.append(f"duplicate Fact id: {fact.id}")
        reports.append({"id": fact.id, "path": fact.path, "ok": not problems, "problems": problems})
    return {
        "facts_root": facts_root,
        "research_root": research_root,
        "ok": bool(reports) and all(report["ok"] for report in reports),
        "facts": reports,
        "summary": {"total": len(reports), "ok": sum(report["ok"] for report in reports)},
    }


def print_report(report: dict) -> None:
    print(f"fact-check ({report['facts_root']})")
    for fact in report["facts"]:
        marker = "ok" if fact["ok"] else "FAIL"
        print(f"  [{marker}] {fact['id'] or '(no id)'}")
        for problem in fact["problems"]:
            print(f"         {problem}")
    print(f"RESULT: {'OK' if report['ok'] else 'INVALID'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate internal experiment Facts")
    parser.add_argument("facts_path", help="one Fact file, or a facts directory")
    parser.add_argument("--research-root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = validate_facts(args.facts_path, args.research_root)
    except ValidationError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"fact-check: ERROR {exc}")
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
