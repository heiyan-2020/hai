---
name: fundamental-thinking
description: >-
  Use the moment you've found a problem from one example — a failing test, a wrong
  output, an experiment that breaks on one prompt, a bad data row — and are about to fix
  it. The tempting move is to make that one example go away by writing the example itself
  into the fix: hardcode it, drop the bad row, tweak a number until the test passes, or
  add a line to a prompt naming that exact case ("when the input is about X, don't do Y").
  That is overfitting — it clears the one case you saw and leaves every other case that
  breaks for the same reason still broken. This skill makes you first figure out the whole
  group of cases like it, find why they break, and fix that instead. The tell is always
  the same, in code or data or a prompt: your fix names the exact case you just saw. Reach
  for it even when asked for a small fix — the small fix is usually the trap.
---

# Fundamental thinking

Here "fix" means any change you make to clear a problem — in code, in data, or in a
prompt. The trap below is the same in all three.

## The trap

You hit a problem on one example: a test fails on input `X`, a function crashes on this
list, an experiment breaks on this prompt, this data row looks wrong, the algorithm
gives the wrong answer for `n=3`. The fast move is to make *that one example* go away by
writing the example itself into your fix:

- add `if x == X: ...`, special-case the empty list, drop the bad row, nudge a constant
  until `n=3` passes;
- or, the version that hides best, put the failing case straight into a **prompt**:
  "when the input is about X, don't do Y". Now the prompt handles the one transcript you
  saw and nothing else.

These are the same mistake wearing different clothes — and the list isn't meant to be
memorized. A config value, a regex, a retry limit, a sampling temperature: a new form
will show up, and it's still the same mistake. The shape to recognize is simple — **your
fix names the exact case you just saw.**

Why it's a mistake: one failing example is almost never alone. It's one case out of a
whole group that breaks for the same underlying reason — call that group the *class*.
Patch the one case and you fix a single point while the rest of the class stays broken.
Worse, you've hidden the symptom that would have led you to the real cause. A prompt that
sprouts a new special-case line for every failing example is the clearest sign of this:
it gets longer and more fragile, and it's quietly wrong on the next input it never saw.
You optimized "make this one thing stop complaining" when the goal was "make it right."

Taking a few minutes to think first is how you avoid a long tail of near-identical bugs.

## Before you fix it, answer three questions

Write the answers down — a couple of sentences, not just a thought. Writing is what
catches the lazy answer. Then confirm the direction before you commit to a fix.

### 1. What's the whole class, not just this one case?

The example in front of you is one sample. Describe the whole group it came from.

- What's the full set of inputs or states that hit this same code, prompt, or pipeline
  and break the same way? Describe it as a set, not one value.
- Is this example the normal case or a corner? If you'd only ever seen this one input,
  would you even know there was a bug — or are siblings of it failing silently right now?
- Walk the obvious regions and ask which ones break: empty / one / many, smallest and
  largest, null or missing or malformed, ordered or shuffled, duplicates, zero and
  negatives, boundary values, repeated or concurrent calls.

If you can't describe the class, you don't understand the bug yet — you've only seen a
symptom.

### 2. Where does it really break — symptom or cause?

The line that throws or returns the wrong value is often downstream of the real defect.
Trace back: what should always be true here, and where did that first stop being true? A
`NoneType has no attribute` deep in a function is the symptom; the cause is whoever
produced the `None` two layers up, and the missing check that let it through.

Fix the cause, not the symptom. A fix that only makes the symptom disappear comes back
later with a different stack trace.

### 3. Would your fix also handle the neighbors of this case?

Before you commit, take two or three nearby inputs you didn't originally test — other
members of the class from question 1 — and run your fix against them, on paper or for
real. A real fix makes the whole class right. An overfit patch handles the one input you
saw and falls over on its neighbors.

This is also your guard against the worst version of the trap: **making the one case pass
instead of making the thing right.** If you catch yourself tuning a number until one
assertion goes green, special-casing the exact input a test uses, or adding a prompt line
that names the one example you saw — stop. That just makes the problem *look* handled,
which is worse than leaving it visibly broken.

## What a good fix looks like

- It fixes the cause, so the whole class is right — not one point.
- It's no bigger than the class. Don't over-build: handling inputs that genuinely can't
  happen is its own kind of noise. Fundamental doesn't mean maximal.
- Where it's practical, it sets up a rule that keeps the class from breaking again — a
  type, a required check, a normalization step — instead of catching each symptom by hand.
- It comes with a test that covers the class — the boundary plus a couple of typical
  members — not just the single input that started this.

## Examples

**Prompt / experiment.** Your agent pipeline gives a malformed answer on one eval
example, so you add to the system prompt: "for questions about tariffs, always return the
number in USD." That's overfit — you've pasted the failing transcript into the
instructions, the next topic with the same confusion still breaks, and the prompt is one
line longer and more fragile. Fundamental: ask *why* the model went wrong here. Usually
the class is "the format or unit was underspecified for a whole family of questions," so
state the rule once and clearly, or fix the real cause (a vague schema, a missing
example, a tool description that lies) — then check it on held-out examples you did *not*
look at, not on the one that started this.

**Bug fix.** A parser crashes on a file with a trailing newline. Overfit: strip the
trailing newline first. Fundamental: the parser assumes every line is non-empty; the real
class is *any* empty line anywhere — blank lines mid-file, all-whitespace files, `\r\n` —
so fix how it handles lines, and test all of those.

**Algorithm.** A graph routine returns the wrong distance for one test pair. Overfit: add
`if src == 4 and dst == 7: return 3`. Fundamental: that pair is wrong because the
relaxation skips equal-weight edges; the class is *every* pair whose shortest path uses
such an edge, so fix the comparison and check it on a fresh random graph.

**Data.** One row has a date like `2026/13/01` and crashes the pipeline. Overfit: drop the
row. Fundamental: ask why a month-13 date exists — it's a `DD/MM` vs `MM/DD` mix-up that
hits *every* row where the day is over 12, a big silent class. Detect the format; don't
delete the evidence.

## When to keep it light

Not every problem needs all this. If the input really is just one value — a literal typo,
a one-off config — fix it and move on; say so in a line and don't invent a class that
isn't there. The point is to match the fix to the real size of the problem: don't shrink
a real class down to one example, and don't blow one example up into an imaginary class.
