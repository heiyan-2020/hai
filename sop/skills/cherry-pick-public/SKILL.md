---
name: cherry-pick-public
description: "Separate public-safe changes from a mixed private branch. Use when a branch contains both private work and public work, especially when comparing against public/main, honoring a repo-local .public-exclude file, asking which remaining files belong in a public commit, and preparing a selected public patch or checkout list."
---

# Cherry Pick Public

Use this skill to triage a mixed branch before creating a public-facing commit.
The workflow compares the current repository state against `public/main`, filters
private paths through `.public-exclude`, then asks the user which remaining files
should be included.

## Tool

Use the bundled script:

```bash
python3 /mnt/nvme2/zyx/projects/hai/sop/skills/cherry-pick-public/scripts/cherry_pick_public.py --help
```

The script is read-only unless `--ensure-ignore`, `--init-exclude`, or
`--patch` is passed.

## Workflow

1. Confirm the repository has a public baseline ref. Default to `public/main`;
   otherwise ask the user for the public ref.
2. Ensure `.public-exclude` is locally ignored:

```bash
python3 /mnt/nvme2/zyx/projects/hai/sop/skills/cherry-pick-public/scripts/cherry_pick_public.py --ensure-ignore
```

If the user has not written `.public-exclude` yet, create an empty one only when
asked, or run the same command with `--init-exclude`.

3. Scan the branch:

```bash
python3 /mnt/nvme2/zyx/projects/hai/sop/skills/cherry-pick-public/scripts/cherry_pick_public.py --base public/main
```

The scan includes:

- committed changes from `public/main...HEAD`
- unstaged or staged working-tree changes
- untracked files that are not already ignored by Git

4. Present only the "Candidate files" section to the user and ask which files
   should be included in the public commit. Do not include files listed under
   "Excluded by .public-exclude" unless the user explicitly overrides the
   exclusion.
5. After the user chooses files, either:

- stage/check out those paths manually in a clean public branch or worktree, or
- generate a patch for those paths:

```bash
python3 /mnt/nvme2/zyx/projects/hai/sop/skills/cherry-pick-public/scripts/cherry_pick_public.py \
  --base public/main \
  --include config.py --include dashboard.py --include docs/config_llm.md \
  --patch /tmp/public-changes.patch
```

Apply the patch only after inspecting it. Prefer a fresh branch from
`public/main` for the final public commit.

## .public-exclude

`.public-exclude` uses `.gitignore`-style patterns and is intentionally local.
The file itself must be ignored by Git. Common examples:

```gitignore
experiments/
.claude-research/
md/
src/prompts.py
```

Supported syntax includes blank lines, comments, `!` negation, leading `/`
root anchoring, trailing `/` directory rules, and `*`, `?`, `**` glob patterns.

## Guardrails

- Never assume an unexcluded file is public. Always ask the user.
- Keep prompt changes out when the user says prompts are private, even if they
  are not in `.public-exclude`.
- Do not mutate the mixed branch while scanning.
- Report deleted files clearly; they can be public changes too, but confirm
  before carrying deletions into the public commit.
