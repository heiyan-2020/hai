---
name: protocol
description: Author and validate a run-agnostic data-lineage Protocol for one code-produced artifact tree. Use before running an experiment, generating a conclusion-bearing table or figure, or trusting a metric whose producing code and reproducible entry point are not yet declared.
---

# Protocol

A Protocol is a reusable contract, not a run record. Store it at `.claude-research/protocols/<task-id>-protocol.md`. Put concrete arguments, commit, branch, environment, hardware, and results in the materialized Fact instead.

Read `<PLUGIN_ROOT>/schema/protocol.schema.md` before authoring. Resolve `<PLUGIN_ROOT>` from this installed skill's plugin root.

## Author

1. Identify or create exactly one entry script that produces the artifact tree end to end.
2. Expose every configurable choice as an argument. List every hard-coded choice under `fixed`. Do not read configuration from environment variables.
3. Infer every produced path from the code and declare the complete `## Run root shape`.
4. Mark each path `[shape-only]`, `[bears conclusions]`, or `[bears conclusions, delegated]`.
5. For an inline conclusion-bearing artifact, list every field and mark it `(important)` or `(shape-only)`. Give each important field one `### Field:` block.
6. For a rich artifact such as a figure, delegate to a child Protocol through `lineage_protocol` instead of describing it twice.
7. Trace each important field to the code that produces it. Use a verbatim snippet of at most five nonblank lines. Point to producing code, not the entry wrapper or output file.

Use `MEASURED`, `DERIVED`, `SYNTHETIC`, or `EXTERNAL` honestly. A `DERIVED` field requires a formula.

## Validate

Run from the project root:

```bash
python3 <PLUGIN_ROOT>/scripts/protocol_check.py \
  .claude-research/protocols/<task-id>-protocol.md
```

Pass `--base <dir>` only when source paths resolve against another root. Fix every failure, including failures in delegated child Protocols. Do not run the formal experiment until validation succeeds.
