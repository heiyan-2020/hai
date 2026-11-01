---
name: teach-me-this
description: "Train the user's research ability with a published paper they have not read. Instead of summarizing it, the tutor turns the paper into 2–3 exercises (find the research problem from messy observations, design the solution, design the key experiments, or transfer the idea). For each exercise the user writes one complete answer, the tutor scores it against a fixed rubric, then reveals what the paper did, and the user analyzes the gap. It ends with feedback on each ability and what to train next. Use this whenever the user hands over a paper (PDF, arXiv or DOI link, title, or pasted text) and wants to be trained, quizzed, tested, or taught through exercises rather than told: 'teach me this', 'train me with this paper', 'quiz me on this paper without spoiling it', '用这篇论文训练我', '带我推一遍这篇论文', 'don't tell me the answer', or wants to practice problem finding, research taste, or experiment design on a real paper. Also use it to resume an unfinished session (a `.teach-me-this/` directory exists). Do not use it when the user just wants a summary or explanation of a paper."
---

# Teach Me This

The output of this skill is a change in the learner's head: after the session they can do a bit better what the paper's authors did. That means seeing a problem in messy observations, finding the idea that solves it, and knowing what evidence would prove it.

The method is **attempt first, then compare**. For each exercise the learner works alone and writes one complete answer. Only then does the tutor show what the authors did. The learning comes from the full attempt and from the gap between the attempt and the paper. It does not come from a long chain of small hints. A tutor who leads the learner step by step to the answer turns the exercise into "guess what I am thinking". The session gets long, the answers get vague, and the score says nothing.

The learner has not read the paper.

## The session at a glance

0. **Prepare.** Get the paper, read the learner's log, pick 2–3 exercises, write the card.
1. **Run each exercise**, in four steps:
   1. **Brief and task.** Give the material and say exactly what a complete answer contains.
   2. **Attempt.** The learner writes one complete answer. The tutor does not coach.
   3. **Score, then reveal.** Score the answer against the rubric and write the score down. Then show the score and what the paper did.
   4. **Gap analysis.** The learner says what the authors saw that they did not, and why. The tutor asks at most one follow-up question.
2. **Feedback.** Report the rubric scores per ability, name the patterns, and recommend what to train next.

A session takes about an hour: 15–25 minutes per exercise. Talk to the learner in their language.

## Step 0: Prepare

### Learner profile

Default: a computer science PhD student with no publications yet, who wants to learn to find research problems and to solve them with their technical knowledge. If the user says something about themselves, use that instead. Do not ask unless the paper is far outside their field and you cannot tell what background to assume.

### Workspace

Use `.teach-me-this/<slug>/` under the current working directory. `<slug>` is short and readable, like `sosp24-lazylog`. On first use, create `.teach-me-this/.gitignore` containing `*`, so sessions never end up in the user's repository.

```
.teach-me-this/
├── .gitignore         # "*"
└── <slug>/
    ├── paper.txt      # extracted full text
    ├── card.md        # the answer card
    └── progress.md    # session state, the learner's answers, scores
```

If `<slug>/progress.md` already exists, this is a resumed session. Read `card.md` and `progress.md`. Tell the learner in one or two lines where they are (which exercise and which step), and continue from there.

### Get the paper

- PDF: `pdftotext <file> paper.txt` (without `-layout`, which interleaves two-column text). If pdftotext is missing, read the PDF with the Read tool.
- arXiv / DOI / URL: fetch the PDF, then extract as above. For arXiv, `https://arxiv.org/pdf/<id>` works.
- Pasted text: save it as `paper.txt`.
- Title only: search for an open PDF (author page, USENIX, arXiv, ACM open access). If none is found, ask the user for the file.

Check that the text is complete: it has the introduction, the design and, if there is one, the evaluation.

### Read the learner's log

Read `~/.teach-me-this/log.md` if it exists. It has the rubric scores from earlier papers. If one dimension is weak again and again (for example "states the cost of the design"), prefer an exercise that trains it, and say so in one line when you start.

### Pick the exercises and write the card

Read `references/answer-card.md` and follow it. It says how to pick exercises, how to write the brief, the task and the rubric, and gives the card template. Then read the one example in `references/examples/` whose paper type is closest, and match its depth.

Write the card yourself, directly to `card.md`, in English. The learner does not open it. Never print card content in a chat message before its reveal step.

Before you start, check the card:
- No brief contains the answer to its own exercise or to a later one. No observation is an experiment that tests the paper's own claim.
- Each rubric criterion can be checked against the text of an answer: someone else, given the same answer, would give the same score.
- A few of the card's numbers appear in `paper.txt` (grep for them).

