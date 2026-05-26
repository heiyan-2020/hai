---
name: pin-audit
description: >-
  Run the machine audit of a project's pins — execute every enforced pin's
  assertion and report pass/fail. Use whenever you need to check that no
  locked design decision has been silently violated: before a commit, after a
  batch of changes, when resuming work, or as Phase 5 of pin-aware-agent. This
  is mechanical once started; before running it, check whether the git
  commit-msg hook is installed and ask the user about installing it only when
  it is missing. The audit is also what the git commit-msg hook runs. Trigger
  on "audit the pins", "check the pins", "did anything break a design
  decision", or after any work that touched pinned code.
type: flow
user-invocable: true
---

# pin-audit

The mechanical layer. It answers one question: **is any enforced design
decision currently violated?** No judgement once the audit starts — just run
the assertions and report.

## How to run

Locate `pins.yaml` (project root or `.claude-research/pins.yaml`), resolve
`<PLUGIN_ROOT>` as the root of this installed plugin, then first check hook
installation for the target repo:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK="$(git -C "$REPO_ROOT" rev-parse --git-path hooks/commit-msg)"
test -f "$HOOK" && grep -q "pin plugin" "$HOOK"
```

- If that command succeeds, the pin hook is already installed. Do not ask the
  user about hook installation; continue directly to the audit.
- If it fails, tell the user the pin commit-msg hook is not installed for this
  repo and ask whether to install it now. If the user agrees, run:

```bash
bash <PLUGIN_ROOT>/scripts/install-hook.sh "$REPO_ROOT"
```

Then run the audit:

```bash
python3 <PLUGIN_ROOT>/scripts/pin_audit.py <pins.yaml>
```

Useful flags:

- `--only id1,id2` — audit just those pins (use after a focused change to get
  fast feedback, e.g. inside Phase 3 of `pin-aware-agent`).
- `--branch <name>` — override branch detection. Pins with `status: disabled`
  and the current branch in `disabled_on` are skipped; this flag controls that
  resolution.
- `--json` — structured output for programmatic callers.

Exit code is `0` only when every enforced pin passes and no pin is
structurally invalid. The git commit-msg hook relies on this exit code.

## Interpreting the result

- **PASS** — the assertion held. The design decision is intact.
- **FAIL** — the assertion broke. Either a real regression (a past decision
  was reverted — the thing this plugin exists to catch), or the decision was
  intentionally changed. If intentional, the pin itself must be updated, and
  the commit message must carry `[pin-update: <id>]` so the hook allows it.
- **SKIP** — the pin is retired, or disabled on this branch. Not enforced.
- **warning: no `# PIN: <id>` anchor** — the assertion still passes, but the
  code breadcrumb is gone. Not a failure; behavior is preserved. Flag it so a
  human can decide whether to restore the anchor.

## When a pin fails

Do not "fix" it by editing the pin or deleting it — that is the silent
rollback in disguise. Treat a FAIL as a finding: report the pin `id`, its
`claim`, and the assertion detail to the human. The decision of whether to
restore the behavior or formally change the pin belongs to the human, not to
you.
