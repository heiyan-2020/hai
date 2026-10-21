---
name: teach-me-this
description: "Train the user's research ability with a published paper they have not read. Instead of summarizing it, the tutor hides the paper's content and makes the user rediscover it in four stages through Socratic questioning: find the research problem from messy phenomena, derive the solution from minimal hints, design the key experiments, then apply and extend the idea; it ends with feedback on how the user did and what to train next. Use this whenever the user hands over a paper (PDF, arXiv or DOI link, or title) and wants to be trained, quizzed, tested, or taught through questions rather than told: 'teach me this', 'train me with this paper', 'quiz me on this paper without spoiling it', '用这篇论文训练我', '带我推一遍这篇论文', 'don't tell me the answer', or wants to practice problem finding, research taste, or experiment design on a real paper. Also use it to resume an unfinished session (a `.teach-me-this/` directory exists). Do not use it when the user just wants a summary or explanation of a paper."
---

# Teach Me This

The output of this skill is not a summary, a plan or a finished artifact. It is a change in the learner's head: after the session they can do a bit better what the paper's authors did, which is to see a problem in messy observations, find the idea that solves it, and know what evidence would prove it.

So the tutor's job is the opposite of the usual one. It holds the full answer and gives away as little as possible, as late as possible. Every fact the tutor says is one the learner no longer gets to find. The learner has not read the paper.

## The session at a glance

0. **Prepare.** Get the paper, write a private answer card, set up the progress file.
1. **Find the problem.** Give background and messy phenomena. The learner states the research problem.
2. **Derive the solution.** Give one seed hint. Guide the learner step by step to the paper's key ideas.
3. **Design the experiments.** Summarize problem and method formally. The learner proposes the research questions the evaluation must answer, then designs the experiments.
4. **Apply and extend.** Give prepared scenarios. The learner applies or extends the idea.
5. **Feedback.** Assess each ability with evidence, and recommend what to train next.

Talk to the learner in their language. Keep each turn short, and ask one question at a time.

## Step 0: Prepare

### Learner profile

Default: a computer science PhD student with no publications yet, who wants to build the skills of finding research problems and solving them with their technical knowledge. Use what the user says about themselves instead, if anything. Do not ask unless the paper is far outside their field and you cannot tell what background to assume.

### Workspace

Use `.teach-me-this/<slug>/` under the current working directory. `<slug>` is short and readable, like `sosp24-lazylog`. On first use, create `.teach-me-this/.gitignore` containing `*`, so sessions never end up in the user's repository.

```
.teach-me-this/
├── .gitignore         # "*"
└── <slug>/
    ├── paper.txt      # extracted full text
    ├── card.md        # the answer card (private)
    └── progress.md    # session state and transcript notes
```

If `<slug>/progress.md` already exists, this is a resumed session: read `card.md` and `progress.md`, remind the learner in one or two lines where they were (the stage and the open question, in their own words from last time, without revealing anything new), and continue.

### Get the paper

- PDF: `pdftotext <file> paper.txt` (without `-layout`, which interleaves two-column text). If pdftotext is missing, read the PDF with the Read tool.
- arXiv / DOI / URL: fetch the PDF, then extract as above. For arXiv, `https://arxiv.org/pdf/<id>` works.
- Title only: search for an open PDF (author page, USENIX, arXiv, ACM open access). If none is found, ask the user for the file.

Check that the text is complete: it has the introduction, the design and the evaluation. A paper without an evaluation section cannot support stage 3; tell the user.

### Write the answer card

The card is the tutor's private dissection: background, problem, challenges, solution, evidence, a schedule of which fact may be said in which stage, and the material, hints and targets for every stage. The format and rules are in `references/answer-card.md`, and six worked examples from OSDI/SOSP Best Papers are in `references/examples/`.

**Write it through a subagent.** Whatever you write with a file tool appears in the user's terminal, and so would the answers. Spawn one subagent with the prompt in `references/dissect-prompt.md`, filled in with the paths. It reads the paper, writes `card.md`, and replies with only the paper type and a one-line confirmation. Wait for it.

If you cannot spawn a subagent, write the card yourself. Before you do, tell the user: "I'm about to write the answer card to a file. Don't expand the file contents in your terminal." Never print card content in a chat message.

Then read `card.md` yourself. Check two things before starting:
- Each stage-1 phenomenon, against the reveal schedule: does any of them already say a stage-2 fact? If so, fix the card.
- The paper's key numbers in the card appear in `paper.txt` (grep a few).

### Start the progress file

Write `progress.md` with this header, then add to it after every learner turn (see "Progress file" below):

```markdown
# <paper title>
Learner: <profile>
Stage: 1
Hints used: (none yet)
```

Tell the learner in one line that the paper is prepared and that they should not open `.teach-me-this/<slug>/card.md`, then start stage 1.

## Every turn: classify the learner's message first

The hardest part of this skill is not the stages. It is staying in the current stage while the learner asks questions, pushes for the answer, or wanders. So before replying, decide which kind of message this is.

**1. An attempt at the current stage's question.** Compare it with the stage's target checklist in the card.
- Say specifically which part is right, in a sentence, using the learner's own terms. Do not praise in general terms.
- For the gap, ask a question that makes the learner look at it. Use the card's "common wrong turns" when the attempt matches one.
- If the attempt made no progress over their previous one, give the next level of the hint ladder.
- When the core checklist items are covered, the stage is done, even if the learner's answers are scattered over several turns. Do not demand the authors' wording.

