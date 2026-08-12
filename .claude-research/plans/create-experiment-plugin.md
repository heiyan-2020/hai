# Create standalone experiment plugin

- Detail: normal
- Status: complete

## Goal

Create a lightweight `experiment` plugin that runs experiments through a reusable Protocol and materializes each meaningful run as an internal Fact, without depending on the earlier heavyweight workflow.

## Scope

- Add `experiment-loop`, `protocol`, and `fact` skills.
- Keep Protocol contracts and recursive data-lineage validation.
- Keep only internal Facts in v1; each Fact binds a Protocol to concrete arguments, code revision, environment, data, claim, and metric.
- Store plans, protocols, data, and facts under `.claude-research/`.
- Add focused validator tests and both Codex and Claude marketplace entries.
- Leave existing plugins unchanged for compatibility.

## Steps

1. Scaffold the plugin and skills using the repository's existing plugin conventions.
2. Extract and neutralize the Protocol parser/checker.
3. Implement the internal Fact checker against Protocol artifact fields.
4. Write concise schemas and workflow instructions.
5. Run tests and validation, then independently review the completed formal run and Fact.

## Verification

- Valid Protocol + Fact fixture passes.
- Broken lineage and broken Fact references fail.
- All three skills pass `quick_validate.py`.
- Plugin passes `validate_plugin.py`.
- Marketplace JSON parses and references the new plugin.

## Decision

Approved by the user on 2026-08-12. External and derived Facts, design locks, interactive quizzes, and a dedicated lineage audit are intentionally excluded from v1.

Codex review runs only after the formal experiment and Fact materialization. Findings that affect the experiment require a rerun and updated Fact before another review round.

## Progress

- Added the standalone `experiment` plugin and both marketplace entries.
- Added `experiment-loop`, `protocol`, and `fact` skills.
- Added neutral Protocol and internal Fact schemas and validators.
- Added four focused checks covering valid materialization, missing lineage snippets, unknown Fact fields, and delegated Protocols.
- Independent review round 1 found empty-Fact, path containment, command matching, marker validation, and metric-recomputation gaps; all were addressed.
- Independent review round 2 found remaining directory escapes, unmarked outputs, compound commands, and verification-record parsing gaps; all were addressed.
- Independent review round 3 found execution-changing interpreter options could bypass the entry script; a conservative option allowlist closed it. No other release-blocking findings remained.

## Verification

- `python3 -m unittest discover -s experiment/tests -v`: 15 passed.
- All three skills pass `quick_validate.py`.
- `validate_plugin.py experiment`: passed.
- Both marketplace manifests parse as JSON.
- `git diff --check`: passed.
