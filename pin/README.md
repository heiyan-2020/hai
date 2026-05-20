# Pin

A Claude Code plugin for **agent-driven research that the human still understands**.

## The problem

Delegating implementation, testing, and data maintenance to an agent while the
human keeps only high-level direction does not work. Two failure modes recur:

1. **Silent rollback of design decisions.** On a long execution chain every
   next-step looks locally fine, but when a step conflicts with an earlier
   decision the agent takes the cheap path and quietly reverts it. The human,
   focused on the current step, only finds out when a symptom gets severe.

2. **Data with no traceable origin.** The agent produces a figure or a number
   and nobody can say, for any single data element, where it came from or how
   it was computed. Facts pile up; nobody is responsible for them.

## The two disciplines

| | **Pin** | **Protocol** |
|---|---|---|
| Guards | A decided design is not silently changed | Every conclusion-bearing data element traces to code |
| Direction | Inward — internal state (code/algorithm invariants) | Outward — results are reported faithfully |
| Failure it kills | Silent rollback of a past decision | "Is this bar measured or fabricated?" being unanswerable |
| Form | `pins.yaml` entries + `# PIN:` code anchors | a per-task `*-protocol.md` data-lineage spec |

The shared philosophy: **close every silent channel.** The agent either follows
a declared path or explicitly escalates to the human. There is no third option.

### Pin

A pin is a machine-checkable assertion that locks one design decision. Its
`assertion` is heterogeneous — a pytest node, a shell command, a `grep` /
`grep_absent` pattern, or a python script. Editing `pins.yaml` itself requires
an explicit human gesture (`[pin-release: <id>]` in the commit message);
without it, the pre-commit hook blocks. That is the root defense against an
agent learning to "delete the pin so the check passes".

### Protocol

A protocol is **not** a file manifest — it is a data-lineage spec. The unit is
the *data element* (each segment/column/row of a figure), not the file. For
each element the protocol records: semantics, source field, the source `file`,
a verbatim **code snippet** (≤5 lines of the actual producing code), and
**nature** (`MEASURED` / `DERIVED` / `SYNTHETIC` / `EXTERNAL`). `DERIVED`
elements must carry a formula. The snippet is the anchor — it survives
line-number drift and shows the lineage logic without opening the file.

## The skills

| Skill | Role |
|---|---|
| `pin-aware-agent` | Orchestrator. The whole workflow; wraps the others. |
| `pin-audit` | Machine audit primitive. Non-interactive. Also run by the git hook. |
| `pin-codex-audit` | Adversarial independent audit via Codex. |
| `pin-grounding` | Interactive learning quiz — the real commit gate. |

### pin-aware-agent workflow

```
Phase 1  READ      pins.yaml + existing protocols
Phase 2  ANALYZE   declare protocol (data lineage) + pin impact + light confirm
Phase 3  IMPLEMENT do the work (may wrap /develop, /execute-plan, ...)
Phase 4  UPDATE    draft new pins
Phase 5  AUDIT     pin-audit: assertions pass, declared==produced, anchors resolve
Phase 6  CODEX     pin-codex-audit: independent adversarial check
Phase 7  GROUND    pin-grounding: quiz the human; passing commits the new pins
```

## Three-layer check

- **Machine** (`pin-audit`, git hook) — anchors resolve, assertions pass, the
  set of new tracked files equals the declared set.
- **Adversarial** (`pin-codex-audit`) — Codex reads the code at each anchor and
  checks the lineage description is true.
- **Human** (`pin-grounding`) — a quiz verifies the human actually understands.

## Layout

```
pin/
├── .claude-plugin/        plugin.json, marketplace.json
├── skills/                the 4 skills
├── schema/                pins.schema.yaml, protocol.schema.md
├── hooks/                 commit-msg.sh (git hook template)
├── scripts/               pinlib.py, pin_audit.py, protocol_check.py, pin_tamper.py, install-hook.sh
├── examples/demo/         a self-contained project the machinery runs against
└── tests/                 unit tests + verify.sh end-to-end proof
```

## Quick start

```bash
# audit all pins in a project
python scripts/pin_audit.py path/to/pins.yaml

# validate a protocol's data lineage
python scripts/protocol_check.py path/to/task-protocol.md

# install the git commit-msg hook into a project
bash scripts/install-hook.sh path/to/project

# run the end-to-end verification
bash tests/verify.sh
```

## Status

v0.1 — `pin` and `protocol` mechanics implemented and verified end-to-end.
See `tests/verify.sh` for the proof that the audit catches a silent rollback
and the hook blocks both a broken pin and an untracked pin deletion.
