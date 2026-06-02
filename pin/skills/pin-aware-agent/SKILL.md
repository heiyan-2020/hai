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

Three disciplines run through every phase:

- **Pin** — a decided design must not change silently. Pins live in `pins.yaml`.
- **Protocol** — every conclusion-bearing data element must trace to code. A
  protocol is a per-task data-lineage spec (`{task-id}-protocol.md`), authored
  and validated through `pin-protocol`.
- **Fact** — every citeable observation is a structured markdown evidence card
  under `.claude-research/facts/`, created and validated through `pin-fact`.

The rule under all three: **close every silent channel.** You either follow a
declared path or you STOP and escalate to the human. There is no third option.

And one rule about *how* you talk to the human, threaded through every phase:
**write for someone who has not read this code.** Every plan, escalation, and
report is read by a person deciding whether to trust your work — not by you, who
just spent an hour in the source. The instant you drop a function name, a file
path, a pipeline stage, or a term you coined this session without saying in plain
words what it is, the human stops being able to follow — and a human who can't
follow can't confirm, which defeats the gates this workflow is built on. Ground
every such term the first time it appears, in one clause.

Resolve paths: pins.yaml is at the project root or `.claude-research/pins.yaml`.
Plugin scripts are under `<PLUGIN_ROOT>/scripts/`, where `<PLUGIN_ROOT>` is
the root of this installed plugin. In Claude Code, `${CLAUDE_PLUGIN_ROOT}` may
already point there; in Codex, resolve it from the installed skill/plugin path.

## Phase 1 — Read context

Read `pins.yaml`, any existing `*-protocol.md`, and existing facts under
`.claude-research/facts/` in this project. You must know every active pin's
`id` and `claim` before touching anything. Run `pin_audit.py <pins.yaml>` once
now to confirm you start from a clean state — if it already fails, surface that
to the human before doing anything else. If `.claude-research/facts/` exists,
also run `fact_check.py` once; inherited fact drift is a blocker for
data-producing work.

## Phase 2 — Analyze the task, then STOP for confirmation

This phase produces a short written plan and **stops for human confirmation**.
Do not implement anything before the human confirms.

The plan *is* the gate. The human reads it to decide whether your understanding
is right, so it has to be readable by them — not a dump of your internal
reasoning. Before writing each part below, picture a sharp colleague who has not
opened this codebase: say the idea and the stakes in plain words first, then
introduce specifics, grounding every code symbol or coined term as you go. And
wherever a part asks the human to *choose* — which protocol, how to resolve a
conflict, what to measure — state each option as what it means and what it trades
off, never as a bare symbol they would have to read the source to decode.

