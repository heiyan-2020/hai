---
name: submit-mr
description: "Create a merge request (GitLab) or pull request (GitHub) from the current branch, auto-detecting the forge from the git remote and driving glab or gh accordingly. Use when the user wants to submit work, open an MR or PR, send a branch for review, or finish a worktree task. Infers the target branch from fork/<target>/... branch names unless the user gives an explicit target branch."
---

# Submit Merge / Pull Request

Open a review request from the current branch with a predictable five-step
workflow: resolve, lint, gather, compose, submit.

The forge is detected automatically from the `origin` remote. On GitLab this
creates a **merge request (MR)** via `glab`; on GitHub it creates a **pull
request (PR)** via `gh`. The workflow is otherwise identical, so this document
uses "the request" when the step applies to both and calls out the per-forge
command only where they genuinely differ.

## Completion Status

End with exactly one of these states:

- `DONE`: request created successfully or an existing request URL was found.
- `BLOCKED`: request cannot be created because of an external blocker, such as missing auth, missing remote, permission failure, or push failure.
- `NEEDS_CONTEXT`: required information is missing, such as a target branch, an undetectable forge, or actual commits to merge.

## Autopilot

Before any confirmation gate, read `.claude/research-config.yaml` if it exists
and check `approval_mode`.

- `interactive` or missing config: present the draft request details and wait for user confirmation.
- `autopilot`: log that autopilot chose the default option and proceed.

Lint failures are hard blockers even in autopilot mode.

## Step 1: Resolve

### Current Branch

Run:

```bash
git rev-parse --abbrev-ref HEAD
```

If the branch is `HEAD`, stop with `NEEDS_CONTEXT`; detached HEAD is not a
valid source branch.

### Remote

Run:

```bash
git remote -v
```

If no `origin` remote exists, stop with `NEEDS_CONTEXT` and ask for the remote
URL. Do not invent one.

Derive `REPO_PATH` (the `owner/project` slug passed to `--repo`) from `origin`:

```bash
git remote get-url origin | sed -E 's|^git@[^:]+:||; s|^https?://[^/]+/||; s|\.git$||'
```

This supports both `git@host:owner/project.git` and
`https://host/owner/project.git`, and the slug format is accepted by both
`glab --repo` and `gh --repo`.

### Detect Forge

Extract the host from the `origin` URL:

```bash
git remote get-url origin | sed -E 's|^git@([^:]+):.*|\1|; s|^https?://([^/]+)/.*|\1|'
```

Pick the platform in this order:

1. Host contains `github` (e.g. `github.com`, `github.mycorp.com`) → **GitHub**, use `gh`.
2. Host contains `gitlab` (e.g. `gitlab.com`, self-hosted `gitlab.example.org`) → **GitLab**, use `glab`.
3. Otherwise the host is a custom/self-hosted domain. Resolve by authentication: run `gh auth status` and `glab auth status` and choose the CLI that reports being logged in to this host. `gh auth status` and `glab auth status` both list their authenticated hosts.
4. If both or neither claim the host, stop with `NEEDS_CONTEXT` and ask the user whether this remote is GitHub or GitLab.

Record the result as `PLATFORM` (`github` or `gitlab`); the auth and submit
steps branch on it.

### Target Branch

Choose the target branch in this order:

1. Use the target branch explicitly provided by the user.
2. If the source branch matches `fork/{target}/...`, use `{target}`.
3. Otherwise use `origin/HEAD`:

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|^refs/remotes/origin/||'
```

If `origin/HEAD` is unavailable, fall back to `main`.

### Auth

Check that the detected CLI is authenticated.

- GitLab: `glab auth status`
- GitHub: `gh auth status`

If not authenticated, stop with `BLOCKED` and tell the user to run the matching
login command (`glab auth login` or `gh auth login`).

### Commits Ahead

Run:

```bash
git log ${TARGET}..HEAD --oneline
```

If there are no commits ahead of the target branch, stop with
`NEEDS_CONTEXT`; there is nothing to merge.

## Step 2: Lint

If this branch changed fact-related files since diverging from target:

```bash
git diff ${TARGET}...HEAD --name-only | grep -q 'facts'
```

then run the project's lint workflow before proceeding.

Preferred order:

1. If `.claude/skills/lint/SKILL.md` exists, read it and follow it against `.claude-research/facts.yaml`.
2. Otherwise, run the repository's documented lint command if one is obvious from `README`, `Makefile`, or project config.

If lint fails, stop with `BLOCKED` and report the errors. Do not create the request.
If no fact-related files changed, skip this step.

## Step 3: Gather

Collect:

```bash
git log ${TARGET}..HEAD --format="- %s" --reverse
git diff ${TARGET}...HEAD --stat
```

If `.claude-research/` exists, derive a channel from the current branch and
look for a plan file:

```bash
CHANNEL=$(echo "$CURRENT_BRANCH" | sed -n 's|^fork/\([^/]*\)/.*|\1|p')
CHANNEL=${CHANNEL:-$(echo "$CURRENT_BRANCH" | tr '/' '-')}
PLAN=".claude-research/channels/$CHANNEL/plan.yaml"
```

If the plan exists, include relevant task IDs and statuses in the request body.

## Step 4: Compose

Create a concise title under 70 characters from the commit log. If one commit
dominates, use that theme. For research tasks, prefer the task description from
the plan file when available.

Use this body shape:

````markdown
## Summary

<2-4 bullets summarizing what changed and why>

## Changes

<commit bullets from git log>

## Diff Stats

```text
<git diff --stat output>
```

---
Generated by an AI coding agent
````

In interactive mode, present (label the request type for the detected forge —
"merge request" on GitLab, "pull request" on GitHub):

```text
Ready to create {merge request | pull request}:

  Forge:  {GitLab | GitHub}
  Source: {CURRENT_BRANCH}
  Target: {TARGET}
  Title:  {TITLE}

  Body preview:
  {BODY}

A) Create it
B) Edit title or body
C) Cancel
```

Proceed only after the user chooses A or provides edits that lead to A.
In autopilot mode, choose A automatically.

## Step 5: Submit

Push the branch (same for both forges):

```bash
git push -u origin ${CURRENT_BRANCH}
```

If the push fails for auth, permission, rejected update, or network reasons,
stop with `BLOCKED` and report the relevant command output.

Create the request with the CLI for the detected `PLATFORM`.

**GitLab** (`glab`):

```bash
glab mr create \
  --repo "${REPO_PATH}" \
  --source-branch "${CURRENT_BRANCH}" \
  --target-branch "${TARGET}" \
  --title "${TITLE}" \
  --description "${BODY}" \
  --no-editor
```

**GitHub** (`gh`):

```bash
gh pr create \
  --repo "${REPO_PATH}" \
  --head "${CURRENT_BRANCH}" \
  --base "${TARGET}" \
  --title "${TITLE}" \
  --body "${BODY}"
```

If the create command reports that a request already exists for this branch,
retrieve and report the existing URL instead of treating it as a failure:

- GitLab: `glab mr view "${CURRENT_BRANCH}" --repo "${REPO_PATH}"`
- GitHub: `gh pr view "${CURRENT_BRANCH}" --repo "${REPO_PATH}" --json url --jq .url`

## Final Report

Use this format:

```text
SUBMIT-MR COMPLETE
==================
Status:  {DONE | BLOCKED | NEEDS_CONTEXT}
Forge:   {GitLab | GitHub}
URL:     {url or N/A}
Source:  {CURRENT_BRANCH}
Target:  {TARGET}
Title:   {TITLE or N/A}
```
