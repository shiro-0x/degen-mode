#!/usr/bin/env python3
"""degen-bench — measure whether the DEGEN block actually changes agent speed.

Runs the same prompt(s) under multiple conditions (no DEGEN, DEGEN installed,
and any custom conditions such as different effort/thinking settings). Each run
is an independent subagent — a fresh agent process in its own isolated
workspace — so the conditions differ only in the instruction files present.
Compares outcome (optional quality check + the answers themselves), token
consumption (input incl. cache + output), and speed (wall + agent time).

Usage:
  bench/degen_bench.py ab "PROMPT"                  # A/B one prompt: baseline vs degen
  bench/degen_bench.py ab "PROMPT" --repeats 5 --parallel 5 --check 'CMD'
  bench/degen_bench.py ab "PROMPT" --save-answers /tmp/ab
  bench/degen_bench.py run                          # over a whole tasks file
  bench/degen_bench.py run --repeats 5 --parallel 4
  bench/degen_bench.py run --conditions bench/conditions.example.json
  bench/degen_bench.py run --agent-cmd 'python3 {mock_agent} {task}'
  bench/degen_bench.py report bench/results/<file>.jsonl [--answers]

The default agent command is:
  claude -p {task} --output-format json --max-turns 8

--parallel N runs up to N subagents at once (default 1). Raise it to finish
faster; each run is independent (own temp workspace), but mind API rate limits.

Notes:
  * {task} in --agent-cmd is replaced with the task prompt.
  * {mock_agent} is replaced with the absolute path to bench/mock_agent.py —
    use it instead of a relative path, since each run executes with its cwd
    set to a fresh temp workspace (so the agent sees the installed
    instruction files), not the directory you launched degen_bench.py from.
  * If your tasks need file edits or shell access, add a permission flag to
    --agent-cmd (e.g. --permission-mode acceptEdits) — only in a sandbox.
  * A condition can set "env" (e.g. MAX_THINKING_TOKENS) and "extra_args"
    (e.g. a different --model), which is how you compare effort levels.
  * A condition with "degen": true can also set "install_args" (extra flags
    passed to degen.sh install, e.g. ["--no-announce"]) — useful to isolate
    the announce line's effect from the DEGEN block itself.

Quality checks (so a speedup can't hide a quality loss):
  --tasks accepts a .json file of [{"prompt": "...", "check": "shell cmd"}]
  instead of a plain .txt prompt list. The agent's answer text is piped to
  "check" on stdin; exit code 0 counts as a pass. The report then shows a
  check% column per condition alongside speed/cost. See
  bench/tasks_with_checks.example.json.
"""

import argparse
import json
import os
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = BENCH_DIR.parent
DEGEN_SH = REPO_ROOT / "degen.sh"
MOCK_AGENT = BENCH_DIR / "mock_agent.py"

DEFAULT_AGENT_CMD = "claude -p {task} --output-format json --max-turns 8"
DEFAULT_CONDITIONS = [
    {"name": "baseline", "degen": False},
    {"name": "degen", "degen": True},
]


def load_tasks(path):
    """Return a list of {"prompt": str, "check": str|None} dicts.

    A .json file holds [{"prompt": ..., "check": ...}, ...] (check
    optional). Anything else is treated as one prompt per line (# comments
    allowed), with no quality check.
    """
    path = Path(path)
    if path.suffix == ".json":
        items = json.loads(path.read_text())
        if not isinstance(items, list) or not items:
            sys.exit(f"error: {path} must be a non-empty JSON array")
        tasks = []
        for it in items:
            if "prompt" not in it:
                sys.exit(f"error: every task needs a 'prompt': {it}")
            tasks.append({"prompt": it["prompt"], "check": it.get("check")})
        return tasks

    tasks = [{"prompt": line.strip(), "check": None}
             for line in path.read_text().splitlines()
             if line.strip() and not line.strip().startswith("#")]
    if not tasks:
        sys.exit(f"error: no tasks found in {path}")
    return tasks


def load_conditions(path):
    if not path:
        return DEFAULT_CONDITIONS
    conds = json.loads(Path(path).read_text())
    if not isinstance(conds, list) or not conds:
        sys.exit(f"error: {path} must be a non-empty JSON array of conditions")
    for c in conds:
        if "name" not in c:
            sys.exit(f"error: every condition needs a 'name': {c}")
    return conds


