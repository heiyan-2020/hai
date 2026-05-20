# Protocol schema  (annotated reference)

A protocol is a **per-task data-lineage spec**. One file per task, named
`{task-id}-protocol.md`, living under `.claude-research/channels/{channel}/`.

It is markdown — not yaml — because the lineage layer needs logical
description that a flat key/value file cannot carry. But it is **not** free
prose: every data element must carry the verbatim core code that produces it
and be tagged with a nature. Anchored to real code, never decorative prose.

A protocol is simultaneously the **manifest** (which data the task produces)
and the **method** (how each piece is produced). Describing how data is
produced *is* declaring that it exists — they are not two documents.

## Structure

````markdown
---
task: <task-id>
artifacts:
  - path: "<relative path to a produced file>"
    run: "<command that produces it>"
    source: "<the infra source file the command lives in>"
    validate:
      - "<command, exit 0 = valid>"
    provenance_fields: [<fields the output file must self-stamp>]
    git_tracked: true            # false for logs / scratch
side_effects:
  - path: "<extra file the run produces>"
    git_tracked: false
---

# <artifact> — one-line description

## Element: <name>
- nature: MEASURED | DERIVED | SYNTHETIC | EXTERNAL
- source_field: <where the value is read from>
- file: <relative path to the source file>
- formula: <expression>            # REQUIRED iff nature == DERIVED
```python
<the core code that produces this element — at most 5 lines>
```

## Element: <name>
...
````

The **snippet** — the fenced code block — is the anchor. It is the actual core
lines that produce the element, copied verbatim. A snippet beats a bare
`file:line`: it survives line-number drift, and a reader (or Codex) sees the
lineage logic without opening the file. Keep it to the core — 5 lines at most,
not a whole function.

## Field consumers

`protocol_check.py` enforces:

- Every `## Element:` block has a `nature:` with one of the 4 valid values.
- Every element names a `file:` and carries a fenced code `snippet`.
- The snippet is at most 5 (non-blank) lines.
- The snippet appears verbatim in the file — matched line-by-line with
  surrounding whitespace stripped, so indentation differences do not matter.
  The line number is *derived* from this match, never stored.
- Every `DERIVED` element carries a `formula:`.
- Frontmatter parses and every `artifacts[].path` is a non-empty string.

`pin-audit.py` (artifact accounting, Phase 5) additionally checks the produced
files against `artifacts[].path` ∪ `side_effects[].path`.

## Nature tags

| Tag | Meaning |
|---|---|
| `MEASURED`  | Read from a real measurement (wall clock, counter, eval score). |
| `DERIVED`   | Computed from other elements. `formula:` is mandatory. |
| `SYNTHETIC` | Produced by a model/heuristic/assumption, not measured. |
| `EXTERNAL`  | Taken from a paper, dataset, or third-party source. |

The nature tag is the integrity signal: a reader instantly knows whether a
bar in a chart is real or fabricated. A `SYNTHETIC` value mislabeled
`MEASURED` is exactly what `pin-codex-audit` exists to catch.
