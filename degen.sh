#!/usr/bin/env bash
#
# degen.sh — install / uninstall the DEGEN.min mindset into AI agent config files.
#
# The DEGEN block is inserted between marker comments so it can be updated or
# removed cleanly without touching the rest of your instructions.
#
#   ./degen.sh install                    # install into every known agent file
#   ./degen.sh install --agent claude     # install into just one agent (e.g. the one you're using now)
#   ./degen.sh install --global           # install into your home-level agent files
#   ./degen.sh uninstall                  # remove from this project's agent files
#   ./degen.sh uninstall --agent claude   # remove from just one agent
#   ./degen.sh status                     # show where DEGEN is installed
#   ./degen.sh agents                     # list known agent names
#
# Options:
#   --agent <name>  Target only this agent (repeatable, or comma-separated).
#                   Run `./degen.sh agents` to see valid names.
#   --no-announce   Omit the announce line. By default the installed block
#                   tells the agent to start every reply with "[DEGEN]", so
#                   you can't forget the mode is active. Re-run install with
#                   or without this flag to toggle it.
#   --dry-run       Show what would change (and a diff of each file) without
#                   writing anything. Works with both install and uninstall.
#   --global        Operate on home-level (~) agent files instead of the project.
#                   Requires --yes (or --dry-run to preview first) since it
#                   affects every project on the machine, not just this one.
#   --yes           Confirm a --global install/uninstall.
#   --dir <path>    Operate on a specific project directory (default: cwd).
#   --all           Write to every known target even if the file doesn't exist yet.
#                   (Default: create the cross-tool files, and update any other
#                    agent files that already exist. Ignored when --agent is set,
#                    since an explicit --agent always creates its file.)
#
# Override the target list with the DEGEN_TARGETS env var (space-separated paths).

set -euo pipefail

DEGEN_START="<!-- DEGEN:START — managed by degen.sh, do not edit inside this block -->"
DEGEN_END="<!-- DEGEN:END -->"
DEGEN_ANNOUNCE='Announce: start every reply with "[DEGEN]", except when the task requires a bare, machine-parseable answer (pure JSON, code-only, etc.) — then omit it so the output stays parseable.'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
SRC="$SCRIPT_DIR/DEGEN.min"

# ---- agent registry ----------------------------------------------------------
# id -> human label, project-relative file, home-relative file (blank = no global target)

declare -A AGENT_LABEL=(
  [claude]="Claude Code"
  [codex]="Codex / AGENTS.md standard"
  [gemini]="Gemini CLI"
  [copilot]="GitHub Copilot"
  [cursor]="Cursor"
  [windsurf]="Windsurf"
  [cline]="Cline"
  [aider]="Aider"
  [grok]="Grok (xAI) — via AGENTS.md standard (experimental, unverified)"
)
declare -A AGENT_PROJECT_FILE=(
  [claude]="CLAUDE.md"
  [codex]="AGENTS.md"
  [gemini]="GEMINI.md"
  [copilot]=".github/copilot-instructions.md"
  [cursor]=".cursorrules"
  [windsurf]=".windsurfrules"
  [cline]=".clinerules"
  [aider]="CONVENTIONS.md"
  [grok]="AGENTS.md"
)
declare -A AGENT_GLOBAL_FILE=(
  [claude]=".claude/CLAUDE.md"
  [codex]=".codex/AGENTS.md"
  [gemini]=".gemini/GEMINI.md"
  [aider]=".config/aider/CONVENTIONS.md"
)
# Default project-mode behavior when no --agent is given: which ids are
# always created vs. only updated if the file already exists.
DEFAULT_CREATE_AGENTS=(claude codex gemini copilot)
DEFAULT_UPDATE_AGENTS=(cursor windsurf cline aider)

# ---- args -------------------------------------------------------------------

