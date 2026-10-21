---
name: create-novelty
description: "Design the novelty and the evaluation of a systems research project so it could stand as an OSDI/SOSP-level paper. Given a research topic, direction, or rough idea, work out the concrete problem, the strawman and baselines down to their root cause, an insight (a fact about the problem that baselines miss) that makes the design feel obvious in hindsight, the design it enables, related-work deltas, and the experiments and per-novelty ablations a top-venue reviewer expects. Grounded in 100 dissected OSDI/SOSP papers (2016–2026). Use this whenever the user asks what would make an idea publishable at OSDI/SOSP/NSDI/EuroSys/ATC or another top systems venue, wants to find or sharpen the novelty of a systems project, asks 'how do I turn X into a paper', wants a research proposal or paper plan for a systems topic, or asks how to design experiments/ablations to prove a systems idea, even if they never say 'novelty'."
---

# Create Novelty

Turn a systems research topic into a paper plan whose novelty a reviewer would accept, and whose experiments would convince them.

## The standard

A top-venue novelty is not a component list, a slogan ("decouple X from Y"), engineering effort, or "first to apply X to Y". It is a causal chain:

> **Insight**: a fact about the problem — workload, hardware, semantics, or usage — that existing approaches do not exploit.
> → **Design**: something this fact makes possible that baselines could not or dared not do.
> → **Why it works**: it removes the specific root cause for which the strawman/baselines fail.

The test: hide all system and component names, and read only the problem, why the baselines fail, and the insight. A person who understood the problem should be able to guess the design direction and say "of course, that is how it should be done". If they cannot, what you have is a mechanism, not an insight; go back and ask what fact lets the mechanism work, or what obstacle stopped prior work.

Hindsight-obvious is not the same as obvious in advance. A good insight usually needed one of: a measurement nobody had made, a re-reading of what the application actually requires, a hardware or workload change that broke an old assumption, or a technique borrowed from another field. Name which one applies; it is also your answer to "why didn't anyone do this before?".

## Reference library

All files are in `references/`. Read them as needed; do not load everything up front.

- `novelty-patterns.md` — 14 insight archetypes distilled from the 100 papers. Each has questions to ask about a new topic, where such facts come from, examples, and when the archetype breaks. This is the main thinking tool. Read it before generating insights.
- `experiment-playbook.md` — how top papers prove each novelty (the evidence ladder, what counts as evidence per paper type), and the weaknesses reviewers attack. Read it before writing the evaluation plan.
- `catalog.md` — one line per paper: id, venue-year, why selected (Best Paper / highly cited / community favorite), one-sentence insight, archetypes. Grep it to find precedents for the user's area or for an archetype.
- `papers/<id>.md` — the full dissection of each paper (Problem, Strawman / Baseline, Novelty, Evidence with ablations and gaps, When it applies). Read the 3–6 most relevant ones in full: the closest precedents in the user's area, plus the best examples of the archetypes you are using. Each entry's header links to where the paper was published.
- `fulltext/<id>.txt` — the full text of each paper, extracted from its PDF. Grep it when an entry does not answer a question (an exact number, a design detail, how an experiment was set up); do not read whole papers.
- `cold-reader-prompt.md` — the prompt for an independent reviewer (step 6).

The library is a calibration and pattern source, not a related-work survey. It stops at 2026 and covers only OSDI/SOSP. Always search the web for recent work in the user's area (step 5).

## Workflow

Work through these steps in order. Steps 1–4 are thinking; write their results down as you go, because the final document is built from them.

### 1. Pin down the problem

Turn the topic into: who has the problem, in what setting, what goes wrong, and how much it costs (latency, cost, failures, developer time). A topic like "LLM agents and file systems" is a direction, not a problem.

- If the topic is broad, propose 2–3 concrete problem framings, say which you would pick and why (biggest pain × most likely to hide an unexploited fact), and continue with that one. Ask the user only if the choice depends on something only they know, such as access to production traces or hardware.
- Every top paper opens with a quantified pain. If you do not have the numbers, do not invent them. Write the motivation measurement that would produce them (what to run, on what workload, what result would confirm the problem), and mark the claim as a hypothesis until measured.

