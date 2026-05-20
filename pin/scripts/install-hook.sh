#!/usr/bin/env bash
#
# install-hook.sh — install the pin commit-msg hook into a target git repo.
#
# Usage:  bash scripts/install-hook.sh <path-to-target-repo>
#
# The hook template's __PIN_SCRIPTS_DIR__ placeholder is replaced with this
# plugin's absolute scripts directory, so the installed hook is self-contained
# and keeps working wherever the target repo lives.

set -euo pipefail

TARGET="${1:?usage: install-hook.sh <path-to-target-repo>}"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPTS_DIR")"
TEMPLATE="$PLUGIN_ROOT/hooks/commit-msg.sh"

[ -f "$TEMPLATE" ] || { echo "install-hook: template not found: $TEMPLATE" >&2; exit 1; }

TARGET="$(cd "$TARGET" && pwd)"
GIT_DIR="$(git -C "$TARGET" rev-parse --git-dir 2>/dev/null || true)"
[ -z "$GIT_DIR" ] && { echo "install-hook: $TARGET is not a git repo" >&2; exit 1; }
case "$GIT_DIR" in /*) ;; *) GIT_DIR="$TARGET/$GIT_DIR" ;; esac

HOOKS_DIR="$GIT_DIR/hooks"
mkdir -p "$HOOKS_DIR"
DEST="$HOOKS_DIR/commit-msg"

if [ -e "$DEST" ] && ! grep -q "pin plugin" "$DEST" 2>/dev/null; then
  cp "$DEST" "$DEST.pre-pin.bak"
  echo "install-hook: existing commit-msg hook backed up to $DEST.pre-pin.bak"
fi

sed "s|__PIN_SCRIPTS_DIR__|$SCRIPTS_DIR|g" "$TEMPLATE" > "$DEST"
chmod +x "$DEST"

echo "install-hook: pin commit-msg hook installed at $DEST"
echo "install-hook: scripts dir = $SCRIPTS_DIR"