CMD="${1:-}"
if [ $# -gt 0 ]; then shift; fi

GLOBAL=0
ALL=0
ANNOUNCE=1
DRYRUN=0
YES=0
DIR="$PWD"
AGENTS_SELECTED=()

while [ $# -gt 0 ]; do
  case "$1" in
    --global)      GLOBAL=1 ;;
    --all)         ALL=1 ;;
    --no-announce) ANNOUNCE=0 ;;
    --dry-run)     DRYRUN=1 ;;
    --yes)         YES=1 ;;
    --dir)    shift; DIR="${1:?--dir needs a path}" ;;
    --agent)
      shift
      IFS=',' read -ra _parts <<< "${1:?--agent needs a name (see: degen.sh agents)}"
      AGENTS_SELECTED+=("${_parts[@]}")
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

for a in "${AGENTS_SELECTED[@]:-}"; do
  [ -z "$a" ] && continue
  if [ -z "${AGENT_LABEL[$a]:-}" ]; then
    echo "unknown agent: $a" >&2
    echo "known agents: ${!AGENT_LABEL[*]}" >&2
    exit 2
  fi
done

if [ "$GLOBAL" -eq 1 ] && [ "$YES" -ne 1 ] && [ "$DRYRUN" -ne 1 ] \
   && { [ "$CMD" = "install" ] || [ "$CMD" = "uninstall" ]; }; then
  echo "refusing: --global affects every project on this machine." >&2
  echo "Preview first with --dry-run, or confirm with --yes." >&2
  exit 2
fi

# ---- target selection -------------------------------------------------------

# Files that we will CREATE if missing (the cross-tool standards, or anything
# explicitly requested via --agent).
CREATE_FILES=()
# Files we only UPDATE when they already exist (tool-specific, default mode only).
UPDATE_FILES=()

if [ -n "${DEGEN_TARGETS:-}" ]; then
  # user-provided list: create all of them
  # shellcheck disable=SC2206
  CREATE_FILES=($DEGEN_TARGETS)
elif [ "${#AGENTS_SELECTED[@]}" -gt 0 ]; then
  # explicit --agent selection: always create/update that agent's file, in
  # whichever scope (project/global) was requested.
  for a in "${AGENTS_SELECTED[@]}"; do
    if [ "$GLOBAL" -eq 1 ]; then
      rel="${AGENT_GLOBAL_FILE[$a]:-}"
      [ -z "$rel" ] && { echo "agent '$a' has no --global target (it's project-only)" >&2; exit 2; }
      CREATE_FILES+=("$HOME/$rel")
    else
      CREATE_FILES+=("$DIR/${AGENT_PROJECT_FILE[$a]}")
    fi
  done
elif [ "$GLOBAL" -eq 1 ]; then
  base="$HOME"
  for a in "${DEFAULT_CREATE_AGENTS[@]}"; do
    rel="${AGENT_GLOBAL_FILE[$a]:-}"
    [ -n "$rel" ] && CREATE_FILES+=("$base/$rel")
  done
  for a in "${DEFAULT_UPDATE_AGENTS[@]}"; do
    rel="${AGENT_GLOBAL_FILE[$a]:-}"
    [ -n "$rel" ] && UPDATE_FILES+=("$base/$rel")
  done
else
  base="$DIR"
  for a in "${DEFAULT_CREATE_AGENTS[@]}"; do
    CREATE_FILES+=("$base/${AGENT_PROJECT_FILE[$a]}")
  done
  for a in "${DEFAULT_UPDATE_AGENTS[@]}"; do
    UPDATE_FILES+=("$base/${AGENT_PROJECT_FILE[$a]}")
  done
fi

# ---- helpers ----------------------------------------------------------------

# Temp files are tracked here and cleaned up on any exit (success, error, or
# an early exit from set -e), instead of relying on a function-local trap —
# `trap ... RETURN` in bash is not function-scoped, it fires on every
# function return until explicitly cleared, which corrupts the caller.
TMP_FILES=()
cleanup_tmp_files() {
  local t
  for t in "${TMP_FILES[@]}"; do
    rm -f "$t"
  done
}
trap cleanup_tmp_files EXIT

