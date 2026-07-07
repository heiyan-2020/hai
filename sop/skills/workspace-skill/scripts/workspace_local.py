#!/usr/bin/env python3
"""Manage local-only files across git workspaces.

The script intentionally supports only the small YAML shape this skill writes.
It avoids a PyYAML dependency so it can run in ordinary project environments.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


CONFIG_DIR = ".workspace"
CONFIG_FILE = "config.yaml"
DEFAULT_WORKSPACE_ROOT = "workspaces"
VALID_ACTIONS = {"ignore", "link", "copy", "skip"}


def die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_root(cwd: Path) -> Path:
    proc = run_git(["rev-parse", "--show-toplevel"], cwd, check=False)
    if proc.returncode != 0:
        return cwd.resolve()
    return Path(proc.stdout.strip()).resolve()


def rel_to(path: Path, base: Path) -> str:
    return os.path.relpath(path, base).replace(os.sep, "/")


def prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")


def prompt_choice(text: str, choices: list[str], default: str) -> str:
    labels = "/".join(choices)
    while True:
        value = prompt(f"{text} ({labels})", default).lower()
        if value in choices:
            return value
        print(f"Please choose one of: {labels}")


def config_path_from_main(main: Path) -> Path:
    return main / CONFIG_DIR / CONFIG_FILE


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        die(f"missing config: {config_path}")

    config: dict[str, object] = {"rules": []}
    current_rule: dict[str, str] | None = None

    for raw in config_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "rules:":
            continue

        if stripped.startswith("- "):
            if current_rule is not None:
                config["rules"].append(current_rule)
            current_rule = {}
            rest = stripped[2:].strip()
            if rest:
                key, value = parse_pair(rest, config_path)
                current_rule[key] = value
            continue

        if ":" in stripped and current_rule is not None and raw.startswith(" "):
            key, value = parse_pair(stripped, config_path)
            current_rule[key] = value
            continue

        if ":" in stripped and not raw.startswith(" "):
            key, value = parse_pair(stripped, config_path)
            config[key] = int(value) if key == "version" else value
            continue

        die(f"cannot parse {config_path}: {raw}")

    if current_rule is not None:
        config["rules"].append(current_rule)

    validate_config(config, config_path)
    return config


def parse_pair(text: str, config_path: Path) -> tuple[str, str]:
    key, sep, value = text.partition(":")
    if not sep:
        die(f"cannot parse {config_path}: {text}")
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return key.strip(), value


def validate_config(config: dict, config_path: Path) -> None:
    if config.get("version") != 1:
        die(f"{config_path} must set version: 1")
    if not config.get("main_workspace"):
        die(f"{config_path} must set main_workspace")
    if not config.get("workspace_root"):
        die(f"{config_path} must set workspace_root")
    if not isinstance(config.get("rules"), list):
        die(f"{config_path} must contain rules")

    for idx, rule in enumerate(config["rules"], start=1):
        action = rule.get("action")
        source = rule.get("source_path")
        if action not in {"ignore", "link", "copy"}:
            die(f"rule {idx} has invalid action: {action}")
        if not source:
            die(f"rule {idx} is missing source_path")
        if action in {"link", "copy"} and not rule.get("target_path"):
            die(f"rule {idx} is missing target_path")


def write_config(config_path: Path, workspace_root: str, rules: list[dict[str, str]]) -> None:
    lines = [
        "version: 1",
        "main_workspace: ..",
        f"workspace_root: {workspace_root}",
        "rules:",
    ]
    for rule in rules:
        lines.append(f"  - source_path: {rule['source_path']}")
        lines.append(f"    action: {rule['action']}")
        if rule["action"] in {"link", "copy"}:
            lines.append(f"    target_path: {rule['target_path']}")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_paths(config_path: Path, config: dict) -> tuple[Path, Path]:
    workspace_dir = config_path.parent.resolve()
    main = (workspace_dir / str(config["main_workspace"])).resolve()
    workspace_root = (workspace_dir / str(config["workspace_root"])).resolve()
    return main, workspace_root


def untracked_files(main: Path) -> list[str]:
    candidates: set[str] = set()
    commands = [
        ["ls-files", "--others", "--exclude-standard"],
        ["ls-files", "--others", "--ignored", "--exclude-standard"],
    ]
    for args in commands:
        proc = run_git(args, main, check=False)
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            path = line.strip()
            if not path:
                continue
            if path == CONFIG_DIR or path.startswith(f"{CONFIG_DIR}/"):
                continue
            candidates.add(path)
    return sorted(candidates)


def append_ignore_entries(main: Path, entries: list[str], use_gitignore: bool) -> Path:
    if use_gitignore:
        ignore_path = main / ".gitignore"
    else:
        git_dir_proc = run_git(["rev-parse", "--git-path", "info/exclude"], main)
        ignore_path = main / git_dir_proc.stdout.strip()

    ignore_path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if ignore_path.exists():
        existing = {
            line.strip()
            for line in ignore_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

    additions = [entry for entry in entries if entry not in existing]
    if additions:
        with ignore_path.open("a", encoding="utf-8") as handle:
            if ignore_path.stat().st_size:
                handle.write("\n")
            handle.write("# workspace-skill\n")
            for entry in additions:
                handle.write(f"{entry}\n")
    return ignore_path


def command_init(args: argparse.Namespace) -> None:
    detected = git_root(Path.cwd())
    main_value = prompt("Main workspace directory", str(detected))
    main = Path(main_value).expanduser().resolve()
    if not main.exists():
        die(f"main workspace does not exist: {main}")

    workspace_root = prompt(
        "Workspace storage directory relative to .workspace", DEFAULT_WORKSPACE_ROOT
    ).strip("/")
    if not workspace_root:
        die("workspace_root cannot be empty")

    config_path = config_path_from_main(main)
    if config_path.exists() and not args.force:
        die(f"{config_path} already exists; rerun with --force to replace it")

    files = untracked_files(main)
    rules: list[dict[str, str]] = []
    ignore_entries = [f"{CONFIG_DIR}/{workspace_root.rstrip('/')}/"]

    if not files:
        print("No untracked or ignored files found.")

    for path in files:
        action = prompt_choice(f"{path}", ["ignore", "link", "copy", "skip"], "skip")
        if action == "skip":
            continue
        if action == "ignore":
            rules.append({"source_path": path, "action": "ignore"})
            ignore_entries.append(path)
            continue
        target = prompt(f"Target path for {path}", path)
        rules.append({"source_path": path, "action": action, "target_path": target})
        ignore_entries.append(path)

    write_config(config_path, workspace_root, rules)
    (config_path.parent / workspace_root).mkdir(parents=True, exist_ok=True)
    ignore_path = append_ignore_entries(main, ignore_entries, args.gitignore)

    print(f"Wrote {config_path}")
    print(f"Updated ignore entries in {ignore_path}")
    print("Run audit next: workspace_local.py audit")


def target_workspace(arg: str, main: Path, workspace_root: Path) -> Path:
    raw = Path(arg).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    if len(raw.parts) == 1:
        return (workspace_root / raw).resolve()
    return (main / raw).resolve()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def apply_link(source: Path, target: Path, force: bool) -> None:
    ensure_parent(target)
    if target.is_symlink():
        current = (target.parent / os.readlink(target)).resolve()
        if current == source.resolve():
            print(f"ok link {target}")
            return
        if not force:
            die(f"{target} is a symlink to a different path; use --force to replace")
        target.unlink()
    elif target.exists():
        if not force:
            die(f"{target} already exists; use --force to replace")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    link_value = os.path.relpath(source, target.parent)
    target.symlink_to(link_value, target_is_directory=source.is_dir())
    print(f"linked {target} -> {link_value}")


def apply_copy(source: Path, target: Path, force: bool) -> None:
    ensure_parent(target)
    if target.exists() or target.is_symlink():
        if not force:
            print(f"skip copy {target} (exists)")
            return
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()

    if source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target)
    print(f"copied {source} -> {target}")


def command_apply(args: argparse.Namespace) -> None:
    config_path = find_config(args.config)
    config = load_config(config_path)
    main, workspace_root = resolve_paths(config_path, config)
    target_root = target_workspace(args.workspace, main, workspace_root)

    if target_root == main:
        die("target workspace resolves to the main workspace")
    target_root.mkdir(parents=True, exist_ok=True)

    for rule in config["rules"]:
        action = rule["action"]
        if action == "ignore":
            continue

        source = (main / rule["source_path"]).resolve()
        target = target_root / rule["target_path"]
        if not source.exists():
            die(f"source does not exist: {source}")
        if action == "link":
            apply_link(source, target, args.force)
        elif action == "copy":
            apply_copy(source, target, args.force)


def find_config(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()

    current = Path.cwd().resolve()
    candidates = [
        current / CONFIG_DIR / CONFIG_FILE,
        current / CONFIG_FILE if current.name == CONFIG_DIR else None,
        current.parent / CONFIG_DIR / CONFIG_FILE,
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()

    root = git_root(current)
    candidate = root / CONFIG_DIR / CONFIG_FILE
    if candidate.exists():
        return candidate.resolve()

    die(f"could not find {CONFIG_DIR}/{CONFIG_FILE}; pass --config")


def configured_workspaces(workspace_root: Path) -> list[Path]:
    if not workspace_root.exists():
        return []
    return sorted(path for path in workspace_root.iterdir() if path.is_dir())


def command_audit(args: argparse.Namespace) -> None:
    config_path = find_config(args.config)
    config = load_config(config_path)
    main, workspace_root = resolve_paths(config_path, config)
    failures = 0

    print(f"config: {config_path}")
    print(f"main: {main}")
    print(f"workspace_root: {workspace_root}")

    if not main.exists():
        print(f"FAIL main workspace missing: {main}")
        failures += 1
    if not workspace_root.exists():
        print(f"WARN workspace root missing: {workspace_root}")

    workspaces = configured_workspaces(workspace_root)
    for rule in config["rules"]:
        source = main / rule["source_path"]
        action = rule["action"]
        if action in {"link", "copy"} and not source.exists():
            print(f"FAIL missing source for {action}: {source}")
            failures += 1
            continue
        print(f"ok source {action}: {rule['source_path']}")

        for ws in workspaces:
            if action == "ignore":
                continue
            target = ws / rule["target_path"]
            if action == "link":
                if not target.is_symlink():
                    print(f"FAIL missing link: {target}")
                    failures += 1
                    continue
                resolved = (target.parent / os.readlink(target)).resolve()
                if resolved != source.resolve():
                    print(f"FAIL wrong link: {target} -> {resolved}")
                    failures += 1
                else:
                    print(f"ok link {target}")
            elif action == "copy":
                if target.exists():
                    print(f"ok copy {target}")
                else:
                    print(f"WARN missing copy target: {target}")

    if failures:
        die(f"audit failed with {failures} failure(s)")
    print("audit passed")


def command_list(args: argparse.Namespace) -> None:
    config_path = find_config(args.config)
    config = load_config(config_path)
    _main, workspace_root = resolve_paths(config_path, config)

    print(f"config: {config_path}")
    print("rules:")
    for rule in config["rules"]:
        if rule["action"] in {"link", "copy"}:
            print(
                f"  {rule['action']}: {rule['source_path']} -> {rule['target_path']}"
            )
        else:
            print(f"  {rule['action']}: {rule['source_path']}")

    workspaces = configured_workspaces(workspace_root)
    print("workspaces:")
    if not workspaces:
        print("  (none)")
    for ws in workspaces:
        print(f"  {ws.name}: {ws}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="interactively write .workspace/config.yaml")
    init.add_argument("--gitignore", action="store_true", help="write ignores to .gitignore")
    init.add_argument("--force", action="store_true", help="replace existing config")
    init.set_defaults(func=command_init)

    apply = sub.add_parser("apply", help="apply configured rules to a workspace")
    apply.add_argument("workspace", help="workspace name under workspace_root or a path")
    apply.add_argument("--config", help="path to .workspace/config.yaml")
    apply.add_argument("--force", action="store_true", help="replace existing targets")
    apply.set_defaults(func=command_apply)

    audit = sub.add_parser("audit", help="check configured sources and workspace targets")
    audit.add_argument("--config", help="path to .workspace/config.yaml")
    audit.set_defaults(func=command_audit)

    list_cmd = sub.add_parser("list", help="show configured rules and known workspaces")
    list_cmd.add_argument("--config", help="path to .workspace/config.yaml")
    list_cmd.set_defaults(func=command_list)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
