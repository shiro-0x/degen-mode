# degen-mode

A small, reversible installer for a fast-but-safe action policy across AI
coding agents — with one command, and remove it just as easily.

DEGEN is a builder mindset: move fast, test boldly, stay honest, and create
real value without losing responsibility. The full principles are in
[`DEGEN.md`](./DEGEN.md); the compact version that gets installed into agents
is [`DEGEN.min`](./DEGEN.min):

```
# DEGEN.min

Act now. Build small. Ship. Learn.
No wait / fake / spam / chaos.
unclear→simple · big→cut · broken→fix · dead→drop · works→push
fail = data · speed ≤ safe
Show progress.
∴ Smallest safe action. Now.
```

## Install

```sh
./degen.sh install                          # into every known agent file
./degen.sh install --agent claude           # into just one agent (e.g. the one you're using now)
./degen.sh install --dry-run                # preview only — writes nothing
./degen.sh install --global --yes           # into your home-level agent files
```

The DEGEN block is inserted between marker comments, so it never clobbers
instructions you already have — existing files are appended to, and re-running
`install` updates the block in place instead of duplicating it.

Not sure what it'll do? Run it with `--dry-run` first — it prints a unified
diff of every file it would touch and writes nothing. `--global` (home-level
config, affecting every project on the machine) refuses to run at all unless
you either pass `--yes` or are just previewing with `--dry-run`.

