---
name: pin-aware-agent
description: >-
  The orchestrator for disciplined agent-driven research work. Use this for ANY
  coding, algorithm, or data-producing research task — building a feature,
  running an experiment, producing a figure or a table. It keeps the human in
  genuine understanding by reading existing design decisions (pins) before
  acting, declaring data lineage (protocols) up front, escalating conflicts
  instead of silently resolving them, and ending with a machine audit, an
  adversarial Codex audit, and an interactive grounding quiz. Trigger whenever
  you are about to start research implementation work and want to avoid silent
  rollback of past decisions or untraceable data — even if the user just says
  "implement X" or "run this experiment".
type: flow
user-invocable: true
---

# pin-aware-agent

You are about to do research work an agent could quietly get wrong. The danger
is not a single bad step — it is a long chain where every step looks locally
fine while a past decision is silently reverted, or a number is produced that
nobody can trace. This workflow keeps the human in real understanding without
making them review every line.

Two disciplines run through every phase:

- **Pin** — a decided design must not change silently. Pins live in `pins.yaml`.
- **Protocol** — every conclusion-bearing data element must trace to code. A
  protocol is a per-task data-lineage spec (`{task-id}-protocol.md`).

The rule under both: **close every silent channel.** You either follow a
declared path or you STOP and escalate to the human. There is no third option.

Resolve paths: pins.yaml is at the project root or `.claude-research/pins.yaml`.
Plugin scripts are under `<PLUGIN_ROOT>/scripts/`, where `<PLUGIN_ROOT>` is
the root of this installed plugin. In Claude Code, `${CLAUDE_PLUGIN_ROOT}` may
already point there; in Codex, resolve it from the installed skill/plugin path.

## Phase 1 — Read context

Read `pins.yaml` and any existing `*-protocol.md` in this project. You must
know every active pin's `id` and `claim` before touching anything. Run
`pin_audit.py <pins.yaml>` once now to confirm you start from a clean state —
if it already fails, surface that to the human before doing anything else.

## Phase 2 — Analyze the task, then STOP for confirmation

This phase produces a short written plan and **stops for human confirmation**.
Do not implement anything before the human confirms.

**2a. Understand the task.** State, in two or three sentences, what you are
about to do.

**2b. Protocol declaration.** List every data artifact the task will produce.
For each, name the protocol that governs it. If a suitable protocol exists,
restate its key bindings (entry point, output path, validation) so the human
can confirm it applies. If no protocol exists, **STOP** — do not free-style
data production. Propose either (a) splitting off an infra/protocol task to
derive one from the existing infrastructure, or (b) explicitly borrowing the
closest protocol, which the human must acknowledge. A protocol is derived by
reading the infra code; every lineage element carries the verbatim core code
(at most 5 lines) that produces it. See `pin-grounding` for how protocol
derivation doubles as a teaching moment.

**2c. Pin impact.** Go through every active pin. Mark each:
`unaffected` / `affected-preserved` (your plan keeps it) / `conflict` (your
plan breaks it). Any `conflict` **blocks** this phase. Escalate it with three
options for the human: keep the pin and change the plan; update the pin and
co-decide; or retire the pin with a stated reason. Never resolve a conflict on
your own — that is exactly the silent rollback this whole workflow exists to
prevent.

**2d. Heads-up on new pins.** Informally — one or two lines — tell the human
what new design decisions this task is likely to introduce and may be worth
pinning later. This is not a formal proposal; it just sets direction.

Present 2a–2d together and wait for the human to confirm.

## Phase 3 — Implement

Do the work. Conform to the declared protocols. Keep every
`affected-preserved` pin actually preserved. If, mid-implementation, you
discover a new conflict that Phase 2 missed, STOP and escalate — do not
absorb it silently.

## Phase 4 — Update pins

Draft the new pins this task earned. A good pin locks a function-level
behavioral property (the force-decode example: "the inducer prompt must end
with the `</tool_call>` marker"), not a variable name and not "the algorithm
is correct". Give each a heterogeneous assertion (`pytest` / `command` /
`grep` / `grep_absent` / `python`) per `schema/pins.schema.yaml`. Do not write
them into `pins.yaml` yet — they are committed only after Phase 7.

## Phase 5 — Machine audit

Run `pin_audit.py <pins.yaml>` (existing pins must still pass — this catches a
silent regression you introduced) and `protocol_check.py` on each task
protocol (every element's code snippet must still appear in its file, every
element must have a nature tag). Also check artifact accounting: the set of new
git-tracked files must
equal the union of declared `artifacts` and `git_tracked` side effects — a
file that is present but undeclared, or declared but absent, **blocks**.

## Phase 6 — Adversarial audit

Invoke `pin-codex-audit`. Codex independently reads the code behind each
lineage snippet and checks: did you miss a silent regression; does each pin's
claim still hold in the code; is any lineage description false (e.g. a
`DERIVED` value labelled `MEASURED`); is anything that deserves a pin not
proposed. Surface its findings to the human verbatim.

## Phase 7 — Grounding (the real commit gate)

Invoke `pin-grounding`. It quizzes the human on what was actually decided —
each new pin's claim, each data element's lineage. **Passing the quiz is what
commits the new pins into `pins.yaml` and accepts the protocol outputs.** A
failed answer triggers a follow-up on the same concept. Understanding is the
gate; nothing lands until the human genuinely holds the model in their head.

## Completion

Report: pins added, protocols declared, audit + Codex outcomes, grounding
result. If any phase escalated, report what the human decided and why.