**2a. Understand the task.** In two or three plain sentences, say what you are
about to do and why it answers the human's question — no internal symbol before
you have put the idea in words a non-reader of the code would follow. (Good: "Run
the same bug-finder on the same code several times; if it is reliable it should
reach the same verdict each time, so how often it contradicts itself is a floor
on its error rate — no answer key needed.")

**2b. Protocol declaration.** List every data artifact the task will produce —
as the tree it is, so a rich node (a figure, a sub-pipeline output) shows which
child protocol its lineage is delegated to. For each, name the protocol that
governs it. If a suitable protocol exists, restate its key bindings (entry
point, output path, validation) so the human can confirm it applies. If no
protocol exists, **STOP** — do not free-style
data production. Propose either (a) splitting off an infra/protocol task to
derive one from the existing infrastructure, or (b) explicitly borrowing the
closest protocol, which the human must acknowledge. When the plan requires
deriving a new protocol or extending one, author it through `pin-protocol` —
it owns *how* a protocol is written (one argument-only script as the
experiment's single entry point, and a verbatim ≤5-line snippet tracing each
number to the infra that computes it). See `pin-grounding` for how protocol
derivation doubles as a teaching moment.

**2c. Fact declaration.** State whether this task will produce or modify any
citeable observations. If yes, declare the fact type and expected path:
`internal/if-NNN-*.md`, `external/ef-NNN-*.md`, or `derived/df-NNN-*.md`.
Internal facts must reference the protocol declared in 2b and the relevant
element names. Derived facts must name their input fact IDs. If a data-producing
task would produce a result but no fact, explain why it is not citeable.

**2d. Pin impact.** Go through every active pin. Mark each:
`unaffected` / `affected-preserved` (your plan keeps it) / `conflict` (your
plan breaks it). Any `conflict` **blocks** this phase. Escalate it with three
options for the human: keep the pin and change the plan; update the pin and
co-decide; or retire the pin with a stated reason. Never resolve a conflict on
your own — that is exactly the silent rollback this whole workflow exists to
prevent.

**2e. Heads-up on new pins.** Informally — one or two lines — tell the human
what new design decisions this task is likely to introduce and may be worth
pinning later. This is not a formal proposal; it just sets direction.

The difference this readability rule makes, on an actual choice this workflow
once put to a human:

- **Unreadable:** "measure variance at the reasoner-verdict layer
  (`_check_post_implies_spec`, pre-probe) or the confirmed-bug layer
  (`bug_validation/summary.json`, post-probe)."
- **Readable:** "Measure which judgment — the model's *first* call on each
  function (from the spec alone, before it runs any test) or its *final* call
  (after it runs tests to confirm)? The first is where vague specs bite hardest;
  the second is steadier because the tests catch mistakes. I suggest both, with
  the first as the headline."

Same decision; only the second is one a human can actually answer.

Present 2a–2e together, end with any open decisions as plain questions, and wait
for the human to confirm.

## Phase 3 — Implement

Do the work. Conform to the declared protocols and facts. Keep every
`affected-preserved` pin actually preserved. When you produce or change a data
artifact, keep its protocol current through `pin-protocol`; do not hand-write
lineage prose. If the task produces a citeable observation, invoke `pin-fact`
and create/update the structured markdown fact; do not hand-write unconstrained
fact prose. If, mid-implementation, you
discover a new conflict or missing protocol/fact declaration that Phase 2
missed, STOP and escalate — do not absorb it silently.

## Phase 4 — Update pins

Draft the new pins this task earned. A good pin locks a function-level
behavioral property (the force-decode example: "the inducer prompt must end
with the `</tool_call>` marker"), not a variable name and not "the algorithm
is correct". Give each a heterogeneous assertion (`pytest` / `command` /
`grep` / `grep_absent` / `python`) per `schema/pins.schema.yaml`. Do not write
them into `pins.yaml` yet — they are committed only after Phase 7.

## Phase 5 — Machine audit

Run `pin_audit.py <pins.yaml>` (existing pins must still pass — this catches a
silent regression you introduced), `protocol_check.py` on each task protocol
(it recurses, so every delegated child protocol is checked too: each element's
code snippet must still appear in its file, every element must have a nature
tag), and `fact_check.py .claude-research/facts` if the project has facts or
this task created one. Also check artifact accounting across the delegation
tree: the set of new git-tracked files must equal the union of declared
`artifacts` (the task protocol's and every child protocol's) and `git_tracked`
side effects — a file that is present but undeclared, or declared but absent,
**blocks**.

## Phase 6 — Adversarial audit

Invoke `pin-codex-audit`. Codex independently reads the code behind each
lineage snippet and checks: did you miss a silent regression; does each pin's
claim still hold in the code; is any lineage description false (e.g. a
`DERIVED` value labelled `MEASURED`); does each new/changed fact truthfully
reflect its data/protocol/source; is anything that deserves a pin not proposed.
Surface its findings to the human verbatim.

## Phase 7 — Grounding (the real commit gate)

Invoke `pin-grounding`. It quizzes the human on what was actually decided —
each new pin's claim, each data element's lineage, and each new/changed fact's
claim and limits. **Passing the quiz is what commits the new pins into
`pins.yaml` and accepts the protocol/fact outputs.** A failed answer triggers a
follow-up on the same concept. Understanding is the gate; nothing lands until
the human genuinely holds the model in their head.

## Completion

Report: pins added, protocols declared, facts created/updated, audit + Codex
outcomes, grounding result. If any phase escalated, report what the human
decided and why.