### 2. Strawman and baselines, down to the root cause

List what a smart engineer would try first (strawman) and what existing systems do (baselines: search the web; also grep `catalog.md`). For each one, write the specific situation in which it fails and why, the root cause, not "has limitations". Include the naive implementation of any obvious idea: if the obvious fix has a hidden cost, that cost is often where the second novelty lives.

The root causes you write here are what the novelty must answer. A novelty that answers no stated failure is not a novelty.

### 3. Generate candidate insights

Read `novelty-patterns.md`. For each archetype, ask its identification questions against this problem, and write down every candidate fact you find. Aim for 5–10 candidates across several archetypes before judging any of them. Generating several and then choosing beats polishing the first idea.

For each candidate, record:
- the fact, stated about the problem (not about your design);
- its status: known (cite a source), plausible but needs measuring (name the measurement), or speculative;
- the design it enables and which root cause from step 2 it removes;
- how the authors would have found it (measurement, semantics, hardware trend, borrowed technique, incidents).

Read 2–4 `papers/<id>.md` entries that use the same archetypes, to calibrate how sharp the fact needs to be and how the design followed from it.

### 4. Choose and build the novelty chain

Pick the candidate with the strongest combination of: removes the most important root cause, is true (or cheaply checkable), and is non-obvious before the fact but obvious after. Then:

- Write Novelty 1 as insight → design → which root cause it removes.
- Ask what new cost or obstacle the core idea creates: scale, consistency, overhead, a case where the fact does not hold. Add that as a strawman (the naive implementation of your idea) and make Novelties 2–3 the designs that remove it, each again backed by a fact. At most 3 novelties; ordinary engineering goes under "other design".
- State the applicability condition: when the insight stops holding and the approach fails. Reviewers respect authors who know their limits.

### 5. Check against related work

Search the web for the closest 3–5 prior works (top systems venues and arXiv, especially the last 2–3 years). For each: what it does, and the delta to your insight. If someone already published the insight, either sharpen it to what they missed or go back to step 3. Do not claim "first" unless you searched for it.

### 6. Cold-reader test

Have someone who has not seen your reasoning judge the chain. If you can spawn a subagent, give it `references/cold-reader-prompt.md` plus only your Problem, Strawman / Baseline and Novelty sections, without design names or your notes. Otherwise, re-read those sections as a skeptical reviewer. Revise any novelty that comes back as "mechanism without the enabling fact", "answers no stated failure", or "jargon", and rewrite every sentence it quotes as hard to read.

### 7. Design the experiments

Read `experiment-playbook.md`. Plan, in this order:

1. **Motivation measurement**: the experiment that shows the problem and the insight's fact are real (often the paper's Section 2). It is also the cheapest early test of the whole idea.
2. **End-to-end result**: workloads, scale, the strongest fair baseline (prefer real systems over reimplementations, same hardware, tuned), and the metric that matches the pain from step 1.
3. **One ablation per novelty**: remove that design or replace it with the strawman, holding everything else fixed. A knob sweep is not an ablation. If a novelty cannot be isolated, say so and explain what weaker evidence you will offer.
4. **Sensitivity and breaking point**: vary the property the insight depends on until the advantage disappears; this backs the applicability condition.
5. **Type-specific evidence**: for bug-finding, new bugs found under the same budget as competitors; for verification, proof effort and evidence that the proof rejects wrong code; for measurement studies, dataset coverage and whether findings generalize.

Then check the plan against the playbook's list of weaknesses that reviewers attack, and fix the ones that apply.

### 8. Kill criteria and first steps

