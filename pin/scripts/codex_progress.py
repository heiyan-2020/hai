#!/usr/bin/env python3
"""codex_progress.py — summarize a `codex exec --json` event stream.

`codex exec --json` prints one JSON event per line as it works
(thread.started, turn.started, item.completed, turn.completed, ...). Watching
that file is how you see what an otherwise-silent, slow Codex run is doing.
This turns the raw JSONL into a compact, human-readable snapshot.

Usage:
    codex_progress.py [--oneline] <events.jsonl>

`--oneline` prints a single status line — used by the Monitor poll loop in the
pin-codex-audit skill, where each line becomes one chat notification. Without
it, a fuller multi-line snapshot is printed.

Parsing is defensive: a half-written final line is ignored, and unknown
event/item types degrade gracefully.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter


def _detail(item_type: str, item: dict) -> str:
    """A short, human-readable description of one completed/started item."""
    if item_type == "command_execution":
        cmd = item.get("command") or item.get("cmd") or ""
        if isinstance(cmd, list):
            cmd = " ".join(str(c) for c in cmd)
        return f"command: {str(cmd)[:90]}"
    if item_type == "agent_message":
        return f"message: {str(item.get('text', ''))[:90]}"
    if item_type == "file_change":
        return f"file_change: {item.get('path', '')}"
    if item_type == "reasoning":
        return "reasoning"
    if item_type == "mcp_tool_call":
        return f"tool_call: {item.get('tool', item.get('name', ''))}"
    return item_type


def collect(path: str) -> dict | None:
    """Parse the JSONL event file into a stats dict, or None if absent."""
    if not os.path.isfile(path):
        return None

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    events = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            continue  # partial trailing line while the file is still written

    item_counts: Counter = Counter()
    last_detail = ""
    in_progress = ""
    done = False
    usage = None
    error = None

    for ev in events:
        etype = ev.get("type", "")
        if etype == "turn.completed":
            done = True
            usage = ev.get("usage")
        if etype == "error" or "error" in etype:
            error = ev.get("message") or json.dumps(ev)[:160]
        item = ev.get("item")
        if isinstance(item, dict):
            itype = item.get("type", "item")
            if etype == "item.completed":
                item_counts[itype] += 1
                in_progress = ""
                last_detail = _detail(itype, item)
            elif etype == "item.started":
                in_progress = _detail(itype, item)

    return {
        "events": len(events),
        "item_counts": item_counts,
        "last_detail": last_detail,
        "in_progress": in_progress,
        "done": done,
        "usage": usage,
        "error": error,
    }


def summarize(path: str) -> str:
    """Multi-line snapshot."""
    s = collect(path)
    if s is None:
        return f"codex progress: {path} not found (run not started?)"

    out = [f"codex progress — {os.path.basename(path)}"]
    out.append(f"  events: {s['events']}   completed items: {sum(s['item_counts'].values())}")
    if s["item_counts"]:
        out.append("  " + "   ".join(f"{k}:{v}" for k, v in sorted(s["item_counts"].items())))
    if s["in_progress"]:
        out.append(f"  in progress: {s['in_progress']}")
    elif s["last_detail"]:
        out.append(f"  last: {s['last_detail']}")
    if s["error"]:
        out.append(f"  ERROR: {s['error']}")
    if s["done"]:
        u = s["usage"]
        if u:
            out.append(f"  status: DONE   tokens in/out: "
                       f"{u.get('input_tokens', '?')}/{u.get('output_tokens', '?')}")
        else:
            out.append("  status: DONE")
    else:
        out.append("  status: running...")
    return "\n".join(out)


def summarize_oneline(path: str) -> str:
    """Single status line — one Monitor notification per poll."""
    name = os.path.basename(path)
    s = collect(path)
    if s is None:
        return f"{name}: not started"
    if s["error"]:
        return f"{name}: ERROR — {s['error']}"
    items = sum(s["item_counts"].values())
    if s["done"]:
        u = s["usage"] or {}
        return (f"{name}: DONE — {items} items, "
                f"tokens in/out {u.get('input_tokens', '?')}/{u.get('output_tokens', '?')}")
    activity = s["in_progress"] or s["last_detail"] or "starting"
    return f"{name}: running — {s['events']} events, {items} items, now={activity}"


def main(argv: list[str]) -> int:
    args = argv[1:]
    oneline = "--oneline" in args
    paths = [a for a in args if not a.startswith("-")]
    if len(paths) != 1:
        print(__doc__)
        return 2
    print(summarize_oneline(paths[0]) if oneline else summarize(paths[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
