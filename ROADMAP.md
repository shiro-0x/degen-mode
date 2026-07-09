# Roadmap

Consolidated from two external reviews and a self-review (2026-07).
DEGEN says: record failures, keep an improvement log. This is that log.

## P0 — Honesty & legal basics

- [x] **Label the README benchmark sample as mock output.** Done: the sample
  table is now explicitly marked as mock-agent output with a note that no
  real multi-repeat benchmark has been published yet.
- [x] **Add a LICENSE.** Done: MIT (`LICENSE`), per the recommendation above.

## P1 — Safety UX

- [x] **`--dry-run` / diff:** done. `--dry-run` prints a unified diff of every
  file that would change (via `diff -u`) and writes nothing — verified it has
  zero filesystem side effects (no directories created either).
- [x] **Require confirmation for `--global`:** done. `install`/`uninstall`
  refuse to run with `--global` unless `--yes` is also passed; `--dry-run`
  alone is allowed through since it doesn't write anything.
- [x] **README Safety & limitations section:** done, plus a more sober
  tagline in the README's opening line.
- [x] **Mark the Grok mapping as experimental:** done, in both `./degen.sh
  agents` output and the README table.

## P2 — Engineering hygiene

- [x] **CI (GitHub Actions):** done (`.github/workflows/ci.yml`, three jobs:
  shellcheck, `tests/smoke.sh`, and a mock run of `degen_bench.py`). Building
  it surfaced a real bug: the README/CI examples used a relative
  `bench/mock_agent.py` path in `--agent-cmd`, which fails because each
  benchmark run executes with its cwd set to a temp workspace, not the
  directory `degen_bench.py` was launched from — every run errored out
  silently into the "err" column. Fixed by adding a `{mock_agent}` template
  placeholder (resolved to an absolute path) alongside `{task}`.
- [x] **Robustness fixes in `degen.sh`:** done. Temp files are tracked in an
  array and cleaned up via a single script-level `EXIT` trap (a function-local
  `trap ... RETURN` was tried first and found to be a bug — it isn't
  function-scoped in bash, it fires on every subsequent function return and
  corrupted the caller; switched to the array + EXIT approach). Temp files
  are created next to the target so `mv` is same-filesystem/atomic, except
  under `--dry-run` where the target directory is deliberately left untouched.
  `status` wording clarified (`file exists, no DEGEN` instead of
  `present, no`). `DEGEN_TARGETS` space-separated behavior documented in the
  README. Also fixed, while touching this code: an unrelated bug where
  re-running `install` on a file containing only the DEGEN block added a
  spurious leading blank line, and a typo (`appendd` instead of `appended`)
  introduced while adding the dry-run verb/past-tense split.
- [ ] **Cut v0.1.0** once CI is green; add repo description/topics on GitHub
  (owner action).

## P3 — Evidence & product

- [ ] **Quality signal in degen-bench:** allow a per-task check command
  (e.g. run the produced snippet's doctests) and record pass/fail per
  condition, so speed gains can't hide quality losses. Publish a real
  benchmark run (≥5 repeats, several tasks, quality checks) in the README.
- [ ] **DEGEN.min wording / safe variant.** *(needs owner decision — this is
  the manifesto.)* Reviewers flagged `unclear→simple` and `works→push` as
  risky when read literally by an agent. Options: (a) amend the core text
  (e.g. `works→test→push`), (b) ship an optional safety-explicit variant
  selectable at install time, (c) keep as-is and rely on the Safety docs.

## Later / maybe

- `doctor` command (detect missing/duplicate/conflicting instruction files).
- Instruction-conflict linting across agent files.
- Multiple built-in templates (safe / balanced / degen).

## Considered and rejected (for now)

- **Renaming the project.** The name is the identity; the tagline and Safety
  docs carry the seriousness instead.
- **Pivoting to a general "agent policy manager."** Scope creep. Smallness is
  the feature. Revisit only if real usage demands it.
- **Enterprise-readiness as a goal.** This is a personal experiment tool
  first; the P0–P2 items above are worth doing regardless.
