# Dissector prompt

Give this prompt to one subagent, with the placeholders filled in. The subagent writes the answer card; the tutor never writes card content where the learner can see it.

---

You are preparing a private answer card for a tutor. The tutor will train a learner (<learner profile>) to rediscover a published paper they have not read: first its research problem from raw phenomena, then its solution from minimal hints, then its key experiments, then applications and extensions. The learner must not see the card, so do not quote any of its content in your reply.

Paper text: <workspace>/paper.txt
Write the card to: <workspace>/card.md

Read, in this order:
1. `<skill-dir>/references/answer-card.md`: the template and the rules. Follow the template exactly; its section names are fixed.
2. The worked example in `<skill-dir>/references/examples/` whose paper type is closest to this paper (the table in answer-card.md lists them). Match its depth and style. If the paper is unlike all of them, read two.
3. The paper text. The text was extracted from a PDF and may have broken lines or interleaved columns; read carefully. Read the introduction, motivation and background, design, and the evaluation's list of questions in full; grep for specific numbers.

What matters most:
- Stage 1 phenomena are the heart of the exercise. They read like what a practitioner in this area would actually see (tool output, measurements, incidents, complaints, a failed fix). Each has no causal claim, no paper vocabulary, and the paper's numbers. The set is in messy order, has exactly one distractor (marked in the tutor notes), and includes a phenomenon where a constraint that rules out the obvious fix bites. Nothing in stage 1 may give away a stage-2 fact: check every phenomenon against your reveal schedule.
- Every number and result comes from the paper. If you re-tell a measurement as a practitioner's observation, keep the paper's numbers. Do not invent results. If something is not in the paper, leave it out.
- Hints go from general to specific, and each level leaves the learner real work. Stage 2 has one ladder per key idea.
- Stage 2's Path uses the paper's real challenges and rejected alternatives as the walls the learner's naive ideas hit.
- Stage 3 picks only the 2–4 experiments that test the core claims, and says what a weak design would get wrong, including gaps in the paper's own evaluation.
- Use gender-neutral wording for any person in the phenomena.
- Write the card in English, in plain words and short sentences.

When done, reply with exactly two lines and nothing else:
Paper type: <type>
Card written: <path> (<N> lines)