Optionally, `--announce` adds an instruction telling the agent to **start
every reply with `[DEGEN]`**, so you can't forget the mode is active. This
is **off by default**: our own benchmark measured the prefix leaking into
strict-format output (pure JSON, code-only answers) and breaking parsers —
see [the benchmark findings below](#a-real-result-and-what-it-means). Enable
it only if your tasks are conversational; re-running `install` with or
without the flag toggles it, and `status` shows which mode each file is in
(`installed` vs `installed (announce)`).

## Try it on one agent first

Applying DEGEN to every agent at once isn't always what you want. If you're
only using one agent right now, target just that one:

```sh
./degen.sh agents                 # list agent ids
./degen.sh install --agent claude # install into CLAUDE.md only
```

`--agent` accepts multiple names, repeated or comma-separated
(`--agent claude,cursor`). Once you're happy with it, run `install` again
without `--agent` to roll it out to the rest.

## Uninstall

```sh
./degen.sh uninstall                  # remove from this project's agent files
./degen.sh uninstall --agent claude   # remove from just one agent
./degen.sh uninstall --dry-run        # preview what would be removed
./degen.sh uninstall --global --yes   # remove from your home-level agent files
```

Uninstall removes only the managed DEGEN block. Files that contained nothing
but the block (i.e. that `degen-mode` created) are deleted; files that had your
own content are left intact with the block cleanly stripped out.

## Status

```sh
./degen.sh status                   # show which targets have DEGEN installed
./degen.sh status --agent claude    # check just one agent
```

## What gets written

By default, in a project, the tool **creates** the cross-tool instruction
files and **updates** any tool-specific files that already exist:

| File                               | Agent            | Behavior         |
| ---------------------------------- | ---------------- | ---------------- |
| `AGENTS.md`                        | Codex / standard | created          |
| `CLAUDE.md`                        | Claude Code      | created          |
| `GEMINI.md`                        | Gemini CLI       | created          |
| `.github/copilot-instructions.md`  | GitHub Copilot   | created          |
| `.cursorrules`                     | Cursor           | updated if present |
| `.windsurfrules`                   | Windsurf         | updated if present |
| `.clinerules`                      | Cline            | updated if present |
| `CONVENTIONS.md`                   | Aider            | updated if present |

With `--global`, it targets home-level config instead
(`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`, …).

**Grok — experimental / unverified mapping:** there's no confirmed dedicated
config-file convention for Grok tooling, so `--agent grok` targets the same
`AGENTS.md` cross-tool standard file as `codex`, as a guess (it's not
included in the plain default `install` to avoid writing that file twice —
use it explicitly: `./degen.sh install --agent grok`). `./degen.sh agents`
labels it `(experimental)` for the same reason. If your Grok tool actually
reads a different file, open an issue or tell us the path and we'll add a
verified mapping.

## Options

| Option         | Description                                                              |
| -------------- | ------------------------------------------------------------------------- |
| `--agent NAME` | Target only this agent (repeatable, or comma-separated). Always creates its file, since you asked for it explicitly. See `./degen.sh agents`. |
| `--announce`   | Add the `[DEGEN]` reply-prefix instruction to the installed block. Off by default — measured to break strict-format output (see benchmark findings). `--no-announce` is still accepted and matches the default. |
| `--dry-run`    | Show what would change, and a diff of each file, without writing anything. |
| `--global`     | Operate on home-level (`~`) agent files instead of the project. Requires `--yes` (or `--dry-run` to preview first). |
| `--yes`        | Confirm a `--global` install/uninstall.                                  |
| `--dir PATH`   | Operate on a specific project directory (default: current dir).         |
| `--all`        | Write to every known target even if the file doesn't exist yet. Ignored when `--agent` is set. |

You can override the target list entirely with an environment variable
(space-separated paths — paths containing spaces aren't supported):

```sh
DEGEN_TARGETS="AGENTS.md docs/agent.md" ./degen.sh install
```

## How it works

The installer wraps `DEGEN.min` in HTML comment markers:

```
<!-- DEGEN:START — managed by degen.sh, do not edit inside this block -->
...DEGEN.min...
<!-- DEGEN:END -->
```

Because the block is delimited, `degen.sh` can find it later to update or
remove it without disturbing anything else in the file. It's idempotent: run
`install` as many times as you like.

## Benchmarking: does DEGEN actually make your agent faster?

Don't take the mindset's word for it — measure it. `bench/degen_bench.py`
runs the same prompt with and without the DEGEN block and compares outcome,
token consumption, and speed. Every run is an **independent subagent** — a
fresh agent process in its own isolated temp workspace, with DEGEN installed
via `degen.sh` itself — so the only thing that differs between conditions is
the instruction files present.

The quickest way in is `ab`: give it one prompt, and it drives subagents
across conditions (in parallel by default with `--parallel`) and shows you
the answers side by side plus the metrics:

```sh
python3 bench/degen_bench.py ab "Refactor this function to be pure" --repeats 5 --parallel 5
python3 bench/degen_bench.py ab "Return JSON with keys a,b summing to 10" --check "python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"a\"]+d[\"b\"]==10'"
python3 bench/degen_bench.py ab "Write a haiku about tests" --save-answers /tmp/ab
```

For a whole suite of tasks instead of a single prompt, use `run`:

```sh
python3 bench/degen_bench.py run                       # baseline vs degen, 3 repeats
python3 bench/degen_bench.py run --repeats 5 --parallel 4 --tasks bench/tasks.txt
python3 bench/degen_bench.py report bench/results/<file>.jsonl [--answers]
```

`--parallel N` runs up to N subagents at once — a big wall-clock win when you
have many runs (in-process test: 6 mock runs went 8.9s → 1.8s at
`--parallel 6`). Each run is independent, so the only limit is your API rate
limit. The report's `tot tok` column is total token consumption (input
including cache, plus output); `in tok` / `out tok` break it down.

Sample output — **from the included mock agent** (`bench/mock_agent.py`),
which is a synthetic stand-in built to simulate a speedup, not a measurement
of any real model. It exists to prove the harness works end-to-end. Run the
real thing yourself before drawing any conclusion (see below):

```
| condition | runs | err | wall s | Δwall | agent s | turns | in tok | out tok | tot tok | Δtot | cost $ |
|-----------|------|-----|--------|-------|---------|-------|--------|---------|---------|------|--------|
| baseline  | 10   | 0   | 1.85   | +0%   | 1.82    | 5     | 1200   | 320     | 1520    | +0%  | 0.0096 |
| degen     | 10   | 0   | 1.22   | -34%  | 1.18    | 3     | 1200   | 202     | 1402    | -8%  | 0.0061 |
```

The default agent command is `claude -p {task} --output-format json
--max-turns 8`; swap in any agent with `--agent-cmd` (the `{task}`
placeholder is replaced with the prompt). To verify the harness without
API cost, point it at the included mock — use the `{mock_agent}` placeholder
rather than a relative path, since each run's working directory is a fresh
temp workspace, not the directory you launched the command from:

```sh
python3 bench/degen_bench.py run --agent-cmd 'python3 {mock_agent} {task}'
python3 bench/degen_bench.py ab "any prompt" --agent-cmd 'python3 {mock_agent} {task}'
```

### Quality checks — a speedup doesn't count if the answer is wrong

`--tasks` also accepts a `.json` file of `[{"prompt": ..., "check": "shell
cmd"}]` instead of a plain prompt list (see
`bench/tasks_with_checks.example.json`). The agent's answer is piped to
`check` on stdin; exit 0 counts as a pass, and the report gets a `check%`
column per condition:

```sh
python3 bench/degen_bench.py run --tasks bench/tasks_with_checks.example.json --repeats 5
```

### A real result, and what it means

We ran the example above against the real `claude` CLI (n=6 per condition —
still small, treat as a lead not a verdict):

```
| condition | runs | err | wall s | Δ    | agent s | Δ    | turns | out tok | Δ     | cost $ | check% |
|-----------|------|-----|--------|------|---------|------|-------|---------|-------|--------|--------|
| baseline  | 6    | 0   | 4.33   | +0%  | 3.27    | +0%  | 1     | 22      | +0%   | 0.0309 | 100%   |
| degen     | 6    | 0   | 5.96   | +37% | 4.86    | +49% | 1     | 235     | +944% | 0.0365 | 50%    |
```

This is the opposite of what the mock sample above suggests, and we're
reporting it because it's real: DEGEN was **slower, used far more tokens,
and passed its quality check less often** on these tasks. Digging into why
(reproduced by hand, not just in this run): the `[DEGEN]` announce prefix
(see [Install](#install)) is sometimes emitted even on tasks that explicitly
ask for a bare, machine-parseable answer ("JSON only, no prose", "one bash
line, no explanation") —

```
$ claude -p 'Reply with valid JSON only...' # with DEGEN installed
[DEGEN] {"a": 4, "b": 6}
```

— which breaks a strict `json.loads()` or similar check on the answer, and
the model sometimes spends extra output on that framing. It doesn't happen
every time (roughly 1 in 3 tries here), which is exactly why small samples
are misleading in both directions.

**First mitigation attempt:** we added an explicit carve-out to the announce
instruction ("...except when the task requires a bare, machine-parseable
answer"). Re-testing by hand, 5 tries each: the JSON-only task came back
clean 5/5, but the bash-one-liner task did **not** improve at all — still
5/5 prefixed with `[DEGEN]`. A partial fix, not a full one.

**Isolation experiment (what actually causes the slowdown):** to separate
the announce line's effect from the DEGEN block itself, we ran three
conditions — baseline, DEGEN with announce, DEGEN without announce — same
three checked tasks, n=12 per condition (36 real runs, carve-out wording
included):

```
| condition      | runs | err | agent s | Δ    | out tok | Δ    | check% |
|----------------|------|-----|---------|------|---------|------|--------|
| baseline       | 12   | 0   | 3.64    | +0%  | 20      | +0%  | 100%   |
| degen-announce | 12   | 0   | 4.27    | +17% | 32      | +60% | 75%    |
| degen-silent   | 12   | 0   | 4.00    | +10% | 25      | +25% | 100%   |
```

Per-task, the verdict is clean: every quality failure came from the
announce condition (bash one-liner: 1/4 passing with announce, 4/4 without),
and the announce line also accounts for most of the extra tokens and
latency. The DEGEN block *by itself* lost nothing on quality (12/12), and on
the one longer code-writing task it actually produced a slightly shorter
answer than baseline (313 vs 348 tokens median). What remains with announce
off is a modest fixed cost (~+10% agent time here) — the block itself is
extra input context the model must read, which you pay on every request and
notice most on tiny tasks.

**As a result of this measurement, the announce feature is now off by
default** (opt back in with `--announce`). If you enable it, don't use it on
tasks that need bare, parseable output. And as always: don't trust anyone's
speedup claim (including the mock sample above) without running the
benchmark on your own tasks with `--repeats 5` or more.

### The harder question: multi-turn build tasks

Everything above used single-turn tasks (`turns` was always 1). But DEGEN's
whole thesis — "build small, smallest safe action, ship" — is about
*agentic* work: tasks where the model can go around several times and might
over-engineer. So we built `bench/tasks_multiturn.example.json`: three small,
mildly under-specified "write a working file" tasks, each verified by
actually running the produced code (the harness runs `check` with its cwd set
to the run's workspace, so it can inspect files the agent wrote, not just the
reply text). Run with a permissive agent command:

```sh
python3 bench/degen_bench.py run --tasks bench/tasks_multiturn.example.json \
  --agent-cmd 'claude -p {task} --output-format json --max-turns 12 --permission-mode acceptEdits' \
  --repeats 3 --parallel 3
```

Result (n=9 per condition, real `claude`, every run produced working code —
100% check pass on both sides):

```
| condition | runs | wall s | Δwall | turns | tot tok | Δtot | check% |
|-----------|------|--------|-------|-------|---------|------|--------|
| baseline  | 9    | 11.72  | +0%   | 3     | 97522   | +0%  | 100%   |
| degen     | 9    | 11.19  | -4%   | 3     | 98168   | +1%  | 100%   |
```

Overall: **basically no difference** — and note this is *not* the net-negative
we saw on trivial tasks, so the block's fixed cost stops mattering once the
task itself is substantial. But the per-task breakdown is the honest story,
because it's genuinely mixed:

| task | baseline | degen | who won |
|------|----------|-------|---------|
| slug.py     | 4 turns / 130k tok | 3 turns / 98k tok | **DEGEN** (baseline over-worked it) |
| parse_kv.py | 2 turns / 65k tok  | 3 turns / 98k tok | **baseline** (DEGEN added a turn) |
| fizzbuzz.py | 3 turns / 98k tok  | 3 turns / 98k tok | tie |

DEGEN helped exactly where its thesis predicts — the `slug` task, where
baseline took an extra pass to polish and DEGEN shipped the minimal working
version (−25% tokens, quality identical, and this held across all 3 repeats).
But it *cost* an extra turn on `parse_kv`, and did nothing on `fizzbuzz`, so
the average is a wash. Honest read: **on real multi-turn work DEGEN is roughly
neutral, not the clear win or clear loss either extreme would suggest — it
nudges the model toward "smallest thing that works," which helps when the
model would otherwise gold-plate and hurts when it would have stopped anyway.**
Caveats: only 3 similar coding tasks, n=3 each, high variance (turns ranged
2–5); `acceptEdits` means the agent couldn't run its own code to self-test, so
this doesn't cover exploratory/test-driven loops. A bigger, more varied run is
the obvious next step (the whole thing cost ~$1.50, so it's cheap to extend).

### Comparing effort levels

Some argue that switching the model's effort/thinking budget matters more
than a mindset block. Conditions are a JSON file, and each condition can set
`env` and `extra_args` — so you can put both hypotheses in the same run:

```json
[
  { "name": "baseline", "degen": false },
  { "name": "degen", "degen": true },
  { "name": "degen-low-effort", "degen": true,
    "env": { "MAX_THINKING_TOKENS": "1024" } },
  { "name": "degen-other-model", "degen": true,
    "extra_args": ["--model", "claude-haiku-4-5"] }
]
```

```sh
python3 bench/degen_bench.py run --conditions bench/conditions.example.json
```

Caveats: results vary run to run — use `--repeats 5` or more and read the
medians. Judge by turns and output tokens as well as time: the DEGEN block
changes *behavior* (fewer turns, shorter output), not raw model latency.
And faster isn't automatically better — spot-check that the answers are
still good.

## Safety & limitations

Read this before installing, especially with `--global`.

**Who this is for:** individual developers who want their agent to move
faster on small, well-scoped tasks, and are comfortable reviewing its output.

**What DEGEN does not do:**
- It does not guarantee code quality, correctness, or security. It's an
  instruction block, not a test suite — review the agent's work the same as
  you would without it.
- It does not make destructive operations safe. The agent still decides what
  "safe" means at a given moment; DEGEN asks for judgment, it doesn't enforce
  it.
- It cannot force an agent to read it. Some tools may ignore instruction
  files entirely, or only read them in certain contexts.

**Where it's a poor fit:**
- Large or ambiguous refactors, where "move fast" is the wrong instinct.
- Production infrastructure, deployments, or anything hard to reverse.
- Team settings without code review — a fast agent still needs a human
  check before merging.
- Anywhere you need a paper trail for *why* an agent was configured a
  particular way (a plain instruction file has no approval workflow).
- **`--announce` + tasks that need a bare, machine-parseable answer** (pure
  JSON, code with no surrounding text, etc). We measured the `[DEGEN]`
  prefix leaking into strict-format output and breaking parsers, which is
  why announce is now off by default — see [the benchmark
  findings](#a-real-result-and-what-it-means). The instruction's built-in
  carve-out helped for "JSON only" requests but not for terse shell
  one-liners, so if you opt in with `--announce`, keep it away from
  anything that must be strictly parseable.

**Before installing `--global`:** it writes to your home-level config, which
affects every project on the machine, not just the one you're in. That's why
`degen.sh` refuses to run with `--global` unless you pass `--yes` (or are just
previewing with `--dry-run`) — prefer a project-local install (the default,
no flag needed) unless you specifically want the home-level one.

If you hit a case where DEGEN's instructions push an agent toward a bad
outcome (e.g. skipping a check it shouldn't have), please open an issue —
that's exactly the kind of failure this project wants to learn from.

## Requirements

`bash`, `awk`, `grep`, and `diff` — available by default on macOS, Linux, and
WSL. The benchmark additionally needs `python3` (stdlib only).

## License

[MIT](./LICENSE)
