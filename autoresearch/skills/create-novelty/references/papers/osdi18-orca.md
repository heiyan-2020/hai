# Orca: Differential Bug Localization in Large-Scale Services
OSDI'18 · Bhagwan, Kumar, Maddila, Philip / Microsoft Research India · Full text: https://www.usenix.org/system/files/osdi18-bhagwan.pdf (camera-ready) · Selected: Best Paper

**One sentence**: Alert text and the culprit code often share identifiers. So using the symptom as a search query, and searching only the changes in this deployment, can localize a bug to a commit.

## Problem
A large email service, Orion (a pseudonym), has hundreds of commits per day. One build can contain more than 200.
The on-call engineer (OCE) must find the culprit commit and revert it fast. They can only pick suspect commits from experience, ask the author, and move on to the next one if wrong.

## Strawman / Baseline
- **OCE checks commits one by one**: On average they look at half the commits of a build → median 22.75 and mean 28.9 over 48 bugs.
- **IR-based bug localization** (match a bug report against past reports, localize to a file) → Assumes the system is similar to the past, but Orion's module dependencies change 1–3% per month. It also only reaches file level.
- **Statistical debugging, delta debugging, git bisect** → Need instrumentation or repeated test runs. But production bugs often appear only for certain clients, regions, or heavy load.
- **Differential static analysis (SymDiff)** → Compares two program versions against given properties. A large service cannot list all properties, and the analysis does not scale to it.
- **Text search in code**: Search whole files → each file changes only about 20 lines on average, and the other few hundred lines cause false matches. Search only changed lines → the matching word is often in the name of the changed function (such as migrat).
- **Search only the build that shows the symptom**: The culprit commit can be in an earlier build (for example, the symptom is in a build with 160 commits, but the root cause is in the previous build).
- **Naively also search earlier builds** → More candidates. Several commits match the same words, so ties and false matches increase.

## Novelty
1. **Symptoms and causes share words, and the candidate set is only recent changes**
   Insight: Words in probe names, exception text, and user complaints often appear in the component names, function names, data types, or protocol names of the culprit change (such as Imap, suggest). And the question is only "which of these new commits", which needs no semantic understanding or past bugs.
   So: Build a search engine with commits as documents and symptoms as queries. Index only the AST diff: the **names** of the added, deleted, or modified entities (class/method/reference, etc.), plus the changed lines. Word weights use IQF (inverse query frequency): the rarer a word is in about 8 million past alerts, the higher its weight. So words like Probe and Exception are down-weighted automatically.
   It does not require reproduction or similarity to the past, so it avoids the root causes of the IR and dynamic methods. It has fewer false matches than whole-file search, and it still catches function names outside the changed lines.
2. **Builds derive from each other, so the search can widen along the derivation chain**
   Insight: Builds are promoted ring by ring (a ring is a group of machines running the same build), and new commits are added inside a ring too. So except for backports, each build has only one parent build.
   So: From the build that shows the symptom, walk back along the derivation chain to the origin build in Ring 0. All commits and backports on the path become candidates. This fills the blind spot of "search only the current build".
3. **After widening the search, break ties with commit risk**
   Insight: When word matches cannot tell commits apart, features of the commit itself (who wrote it, what it changed) can still separate risk.
   So: Train a regression tree on about 93,000 commits. It predicts risk from developer experience, file ownership, code hotspots, and change complexity. Use this as the second sort key.

## Evidence
- End to end: On 48 bugs whose root cause was worked out by hand, top-10 recall is 77% (37/48), MRR 0.42, and a query takes 5.97 s on average. Commits the OCE must check: the median drops from 22.75 to 3.5 and the mean from 28.9 to 9.4 (3×).
- Novelty 1 → No direct ablation: no comparison with whole-file search, file-name-only search, plain-text diff, or IR tools. Matching words: component names 14, feature words 17, protocols 4, data types 2.
- Novelty 2 → Adding the derivation graph raises recall from 0.69 to 0.77 (4 more found). For these 4 bugs, the commits to check drop from 59.4 to 1.25 on average, but MRR drops from 0.44 to 0.38.
- Novelty 3 → Adding risk ranking brings MRR back to 0.42, and top-10 recall stays the same.
- Gaps: The 48 bugs are the subset whose root cause could be completed by hand. The "no Orca" effort is estimated as randomly checking half a build, not measured on experienced OCEs.

## When it applies
The symptom must contain code-related specific words. It cannot find performance problems such as high CPU or OOM, or problems where a configuration change triggers old code (these are 1 and 4 of the 11 failures).
