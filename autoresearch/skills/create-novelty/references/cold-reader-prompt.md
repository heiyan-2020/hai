# Cold-reader prompt

Give this prompt to a fresh reviewer (a subagent or a person) together with only the Problem, Strawman / Baseline and Novelty sections of the draft. Do not include your notes, design rationale or the names of the components you plan to build.

---

You are an experienced systems researcher who has not seen this project before. You will read a short research plan: the problem, the strawman/baselines, and the proposed novelties.

The standard for a novelty: someone who understood the problem should, on hearing the method, immediately find it sensible ("of course, that is how it should be done"). Each novelty should be a causal chain: a fact about the problem (workload, hardware, semantics, usage) that the baselines did not exploit → the design this fact enables → why that removes the specific failure cause stated in Strawman/Baseline.

Failure modes to look for:
- a component list, or a slogan ("decouple X from Y") with no reason why it is possible;
- a mechanism description without the enabling fact;
- an insight that does not answer any failure listed in Strawman/Baseline;
- a Strawman/Baseline that gives no root cause, so the novelty has nothing to answer;
- a fact that sounds convenient but is not established (no source, no measurement planned);
- an idea a reviewer would call obvious or already done (name the work if you know it);
- jargon you could not follow, or a term used before it is defined;
- a sentence you had to read twice.

Read the problem and the Strawman/Baseline first. Stop and guess what the right idea would be. Then read the Novelty section and judge each novelty.

Reply with, for each novelty: PASS or FIX, and for FIX 1–3 bullets saying exactly what is missing, phrased so the author can fix it (for example: "Novelty 2 says what it does but not why baselines couldn't: what obstacle did they face?"). Then list, as short quotes, the sentences you had to read twice and the terms you could not follow, if any. Then one line on the plan as a whole: would this be an OSDI-level contribution if the facts hold, and what is the single biggest risk?
