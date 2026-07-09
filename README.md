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

So you can't forget the mode is active, the installed block also tells the
agent to **start every reply with `[DEGEN]`**. The tag costs a few tokens and
nothing more. If you don't want it, install with `--no-announce`; re-running
`install` with or without the flag toggles it, and `status` shows which mode
each file is in (`installed` vs `installed (silent)`).

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
| `--no-announce` | Omit the `[DEGEN]` reply-prefix instruction from the installed block (on by default). |
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
runs the same tasks with and without the DEGEN block (each run in a fresh
temporary workspace, DEGEN installed via `degen.sh` itself) and compares
wall time, agent-reported duration, turns, output tokens, and cost:

```sh
python3 bench/degen_bench.py run                # baseline vs degen, 3 repeats
python3 bench/degen_bench.py run --repeats 5 --tasks bench/tasks.txt
python3 bench/degen_bench.py report bench/results/<file>.jsonl
```

Sample output — **from the included mock agent** (`bench/mock_agent.py`),
which is a synthetic stand-in built to simulate a speedup, not a measurement
of any real model. It exists to prove the harness works end-to-end. Run the
real thing yourself before drawing any conclusion (see below):

```
| condition | runs | err | wall s | Δ    | agent s | Δ    | turns | out tok | Δ    | cost $ |
|-----------|------|-----|--------|------|---------|------|-------|---------|------|--------|
| baseline  | 6    | 0   | 2.03   | +0%  | 2.00    | +0%  | 5     | 346     | +0%  | 0.0104 |
| degen     | 6    | 0   | 1.26   | -38% | 1.23    | -38% | 3     | 204     | -41% | 0.0061 |
```

The default agent command is `claude -p {task} --output-format json
--max-turns 8`; swap in any agent with `--agent-cmd` (the `{task}`
placeholder is replaced with the prompt). To verify the harness without
API cost, point it at the included mock — use the `{mock_agent}` placeholder
rather than a relative path, since each run's working directory is a fresh
temp workspace, not the directory you launched the command from:

```sh
python3 bench/degen_bench.py run --agent-cmd 'python3 {mock_agent} {task}'
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

**Update:** the installed instruction now has an explicit carve-out ("...except
when the task requires a bare, machine-parseable answer"). Re-testing by
hand, 5 tries each: the JSON-only task came back clean 5/5 — the carve-out
worked there. The bash-one-liner task did **not** improve at all — still
5/5 prefixed with `[DEGEN]`. Our read: the model reliably recognizes "JSON
only" as the kind of bare output the carve-out means, but doesn't extend
that same reading to "a bash one-liner, no explanation" — it's still
prose-adjacent enough that the model treats the prefix as compatible. So
the carve-out is a partial fix, not a full one.

Practical takeaway unchanged: **if a task needs bare, parseable output, use
`--no-announce`** rather than relying on the carve-out — and don't trust
anyone's speedup claim (including the mock sample above, and including this
one) without running it on your own tasks with `--repeats 5` or more.

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
- **Tasks that need a bare, machine-parseable answer** (pure JSON, code with
  no surrounding text, etc). The installed instruction tells the agent to
  skip the `[DEGEN]` prefix for this case, and that reliably worked in our
  testing for an explicit "JSON only" request — but did not help at all for
  a "one-line bash command, no explanation" request, which still got
  prefixed every time. Don't rely on the carve-out; use `--no-announce` for
  anything that must be strictly parseable — see [the benchmark finding
  below](#a-real-result-and-what-it-means).

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
