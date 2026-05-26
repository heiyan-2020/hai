#!/usr/bin/env bash
#
# verify.sh — end-to-end proof that the pin plugin runs and does its job.
#
# It proves, on a throwaway copy of examples/demo:
#   1. the unit tests pass
#   2. pin-audit, protocol-check, and fact-check pass on a clean project
#   3. a SILENT ROLLBACK of a design decision is caught by pin-audit
#   4. the git hook BLOCKS a commit that violates a pin
#   5. the git hook BLOCKS removing a pin without a human gesture
#   6. the git hook ALLOWS removing a pin WITH the [pin-release:] gesture
#
# Exit code 0 iff every scenario behaves as expected.

set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$PLUGIN_ROOT/scripts"
DEMO_SRC="$PLUGIN_ROOT/examples/demo"
PY="$(command -v python3 || command -v python)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASS=0
FAIL=0
pass() { echo "  PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
# expect <actual-rc> <wanted-rc> <description>
expect() {
  if [ "$1" -eq "$2" ]; then pass "$3"; else fail "$3 (rc=$1, wanted $2)"; fi
}

# break the inducer so its prompt no longer ends with the tool-call marker
break_marker() {
  "$PY" - "$1" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read().replace("{TOOL_CALL_MARKER}", "")
open(p, "w").write(s)
EOF
}

make_repo() {  # $1 = dest; copies the demo, git-inits it, installs the hook
  cp -r "$DEMO_SRC" "$1"
  git -C "$1" init -q
  git -C "$1" config user.email "verify@pin.test"
  git -C "$1" config user.name "pin verify"
  bash "$SCRIPTS/install-hook.sh" "$1" >/dev/null
}

echo "================================================================"
echo "pin plugin — end-to-end verification"
echo "================================================================"

# --- 1. unit tests --------------------------------------------------------
echo
echo "[1] unit tests"
"$PY" -m pytest "$PLUGIN_ROOT/tests" -q > "$WORK/pytest.log" 2>&1
rc=$?
[ "$rc" -ne 0 ] && cat "$WORK/pytest.log"
expect "$rc" 0 "unit test suite passes"

# --- 2. clean audit + protocol check -------------------------------------
echo
echo "[2] machine checks on a clean project"
cp -r "$DEMO_SRC" "$WORK/clean"
"$PY" "$SCRIPTS/pin_audit.py" "$WORK/clean/pins.yaml" > "$WORK/audit.log" 2>&1
expect $? 0 "pin-audit passes on the clean demo"
"$PY" "$SCRIPTS/protocol_check.py" \
  "$WORK/clean/protocols/demo-latency-protocol.md" \
  --base "$WORK/clean" > "$WORK/proto.log" 2>&1
expect $? 0 "protocol-check passes on the clean demo"
"$PY" "$SCRIPTS/fact_check.py" \
  "$WORK/clean/facts" \
  --research-root "$WORK/clean" > "$WORK/facts.log" 2>&1
expect $? 0 "fact-check passes on the clean demo"

# --- 3. silent rollback is caught ----------------------------------------
echo
echo "[3] silent rollback of a design decision"
cp -r "$DEMO_SRC" "$WORK/rollback"
break_marker "$WORK/rollback/src/inducer.py"
"$PY" "$SCRIPTS/pin_audit.py" "$WORK/rollback/pins.yaml" > "$WORK/rollback.log" 2>&1
expect $? 1 "pin-audit catches the removed tool-call marker"

# --- 4. hook blocks a pin-violating commit -------------------------------
echo
echo "[4] git hook blocks a commit that violates a pin"
make_repo "$WORK/repo_b"
if grep -Fq "$SCRIPTS" "$WORK/repo_b/.git/hooks/commit-msg"; then
  fail "installed hook should not embed the plugin scripts absolute path"
else
  pass "installed hook avoids plugin scripts absolute path"
fi
if [ -f "$WORK/repo_b/.git/hooks/pin-scripts/pin_audit.py" ] \
  && [ -f "$WORK/repo_b/.git/hooks/pin-scripts/pin_tamper.py" ]; then
  pass "hook support scripts are vendored beside the hook"
else
  fail "hook support scripts should be vendored beside the hook"
fi
git -C "$WORK/repo_b" add -A
git -C "$WORK/repo_b" commit -q -m "initial import" > "$WORK/b_init.log" 2>&1
expect $? 0 "clean initial commit succeeds"

break_marker "$WORK/repo_b/src/inducer.py"
git -C "$WORK/repo_b" add -A
git -C "$WORK/repo_b" commit -q -m "tweak inducer" > "$WORK/b_break.log" 2>&1
rc=$?
[ "$rc" -eq 0 ] && fail "commit with a broken pin should have been blocked" \
  || pass "commit blocked when a pin assertion fails"

# --- 5 & 6. hook tamper gate on pins.yaml --------------------------------
echo
echo "[5] git hook blocks removing a pin without a human gesture"
make_repo "$WORK/repo_c"
git -C "$WORK/repo_c" add -A
git -C "$WORK/repo_c" commit -q -m "initial import" > "$WORK/c_init.log" 2>&1

# delete the decode-time-is-measured pin from pins.yaml
"$PY" - "$WORK/repo_c/pins.yaml" <<'EOF'
import sys, yaml
p = sys.argv[1]
doc = yaml.safe_load(open(p))
doc["pins"] = [x for x in doc["pins"] if x["id"] != "decode-time-is-measured"]
yaml.safe_dump(doc, open(p, "w"), sort_keys=False)
EOF

git -C "$WORK/repo_c" add -A
git -C "$WORK/repo_c" commit -q -m "drop a pin" > "$WORK/c_notamper.log" 2>&1
rc=$?
[ "$rc" -eq 0 ] && fail "pin removal without a gesture should be blocked" \
  || pass "commit blocked: pin removed without [pin-release:]"

echo
echo "[6] git hook allows the same removal WITH the gesture"
git -C "$WORK/repo_c" commit -q \
  -m "drop a pin

[pin-release: decode-time-is-measured]" > "$WORK/c_tamper.log" 2>&1
rc=$?
[ "$rc" -eq 0 ] && pass "commit allowed once the removal is acknowledged" \
  || { cat "$WORK/c_tamper.log"; fail "acknowledged removal should be allowed"; }

# --- summary --------------------------------------------------------------
echo
echo "================================================================"
echo "  $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
  echo "  RESULT: the pin plugin runs successfully."
  echo "================================================================"
  exit 0
fi
echo "  RESULT: verification FAILED."
echo "================================================================"
exit 1
