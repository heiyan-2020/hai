"""Shared parsing for the pin plugin: pins.yaml and *-protocol.md.

Pure stdlib + pyyaml. No side effects on import.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

VALID_STATUS = {"active", "retired", "disabled"}
VALID_ASSERTION_TYPES = {"pytest", "command", "grep", "grep_absent", "python"}
VALID_NATURE = {"MEASURED", "DERIVED", "SYNTHETIC", "EXTERNAL"}


class PinError(Exception):
    """Raised when pins.yaml or a protocol file is structurally invalid."""


# --------------------------------------------------------------------------
# Pins
# --------------------------------------------------------------------------
@dataclass
class Pin:
    id: str
    claim: str
    branch: str
    born_at: str
    status: str
    assertion: dict[str, Any]
    code_locations: list[str] = field(default_factory=list)
    disabled_on: list[str] = field(default_factory=list)
    retire_reason: str = ""

    def is_enforced(self, branch: str) -> bool:
        """A pin is enforced unless retired, or disabled on the current branch."""
        if self.status == "retired":
            return False
        if self.status == "disabled" and branch in self.disabled_on:
            return False
        return True

    def validate(self) -> list[str]:
        """Return a list of structural problems (empty == valid)."""
        problems: list[str] = []
        if not self.id:
            problems.append("pin missing 'id'")
        if not self.claim:
            problems.append(f"pin '{self.id}': missing 'claim'")
        if self.status not in VALID_STATUS:
            problems.append(
                f"pin '{self.id}': status '{self.status}' not in {sorted(VALID_STATUS)}"
            )
        atype = self.assertion.get("type")
        if atype not in VALID_ASSERTION_TYPES:
            problems.append(
                f"pin '{self.id}': assertion.type '{atype}' not in "
                f"{sorted(VALID_ASSERTION_TYPES)}"
            )
        if atype in {"pytest", "command", "python"} and not self.assertion.get("target"):
            problems.append(f"pin '{self.id}': assertion.type '{atype}' needs 'target'")
        if atype in {"grep", "grep_absent"}:
            if not self.assertion.get("pattern"):
                problems.append(f"pin '{self.id}': assertion.type '{atype}' needs 'pattern'")
            if not self.code_locations:
                problems.append(
                    f"pin '{self.id}': assertion.type '{atype}' needs 'code_locations'"
                )
        if self.status == "retired" and not self.retire_reason:
            problems.append(f"pin '{self.id}': retired pins need 'retire_reason'")
        return problems


def load_pins(path: str) -> list[Pin]:
    """Parse a pins.yaml file into Pin objects. Raises PinError on bad structure."""
    if not os.path.isfile(path):
        raise PinError(f"pins file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    if not isinstance(doc, dict) or "pins" not in doc:
        raise PinError(f"{path}: top-level 'pins:' key missing")
    raw_pins = doc["pins"] or []
    if not isinstance(raw_pins, list):
        raise PinError(f"{path}: 'pins' must be a list")
    pins: list[Pin] = []
    for i, raw in enumerate(raw_pins):
        if not isinstance(raw, dict):
            raise PinError(f"{path}: pin #{i} is not a mapping")
        pins.append(
            Pin(
                id=raw.get("id", ""),
                claim=raw.get("claim", ""),
                branch=raw.get("branch", ""),
                born_at=str(raw.get("born_at", "")),
                status=raw.get("status", "active"),
                assertion=raw.get("assertion", {}) or {},
                code_locations=list(raw.get("code_locations", []) or []),
                disabled_on=list(raw.get("disabled_on", []) or []),
                retire_reason=raw.get("retire_reason", "") or "",
            )
        )
    ids = [p.id for p in pins]
    dupes = {x for x in ids if ids.count(x) > 1}
    if dupes:
        raise PinError(f"{path}: duplicate pin ids: {sorted(dupes)}")
    return pins


# --------------------------------------------------------------------------
# Protocols
# --------------------------------------------------------------------------
@dataclass
class LineageElement:
    name: str
    nature: str = ""
    source_field: str = ""
    file: str = ""
    snippet: str = ""
    formula: str = ""


@dataclass
class Protocol:
    task: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    side_effects: list[dict[str, Any]] = field(default_factory=list)
    elements: list[LineageElement] = field(default_factory=list)
    path: str = ""


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_ELEMENT_HEADER_RE = re.compile(r"^##\s+Element:\s*(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^-\s*([A-Za-z_]+)\s*:\s*(.*)$")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)


def load_protocol(path: str) -> Protocol:
    """Parse a *-protocol.md file: yaml frontmatter + `## Element:` lineage blocks."""
    if not os.path.isfile(path):
        raise PinError(f"protocol file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    fm_match = _FRONTMATTER_RE.match(text)
    if not fm_match:
        raise PinError(f"{path}: missing yaml frontmatter (--- ... ---)")
    try:
        fm = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise PinError(f"{path}: frontmatter is not valid yaml: {exc}") from exc
    if not isinstance(fm, dict):
        raise PinError(f"{path}: frontmatter must be a mapping")

    body = text[fm_match.end():]
    elements = _parse_elements(body)

    return Protocol(
        task=fm.get("task", ""),
        artifacts=list(fm.get("artifacts", []) or []),
        side_effects=list(fm.get("side_effects", []) or []),
        elements=elements,
        path=path,
    )


def _parse_elements(body: str) -> list[LineageElement]:
    """Split the body on `## Element:` headers.

    Within each element block, the `- key: value` bullets are read from the
    text *before* the fenced code block, and the first fenced code block is
    captured verbatim as the element's `snippet`. Parsing bullets only before
    the fence keeps a line of code that happens to look like a bullet from
    being misread.
    """
    headers = list(_ELEMENT_HEADER_RE.finditer(body))
    elements: list[LineageElement] = []
    for idx, hdr in enumerate(headers):
        name = hdr.group(1).strip()
        start = hdr.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(body)
        block = body[start:end]

        el = LineageElement(name=name)
        fence = _FENCE_RE.search(block)
        if fence:
            el.snippet = fence.group(1)
            bullet_region = block[:fence.start()]
        else:
            bullet_region = block

        for line in bullet_region.splitlines():
            m = _BULLET_RE.match(line.strip())
            if not m:
                continue
            key, val = m.group(1).lower(), m.group(2).strip()
            if key in {"nature", "source_field", "file", "formula"}:
                setattr(el, key, val)
        elements.append(el)
    return elements


# --------------------------------------------------------------------------
# Snippet location
# --------------------------------------------------------------------------
def locate_snippet(snippet: str, file_rel: str, base_dir: str) -> tuple[bool, str, int | None]:
    """Check that a lineage snippet appears verbatim in its file.

    The snippet is the real anchor: a few lines of the actual code that
    produces a data element. It is matched line-by-line with surrounding
    whitespace stripped, so indentation differences do not matter and the
    match survives line-number drift. Returns (ok, detail, start_line).
    """
    if not file_rel:
        return False, "no 'file' given for the snippet", None
    full = file_rel if os.path.isabs(file_rel) else os.path.join(base_dir, file_rel)
    if not os.path.isfile(full):
        return False, f"file not found ({full})", None

    needle = [ln.strip() for ln in snippet.splitlines() if ln.strip()]
    if not needle:
        return False, "snippet is empty", None

    with open(full, "r", encoding="utf-8", errors="replace") as fh:
        haystack = [ln.strip() for ln in fh.read().splitlines()]

    n = len(needle)
    hits = [i for i in range(len(haystack) - n + 1) if haystack[i:i + n] == needle]
    if not hits:
        return False, f"snippet not found in {file_rel}", None
    where = hits[0] + 1
    if len(hits) > 1:
        return True, f"snippet found in {file_rel}:{where} (and {len(hits) - 1} more)", where
    return True, f"snippet found in {file_rel}:{where}", where
