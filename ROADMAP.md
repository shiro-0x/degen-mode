# Roadmap

Consolidated from two external reviews and a self-review (2026-07).
DEGEN says: record failures, keep an improvement log. This is that log.

## P0 — Honesty & legal basics

- [ ] **Label the README benchmark sample as mock output.** The `-38% / -41%`
  table in the Benchmarking section comes from the included mock agent
  (synthetic, built to show a speedup). Presenting it unlabeled violates our
  own No Fake Hype rule. Label it clearly or replace it with real,
  multi-repeat measurements.
- [ ] **Add a LICENSE.** *(needs owner decision — MIT recommended.)* Without
  one, nobody can legally use this at all.

## P1 — Safety UX

- [ ] **`--dry-run` / `diff`:** show exactly which files would change and the
  unified diff of the managed block, before writing anything.
- [ ] **Require confirmation for `--global`:** refuse home-level writes
  without `--yes` (they affect every project on the machine).
- [ ] **README Safety & limitations section:** who this is for; not suited to
  large refactors, ambiguous specs, or production operations; DEGEN does not
  guarantee quality; team use should go through review; some agents may
  ignore instruction files. Also adopt a more sober tagline
  ("a fast, reversible, safety-aware action policy for AI coding agents").
- [ ] **Mark the Grok mapping as experimental** in `agents` output and the
  README table (no confirmed dedicated config convention; targets AGENTS.md).

## P2 — Engineering hygiene

- [ ] **CI (GitHub Actions):** `shellcheck degen.sh`, smoke tests
  (install / append-to-existing / idempotent re-install / status /
  uninstall-restores-content), and a mock run of `degen_bench.py`.
- [ ] **Robustness fixes in `degen.sh`:** `trap`-based temp-file cleanup;
  create temp files next to the target so `mv` is atomic; clearer `status`
  wording than `present, no`; document that `DEGEN_TARGETS` is
  space-separated (paths with spaces unsupported).
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
