# Answer card: how to write one

An answer card is the tutor's private dissection of one paper. The tutor writes it before the first question and never shows it. Every stage of the session is driven from it: what to show, which hint comes next, when an answer is close enough, and what must stay hidden until later.

Worked examples are in `examples/`. Read at least one before writing a card, preferably the one whose paper type matches the paper at hand:

| Example | Paper type | What its stage 1 looks like |
|---------|------------|-----------------------------|
| `sosp24-lazylog.md` | new system, latency | a trace, a forbidden config knob, a consumer's requirement |
| `sosp25-rearchitecting-the-thread.md` | new system, architecture | hardware counters, a failed tuning attempt, scaling curves |
| `osdi21-pollux.md` | new system, scheduling / ML | job completion times, users' habits, training curves |
| `osdi23-triangulating-python-perform.md` | tool, measurement | confusing profiler output, overhead numbers |
| `osdi16-early-detection-of.md` | tool, reliability (study-driven) | postmortems, ticket statistics, an audit |
| `sosp21-using-lightweight-formal.md` | verification / methodology | review questions nobody could answer; no speedup plots in stage 3 |

## Why the card exists

Two failures ruin this kind of training, and both come from improvising during the conversation:

- **Leaking.** Under pressure ("just tell me"), or while answering a side question, the tutor says a fact that belongs to a later stage. Once said, it cannot be unsaid, and the learner never gets to find it.
- **Drifting.** Without a fixed target, the tutor accepts a vague answer, or keeps pushing toward its own idea rather than the paper's.

The card fixes both in advance: a reveal schedule says which fact may be said in which stage, hints are written before the learner is under pressure, and each stage has a target with a checklist.

## Rules that hold across the whole card

- **Reveal schedule.** Every fact that carries the paper's idea is assigned to the earliest stage where it may be said. Before writing each stage's material, check it against the schedule. A phenomenon in stage 1 that already states the stage-2 insight makes stage 2 pointless.
- **No author vocabulary before its stage.** The paper's coined terms ("lazy ordering", the system name) name the answer. Use plain words until the stage that reveals them.
- **Ground everything in the paper.** Numbers, baselines and observations come from the paper's text. Where a phenomenon is a re-telling (the paper states a measurement; the card describes how an engineer would run into it), keep the numbers the paper reports. Do not invent results.
- **Language.** Write the card in English. The tutor speaks to the learner in the learner's language.

## Template

Copy this structure. Section names are fixed so the tutor can find things; the content under each is free-form.