block() {
  # emit the full managed block (markers + content)
  printf '%s\n' "$DEGEN_START"
  cat "$SRC"
  [ "$ANNOUNCE" -eq 1 ] && printf '%s\n' "$DEGEN_ANNOUNCE"
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
  local f="$1" dir tmp verb past rest
  dir="$(dirname "$f")"
  if [ "$DRYRUN" -eq 1 ]; then
    # no side effects on preview: don't create the target directory, just a
    # scratch tmp file to diff against.
    tmp="$(mktemp)"
  else
    mkdir -p "$dir"
    tmp="$(mktemp "$dir/.degen.tmp.XXXXXX")"
  fi
  TMP_FILES+=("$tmp")

  if has_block "$f"; then
    verb="update"; past="updated"
    rest="$(strip_block "$f")"
    if [ -n "$rest" ]; then
      { printf '%s\n\n' "$rest"; block; } > "$tmp"
    else
      block > "$tmp"
    fi
  elif [ -f "$f" ]; then
    verb="append"; past="appended"
    { cat "$f"; printf '\n'; block; } > "$tmp"
  else
    verb="create"; past="created"
    block > "$tmp"
  fi

  if [ "$DRYRUN" -eq 1 ]; then
    echo "would $verb  $f"
    diff -u "$( [ -f "$f" ] && echo "$f" || echo /dev/null )" "$tmp" || true
    return
  fi

  mv "$tmp" "$f"
  printf '%-9s %s\n' "$past" "$f"
}

uninstall_one() {
  local f="$1" tmp
  has_block "$f" || return 0
  tmp="$(mktemp "$(dirname "$f")/.degen.tmp.XXXXXX")"
  TMP_FILES+=("$tmp")
  strip_block "$f" > "$tmp"

  if [ "$DRYRUN" -eq 1 ]; then
    if [ -s "$tmp" ]; then
      echo "would clean   $f"
      diff -u "$f" "$tmp" || true
    else
      echo "would remove  $f"
    fi
    return
  fi

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
  if [ "$wrote" -ne 1 ]; then
    echo "nothing to do."
  elif [ "$DRYRUN" -eq 1 ]; then
    echo "(dry run — nothing written; re-run without --dry-run to apply)"
  else
    echo "DEGEN installed."
  fi
}

cmd_uninstall() {
  for f in "${CREATE_FILES[@]}" "${UPDATE_FILES[@]}"; do
    uninstall_one "$f"
  done
  if [ "$DRYRUN" -eq 1 ]; then
    echo "(dry run — nothing written; re-run without --dry-run to apply)"
  else
    echo "DEGEN uninstalled."
  fi
}

cmd_status() {
  local any=0
  for f in "${CREATE_FILES[@]}" "${UPDATE_FILES[@]}"; do
    if has_block "$f"; then
      if grep -qF "$DEGEN_ANNOUNCE" "$f"; then
        echo "installed             $f"
      else
        echo "installed (silent)    $f"
      fi
      any=1
    elif [ -f "$f" ]; then
      echo "file exists, no DEGEN $f"
    fi
  done
  [ "$any" -eq 1 ] || echo "DEGEN is not installed in these targets."
}

cmd_agents() {
  printf '%-10s %-28s %s\n' "id" "agent" "project file"
  for a in "${!AGENT_LABEL[@]}"; do
    printf '%-10s %-28s %s\n' "$a" "${AGENT_LABEL[$a]}" "${AGENT_PROJECT_FILE[$a]}"
  done | sort
}

case "$CMD" in
  install)   cmd_install ;;
  uninstall) cmd_uninstall ;;
  status)    cmd_status ;;
  agents)    cmd_agents ;;
  ""|-h|--help|help)
    # print the leading comment header (skip the shebang, stop at first code line)
    awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"
    ;;
  *)
    echo "unknown command: $CMD" >&2
    echo "usage: degen.sh {install|uninstall|status|agents} [--agent NAME] [--dry-run] [--global --yes] [--dir PATH] [--all]" >&2
    exit 2
    ;;
esac
