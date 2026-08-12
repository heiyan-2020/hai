"""Parse experiment Protocol markdown files."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

VALID_NATURES = {"MEASURED", "DERIVED", "SYNTHETIC", "EXTERNAL"}


class ValidationError(Exception):
    """Raised when a Protocol or Fact cannot be parsed."""


@dataclass
class LineageField:
    name: str
    nature: str = ""
    source_field: str = ""
    file: str = ""
    formula: str = ""
    snippet: str = ""


@dataclass
class Artifact:
    path: str
    contains: str = ""
    git_tracked: bool | None = None
    lineage_protocol: str = ""
    fields: list[dict[str, Any]] = field(default_factory=list)
    field_blocks: list[LineageField] = field(default_factory=list)


@dataclass
class ShapeNode:
    path: str
    bears_conclusions: bool = False
    delegated: bool = False
    tags: frozenset[str] = field(default_factory=frozenset)
    marker_count: int = 0


@dataclass
class Protocol:
    task: str
    script: str
    parameters: list[dict[str, Any]]
    fixed: list[Any] | None
    run_root_shape: list[ShapeNode]
    artifacts: list[Artifact]
    path: str


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_FIELD_HEADER_RE = re.compile(r"^###\s+Field:\s*(.+?)\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)
_SHAPE_MARKER_RE = re.compile(r"\[([^\]]*)\]")
_FIELD_LIST_RE = re.compile(r"^-\s*(\S+)\s*\((important|shape-only)\)\s*$")
_BULLET_RE = re.compile(r"^-\s*([A-Za-z_]+)\s*:\s*(.*)$")


def load_protocol(path: str) -> Protocol:
    if not os.path.isfile(path):
        raise ValidationError(f"Protocol not found: {path}")
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
    shape, artifacts = _parse_body(text[match.end():])
    return Protocol(
        task=str(meta.get("task", "") or ""),
        script=str(meta.get("script", "") or ""),
        parameters=meta.get("parameters", []),
        fixed=meta.get("fixed") if "fixed" in meta else None,
        run_root_shape=shape,
        artifacts=artifacts,
        path=path,
    )


def _parse_body(body: str) -> tuple[list[ShapeNode], list[Artifact]]:
    headers = list(_SECTION_RE.finditer(body))
    shape: list[ShapeNode] = []
    artifacts: list[Artifact] = []
    for index, header in enumerate(headers):
        title = header.group(1).strip()
        start = header.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(body)
        block = body[start:end]
        if title.lower() == "run root shape":
            shape = _parse_shape(block)
        elif title.lower().startswith("artifact:"):
            artifacts.append(_parse_artifact(title.split(":", 1)[1].strip(), block))
    return shape, artifacts


def _parse_shape(block: str) -> list[ShapeNode]:
    fence = _FENCE_RE.search(block)
    region = fence.group(1) if fence else block
    nodes: list[ShapeNode] = []
    for line in region.splitlines():
        stripped = line.strip()
        if not stripped or (stripped.startswith("<run_root>") and stripped.endswith("/")):
            continue
        markers = list(_SHAPE_MARKER_RE.finditer(line))
        path_region = line[:markers[0].start()] if markers else line
        path = re.sub(r"^[\s│├└─]+", "", path_region).strip()
        if not path:
            continue
        tags = (frozenset(part.strip().lower() for part in markers[0].group(1).split(",") if part.strip())
                if markers else frozenset())
        nodes.append(ShapeNode(
            path=path,
            bears_conclusions="bears conclusions" in tags,
            delegated="delegated" in tags,
            tags=tags,
            marker_count=len(markers),
        ))
    return nodes


def _parse_artifact(path: str, block: str) -> Artifact:
    artifact = Artifact(path=path)
    field_headers = list(_FIELD_HEADER_RE.finditer(block))
    preamble = block[:field_headers[0].start()] if field_headers else block
    in_fields = False
    for raw in preamble.splitlines():
        line = raw.strip()
        if line.startswith("contains:"):
            artifact.contains = line.split(":", 1)[1].strip()
            in_fields = False
        elif line.startswith("git_tracked:"):
            artifact.git_tracked = line.split(":", 1)[1].strip().lower() == "true"
            in_fields = False
        elif line.startswith("lineage_protocol:"):
            artifact.lineage_protocol = line.split(":", 1)[1].strip().strip("\"'")
            in_fields = False
        elif line == "fields:":
            in_fields = True
        elif in_fields and line.startswith("- "):
            match = _FIELD_LIST_RE.match(line)
            if match:
                artifact.fields.append({
                    "name": match.group(1),
                    "important": match.group(2) == "important",
                })
            else:
                artifact.fields.append({"name": line[2:].strip(), "important": None})
    for index, header in enumerate(field_headers):
        start = header.end()
        end = field_headers[index + 1].start() if index + 1 < len(field_headers) else len(block)
        artifact.field_blocks.append(_parse_field(header.group(1).strip(), block[start:end]))
    return artifact


def _parse_field(name: str, block: str) -> LineageField:
    result = LineageField(name=name)
    fence = _FENCE_RE.search(block)
    bullet_region = block
    if fence:
        result.snippet = fence.group(1)
        bullet_region = block[:fence.start()]
    for raw in bullet_region.splitlines():
        match = _BULLET_RE.match(raw.strip())
        if not match:
            continue
        key, value = match.group(1).lower(), match.group(2).strip()
        if key in {"nature", "source_field", "file", "formula"}:
            setattr(result, key, value)
    return result


def locate_snippet(snippet: str, file_path: str, base_dir: str) -> tuple[bool, str, int | None]:
    if os.path.isabs(file_path):
        return False, f"file escapes project root: {file_path}", None
    root = os.path.realpath(base_dir)
    full_path = os.path.realpath(os.path.join(root, file_path))
    try:
        if os.path.commonpath((root, full_path)) != root:
            return False, f"file escapes project root: {file_path}", None
    except ValueError:
        return False, f"file escapes project root: {file_path}", None
    if not os.path.isfile(full_path):
        return False, f"file not found: {file_path}", None
    needle = [line.strip() for line in snippet.splitlines() if line.strip()]
    if not needle:
        return False, "snippet is empty", None
    with open(full_path, encoding="utf-8", errors="replace") as handle:
        haystack = [line.strip() for line in handle.read().splitlines()]
    width = len(needle)
    hits = [index for index in range(len(haystack) - width + 1)
            if haystack[index:index + width] == needle]
    if not hits:
        return False, f"snippet not found in {file_path}", None
    if len(hits) > 1:
        return False, f"snippet appears {len(hits)} times in {file_path}", None
    return True, "", hits[0] + 1
