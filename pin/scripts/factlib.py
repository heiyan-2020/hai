"""Structured markdown facts for the pin plugin.

Facts are markdown files with yaml frontmatter and fixed body sections. The
frontmatter is the machine interface; the body is a constrained evidence card
for humans, not free-form prose.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from pinlib import PinError, load_protocol

VALID_FACT_TYPES = {"internal", "external", "derived"}
TYPE_PREFIX = {"internal": "if-", "external": "ef-", "derived": "df-"}
# Body sections are ordered for progressive disclosure: the conclusion first
# (Bottom line), then the proof and its boundary (Key evidence, Scope & limits),
# then the audit trail (Lineage, Reproduction). A reader can stop at any heading
# once convinced. The frontmatter remains the machine source of truth.
REQUIRED_SECTIONS = {
    "internal": [
        "Bottom line",
        "Key evidence",
        "Scope & limits",
        "Lineage",
        "Reproduction",
    ],
    "external": [
        "Bottom line",
        "Source quote",
        "Scope & limits",
    ],
    "derived": [
        "Bottom line",
        "Inputs",
        "Derivation",
        "Scope & limits",
    ],
}
CAUSAL_RE = re.compile(
    r"\b(because|due to|caused by|causes?|therefore|explains?|suggests that)\b",
    re.IGNORECASE,
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
# Sections whose backtick-quoted, repo-relative paths must resolve on disk.
_PATH_CHECKED_SECTIONS = ("Key evidence", "Lineage")
_PLACEHOLDER_CHARS = set("<>{}*…")


@dataclass
class Fact:
    path: str
    meta: dict[str, Any]
    body: str
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return str(self.meta.get("id", "") or "")

    @property
    def type(self) -> str:
        return str(self.meta.get("type", "") or "")

    @property
    def claim(self) -> str:
        return str(self.meta.get("claim", "") or "")


def load_fact(path: str) -> Fact:
    """Parse a structured markdown fact file."""
    if not os.path.isfile(path):
        raise PinError(f"fact file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    fm_match = _FRONTMATTER_RE.match(text)
    if not fm_match:
        raise PinError(f"{path}: missing yaml frontmatter (--- ... ---)")
    try:
        meta = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise PinError(f"{path}: frontmatter is not valid yaml: {exc}") from exc
    if not isinstance(meta, dict):
        raise PinError(f"{path}: frontmatter must be a mapping")
    body = text[fm_match.end():]
    return Fact(path=path, meta=meta, body=body, sections=_parse_sections(body))


def discover_facts(facts_root: str) -> list[Fact]:
    """Load all markdown facts under internal/, external/, and derived/."""
    facts: list[Fact] = []
    for fact_type in sorted(VALID_FACT_TYPES):
        root = os.path.join(facts_root, fact_type)
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in sorted(filenames):
                if name.endswith(".md"):
                    facts.append(load_fact(os.path.join(dirpath, name)))
    return facts


def validate_facts(facts_root: str, research_root: str | None = None) -> dict:
    """Validate a facts directory and return a report dictionary."""
    facts_root = os.path.abspath(facts_root)
    research_root = os.path.abspath(research_root or os.path.dirname(facts_root))
    facts = discover_facts(facts_root)
    problems: list[str] = []

    by_id: dict[str, Fact] = {}
    for fact in facts:
        if fact.id in by_id:
            problems.append(
                f"duplicate fact id '{fact.id}': {by_id[fact.id].path} and {fact.path}"
            )
        elif fact.id:
            by_id[fact.id] = fact

    reports = []
    for fact in facts:
        fact_problems = validate_fact(fact, facts_root, research_root, by_id)
        reports.append({
            "id": fact.id,
            "type": fact.type,
            "path": fact.path,
            "ok": not fact_problems,
            "problems": fact_problems,
        })
        problems.extend(f"{_display_path(fact.path, facts_root)}: {p}" for p in fact_problems)

    return {
        "facts_root": facts_root,
        "research_root": research_root,
        "ok": not problems,
        "problems": problems,
        "facts": reports,
        "summary": {
            "total": len(facts),
            "ok": sum(r["ok"] for r in reports),
            "internal": sum(r["type"] == "internal" for r in reports),
            "external": sum(r["type"] == "external" for r in reports),
            "derived": sum(r["type"] == "derived" for r in reports),
        },
    }


def validate_fact(
    fact: Fact,
    facts_root: str,
    research_root: str,
    facts_by_id: dict[str, Fact],
) -> list[str]:
    """Return structural and reference problems for one fact."""
    problems: list[str] = []
    meta = fact.meta

    fact_type = fact.type
    if fact_type not in VALID_FACT_TYPES:
        problems.append(f"type '{fact_type}' not in {sorted(VALID_FACT_TYPES)}")
    else:
        rel = os.path.relpath(fact.path, facts_root)
        if not rel.split(os.sep, 1)[0] == fact_type:
            problems.append(f"file for type '{fact_type}' must live under facts/{fact_type}/")
        prefix = TYPE_PREFIX[fact_type]
        if not fact.id.startswith(prefix):
            problems.append(f"id '{fact.id}' must start with '{prefix}'")

    for key in ["id", "type", "status", "created_at", "question", "claim", "tldr"]:
        if not meta.get(key):
            problems.append(f"frontmatter missing '{key}'")

    metric = meta.get("metric")
    if not isinstance(metric, dict):
        problems.append("frontmatter 'metric' must be a mapping")
    else:
        for key in ["name", "value", "unit"]:
            if key not in metric or metric.get(key) in {None, ""}:
                problems.append(f"frontmatter metric missing '{key}'")

    problems.extend(_check_sections(fact))
    problems.extend(_check_bottom_line(fact))
    problems.extend(_check_scope_limits(fact))
    problems.extend(_check_markdown_links(fact))
    problems.extend(_check_path_references(fact, research_root))

    if fact_type == "internal":
        problems.extend(_check_internal(fact, research_root))
    elif fact_type == "external":
        problems.extend(_check_external(fact))
    elif fact_type == "derived":
        problems.extend(_check_derived(fact, facts_by_id))

    return problems


def _parse_sections(body: str) -> dict[str, str]:
    headers = list(_H2_RE.finditer(body))
    sections: dict[str, str] = {}
    for i, header in enumerate(headers):
        name = header.group(1).strip()
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        sections[name] = body[start:end].strip()
    return sections


def _check_sections(fact: Fact) -> list[str]:
    problems: list[str] = []
    expected = REQUIRED_SECTIONS.get(fact.type)
    if not expected:
        return problems
    actual = list(fact.sections)
    if actual != expected:
        problems.append(
            f"sections must be exactly {expected}; found {actual}"
        )
    return problems


def _check_bottom_line(fact: Fact) -> list[str]:
    """The conclusion section. It must mirror the canonical frontmatter so the
    human-facing summary can never silently drift from the machine record:
    `- Answer:` echoes `tldr`, `- Claim:` echoes `claim`, plus the headline
    metric. Causal language stays banned — facts record what was observed."""
    problems: list[str] = []
    bl = fact.sections.get("Bottom line", "")
    tldr = str(fact.meta.get("tldr", "") or "")
    if tldr and f"- Answer: {tldr}" not in bl:
        problems.append("Bottom line must open with `- Answer: <tldr>` echoing frontmatter tldr")
    if fact.claim and f"- Claim: {fact.claim}" not in bl:
        problems.append("Bottom line must restate frontmatter claim as `- Claim: ...`")
    metric = fact.meta.get("metric") if isinstance(fact.meta.get("metric"), dict) else {}
    if metric:
        metric_text = f"- Metric: {metric.get('name')}"
        if metric_text not in bl:
            problems.append("Bottom line must include a `- Metric:` bullet")
    if CAUSAL_RE.search(fact.claim) or CAUSAL_RE.search(bl):
        problems.append("Bottom line/claim contains causal or explanatory language")
    return problems


def _check_scope_limits(fact: Fact) -> list[str]:
    scope = fact.sections.get("Scope & limits", "")
    bullets = [ln for ln in scope.splitlines() if ln.strip().startswith("- ")]
    if not bullets:
        return ["Scope & limits must contain at least one bullet"]
    return []


def _check_markdown_links(fact: Fact) -> list[str]:
    problems: list[str] = []
    for raw in _MD_IMAGE_RE.findall(fact.body):
        target = raw.split()[0].strip()
        if _is_url(target):
            continue
        full = os.path.normpath(os.path.join(os.path.dirname(fact.path), target))
        if not os.path.exists(full):
            problems.append(f"markdown image path does not exist: {target}")
    return problems


def _check_path_references(fact: Fact, research_root: str) -> list[str]:
    """Every concrete repo path the proof cites must resolve on disk — that is
    what makes the fact reproducible rather than merely plausible. We scan the
    evidence and lineage sections (not whole-body, to avoid commands), skip
    fenced code blocks, URLs, and placeholder tokens like `<out>/...`. A path is
    a backtick token containing a `/`; bare values such as `629` are ignored."""
    problems: list[str] = []
    seen: set[str] = set()
    for section in _PATH_CHECKED_SECTIONS:
        text = _FENCE_RE.sub("", fact.sections.get(section, ""))
        for token in _BACKTICK_RE.findall(text):
            target = token.strip()
            if "/" not in target or _is_url(target):
                continue
            if any(ch in target for ch in _PLACEHOLDER_CHARS):
                continue
            if target in seen:
                continue
            seen.add(target)
            if not os.path.exists(_resolve_research_path(target, research_root)):
                problems.append(f"path referenced in {section} does not exist: {target}")
    return problems


def _check_internal(fact: Fact, research_root: str) -> list[str]:
    problems: list[str] = []
    data = fact.meta.get("data")
    if not isinstance(data, dict):
        problems.append("internal fact needs frontmatter data mapping")
    else:
        primary = data.get("primary_path")
        if not primary:
            problems.append("internal fact needs data.primary_path")
        else:
            _check_path_exists(problems, "data.primary_path", str(primary), research_root)
        for path in data.get("supporting_paths", []) or []:
            _check_path_exists(problems, "data.supporting_paths", str(path), research_root)

    protocol = fact.meta.get("protocol")
    if not isinstance(protocol, dict):
        problems.append("internal fact needs frontmatter protocol mapping")
    else:
        proto_path = protocol.get("path")
        elements = protocol.get("elements")
        if not proto_path:
            problems.append("internal fact needs protocol.path")
        if not isinstance(elements, list) or not elements:
            problems.append("internal fact needs non-empty protocol.elements")
        if proto_path and isinstance(elements, list):
            full = _resolve_research_path(str(proto_path), research_root)
            if not os.path.isfile(full):
                problems.append(f"protocol.path does not exist: {proto_path}")
            else:
                try:
                    proto = load_protocol(full)
                    known = {el.name for el in proto.elements}
                    for el in elements:
                        if el not in known:
                            problems.append(
                                f"protocol element '{el}' not found in {proto_path}"
                            )
                except PinError as exc:
                    problems.append(f"protocol.path invalid: {exc}")

    repro = fact.meta.get("repro")
    if not isinstance(repro, dict):
        problems.append("internal fact needs frontmatter repro mapping")
    else:
        for key in ["command", "commit"]:
            if not repro.get(key):
                problems.append(f"internal fact needs repro.{key}")
    return problems


def _check_external(fact: Fact) -> list[str]:
    problems: list[str] = []
    source = fact.meta.get("source")
    if not isinstance(source, dict):
        return ["external fact needs frontmatter source mapping"]
    for key in ["url", "citation", "quote", "accessed_at"]:
        if not source.get(key):
            problems.append(f"external fact needs source.{key}")
    return problems


def _check_derived(fact: Fact, facts_by_id: dict[str, Fact]) -> list[str]:
    problems: list[str] = []
    derived_from = fact.meta.get("derived_from")
    if not isinstance(derived_from, list) or not derived_from:
        problems.append("derived fact needs non-empty derived_from list")
    else:
        for fact_id in derived_from:
            if fact_id not in facts_by_id:
                problems.append(f"derived_from fact not found: {fact_id}")

    derivation = fact.meta.get("derivation")
    if not isinstance(derivation, dict):
        problems.append("derived fact needs derivation mapping")
    elif not (derivation.get("formula") or derivation.get("method")):
        problems.append("derived fact needs derivation.formula or derivation.method")
    return problems


def _check_path_exists(
    problems: list[str], field: str, path: str, research_root: str
) -> None:
    if not os.path.exists(_resolve_research_path(path, research_root)):
        problems.append(f"{field} does not exist: {path}")


def _resolve_research_path(path: str, research_root: str) -> str:
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(research_root, path))


def _is_url(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")


def _display_path(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path