def parse_agent_json(stdout):
    """Best-effort parse of the agent's JSON output (whole stdout or last line)."""
    for candidate in (stdout, stdout.strip().splitlines()[-1] if stdout.strip() else ""):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, IndexError):
            continue
    return {}


CHECK_TIMEOUT = 30  # seconds; quality checks should be quick and local


def run_check(check_cmd, answer_text):
    """Run a quality-check shell command with the agent's answer on stdin.
    Returns True/False, or None if the check itself couldn't run."""
    try:
        proc = subprocess.run(check_cmd, shell=True, input=answer_text,
                              text=True, capture_output=True, timeout=CHECK_TIMEOUT)
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def run_once(task, cond, agent_cmd, timeout):
    prompt = task["prompt"]
    work = Path(tempfile.mkdtemp(prefix="degen-bench-"))
    rec = {
        "condition": cond["name"],
        "task": prompt[:120],
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        if cond.get("degen"):
            subprocess.run(
                [str(DEGEN_SH), "install", "--dir", str(work),
                 "--agent", cond.get("agent", "claude"),
                 *(cond.get("install_args") or [])],
                check=True, capture_output=True,
            )
        env = os.environ.copy()
        env.update({k: str(v) for k, v in (cond.get("env") or {}).items()})
        cmd = [a.replace("{task}", prompt).replace("{mock_agent}", str(MOCK_AGENT))
               for a in shlex.split(agent_cmd)]
        cmd += [str(a) for a in (cond.get("extra_args") or [])]

        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=work, env=env, capture_output=True,
                                  text=True, timeout=timeout)
            rec["exit_code"] = proc.returncode
            stdout = proc.stdout
        except subprocess.TimeoutExpired:
            rec["exit_code"] = None
            rec["timed_out"] = True
            stdout = ""
        rec["wall_s"] = round(time.monotonic() - t0, 3)

        data = parse_agent_json(stdout)
        rec["agent_s"] = round(data["duration_ms"] / 1000, 3) if "duration_ms" in data else None
        rec["api_s"] = round(data["duration_api_ms"] / 1000, 3) if "duration_api_ms" in data else None
        rec["turns"] = data.get("num_turns")
        rec["cost_usd"] = data.get("total_cost_usd")

        # Token consumption. "input" folds in cache reads/creation so the total
        # reflects everything the request actually billed, not just fresh input.
        usage = data.get("usage") or {}
        def _tok(k):
            v = usage.get(k)
            return v if isinstance(v, int) else 0
        in_tok = _tok("input_tokens") + _tok("cache_read_input_tokens") + _tok("cache_creation_input_tokens")
        out_tok = usage.get("output_tokens")
        rec["in_tokens"] = in_tok if usage else None
        rec["out_tokens"] = out_tok
        rec["total_tokens"] = (in_tok + (out_tok or 0)) if usage else None
        rec["is_error"] = data.get("is_error", rec.get("exit_code") not in (0, None))

        # Capture the answer text itself so outcomes can be compared/eyeballed,
        # not just pass/fail. This is also what a quality check is run against.
        rec["answer"] = data.get("result", stdout)
        if task.get("check") and not rec["is_error"]:
            rec["check_pass"] = run_check(task["check"], rec["answer"])
        elif task.get("check"):
            rec["check_pass"] = False  # agent errored -> can't have passed the check
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return rec


def summarize(records):
    """Group records by condition (insertion order) and compute medians."""
    order, groups = [], {}
    for r in records:
        c = r["condition"]
        if c not in groups:
            order.append(c)
            groups[c] = []
        groups[c].append(r)
    # If records carry the intended condition order (stamped at run time), use
    # it so parallel/out-of-order completion doesn't reshuffle the baseline row.
    # Records without it (older files) keep first-appearance order via the
    # stable sort.
    order.sort(key=lambda c: min((r.get("_order", 10**9) for r in groups[c]),
                                 default=10**9))

    def med(rs, key):
        vals = [r[key] for r in rs if r.get(key) is not None]
        return statistics.median(vals) if vals else None

    rows = []
    for c in order:
        rs = groups[c]
        checked = [r for r in rs if r.get("check_pass") is not None]
        rows.append({
            "condition": c,
            "runs": len(rs),
            "errors": sum(1 for r in rs if r.get("is_error") or r.get("timed_out")),
            "wall_s": med(rs, "wall_s"),
            "agent_s": med(rs, "agent_s"),
            "turns": med(rs, "turns"),
            "in_tokens": med(rs, "in_tokens"),
            "out_tokens": med(rs, "out_tokens"),
            "total_tokens": med(rs, "total_tokens"),
            "cost_usd": med(rs, "cost_usd"),
            "check_pass_rate": (sum(1 for r in checked if r["check_pass"]) / len(checked)
                                if checked else None),
        })
    return rows


