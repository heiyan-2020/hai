---
name: fact
description: Materialize one concrete Protocol run as a validated internal Fact with a bounded observational claim, headline metric, stored evidence, exact reproduction metadata, and artifact-field lineage. Use after a meaningful experiment run, including a negative result that answers the experiment question.
---

# Fact

A Fact is a concrete materialization of a Protocol:

```text
Protocol + actual command + revision + environment + artifacts -> Fact
```

This first version supports internal experiment Facts only. Store them under `.claude-research/facts/internal/` and their evidence under `.claude-research/data/<fact-id>/`.

Read `<PLUGIN_ROOT>/schema/fact.schema.md` before authoring.

## Create

1. Allocate the next `if-NNN` ID by scanning `.claude-research/facts/internal/`.
2. Preserve the result even when it is negative. Do not create a Fact for an operational failure unless that failure answers the experiment question.
3. Write one short observational `claim`; put causality and caveats outside it.
4. Choose one headline metric that directly tests the claim. Compare like with like and use only supported precision.
5. Reference the governing Protocol and every cited `(artifact, field)` pair. For a delegated artifact, cite its child Protocol.
6. Record the exact command, commit, branch, environment, and hardware.
7. Store primary and supporting evidence under `.claude-research/data/<fact-id>/`.
8. Write the required body sections in order: `Bottom line`, `Key evidence`, `Scope & limits`, `Lineage`, `Reproduction`.
9. Put the cheap raw-evidence recomputation in a fenced command, run it, compare its output with `metric.value`, and record the result as `Verified:`.

`Reproduction` must distinguish a cheap recomputation from stored raw rows from the expensive command that regenerates them. Recompute the metric; do not merely print a stored summary value.

## Validate

Run:

```bash
python3 <PLUGIN_ROOT>/scripts/fact_check.py \
  .claude-research/facts/internal/<fact-id>-<slug>.md \
  --research-root .claude-research
```

Fix every structural, path, Protocol-field, and reproduction error. A run is not finished until its Fact validates.
