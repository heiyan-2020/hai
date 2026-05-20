#!/usr/bin/env bash
#
# pin plugin — git commit-msg hook.
#
# Installed into a project as .git/hooks/commit-msg by scripts/install-hook.sh.
# It runs at every commit and enforces two things:
#
#   1. pin-audit passes — no enforced design decision is currently violated.
#   2. Any pre-existing pin that this commit removes or modifies is explicitly
#      acknowledged in the commit message with a gesture:
#          [pin-release: <id>]   [pin-disable: <id>]   [pin-update: <id>]
#      Without the gesture the commit is blocked. This is the root defense
#      against an agent silently deleting a pin to make a check pass.
#
# A repo with no pins.yaml is unaffected — the hook exits 0 immediately.

set -euo pipefail

PIN_SCRIPTS_DIR="__PIN_SCRIPTS_DIR__"
MSG_FILE="${1:?commit-msg hook expects the message file as argument 1}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$REPO_ROOT" ] && exit 0

# Locate pins.yaml — repo root, then .claude-research/.
PINS=""
for candidate in "$REPO_ROOT/pins.yaml" "$REPO_ROOT/.claude-research/pins.yaml"; do
  if [ -f "$candidate" ]; then PINS="$candidate"; break; fi
done
[ -z "$PINS" ] && exit 0   # repo does not use pin

PY="$(command -v python3 || command -v python)"

# --- 1. audit -------------------------------------------------------------
if ! "$PY" "$PIN_SCRIPTS_DIR/pin_audit.py" "$PINS"; then
  echo
  echo "pin: commit BLOCKED — a pinned design decision is violated."
  echo "     Fix the regression, or if the change is intentional, update the"
  echo "     pin and acknowledge it with [pin-update: <id>] in the message."
  exit 1
fi

# --- 2. tamper check ------------------------------------------------------
TOUCHED="$("$PY" "$PIN_SCRIPTS_DIR/pin_tamper.py" "$PINS" || true)"
if [ -n "$TOUCHED" ]; then
  MSG="$(cat "$MSG_FILE")"
  MISSING=""
  while IFS= read -r id; do
    [ -z "$id" ] && continue
    # accept [pin-release|disable|update: <id>], tolerant of inner spaces
    if ! printf '%s' "$MSG" | grep -Eq "\[pin-(release|disable|update): *${id} *\]"; then
      MISSING="$MISSING $id"
    fi
  done <<< "$TOUCHED"

  if [ -n "$MISSING" ]; then
    echo
    echo "pin: commit BLOCKED — these existing pins were removed or modified"
    echo "     without an explicit human gesture:"
    for id in $MISSING; do echo "       - $id"; done
    echo
    echo "     If you really mean to change them, add one line per pin to the"
    echo "     commit message, e.g.:"
    echo "         [pin-release: $(echo "$MISSING" | awk '{print $1}')]"
    exit 1
  fi
fi

exit 0
