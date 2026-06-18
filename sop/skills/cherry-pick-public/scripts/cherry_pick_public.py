#!/usr/bin/env python3
"""Triage public-safe files from a mixed private branch."""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Change:
    path: str
    status: str
    source: str


@dataclass(frozen=True)
class Rule:
    pattern: str
    negated: bool
    directory_only: bool
    anchored: bool
    raw: str


def run_git(args: list[str], cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def repo_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("Not inside a Git repository.")
    return Path(proc.stdout.strip())


def parse_name_status(output: str, source: str) -> list[Change]:
    changes: list[Change] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") or status.startswith("C"):
            if len(parts) >= 3:
                changes.append(Change(parts[1], status, source))
                changes.append(Change(parts[2], status, source))
            continue
        if len(parts) >= 2:
            changes.append(Change(parts[1], status, source))
    return changes


def collect_changes(root: Path, base: str) -> list[Change]:
    run_git(["rev-parse", "--verify", base], root)
    changes = []
    changes.extend(parse_name_status(run_git(["diff", "--name-status", f"{base}...HEAD"], root), "branch"))
    changes.extend(parse_name_status(run_git(["diff", "--name-status"], root), "worktree"))
    changes.extend(parse_name_status(run_git(["diff", "--cached", "--name-status"], root), "index"))
    untracked = run_git(["ls-files", "--others", "--exclude-standard"], root)
    for path in untracked.splitlines():
        if path.strip():
            changes.append(Change(path.strip(), "?", "untracked"))
    return merge_changes(changes)


def merge_changes(changes: list[Change]) -> list[Change]:
    by_path: dict[str, Change] = {}
    for change in changes:
        if change.path in by_path:
            prev = by_path[change.path]
            status = prev.status if prev.status == change.status else f"{prev.status},{change.status}"
            source = prev.source if prev.source == change.source else f"{prev.source},{change.source}"
            by_path[change.path] = Change(change.path, status, source)
        else:
            by_path[change.path] = change
    return [by_path[path] for path in sorted(by_path)]


def load_rules(path: Path) -> list[Rule]:
    if not path.exists():
        return []
    rules: list[Rule] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        line = line.replace("\\ ", " ")
        anchored = line.startswith("/")
        if anchored:
            line = line[1:]
        directory_only = line.endswith("/")
        if directory_only:
            line = line.rstrip("/")
        if line:
            rules.append(Rule(line, negated, directory_only, anchored, raw_line))
    return rules


def path_is_dirish(path: str, root: Path) -> bool:
    return (root / path).is_dir() or path.endswith("/")


def match_rule(path: str, rule: Rule, root: Path) -> bool:
    path = path.strip("/")
    if rule.directory_only:
        if path == rule.pattern or path.startswith(f"{rule.pattern}/"):
            return True
        if not path_is_dirish(path, root) and "/" not in rule.pattern:
            return False

    candidates = [path]
    if not rule.anchored and "/" not in rule.pattern:
        candidates.extend(path.split("/"))

    patterns = [rule.pattern]
    if not rule.anchored and "/" in rule.pattern:
        patterns.append(f"**/{rule.pattern}")
    if rule.directory_only:
        patterns.extend([f"{rule.pattern}/**", f"**/{rule.pattern}/**"])

    return any(fnmatch.fnmatchcase(candidate, pattern) for candidate in candidates for pattern in patterns)


def excluded(path: str, rules: list[Rule], root: Path) -> tuple[bool, str | None]:
    ignored = False
    matched_by: str | None = None
    for rule in rules:
        if match_rule(path, rule, root):
            ignored = not rule.negated
            matched_by = rule.raw
    return ignored, matched_by


def ensure_gitignore(root: Path, init_exclude: bool) -> None:
    gitignore = root / ".gitignore"
    exclude = root / ".public-exclude"
    if init_exclude and not exclude.exists():
        exclude.write_text("# Private paths excluded from public branch triage.\n", encoding="utf-8")

    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    normalized = {line.strip() for line in lines}
    if ".public-exclude" not in normalized and "/.public-exclude" not in normalized:
        with gitignore.open("a", encoding="utf-8") as handle:
            if lines and lines[-1] != "":
                handle.write("\n")
            handle.write(".public-exclude\n")
        print("Added .public-exclude to .gitignore")
    else:
        print(".public-exclude is already ignored by .gitignore")


def render(changes: list[Change], rules: list[Rule], root: Path) -> tuple[list[Change], list[tuple[Change, str]]]:
    candidates: list[Change] = []
    ignored: list[tuple[Change, str]] = []
    for change in changes:
        is_excluded, rule = excluded(change.path, rules, root)
        if is_excluded:
            ignored.append((change, rule or ""))
        else:
            candidates.append(change)
    return candidates, ignored


def print_table(title: str, rows: list[tuple[str, str, str, str]]) -> None:
    print(f"\n## {title}")
    if not rows:
        print("(none)")
        return
    print("status\tsource\tpath\trule")
    for status, source, path, rule in rows:
        print(f"{status}\t{source}\t{path}\t{rule}")


def create_patch(root: Path, base: str, includes: list[str], output: Path) -> None:
    if not includes:
        raise SystemExit("--patch requires at least one --include path")
    diff = run_git(["diff", "--binary", f"{base}...HEAD", "--", *includes], root)
    worktree = run_git(["diff", "--binary", "--", *includes], root)
    cached = run_git(["diff", "--cached", "--binary", "--", *includes], root)
    untracked = set(run_git(["ls-files", "--others", "--exclude-standard"], root).splitlines())
    payload = diff
    if cached:
        payload += "\n" + cached
    if worktree:
        payload += "\n" + worktree
    for path in includes:
        if path in untracked:
            proc = subprocess.run(
                ["git", "diff", "--no-index", "--binary", "--", "/dev/null", path],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if proc.returncode not in (0, 1):
                raise SystemExit(proc.stderr.strip() or f"failed to diff untracked file: {path}")
            if proc.stdout:
                payload += "\n" + proc.stdout
    output.write_text(payload, encoding="utf-8")
    print(f"Wrote patch: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="public/main", help="public baseline ref, default: public/main")
    parser.add_argument("--exclude-file", default=".public-exclude", help="gitignore-style local exclude file")
    parser.add_argument("--ensure-ignore", action="store_true", help="add .public-exclude to .gitignore if missing")
    parser.add_argument("--init-exclude", action="store_true", help="create .public-exclude if missing")
    parser.add_argument("--include", action="append", default=[], help="path to include when writing --patch")
    parser.add_argument("--patch", type=Path, help="write a patch containing selected --include paths")
    args = parser.parse_args()

    root = repo_root()
    os.chdir(root)

    if args.ensure_ignore or args.init_exclude:
        ensure_gitignore(root, args.init_exclude)

    rules = load_rules(root / args.exclude_file)
    changes = collect_changes(root, args.base)
    candidates, ignored = render(changes, rules, root)

    print(f"# cherry-pick-public scan")
    print(f"repo\t{root}")
    print(f"base\t{args.base}")
    print(f"exclude\t{args.exclude_file} ({len(rules)} rules)")
    print_table(
        "Candidate files",
        [(c.status, c.source, c.path, "") for c in candidates],
    )
    print_table(
        "Excluded by .public-exclude",
        [(c.status, c.source, c.path, rule) for c, rule in ignored],
    )

    if args.patch:
        create_patch(root, args.base, args.include, args.patch)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
