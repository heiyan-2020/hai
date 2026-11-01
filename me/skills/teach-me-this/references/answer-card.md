# Answer card: how to write one

An answer card is the tutor's private plan for one paper. It holds 2–3 exercises. For each exercise it has the material to give, the task, a rubric fixed before the learner answers, and the paper's answer to reveal afterwards.

Worked examples are in `examples/`. Read the one whose paper type is closest:

| Example | Paper type | Exercises |
|---------|------------|-----------|
| `sosp24-lazylog.md` | new system, latency | problem · solution · experiments |
| `sosp25-rearchitecting-the-thread.md` | new system, architecture | problem · solution · experiments |
| `osdi21-pollux.md` | new system, scheduling / ML | problem · solution · experiments |
| `osdi23-triangulating-python-perform.md` | tool, measurement | problem · solution · experiments |
| `osdi16-early-detection-of.md` | tool, reliability (study-driven) | problem · solution · transfer |
| `sosp21-using-lightweight-formal.md` | verification / methodology | problem · solution · transfer |

## Why the card exists

The tutor decides three things in advance, before the learner is in front of it:

- **What the learner sees before answering.** A brief that already contains the answer makes the exercise pointless.
- **What counts as a good answer.** Without a rubric written in advance, the tutor scores by impression. The impression is generous, and it drifts towards whatever the learner said.
- **What to reveal afterwards.** It is short and prepared, so the reveal does not turn into a lecture.

## Abilities and rubric dimensions

Every rubric criterion is tagged with one of these dimensions. They are the same for every paper, so that the log can compare papers and show which dimension stays weak.

**Problem finding**
- `P-cause`: names the root cause, not a symptom ("the append waits for ordering", not "latency is high").
- `P-strawman`: names the obvious fix a practitioner would try first, and why it fails (the constraint it breaks, or the cause it misses).
- `P-signal`: combines several observations; sets aside the one that is unrelated.
- `P-goal`: states the goal so that a solution can be judged against it (what must be kept, what must improve).

**Solution design**
- `S-insight`: states the fact about the problem or workload that the design exploits.
- `S-mechanism`: the mechanism is concrete enough to build.
- `S-correct`: says why it is correct or safe, including the failure case that threatens it.
- `S-cost`: says what the design pays for, and when that cost is bad.

**Experiment design**
- `E-claim`: tests the headline claim against the strongest fair baseline.
- `E-cost`: tests the cost of the design and its worst case.
- `E-ablation`: isolates the contribution of each key idea.
- `E-refute`: a workload and metric whose result could refute the claim (tails, realistic load, not only the friendly case).

**Transfer**
- `T-assumption`: names which assumption of the paper the scenario changes.
- `T-insight`: judges whether the insight still holds, not only whether the mechanism can be copied.
- `T-evidence`: proposes a change and the evidence that would show it works.

## Picking the exercises

- **2–3 exercises.** The default is problem finding, then solution design, then experiment design. Use transfer instead of experiment design when the paper's evaluation is thin (no real baselines, preliminary numbers) or when the learner's log shows transfer is the weak ability.
- **Prefer the weak dimensions.** If `~/.teach-me-this/log.md` shows a dimension scored No or Partial on several papers, pick an exercise that has a criterion for it.
- **Each exercise trains one central idea.** The session does not cover the paper. When the paper has many parts (an architecture with five modules, a system with six optimizations), the solution exercise targets the one or two ideas that follow directly from the core problem. Everything else goes into "also tell".
- **Exercises chain.** The reveal of exercise N gives what the brief of exercise N+1 needs. The solution exercise starts from the paper's problem statement, not from the learner's.

## Writing the brief

The brief is the only material the learner gets. It shows what a practitioner would see. It never shows why.

