---
name: workspace-skill
description: Manage untracked, local-only project files across multiple git workspaces using a main workspace as the source. Use when Codex needs to initialize or apply rules for files such as .env, local databases, credentials, caches, generated state, or other files that are not tracked by git but must be ignored, symlinked, or copied into sibling workspaces.
---

# Workspace Skill

## Overview

Use this skill to keep git-untracked local files consistent across multiple workspaces without moving the source files out of the project. Treat the main workspace as the source of truth, store configuration in `.workspace/config.yaml`, and put other workspaces under `.workspace/workspaces/` by default.

Bundled script:

```bash
python3 <skill-dir>/scripts/workspace_local.py <command>
```

## Model

Use this project layout unless the user asks otherwise:

```text
<project-root>/
  .env
  local.db
  .workspace/
    config.yaml
    workspaces/
      feature-a/
      feature-b/
```

Keep `.workspace/config.yaml` trackable by default. Ignore `.workspace/workspaces/` and any user-selected local-only paths through `.git/info/exclude` by default, unless the user asks to update `.gitignore`.

Configuration fields:

```yaml
version: 1
main_workspace: ..
workspace_root: workspaces
rules:
  - source_path: .env
    action: link
    target_path: .env
  - source_path: local.db
    action: copy
    target_path: local.db
  - source_path: scratch/
    action: ignore
```

Path meanings:

- `main_workspace` is relative to `.workspace/config.yaml`; default `..` means the project root.
- `workspace_root` is relative to `.workspace/`; default `workspaces`.
- `source_path` is relative to the main workspace.
- `target_path` is relative to each target workspace.

Rule actions:

- `ignore`: add the source path to local ignore rules and do not sync it.
- `link`: create a symlink in each target workspace pointing back to the main workspace file.
- `copy`: copy the source file or directory into the target workspace once; do not track later changes unless reapplied with `--force`.
- `skip`: initialization-only choice; do not write a rule.

## Workflow

1. Find the skill directory, then run initialization from the main workspace:

   ```bash
   python3 <skill-dir>/scripts/workspace_local.py init
   ```

2. During `init`, classify each untracked or ignored file as `ignore`, `link`, `copy`, or `skip`. For `link` and `copy`, accept the default target path unless the file should land elsewhere in target workspaces.

3. Apply rules to a workspace by name or path:

   ```bash
   python3 <skill-dir>/scripts/workspace_local.py apply feature-a
   python3 <skill-dir>/scripts/workspace_local.py apply .workspace/workspaces/feature-a
   ```

4. Audit after changing rules, moving workspaces, or deleting local files:

   ```bash
   python3 <skill-dir>/scripts/workspace_local.py audit
   ```

5. List configured rules and known workspaces:

   ```bash
   python3 <skill-dir>/scripts/workspace_local.py list
   ```

## Safety Rules

- Never print secret file contents.
- Do not overwrite existing target files unless the user requests `--force`.
- Do not add `.workspace/` wholesale to ignore rules, because that would hide `.workspace/config.yaml`.
- Prefer `.git/info/exclude` for machine-local ignore entries. Use `.gitignore` only when the user wants the ignore policy committed.
- Warn that link rules depend on the main workspace continuing to exist at its configured path.
- Run `audit` after `init` or manual edits to verify source files, symlinks, copies, and ignore entries.

## Commands

```bash
python3 <skill-dir>/scripts/workspace_local.py init [--gitignore]
python3 <skill-dir>/scripts/workspace_local.py apply <workspace-name-or-path> [--force]
python3 <skill-dir>/scripts/workspace_local.py audit
python3 <skill-dir>/scripts/workspace_local.py list
```
