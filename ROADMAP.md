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

- [x] **Quality signal in degen-bench:** done. `--tasks` accepts a `.json`
  file of `{"prompt", "check"}` pairs; the agent's answer is piped to
  `check` on stdin, exit 0 = pass, and the report shows a `check%` column
  (`bench/tasks_with_checks.example.json`). Building the example surfaced
  two real bugs worth naming: (1) the first draft of the ISO-8601 duration
  check asserted the wrong expected value (9000 instead of the correct
  95400 for `P1DT2H30M`), which would have silently scored a correct model
  answer as a failure — caught by manually inspecting a real Claude
  response instead of trusting the check; (2) the bash-one-liner check
  choked on a real answer the model wrapped in backticks, fixed by
  stripping common code-fence/backtick wrapping before executing.
- [x] **Publish a real benchmark run** (n=6/condition — still small, framed
  as a lead not a verdict; ≥5 repeats target still open for a larger run).
  Result, and it's the opposite of the mock sample: DEGEN was slower
  (+37% wall / +49% agent time), used far more output tokens (+944%!),
  and passed its quality check less often (50% vs 100%) on these three
  tasks. Root-caused by hand: the `[DEGEN]` announce prefix is
  intermittently (~1 in 3 tries observed) emitted even on tasks that ask
  for a bare, machine-parseable answer, breaking strict JSON/code-only
  checks and inflating tokens with the extra framing. Documented in the
  README benchmarking section and Safety & limitations. This is a real,
  reproducible cost of the announce feature as currently implemented,
  not just noise — see the next item.
- [ ] **Announce feature vs. strict-output tasks.** *(needs owner decision.)*
  Given the finding above, options: (a) leave `--announce` on by default as
  today and rely on users passing `--no-announce` for strict-format tasks
  (current state); (b) have the installed instruction explicitly carve out
  an exception ("...except when the task requires bare machine-parseable
  output"); (c) turn announce off by default. (a) keeps the original
  "can't forget it's on" goal fully intact and is the status quo; (b) adds
  wording complexity to DEGEN.min for a corner case; (c) contradicts the
  explicit "on by default" requirement this feature was built to satisfy.
  No change made pending a decision.
- [ ] **DEGEN.min wording / safe variant.** *(needs owner decision — this is
  the manifesto.)* Reviewers flagged `unclear→simple` and `works→push` as
  risky when read literally by an agent. Options: (a) amend the core text
  (e.g. `works→test→push`), (b) ship an optional safety-explicit variant
  selectable at install time, (c) keep as-is and rely on the Safety docs.
- [ ] **Larger real benchmark run** (≥5 repeats, more/varied tasks) to see
  if the n=6 finding above holds up or was itself a small-sample artifact.

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
