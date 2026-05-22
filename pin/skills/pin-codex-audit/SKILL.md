---
name: pin-codex-audit
description: >-
  Run an adversarial, independent audit of newly proposed pins and protocol
  data-lineage using Codex as a second pair of eyes. Use after pins are drafted
  and before grounding (Phase 6 of pin-aware-agent), or any time you want an
  outside check that a lineage description is actually true and that no silent
  regression was missed. Self-review by the same agent that wrote the code has
  blind spots — this skill closes them. Trigger on "codex audit the pins",
  "independent review of the lineage", or as part of the pin-aware-agent flow.
type: flow
user-invocable: true
---

# pin-codex-audit

Single-agent self-review is shallow: the agent that wrote the code treats its
own implementation as the default and cannot see what it normalized away. Codex
did not write this code — its independent reading is the point.

Two things make a Codex audit useful instead of slow and vague:

- **Codex must know the system, not the whole project.** It is briefed on what
  pins and protocols are, and told its job is narrow: check this diff against
  the *declared* pins and protocols, not audit the entire codebase.
- **Point Codex at the repo; do not paste everything in.** `codex exec` runs
  inside the repo and can read files and run `git diff` itself. Pasting
  pins.yaml + the protocol + whole scripts + a 600-line diff into one prompt is
  what makes the audit crawl. Hand Codex the briefing, the questions, and the
  file paths — let it read what it needs.

## Step 1 — Assemble the inputs as files (not pasted text)

You need three paths. Locate them; do not read their contents into the prompt.

- **Existing pins** — `pins.yaml` (project root or `.claude-research/`).
- **Proposed pins** — the pins drafted this task are not in `pins.yaml` yet
  (they land only at grounding). Write them to a temp file, e.g.
  `.claude-research/channels/<channel>/proposed-pins.yaml`, so Codex can read
  them.
- **Protocol(s)** — each `*-protocol.md` for the task.

The briefing Codex needs is fixed and lives at
`<PLUGIN_ROOT>/skills/pin-codex-audit/references/codex-briefing.md`, where
`<PLUGIN_ROOT>` is the root of this installed plugin.

## Step 2 — Two Codex calls, run in parallel

The four audit questions split into two independent groups. Issue both
`codex exec` calls **in the same turn** so they run concurrently — that roughly
halves the wall-clock. Each prompt = the briefing file + that call's questions +
the file paths to read. Run Codex with the project as its working directory
(`-C <project-root>`) so its file reads and `git diff` resolve.

**Call A — diff review** (needs the diff; reasoning effort `high`):

> Q1 MISSED REGRESSION — Run `git diff HEAD`. Is any pre-existing design
> decision silently weakened or reverted — something no existing pin covers, so
> the machine audit could not catch it? The existing pins are in `<pins.yaml>`.
>
> Q4 MISSING PIN — Does the diff introduce a load-bearing decision that deserves
> a pin, but none is among the existing pins (`<pins.yaml>`) or the proposed
> pins (`<proposed-pins.yaml>`)?

**Call B — consistency review** (needs current code state, not the diff;
reasoning effort `medium`):

> Q2 CLAIM HOLDS — For each pin in both `<pins.yaml>` and `<proposed-pins.yaml>`,
> read its `claim` and the actual code at its `code_locations`. Do not grade the
> pin's machine assertion — it is only a fast tripwire and may be shallow by
> design. Read the code logic yourself and judge one thing: does the design
> decision in the claim still genuinely hold in the code? If a pin's machine
> audit passed but you find its claim no longer holds, say so — that is the
> highest-severity finding, the tripwire let a real silent rollback through.
>
> Q3 FALSE LINEAGE — For each element in `<protocol path(s)>`, read its code
> `snippet` and the surrounding code in its `file`. Does the `nature` tag tell
> the truth about what the code actually does? Also confirm the snippet still
> appears in the file — a stale snippet means the lineage has drifted.

### Invocation — background runs + a Monitor, never a blocking wait

A plain `codex exec` prints nothing until it finishes, so a slow call is
indistinguishable from a hang. Three rules, all of them your job — never the
user's — make the audit observable:

- **`--json`** — Codex prints one event per line as it works (every command,
  every reasoning step). Pair with `-o` to get the clean final answer in its
  own file.
- **Background** — launch each call with the Bash tool's `run_in_background`
  mode, so neither blocks and the two run in parallel.
- **Monitor** — arm one `Monitor` that polls the event files and emits a
  progress line every 30s. Do not poll by hand, and never tell the user to run
  anything.

**Launch each call (A and B) as a background Bash command.** Build the prompt
as a file first — an unquoted heredoc would mangle the briefing's backticks:

```bash
{
  cat "<PLUGIN_ROOT>/skills/pin-codex-audit/references/codex-briefing.md"
  printf '\n## Questions\n<the two questions for this call>\n'
  printf '\n## What to read\n<the file paths for this call>\n'
} > /tmp/pin-codex-A.txt

codex exec -m <model> -c model_reasoning_effort=<high|medium> \
  --full-auto -C <project-root> --json \
  -o /tmp/pin-codex-A-final.txt - < /tmp/pin-codex-A.txt \
  > /tmp/pin-codex-A-events.jsonl 2>&1
echo "rc=$?" > /tmp/pin-codex-A.done
```

The trailing `.done` sentinel is written whether Codex succeeds **or** crashes
— a crashed run never writes `turn.completed`, so the Monitor must key off the
sentinel, not the events, to know the call is truly over.

**Then arm one Monitor over both calls.** Use a generous `timeout_ms` (Codex
runs for minutes — `1800000` is safe) and this poll loop as the Monitor
command:

```bash
PROG="<PLUGIN_ROOT>/scripts/codex_progress.py"
while true; do
  python3 "$PROG" --oneline /tmp/pin-codex-A-events.jsonl
  python3 "$PROG" --oneline /tmp/pin-codex-B-events.jsonl
  if [ -f /tmp/pin-codex-A.done ] && [ -f /tmp/pin-codex-B.done ]; then
    echo "both codex calls finished"
    break
  fi
  sleep 30
done
```

Each poll prints two status lines — one per call — which arrive as a single
chat notification, so the wait is legible instead of silent. The Monitor exits
the moment both `.done` sentinels exist (covering crash and success alike).

When the Monitor ends, read the two `-o` files for the final answers and the
`.jsonl` files for the full traces.

Use the project's configured Codex model; if none, `gpt-5.5` is a reasonable
default. `humanize:ask-codex` is an alternative wrapper, but it does not expose
the `--json` event stream — you would lose the live progress view, so prefer
the direct call here.

## Step 3 — Report and record

Relay both calls' findings to the human **verbatim** — do not soften or
summarize away a concern. For each finding, attach what you intend to do: fix
the regression, re-pin to the right property, correct the nature tag, or add the
missing pin. The human decides; you do not quietly accept or dismiss.

Save both calls' final answers (the `-o` files) and their event traces (the
`.jsonl` files) under `.claude-research/channels/<channel>/` so there is an
audit trail of what Codex actually said — and did — at this point in time.

A clean pass on both calls is a real signal — record it. A finding is not a
failure of the work; it is the adversarial layer doing its job before the human
is asked to ground on something subtly wrong.