For a **problem-finding** exercise: a short neutral background, then 3–5 numbered observations.
- One observation each, in at most two sentences. Do not join two unrelated things into one item.
- Concrete: the paper's numbers, a named tool or setting, a quoted complaint.
- No causal claim and no author vocabulary. "p50 put latency is 1.5 ms even at 5% load" is an observation. "Ordering on the critical path causes latency" is the answer.
- Strawmen. The brief may show one obvious fix being tried and failing (a benchmark, an incident, a refused proposal). For the other obvious fixes, show only the constraint, as a plain fact, and leave the learner to come up with the fix it rules out. The tutor notes list every strawman the rubric expects.
- At most one distractor: true and plausible, but unrelated. Mark it in the tutor notes.
- Do not write one observation per part of the paper. The observations serve the core problem only.
- Nothing in a brief may answer a later exercise. Never use an experiment that tests the paper's own claim (its system against baselines, or its ablations) as an observation. Measurements of existing systems that show the problem are fine. When a later rubric criterion builds on something a brief showed, its Yes must require more than repeating it.

For a **solution** exercise: the problem statement (the paper's, as revealed in exercise 1), then 3–5 facts about the setting that a practitioner could know, such as how applications use the API, what the workload looks like, or what the hardware does. Include the facts the insight rests on, mixed with neutral facts. Do not describe any mechanism.

For an **experiment** exercise: the formal summary of the problem and the method, with the paper's names, and the claims the authors make.

For a **transfer** exercise: one scenario that changes one assumption the paper relies on, or that moves its insight to another system.

## Writing the task

The task says what a complete answer contains, in general terms, with a length. It never names the paper's content. Examples:

- Problem: "In 4–6 sentences: what fails, the root cause, the obvious fix someone would try first and why it fails, and which observations support this. Say which observation, if any, is unrelated."
- Solution: "Describe your design: (a) the one fact about the problem or workload it exploits, (b) the mechanism, (c) why it is correct, including the failure case that most threatens it, (d) what it costs and when that cost is bad."
- Experiments: "List the 2–3 research questions the evaluation must answer. For the most important one, give the baselines, the workload, the metric, and the result that would refute the claim. For the others, one line each."
- Transfer: "Which assumption of the paper changes here? Does the insight still hold? What would you change, and what evidence would show that it works?"

## Writing the rubric

3–5 criteria per exercise, each tagged with a dimension. For each: what **Yes** looks like for this paper, and what counts as **Partial**. Write it so that another tutor, given the same answer, would give the same score.

- Yes needs the idea stated, in any words. "Something has to know which task a message belongs to" is Yes for "a persistent global coordinator is needed". "Maybe an index?" is not.
- List any known valid alternatives that also earn Yes.

## The hint

One hint per exercise, given only when the learner asks. It points at where to look ("look at what the writers do with the return value"). It never names the mechanism or the cause.

## The paper's answer

What the reveal shows, in 4–8 sentences, in plain words, now with the paper's terms. For the experiment exercise: what the paper ran, what it found, and where its evaluation falls short. Add the section numbers of the paper so the learner can read further.

## Common gaps

Typical differences between attempts and the paper. For each, the one follow-up question to ask in the gap analysis.

## Template

Section names are fixed so the tutor can find things.

```markdown
# <Paper title>
<Venue'Year> · <authors / institution> · <link>
Paper type: <new system | tool | measurement | verification | design article | ...>

## Dissection
- Background: <what the field looks like>
- Problem: <the one problem, as the authors would state it>
- Challenges: <why it is hard; what breaks the obvious approaches>
- Solution: <the key ideas, each as insight → design → which failure it removes>
- Evidence: <the main results, with numbers>

Safe background (may be explained whenever asked): <concepts>
Protected terms (not before the reveal of exercise N): <term (N)>, ...

## Exercise 1: <ability> — <one line>
### Brief
<background and material, as given to the learner>
Tutor notes: <what each item points at; which one is the distractor>
### Task
<what a complete answer contains, with a length>
### Hint
<one hint>
### Rubric
1. [<dimension>] <criterion>. Yes: <...>. Partial: <...>.
2. ...
### Paper's answer
<4–8 sentences; section numbers>
### Also tell
<parts of the paper this session does not train, a few lines each; what the next brief needs>
### Common gaps
- <gap> → <follow-up question>

## Exercise 2: ...
(same sections)
```