Write which result would kill the idea (usually: the insight's fact turns out false or rare in real workloads) and the cheapest experiment that would reveal it. Order the work so that experiment runs first.

## Output

Write the result as a Markdown file in the user's working directory (e.g. `novelty-<topic-slug>.md`) and summarize it in chat. Write it in the user's language, headings included (the template below is in English). The body is structured like the library entries, so the user can compare it side by side with real OSDI papers. Everything a reader needs only to check or reproduce your reasoning goes into the appendix.

```markdown
# <working title>

**One sentence**: <problem + core insight, one sentence>

## Conclusion
<3–5 short sentences: the idea in plain words; the closest prior work and how this differs; the one fact still unproven, and the first experiment that settles it>

## Problem
<who, what setting, what goes wrong, how much; unmeasured numbers are marked as hypotheses (the measurement is in the appendix)>

## Strawman / Baseline
- **<approach>**: <what it does> → <when it fails and the root cause>

## Novelty
1. **<insight as a short title, not a component name>**
   Insight: … So: … This removes <which root cause>, because …
   Fact status: known (source) / needs measurement / speculative
2. …

Other design: <engineering that is not novelty, one line>

## Difference from recent work
- <work, venue year>: <delta, one line>

## Evaluation plan
- Motivation measurement: …
- End to end: …
- Novelty 1 → <ablation>: <expected result if the insight holds>
- …
- Sensitivity / breaking point: …
- Reviewer attacks closed in advance: <attack → the experiment or control that closes it, one line each>

## When it applies
<when the insight stops holding>

## Risks and first step
- Fatal result: …
- First experiment: …

## Appendix
### A. Assumptions and choices  <assumptions you made for the user, framings you considered>
### B. Measurement and experiment details  <procedures, datasets, thresholds, workloads, how each control is built>
### C. Related work details  <what each work does, with sources and what you did not check>
### D. Other candidate insights  <unpicked candidates, one line each with why not; the user may prefer one>
```

## Writing the document

The reader is a busy researcher. They want to know in a few minutes whether the idea is good, and what to do on Monday. Iteration showed that dense documents hide good ideas: when every sentence carries three citations, two hedges and a coined term, the reader cannot see the insight. Write for that reader:

- **Lead with the point.** The One sentence and the Conclusion must carry the whole idea. A reader who stops there should know what the insight is, why it is new, and what could kill it.
- **Make the body short by writing tighter, not by cutting items.** From One sentence to Risks and first step, aim for about 1500–2000 English words (3000–4000 Chinese characters), roughly two library entries; the Evaluation plan may add what it needs, one line per experiment. Shorten by using short sentences, and by moving procedures, sources, assumptions and side discussion to the appendix. Do not shorten by dropping items that carry the argument. The body keeps every strawman a novelty answers (including the naive version of your own idea), every closest prior work, and every experiment from step 7: the strongest baseline, one ablation per novelty, and each reviewer attack you closed. In an earlier version, writers who cut these to fit the budget lost the experiment design that reviewers value most.
- **One idea per sentence.** Aim for sentences under about 50 Chinese characters or 25 English words. Split long sentences and chains of clauses. Prefer active voice: say who does what.
- **Use words the reader already has.** Define each term of art in plain words the first time it appears. Do not invent names for ideas (noun stacks such as "write-path amplification attribution surface"). Say the idea in ordinary words. Use the same word for the same thing throughout.
- **Keep sources and hedges out of the flow.** In the body, cite with a short tag such as (Beluga, SIGMOD'26). Put arXiv numbers, quoted figures and "not checked in code" notes in appendix C. Mark a fact's status once, in its Fact status line, not in every sentence.
- **Format only when it helps.** Use a list for three or more parallel items. Use a table only for a real grid. Use prose for one or two points.
- **Keep exact facts.** Short is not vague. Keep numbers, names and conditions. Say plainly what is unknown.

Before you finish, read the body once as that reader. Fix any sentence you had to read twice and any term the reader has not seen. Check that the first two sections alone give the idea.

The chat summary is shorter still: the One sentence, the closest prior work and the delta, the first experiment, and the file path.

## Honesty rules

- Never invent numbers about the user's problem. A number is either cited (with source), measured by the user, or written as a hypothesis with the measurement that would produce it.
- Never state that a prior work does or does not do something without having looked. Say "not checked" if you did not.
- When citing a library paper as precedent, describe it as the entry does. The entries were written from the full papers and flag their own gaps.
- If the honest conclusion is that the topic has no OSDI-level insight yet, say so, and say what measurement or access would be most likely to reveal one. That is more useful than a dressed-up mechanism.