```markdown
# <Paper title>
<Venue'Year> · <authors / institution> · <link>
Paper type: <new system | tool | measurement | verification | ...>
> Spoiler: this card dissects the paper. Do not read it if you want to train on this paper.

## Dissection
- Background: <what the field looks like; what a reader must know>
- Problem: <the one problem the paper solves, as the authors would state it>
- Challenges: <why it is hard; what breaks the obvious approaches>
- Solution: <the key ideas, each as insight → design → which failure it removes>
- Evidence: <the main results, with numbers>

## Reveal schedule
| Fact | Earliest stage |
|------|----------------|
| ... | 1 / 2 / 3 / 4 |

Protected terms (do not say before the stage shown): <term (stage)>, ...
Safe background (may be explained whenever asked): <concepts>, ...

## Stage 1: Find the problem
### Background to give
<A short, neutral setup. Describe the world the learner works in, not the paper's argument.>

### Phenomena
<4–6 numbered observations, in the order shown to the learner. See "Writing phenomena" below.>
Tutor notes: <which phenomena are load-bearing, which one is the distractor, and what each is meant to point at>

### Hint ladder
- L1: <a nudge about where to look>
- L2: <a sharper question that narrows the space>
- L3: <a near-statement that leaves only the final step to the learner>
- Bottom-out: <state the problem; used only after L3 fails or the learner explicitly gives up>

### Target
<The problem statement, 2–4 sentences.>
Checklist (the stage ends when the core items are covered in the learner's own words):
- [core] <element>
- [core] <element>
- [detail] <nice to have>

### Common wrong turns
- <a plausible but wrong framing> → <the question that redirects it>

## Stage 2: Derive the solution
### Seed hint
<The single hint given at the start of stage 2. It points at where the insight comes from, never at the mechanism.>

### Path
<The likely route from the learner's first idea to the paper's design. For each step: the naive move the learner is likely to make, the obstacle (from the paper's challenges or rejected alternatives) to present as "your idea hits this wall", and what getting past it looks like.>

### Hint ladder
<L1–L3 and bottom-out, as in stage 1. One ladder per key idea if the paper has several.>

### Target
<The key ideas, each as insight → design → why it removes the failure.>
Checklist:
- [core] ...
- [detail] ...

## Stage 3: Design the experiments
### Summary to give
<The formal statement of problem and method, given at the start of stage 3. This is where protected terms may first be used.>

### Key research questions
<2–4 questions the evaluation must answer, each with why a reviewer would insist on it. Pick the ones that test the core claims; leave out the paper's secondary experiments.>

### Key experiments
<For each question: baselines, workload, metric, the paper's setup and result, and what a weak design gets wrong (wrong baseline, unfair comparison, cherry-picked workload, missing tail metric, missing ablation).>

### Reviewer probes
<Questions to ask about the learner's design, from a reviewer's point of view.>

## Stage 4: Apply and extend
### Scenarios
<2–3 scenarios. Each changes one assumption the paper relies on, or moves its insight to another system. For each: the setup to give, the guiding question, and one or two directions that would count as good answers. These are not the only valid answers.>
```

## Writing phenomena

Stage 1 trains the skill of turning raw observations into a research problem. The phenomena are the whole exercise, so they deserve the most care.

**Write what someone would actually see.** A phenomenon is what you notice while running an experiment, operating a system, reading a trace, or hearing a complaint. "p50 put latency is 1.5 ms even at 5% load" is a phenomenon. "Ordering on the critical path causes high latency" is the authors' conclusion; it is the answer, not a phenomenon.

Checks for each phenomenon:

- **No causal claim.** It reports what happened, not why. The learner supplies the why.
- **No author vocabulary.** Use plain words, never the paper's coined terms or its framing.
- **Concrete.** Numbers from the paper, a named tool or setting, a quoted complaint. Vague phenomena ("performance is bad") give the learner nothing to reason with.
- **Partial.** Each phenomenon shows one piece. The problem appears only when several are combined.

Checks for the set:

- **Messy order.** Do not present them in the order of the paper's argument. Real observations arrive out of order.
- **One distractor.** Include one observation that is true and plausible but unrelated to the problem (a GC pause, a misconfigured client). It trains the learner to separate signal from noise. Mark it in the tutor notes.
- **Constraints show up too.** If the problem has a constraint that rules out an obvious fix (durability, compatibility, cost), include a phenomenon where that constraint bites, so the learner discovers it rather than being told.
- **Nothing from stage 2.** Check the set against the reveal schedule. The facts that make the solution possible belong to stage 2's hints.

## Writing hints

Hints go from general to specific. Each level should leave the learner something real to do.

- L1 points at where to look ("look at what the writers do with the return value").
- L2 asks a question that narrows the space ("when do readers actually read?").
- L3 nearly states the answer and leaves the last step ("what if the order only had to exist by the time someone reads?").
- Bottom-out states it. It is given only when L3 fails or the learner explicitly gives up, and the feedback records that it was used.

A stage can need more than one ladder. In stage 2 there is usually one per key idea, and later ladders are only reached after the learner has the earlier idea.

## Picking the key experiments

A paper's evaluation is broad. Pick the 2–4 questions that test its core claims: usually the headline benefit, the cost the design pays for it (and the worst case where that cost shows), and one ablation per key idea. For each, note what a weak design would get wrong; this is where most of the learner's feedback in stage 3 comes from.
