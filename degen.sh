#!/usr/bin/env bash
#
# degen.sh — install / uninstall the DEGEN.min mindset into AI agent config files.
#
# The DEGEN block is inserted between marker comments so it can be updated or
# removed cleanly without touching the rest of your instructions.
#
#   ./degen.sh install            # install into this project's agent files
#   ./degen.sh install --global   # install into your home-level agent files
#   ./degen.sh uninstall          # remove from this project's agent files
#   ./degen.sh uninstall --global # remove from your home-level agent files
#   ./degen.sh status             # show where DEGEN is installed
#
# Options:
#   --global        Operate on home-level (~) agent files instead of the project.
#   --dir <path>    Operate on a specific project directory (default: cwd).
#   --all           Write to every known target even if the file doesn't exist yet.
#                   (Default: create the cross-tool files, and update any other
#                    agent files that already exist.)
#
# Override the target list with the DEGEN_TARGETS env var (space-separated paths).

set -euo pipefail

DEGEN_START="<!-- DEGEN:START — managed by degen.sh, do not edit inside this block -->"
DEGEN_END="<!-- DEGEN:END -->"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
SRC="$SCRIPT_DIR/DEGEN.min"

# ---- args -------------------------------------------------------------------

CMD="${1:-}"
[ $# -gt 0 ] && shift || true

GLOBAL=0
ALL=0
DIR="$PWD"

while [ $# -gt 0 ]; do
  case "$1" in
    --global) GLOBAL=1 ;;
    --all)    ALL=1 ;;
    --dir)    shift; DIR="${1:?--dir needs a path}" ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# ---- target selection -------------------------------------------------------

# Files that we will CREATE if missing (the cross-tool standards).
CREATE_FILES=()
# Files we only UPDATE when they already exist (tool-specific).
UPDATE_FILES=()

if [ -n "${DEGEN_TARGETS:-}" ]; then
  # user-provided list: create all of them
  # shellcheck disable=SC2206
  CREATE_FILES=($DEGEN_TARGETS)
elif [ "$GLOBAL" -eq 1 ]; then
  base="$HOME"
  CREATE_FILES=(
    "$base/.claude/CLAUDE.md"     # Claude Code (global)
    "$base/.codex/AGENTS.md"      # Codex / AGENTS.md standard (global)
    "$base/.gemini/GEMINI.md"     # Gemini CLI (global)
  )
  UPDATE_FILES=(
    "$base/.config/aider/CONVENTIONS.md"
  )
else
  base="$DIR"
  CREATE_FILES=(
    "$base/AGENTS.md"                          # cross-tool standard (Codex, etc.)
    "$base/CLAUDE.md"                           # Claude Code
    "$base/GEMINI.md"                           # Gemini CLI
    "$base/.github/copilot-instructions.md"     # GitHub Copilot
  )
  UPDATE_FILES=(
    "$base/.cursorrules"    # Cursor (legacy)
    "$base/.windsurfrules"  # Windsurf
    "$base/.clinerules"     # Cline
    "$base/CONVENTIONS.md"  # Aider
  )
fi

# ---- helpers ----------------------------------------------------------------

block() {
  # emit the full managed block (markers + content)
  printf '%s\n' "$DEGEN_START"
  cat "$SRC"
  printf '%s\n' "$DEGEN_END"
}

has_block() {
  [ -f "$1" ] && grep -qF "$DEGEN_START" "$1"
}

# print $1 with the DEGEN block removed and trailing blank lines trimmed
strip_block() {
  awk -v s="$DEGEN_START" -v e="$DEGEN_END" '
    index($0, s) { inblk=1; next }
    index($0, e) { inblk=0; next }
    !inblk { print }
  ' "$1" | awk '
    { lines[NR]=$0 }
    END {
      last=NR
      while (last>0 && lines[last] ~ /^[[:space:]]*$/) last--
      for (i=1; i<=last; i++) print lines[i]
    }
  '
}

install_one() {
  local f="$1" tmp
  tmp="$(mktemp)"
  mkdir -p "$(dirname "$f")"
  if has_block "$f"; then
    # update in place: strip old block, re-append fresh one
    { strip_block "$f"; [ -s "$f" ] && printf '\n'; block; } > "$tmp"
    mv "$tmp" "$f"
    echo "updated  $f"
  elif [ -f "$f" ]; then
    { cat "$f"; printf '\n'; block; } > "$tmp"
    mv "$tmp" "$f"
    echo "appended $f"
  else
    block > "$f"
    echo "created  $f"
  fi
}

uninstall_one() {
  local f="$1" tmp
  has_block "$f" || return 0
  tmp="$(mktemp)"
  strip_block "$f" > "$tmp"
  if [ -s "$tmp" ]; then
    mv "$tmp" "$f"
    echo "cleaned  $f"
  else
    # file had nothing but the DEGEN block -> we created it, remove it
    rm -f "$tmp" "$f"
    echo "removed  $f"
  fi
}

# ---- commands ---------------------------------------------------------------

cmd_install() {
  [ -f "$SRC" ] || { echo "error: $SRC not found" >&2; exit 1; }
  local wrote=0
  for f in "${CREATE_FILES[@]}"; do
    install_one "$f"; wrote=1
  done
  for f in "${UPDATE_FILES[@]}"; do
    if [ "$ALL" -eq 1 ] || [ -f "$f" ]; then
      install_one "$f"; wrote=1
    fi
  done
  [ "$wrote" -eq 1 ] && echo "DEGEN installed." || echo "nothing to do."
}

cmd_uninstall() {
  for f in "${CREATE_FILES[@]}" "${UPDATE_FILES[@]}"; do
    uninstall_one "$f"
  done
  echo "DEGEN uninstalled."
}

cmd_status() {
  local any=0
  for f in "${CREATE_FILES[@]}" "${UPDATE_FILES[@]}"; do
    if has_block "$f"; then echo "installed    $f"; any=1
    elif [ -f "$f" ]; then echo "present, no  $f"
    fi
  done
  [ "$any" -eq 1 ] || echo "DEGEN is not installed in these targets."
}

case "$CMD" in
  install)   cmd_install ;;
  uninstall) cmd_uninstall ;;
  status)    cmd_status ;;
  ""|-h|--help|help)
    sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)
    echo "unknown command: $CMD" >&2
    echo "usage: degen.sh {install|uninstall|status} [--global] [--dir PATH] [--all]" >&2
    exit 2
    ;;
esac