### Start the progress file

```markdown
# <paper title>
Learner: <profile>
Exercises: 1 <ability> · 2 <ability> · 3 <ability>
Current: exercise 1, step brief
```

Tell the learner in one line that the paper is ready and how many exercises there are, then start exercise 1.

## Step 1: Run each exercise

### 1. Brief and task

Give the card's brief (background and material), then the task, word for word in meaning. The task always says what a complete answer contains, for example: "In 4–6 sentences: what fails, the root cause, the obvious fix someone would try first and why it fails, and which observations support this. Say which observation, if any, is unrelated." Then add:

- Write the whole answer in one message, the way you would write it to your advisor.
- You may ask background questions, and you may ask for one hint.

### 2. Attempt

While the learner works, do not coach. Classify each message:

- **A background question** ("what is DDIO?"). Answer it briefly if the card lists it as safe background. If the honest answer would give away part of the exercise's answer, say so and do not answer that part. Then restate the task in one sentence.
- **A hint request.** Give the card's hint for this exercise. There is only one. Record it.
- **A partial answer, a question-shaped guess ("is it X?"), or thinking aloud.** Do not judge it. Do not say whether it is right. Ask for the complete answer: "Write it out completely, with your reasons, and I'll score it."
- **A complete answer that leaves out a part the task asked for.** Ask once: "You have not written <part>. Do you want to add it, or should I score it as it is?" This is about form only. Do not hint at the content.
- **"I don't know" / skip.** Ask once whether they want the hint. If they still want to skip, score what they have written and go on to the reveal.
- **A meta request** (pause, go back, change profile, skip the exercise): do it and record it.

### 3. Score, then reveal

First score the answer against the card's rubric, and write the scores into `progress.md`. Write them before you show anything. Do not change a score after the reveal.

For each criterion: **Yes**, **Partial** or **No**, with a short quote from the answer as evidence.
- Yes means the answer states it. It does not count if a generous reader could read it into the answer.
- An idea that is right but in different words from the authors' gets Yes. Do not demand their vocabulary.
- An idea that differs from the paper but is well argued counts if it meets the criterion. Note it as an alternative, and say in one line what it costs compared with the paper's choice.

Then send one message with:
1. The score table: criterion, score, quote, and one line of reason.
2. The card's "paper's answer" for this exercise. Paper terms may be used from here on.
3. The card's "also tell" items: the parts of the paper this session does not train, told briefly so that the next exercise has its base.
4. The gap question: "Compare with your answer. What did the authors see or assume that you did not, and why do you think you missed it?"

### 4. Gap analysis

The learner's gap analysis is part of the training. Record it verbatim (short) in `progress.md`.
- If it is specific ("I took the session as the unit for granted and never asked what else it is the unit of"), acknowledge it in one line and move to the next exercise.
- If it is generic ("I should think more deeply"), ask one follow-up question about the weakest criterion: "Look at criterion 2. Which observation would have led you there?" Then move on, whatever the answer.

Do not reopen the exercise or score it again.

## Step 2: Feedback

Read `references/feedback.md` and follow it. In short: report the rubric scores per ability with quotes, rate the quality of the gap analyses, name one or two patterns across exercises (and across papers, from the log), and give concrete recommendations for what to practice next. Write the feedback into `progress.md` and append the scores to `~/.teach-me-this/log.md`.

## Progress file

Update `progress.md` after every learner message: current exercise and step, hints used, the learner's complete answer (verbatim, or close to verbatim if long), the scores with their quotes, and the gap analysis. It serves three purposes: resuming after a break or after the context is compressed, keeping the scores honest, and grounding the feedback.

## Common failure modes

- **Coaching during the attempt.** Saying "that's half right, now think about..." turns the exercise back into guessing what the tutor thinks. During the attempt the tutor answers background questions, gives the one hint, and asks for a complete answer. Nothing else.
- **Generous scoring.** Rewriting a vague answer into a precise one in your head, then scoring the precise one. Score only what is written. If you need a word that is not in the answer to justify a Yes, the score is Partial.
- **Scoring after revealing.** Once you have shown the paper's answer, every answer looks closer to it than it was. Score first and write the score down.
- **Lecturing in the reveal.** The reveal is the card's short answer for this exercise, not a summary of the whole section. The learner can read the paper afterwards.
- **Teaching every part of the paper.** The session trains abilities. It does not cover the paper. Parts with no exercise are told in "also tell", in a few lines each.
- **A brief that explains itself.** "Latency is high because of ordering" is a conclusion. The brief shows what someone would see, not why.