def fmt(v, spec=".2f"):
    return "-" if v is None else format(v, spec)


def delta(v, base):
    if v is None or base in (None, 0):
        return "-"
    return f"{(v - base) / base * 100:+.0f}%"


def print_report(rows):
    base = rows[0]
    has_checks = any(r["check_pass_rate"] is not None for r in rows)
    print(f"\n## degen-bench results (median of runs; Δ vs `{base['condition']}`)\n")
    cols = ["condition", "runs", "err", "wall s", "Δwall", "agent s", "turns",
            "in tok", "out tok", "tot tok", "Δtot", "cost $"]
    if has_checks:
        cols.append("check%")
    print("| " + " | ".join(cols) + " |")
    print("|" + "|".join("---" for _ in cols) + "|")
    for r in rows:
        cells = [
            r["condition"], str(r["runs"]), str(r["errors"]),
            fmt(r["wall_s"]), delta(r["wall_s"], base["wall_s"]),
            fmt(r["agent_s"]), fmt(r["turns"], ".0f"),
            fmt(r["in_tokens"], ".0f"), fmt(r["out_tokens"], ".0f"),
            fmt(r["total_tokens"], ".0f"), delta(r["total_tokens"], base["total_tokens"]),
            fmt(r["cost_usd"], ".4f"),
        ]
        if has_checks:
            rate = r["check_pass_rate"]
            cells.append("-" if rate is None else f"{rate * 100:.0f}%")
        print("| " + " | ".join(cells) + " |")
    print("\nLower is faster/cheaper. `tot tok` is total token consumption "
          "(input incl. cache + output).")
    print("Judge by tokens and turns as well as time — the DEGEN block changes "
          "behavior, not just latency.")
    if has_checks:
        print("check% is the share of runs whose answer passed its quality check —")
        print("a speed or token win does not count if quality drops.")


def print_answers(records, sample=1):
    """Show a sample of the actual answers per condition, so outcomes on
    open-ended tasks can be eyeballed (not just pass/fail)."""
    per_cond = {}
    for r in records:
        per_cond.setdefault(r["condition"], []).append(r)
    print("\n## Sample answers (compare the outcome, not just the numbers)\n")
    for cond, rs in per_cond.items():
        print(f"### {cond}")
        for r in rs[:sample]:
            ans = (r.get("answer") or "").strip()
            if len(ans) > 1200:
                ans = ans[:1200] + "\n…[truncated]"
            passed = r.get("check_pass")
            tag = "" if passed is None else f" (check: {'pass' if passed else 'FAIL'})"
            print(f"- tokens={r.get('total_tokens') or '-'}, "
                  f"wall={r.get('wall_s')}s{tag}")
            print("```")
            print(ans)
            print("```")
        print()


