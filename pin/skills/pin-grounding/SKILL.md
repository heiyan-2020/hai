---
name: pin-grounding
description: >-
  Interactively quiz the human until they genuinely understand the design
  decisions, data lineage, and fact claims an agent just produced — then commit
  the new pins.
  Use as the final gate of pin-aware-agent (Phase 7), or any time the user
  wants to verify they actually understand delegated work before it lands.
  This is a learning loop, not a rubber stamp: one multiple-choice question at
  a time, wrong answers trigger a follow-up on the same concept. Trigger on
  "ground me on this", "quiz me on what we built", "make sure I understand
  before committing the pins".
type: flow
user-invocable: true
---

# pin-grounding

The point of the whole plugin is that the human keeps a true mental model of
their project. This skill is where that is verified. Passing the quiz is what
**commits the new pins into `pins.yaml`** and accepts the protocol outputs.
Nothing lands before the human holds it in their head.

## What to quiz on

The anchors are concrete: each newly proposed pin's `claim`, each protocol
lineage element, and each new/changed fact's `claim`, inputs, and stated
limitations. Build one question per anchor.

## Question shape — the critical rule

Questions verify **what was actually decided or done**, not whether it was a
good decision. The human delegated the work; their cognitive debt is "I don't
know what was actually built." Grounding exposes that debt. Once they know what
was done, they can judge it themselves — and, crucially, they will notice later
if the agent silently violates it.

**Bad** (asks the human to be a reviewer):
> "What's the integrity risk of labelling `tokens × ms_per_tok` as wall time?"

**Good** (tests knowledge of the actual implementation):
> "How does the Decode segment of the latency figure get its value?"
> with one correct option (the real implementation) and three plausible
> alternatives a reasonable researcher might have assumed instead.

The wrong options are not random — each encodes a misconception the human
might be carrying. Which wrong option they pick tells you what they got wrong.

## Where the correct option goes — do not let it default to A

A model writing a multiple-choice question thinks of the correct answer first
and tends to write it as option A every single time. The human notices within
two questions, starts picking A on reflex, and the quiz verifies nothing.

Take the position out of your own hands. For **every** question — including the
variant questions after a wrong answer — draw a real random slot before you
present it:

```bash
python3 -c "import random; print(random.randint(0, 3))"
```

Put the correct answer at that index (0=A, 1=B, 2=C, 3=D) and the three
distractors in the remaining slots. Draw fresh each time. Never pick the slot
yourself — a model's own sense of "random" is biased and the human will feel
the pattern even if you cannot.

## The loop

Ask **one** question at a time and wait for the answer.

- **Correct** — confirm briefly, point at the anchor (the pin id, or the
  element's `file` + code snippet) so it sticks, move to the next.
- **Wrong** — do not move on. Explain the gap between what they assumed and
  what was actually done. Then draw a **variant** question on the *same*
  concept (a different anchor under the same idea) to confirm the correction
  landed. Do not ask a "now do you see why it's bad?" follow-up — that turns
  grounding into planning, which is a different skill.

Default to five questions; the user may ask for more. Cover pins, protocol
lineage, and facts when all three changed.

## On passing

When the human has demonstrated understanding of every anchor:

1. Write the new pins into `pins.yaml` (root or `.claude-research/`), following
   `schema/pins.schema.yaml`. Set each pin's `born_at` to the current commit
   and `branch` to the current branch.
2. Add a `# PIN: <id>` anchor comment in each pin's `code_locations`.
3. Save a grounding record under `.claude-research/grounding/` — the questions,
   the anchors, which were missed and corrected. This is the audit trail of the
   human's understanding at this point in time.
4. Run `pin_audit.py` once more to confirm the freshly written pins all pass.

## On not finishing

If the human cannot answer even after the correction loop, do **not** commit
the pins. Report which concept did not land. The work is not lost — it stays
as a draft. Grounding is a gate, not a formality; an ungrounded pin is worse
than no pin because it gives false confidence.
