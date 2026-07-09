#!/usr/bin/env bash
# Smoke tests for degen.sh. Run from anywhere; paths are resolved relative to
# this file. Exits non-zero on first failure.
set -euo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(dirname "$TESTS_DIR")"
DEGEN="$REPO_ROOT/degen.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0
fail=0

assert() {
  local desc="$1"; shift
  if "$@"; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    echo "FAIL: $desc"
  fi
}

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    echo "FAIL: $desc (expected [$expected], got [$actual])"
  fi
}

# ---- 1. fresh install creates the cross-tool files ---------------------
d="$WORK/t1"; mkdir -p "$d"
"$DEGEN" install --dir "$d" >/dev/null
assert "t1: CLAUDE.md created" [ -f "$d/CLAUDE.md" ]
assert "t1: AGENTS.md created" [ -f "$d/AGENTS.md" ]
assert "t1: GEMINI.md created" [ -f "$d/GEMINI.md" ]
assert "t1: copilot-instructions.md created" [ -f "$d/.github/copilot-instructions.md" ]
assert "t1: no announce line by default" bash -c "! grep -q 'Announce' '$d/CLAUDE.md'"

# ---- 2. re-running install is idempotent (no duplicate blocks) ---------
"$DEGEN" install --dir "$d" >/dev/null
markers="$(grep -cF 'DEGEN:START' "$d/CLAUDE.md")"
assert_eq "t2: idempotent re-install (single marker)" "1" "$markers"

# ---- 3. install appends to a file with existing content -----------------
d="$WORK/t3"; mkdir -p "$d"
printf '# My notes\nkeep this\n' > "$d/CLAUDE.md"
"$DEGEN" install --dir "$d" --agent claude >/dev/null
assert "t3: original content preserved" bash -c "grep -q 'keep this' '$d/CLAUDE.md'"
assert "t3: DEGEN block appended" bash -c "grep -qF 'DEGEN:START' '$d/CLAUDE.md'"

# ---- 4. uninstall removes files it created, restores the rest -----------
d="$WORK/t4"; mkdir -p "$d"
"$DEGEN" install --dir "$d" >/dev/null
printf '# proj\nhello\n' > "$d/CONVENTIONS.md"
"$DEGEN" install --dir "$d" --agent aider >/dev/null
"$DEGEN" uninstall --dir "$d" >/dev/null
assert "t4: pure-DEGEN file removed" bash -c "[ ! -e '$d/CLAUDE.md' ]"
assert "t4: file with prior content survives" [ -f "$d/CONVENTIONS.md" ]
assert_eq "t4: prior content restored exactly" "$(printf '# proj\nhello')" "$(cat "$d/CONVENTIONS.md")"

# ---- 5. --agent targets only the requested agent -------------------------
d="$WORK/t5"; mkdir -p "$d"
"$DEGEN" install --dir "$d" --agent claude >/dev/null
assert "t5: only CLAUDE.md created" bash -c "[ \"\$(ls '$d')\" = 'CLAUDE.md' ]"

# ---- 6. unknown agent name fails ------------------------------------------
d="$WORK/t6"; mkdir -p "$d"
set +e
"$DEGEN" install --dir "$d" --agent not-a-real-agent >/dev/null 2>"$WORK/t6.err"
rc=$?
set -e
assert_eq "t6: unknown agent exits non-zero" "2" "$rc"

# ---- 7. --dry-run writes nothing ------------------------------------------
d="$WORK/t7"; mkdir -p "$d"
"$DEGEN" install --dir "$d" --agent claude --dry-run >/dev/null
assert "t7: dry-run created no files" bash -c "[ -z \"\$(ls -A '$d')\" ]"

# ---- 8. --global refuses without --yes, allows --dry-run ------------------
gd="$WORK/fakehome"
set +e
HOME="$gd" "$DEGEN" install --global --agent claude >/dev/null 2>/dev/null
rc=$?
set -e
assert_eq "t8: --global without --yes exits non-zero" "2" "$rc"
assert "t8: --global without --yes creates nothing" bash -c "[ ! -e '$gd' ]"
HOME="$gd" "$DEGEN" install --global --agent claude --dry-run >/dev/null
assert "t8: --global --dry-run still creates nothing" bash -c "[ ! -e '$gd' ]"
HOME="$gd" "$DEGEN" install --global --agent claude --yes >/dev/null
assert "t8: --global --yes writes the file" [ -f "$gd/.claude/CLAUDE.md" ]

# ---- 9. announce is opt-in; status reports both modes ----------------------
d="$WORK/t9"; mkdir -p "$d"
"$DEGEN" install --dir "$d" --agent claude >/dev/null
out="$("$DEGEN" status --dir "$d" --agent claude)"
assert "t9: default install shows plain installed" bash -c "echo '$out' | grep -q '^installed  *' && ! echo '$out' | grep -q 'announce'"
"$DEGEN" install --dir "$d" --agent claude --announce >/dev/null
assert "t9: --announce adds the announce line" bash -c "grep -q 'Announce' '$d/CLAUDE.md'"
out="$("$DEGEN" status --dir "$d" --agent claude)"
assert "t9: status shows installed (announce)" bash -c "echo '$out' | grep -q 'installed (announce)'"
"$DEGEN" install --dir "$d" --agent claude >/dev/null
assert "t9: re-install without flag removes announce line" bash -c "! grep -q 'Announce' '$d/CLAUDE.md'"

echo
echo "smoke.sh: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
