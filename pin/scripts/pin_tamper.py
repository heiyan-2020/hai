#!/usr/bin/env python3
"""pin_tamper.py — detect removed or modified pins relative to a git ref.

Adding a new pin is normal (pins are born through pin-grounding). Removing or
changing a pin that already existed is the move an agent makes to dodge a
failing check — so it must carry an explicit human gesture in the commit
message. This script reports which existing pins were touched; the commit hook
turns that into a block.

Usage:
    pin_tamper.py <pins.yaml> [--against HEAD]

Prints one touched pin id per line. Exit 0 always (this is a query, not a gate).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import yaml


def _git(args: list[str], cwd: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return proc.returncode, proc.stdout


def _pin_map(text: str) -> dict[str, dict]:
    """Parse pins.yaml text into {id: pin-dict}. Tolerant of empty/bad input."""
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return {}
    pins = doc.get("pins", []) if isinstance(doc, dict) else []
    out: dict[str, dict] = {}
    for p in pins or []:
        if isinstance(p, dict) and p.get("id"):
            out[p["id"]] = p
    return out


def touched_pins(pins_path: str, against: str = "HEAD") -> list[str]:
    pins_path = os.path.abspath(pins_path)
    repo_dir = os.path.dirname(pins_path)

    code, root = _git(["rev-parse", "--show-toplevel"], repo_dir)
    if code != 0:
        return []  # not a git repo — nothing to compare
    repo_root = root.strip()
    rel = os.path.relpath(pins_path, repo_root)

    code, old_text = _git(["show", f"{against}:{rel}"], repo_root)
    if code != 0:
        return []  # pins.yaml did not exist at <against> — every pin is new

    if not os.path.isfile(pins_path):
        new_text = ""  # file deleted wholesale
    else:
        with open(pins_path, "r", encoding="utf-8") as fh:
            new_text = fh.read()

    old, new = _pin_map(old_text), _pin_map(new_text)
    touched = [pid for pid, old_pin in old.items()
               if pid not in new or new[pid] != old_pin]
    return sorted(touched)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Report removed/modified pins.")
    ap.add_argument("pins_path")
    ap.add_argument("--against", default="HEAD")
    args = ap.parse_args(argv)
    for pid in touched_pins(args.pins_path, args.against):
        print(pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
