# Feedback at the end of a session

The feedback is the part the learner takes away. It must be specific enough that they could act on it tomorrow, and honest enough to be worth reading. Every claim comes from `progress.md`: the rubric scores with their quotes, the hints used, and the gap analyses. Nothing comes from a general impression. Do not raise a score now.

## Structure

Write it in the learner's language.

```markdown
## Feedback: <paper>

### Overall
<2–3 sentences: the strongest ability shown, the main thing to work on.>

### Exercise 1: <ability>
| Criterion | Dimension | Score | Evidence |
|-----------|-----------|-------|----------|
| ... | P-cause | Yes / Partial / No | "<quote>" |
Hint used: yes / no
<One or two sentences on what the score means: what they did, and what was missing.>

### Exercise 2: ...

### Gap analysis
<Were their gap analyses specific (named the assumption or observation they missed) or generic ("think more")? Quote one.>

### Patterns
<1–2 habits seen in more than one exercise, or across papers in the log. Positive ones count too.>

### What to practice next
<2–3 concrete recommendations.>
```

## What the scores mean

Say what was missing, not only the score. "P-strawman: No" says little. "Proposed moving the agent to a cloud VM, and did not use observation 4, where that already failed" is something the learner can work on.

Common readings:

- **P-cause Partial**: the answer names a symptom or a category ("the abstraction does not fit") and stops before the mechanism of the failure.
- **S-insight No, S-mechanism Yes**: the learner built a mechanism without saying what fact makes it work. This often means they copied a known pattern.
- **S-cost No**: the design has no stated downside. Every real design has one.
- **E-cost No**: the experiments test only the friendly case.
- **T-insight No**: the learner moved the mechanism to the new setting without checking whether the fact behind it still holds.

## Patterns

Look for habits that show up in more than one exercise, or in this paper and earlier ones in the log. Common ones:

- Jumping to a mechanism before naming the root cause.
- Taking the existing system's structure as given ("make step X faster") instead of asking whether step X is needed.
- Not asking what the obvious fix would be, or why it would fail.
- Answers phrased as guesses or questions instead of claims with reasons.
- Strong on design, weak on evaluation (or the reverse).
- Specific, honest gap analyses (worth praising: this is the habit that makes practice work).

## What to practice next

Make the recommendations concrete and tie them to the weakest dimensions:

- A kind of paper to train on next, by type (see the table in `answer-card.md`). For someone weak at P-cause, a study-driven paper whose problem comes from measurements. For someone weak at E-cost, a paper whose design moves a cost somewhere.
- A specific exercise: "For your next paper, before reading the design, write down which part of the current system is unnecessary for the application, and why."
- If the log has earlier entries, compare: say whether a dimension that was weak before has improved or is still weak.

## Log entry

Append to `~/.teach-me-this/log.md` (create it if missing). List every criterion with its dimension and score, so that later sessions can count them.

```markdown
## <date> · <paper> (<paper type>)
- Ex1 <ability>: P-cause Yes · P-strawman No · P-signal Yes · P-goal Partial · hint: no
- Ex2 <ability>: S-insight Partial · S-mechanism Yes · S-correct No · S-cost No · hint: yes
- Gap analysis: specific | generic
- Patterns: <one line>
- Next: <one line>
```
