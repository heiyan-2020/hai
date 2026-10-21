# Feedback at the end of a session

The feedback is the part the learner takes away. It must be specific enough that they could act on it tomorrow, and honest enough that it is worth reading. Base every claim on what they said in this session (quotes in `progress.md`), not on a general impression.

## Structure

Use this structure, in the learner's language.

```markdown
## Feedback: <paper>

### Overall
<2–3 sentences: the strongest ability shown, the main thing to work on.>

### Problem finding (stage 1)
<Assessment + 1–2 short quotes + hints used.>

### Solution derivation (stage 2)
<Same, per key idea where useful.>

### Experiment design (stage 3)
<Same.>

### Application and extension (stage 4)
<Same.>

### Patterns
<1–2 habits seen in more than one stage. Positive ones count too.>

### What to practice next
<2–3 concrete recommendations.>
```

## How to assess each ability

For each ability, say where the learner was on this scale, and why:

- **Independent**: reached the core items with no hint or with L1 only.
- **Guided**: needed L2–L3, but made the final step themselves.
- **Shown**: needed the bottom-out, or skipped.

Hints are the most honest measure; report them as numbers ("stage 2, idea 1: L2; idea 2: bottom-out"). Then say what the hints were needed for, because that is the useful part. "Needed L2" says little. "Saw that the append waits, but took the fix 'make Paxos faster' as given and did not ask who needs the position" is something the learner can work on.

What to look for, per ability:

- **Problem finding**: did they combine phenomena or fixate on one? Did they separate the distractor from the signal? Did they state a root cause, or only a symptom? Did they notice the constraints that rule out the cheap fixes, or propose one of those fixes?
- **Solution derivation**: did they ask what the problem allows (what is not needed, what is already known), or go straight to mechanisms? When a wall was presented, did they patch the symptom or rethink the assumption? Did they justify why the idea is safe or correct?
- **Experiment design**: did their research questions cover the headline claim, the cost the design pays, and one ablation per key idea? Were baselines fair (same framework, same throughput point, strongest version)? Did they ask for tail metrics and worst cases, or only friendly ones?
- **Application and extension**: did they identify which assumption of the paper their scenario changes? Did they transfer the insight (a fact about the problem) or only the mechanism?

## Patterns

Look for habits that show up in more than one stage. Common ones:

- Jumping to a mechanism before naming the root cause.
- Taking the existing system's structure as given ("make step X faster") instead of asking whether step X is needed.
- Ignoring constraints until they are pointed out.
- Strong on design, weak on evaluation (or the reverse).
- Asking good clarifying questions before answering (worth praising).

## What to practice next

Make the recommendations concrete and tied to the patterns:

- A kind of paper to train on next, by type (see the table in `answer-card.md`): for someone weak at problem finding, a study-driven paper whose problem comes from measurements; for someone weak at evaluation, a verification or methodology paper.
- A specific exercise: "For your next paper, before reading the design, write down which part of the current system is unnecessary for the application, and why."
- If `~/.teach-me-this/log.md` has earlier entries, compare. Say whether a pattern from before has improved or is still there.

## Log entry

Append to `~/.teach-me-this/log.md` (create it if missing):

```markdown
## <date> · <paper> (<paper type>)
- Problem finding: <Independent|Guided|Shown> — <one line>
- Solution derivation: <...> — <one line>
- Experiment design: <...> — <one line>
- Application/extension: <...> — <one line>
- Patterns: <one line>
- Next: <one line>
```