def save_answers(records, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for r in records:
        c = r["condition"]
        n = counts.get(c, 0) + 1
        counts[c] = n
        (out_dir / f"{c}-{n:02d}.txt").write_text(r.get("answer") or "")
    print(f"saved {sum(counts.values())} answer file(s) to {out_dir}/")


def default_out():
    return BENCH_DIR / "results" / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl"


def execute_matrix(tasks, conditions, agent_cmd, timeout, repeats, parallel, out_path):
    """Run every (repeat x task x condition) cell — each an independent subagent
    (a fresh agent process in its own isolated workspace) — writing one JSONL
    record per run. With parallel>1, up to `parallel` subagents run at once."""
    jobs = [(task, cond)
            for _ in range(repeats)
            for task in tasks
            for cond in conditions]  # interleaved so serial runs spread load bias
    total = len(jobs)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Remember the intended condition order so the report's baseline column is
    # stable even though parallel runs complete out of order.
    cond_order = {c["name"]: i for i, c in enumerate(conditions)}

    records = []
    write_lock = threading.Lock()
    done = 0
    with out_path.open("w") as f, ThreadPoolExecutor(max_workers=parallel) as ex:
        futures = [ex.submit(run_once, task, cond, agent_cmd, timeout)
                   for (task, cond) in jobs]
        for fut in as_completed(futures):
            rec = fut.result()
            rec["_order"] = cond_order.get(rec["condition"], 10**9)
            with write_lock:
                done += 1
                records.append(rec)
                f.write(json.dumps(rec) + "\n")
                f.flush()
                flag = " ERR" if rec.get("is_error") or rec.get("timed_out") else ""
                print(f"  [{done}/{total}] {rec['condition']:<16} "
                      f"wall={rec['wall_s']:.1f}s tok={rec.get('total_tokens') or '-'}"
                      f" turns={rec.get('turns') or '-'}{flag}")
    return records


def cmd_run(args):
    tasks = load_tasks(args.tasks)
    conditions = load_conditions(args.conditions)
    out = Path(args.out) if args.out else default_out()
    total = len(tasks) * len(conditions) * args.repeats
    print(f"degen-bench: {len(tasks)} task(s) x {len(conditions)} condition(s) "
          f"x {args.repeats} repeat(s) = {total} runs "
          f"(parallel={args.parallel}) -> {out}")
    records = execute_matrix(tasks, conditions, args.agent_cmd, args.timeout,
                             args.repeats, args.parallel, out)
    print_report(summarize(records))


def cmd_ab(args):
    """A/B one prompt across conditions: same prompt, compare outcome, tokens,
    and speed, driving subagents in parallel by default."""
    task = {"prompt": args.prompt, "check": args.check}
    conditions = load_conditions(args.conditions)
    out = Path(args.out) if args.out else default_out()
    print(f"degen-bench ab: 1 prompt x {len(conditions)} condition(s) "
          f"x {args.repeats} repeat(s) = {len(conditions) * args.repeats} runs "
          f"(parallel={args.parallel}) -> {out}")
    records = execute_matrix([task], conditions, args.agent_cmd, args.timeout,
                             args.repeats, args.parallel, out)
    print_report(summarize(records))
    print_answers(records, sample=args.show_answers)
    if args.save_answers:
        save_answers(records, args.save_answers)


def cmd_report(args):
    records = [json.loads(l) for l in Path(args.results).read_text().splitlines() if l.strip()]
    if not records:
        sys.exit("error: no records in results file")
    print_report(summarize(records))
    if getattr(args, "answers", False):
        print_answers(records, sample=10)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--conditions", default=None,
                        help="JSON file of conditions (default: baseline vs degen)")
        sp.add_argument("--repeats", type=int, default=3,
                        help="runs per task per condition")
        sp.add_argument("--parallel", type=int, default=1,
                        help="max subagents to run at once (default 1; raise to "
                             "go faster, but watch API rate limits)")
        sp.add_argument("--agent-cmd", default=DEFAULT_AGENT_CMD,
                        help="agent command template; {task} is replaced with the prompt")
        sp.add_argument("--timeout", type=int, default=600,
                        help="per-run timeout in seconds")
        sp.add_argument("--out", default=None, help="results .jsonl path")

    r = sub.add_parser("run", help="run the benchmark over a tasks file")
    r.add_argument("--tasks", default=str(BENCH_DIR / "tasks.txt"),
                   help="prompts file (.txt one-per-line, or .json with checks)")
    add_common(r)
    r.set_defaults(func=cmd_run)

    a = sub.add_parser("ab", help="A/B one prompt: same prompt, compare outcome/tokens/speed")
    a.add_argument("prompt", help="the prompt to run under each condition")
    a.add_argument("--check", default=None,
                   help="shell command; the answer is piped to it on stdin, exit 0 = pass")
    a.add_argument("--show-answers", type=int, default=1,
                   help="how many sample answers to print per condition (default 1)")
    a.add_argument("--save-answers", default=None,
                   help="directory to write every full answer to (for side-by-side review)")
    add_common(a)
    a.set_defaults(func=cmd_ab)

    p = sub.add_parser("report", help="re-print the summary for a results file")
    p.add_argument("results", help="path to a results .jsonl file")
    p.add_argument("--answers", action="store_true", help="also print captured answers")
    p.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
