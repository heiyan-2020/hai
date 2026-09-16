---
name: aba
description: >-
  Consolidate corrections into the current intended result instead of appending
  conversational edit history to the deliverable. Use when revising an answer,
  document, plan, or implementation after feedback, especially when an unwanted
  addition survives as a negation, version label, disclaimer, or obsolete framing.
  Preserve change history when the user requests it or it matters to using the result.
---

# ABA

Deliver the current intended state. Do not make the user read the operations that
got you there.

## The meme

用户要番茄炒蛋，LLM 端来番茄炒肉加牛腩。用户问为什么加牛腩，LLM 说：
“你说得对，番茄炒蛋不应该加牛腩，需要我重新做吗？”用户同意后，LLM 又端来：
“你好，这是番茄炒蛋（去牛腩版）。”

The correction became another append-only entry. The intended dish is simply
“番茄炒蛋”; the assistant's unrequested beef is not a feature of its identity.
And removing beef is insufficient if the dish still lacks eggs.

## Merge the state

- Reconstruct the current request from the original goal and the user's accepted
  changes. Later corrections replace the parts they address; earlier requirements
  that still apply remain in force. Your own mistaken additions are not requirements.
- Revise the affected deliverable itself. Replace or delete superseded content and
  reconcile dependent wording, examples, names, and behavior within the task's scope.
  Appending a correction beneath an unchanged wrong answer does not complete the edit.
- Check the whole result against the current request, not just the last complaint.
  Feedback naming one symptom does not endorse the rest of your previous output.
- Present the result on its own terms. Drop labels such as “X removed,” “corrected
  edition,” or “now without Y” when they only memorialize your detour. Do not turn an
  abandoned approach into a permanent warning, heading, option, or selling point.
- When the correction and authorization are clear, carry it through. Do not add a
  “shall I fix it?” turn merely to reconfirm the work the user already requested.

## Keep meaningful history and constraints

This is about integrating edits, not hiding mistakes or erasing evidence. Explain
what changed when asked, and retain required audit records, unresolved limitations,
or consequences that affect the user's decisions. Keep any necessary change summary
separate from the deliverable. Do not imply that work was fixed or verified unless it was.

An explicit user constraint still belongs in the result when useful. A requested
beef-free menu may need that label; accidentally adding beef to scrambled eggs does
not create such a requirement. Likewise, an actual revision log or migration guide
needs history. Choose based on the user's task, not a blanket ban on negative wording.

## Before delivering

Ask: if I had received the consolidated request at the start, would this result still
have this title, explanation, or caveat? If its only purpose is to narrate my mistake,
remove it. Then check that the underlying work, not just its description, matches.