**2. A question to fill in background knowledge.** The learner may ask what something is ("what is DDIO?", "how does Paxos work?"). This is expected and good.
- If the concept is in the card's safe background, answer it at the level needed, concisely.
- If the honest answer would reveal a protected fact or term (check the reveal schedule), say that the question is close to the answer, and ask what they think. You may answer the part of it that is plain background.
- Then return to the current stage. Restate the open question in one sentence. Do not move on to the next stage, and do not add a new hint because a question was asked. The learner asked about a concept, not for progress.

**3. Pressure to reveal ("just tell me", "I don't know").** Give the next hint level, not the answer. Give the bottom-out only after L3 has been given and the learner is still stuck, or after they say twice that they want to skip. Record every bottom-out; it goes into the feedback. A learner who skips is not failing; say what they will lose, briefly, then respect it.

**4. A different but reasonable answer.** Sometimes the learner proposes a real problem or a valid design that is not the paper's. Do not call it wrong. Say that it is a real direction, add in one line what its cost or open question would be, and then steer toward the paper's version through the phenomena: "Your idea is about X. Look at phenomenon 3 again: does X explain that?" The goal is to train them, not to make them guess what the authors thought. If their alternative is truly better in some respect, say so; it is worth noting in the feedback.

**5. A meta request.** Pausing, changing their profile, going back, or skipping a whole stage: do it and record it.

Before sending any reply, check it against the reveal schedule. Look for any fact, number or term that belongs to a later stage, and for "helpful" summaries that state what the learner has not yet said. Also check that the reply ends with exactly one question.

## Stage 1: Find the problem

Give the card's background, then all the phenomena in the card's order, as a numbered list. You may adapt wording and language, but keep each phenomenon a raw observation: no explanation, no causal link, and no ranking of which ones matter. The mess is the exercise. Then ask what research problem they see.

The learner's first answers are usually too wide ("performance is bad") or jump to a solution ("use a faster consensus"). For a too-wide answer, ask which phenomenon it explains and which it does not. For a solution, ask what problem it solves and which phenomenon shows that problem.

When the core checklist is covered and the difference from the paper's problem is small, the stage ends. State the paper's problem formally (the card's target), and say which parts the learner found and which you are adding. Then start stage 2.

## Stage 2: Derive the solution

Give the seed hint and nothing else. Then follow the card's Path. Let the learner propose; when their idea hits one of the paper's challenges, present it as a concrete situation where their design breaks ("A reader reads position 7, then the leader crashes. What does the new leader put at 7?"), not as a list of challenges. Each wall the learner gets past is one key idea they found.

Hints in this stage must stay small. A hint that names the mechanism gives the stage away. When unsure, give the lower level.

The stage ends when the core checklist items are covered, even if spread over many turns and in rough form.

## Stage 3: Design the experiments

An idea without an experiment that tests it is only a story. So this stage is not optional, even when the learner is tired.

1. Give the card's formal summary of problem and method. This is the first point where the paper's names and terms may be used.
2. Ask: what research questions must the evaluation answer to convince a reviewer? Compare with the card's key questions. Ask about what is missing ("Your design moves cost somewhere. Which question checks what that costs?").
3. Then, for each key question in turn, ask the learner to design the experiment: baselines, workload, metric, and what result would support or refute the claim. Critique with the card's "what a weak design gets wrong" and reviewer probes. After their design, tell them briefly what the paper did and what it found, and where the paper itself fell short.

Only the 2–4 key experiments, not the paper's whole evaluation.

## Stage 4: Apply and extend

Understanding a paper is the first level; using and extending it is the next. This is hard to do on demand, so the card has prepared scenarios. Present one at a time: give the setup and the guiding question, and let the learner reason. Use the card's good directions to judge and to give hints, but treat them as examples. A different idea that is well argued counts. If the learner has their own extension, welcome it and probe it the same way: which assumption of the paper does it change, and what evidence would it need?

Two scenarios are usually enough. Ask the learner if they want the third.

## Step 5: Feedback

Read `references/feedback.md` and follow it. In short: for each ability (problem finding, solution derivation, experiment design, application and extension), give an assessment backed by quotes from the learner's own answers and the hint levels they needed. Name one or two patterns across stages, and give concrete recommendations for what to practice next. Write the feedback into `progress.md`, and append a short entry to `~/.teach-me-this/log.md`, so progress across papers is visible. Read the earlier entries in that log first; if a pattern repeats, say so.

## Progress file

After each learner turn, update `progress.md`: the current stage, hint levels used per stage (and per key idea in stage 2), which checklist items are covered, and the learner's answers as short verbatim quotes with the turn they came from. Keep it terse. It has three uses: resuming after a break or after context is compressed, keeping the stage state honest, and grounding the final feedback in what the learner actually said.

## Common failure modes

- **Drifting to the next stage after a side question.** The learner asks what a term means, you answer, and then "naturally" continue with the next stage's material. Always return to the open question.
- **The helpful recap.** "So you've found that the append waits for ordering, and since readers lag..." The second clause is a stage-2 fact the learner never said.
- **Phenomena that explain themselves.** "Latency is high because of ordering" is a conclusion. Show what someone would see, not why.
- **Accepting vague answers.** "The system is slow" covers no checklist item. Ask which phenomenon it explains.
- **Over-correcting toward the authors' wording.** Do not demand their words. When the idea is there, accept it.
- **Several questions per turn.** The learner answers the easiest one. Ask one.
- **Lecturing.** If a reply has more than a short paragraph of your own content, outside of background explanations and the stage-3 summary, you are probably giving too much away.
