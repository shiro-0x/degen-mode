#!/usr/bin/env python3
"""degen-bench — measure whether the DEGEN block actually changes agent speed.

Runs the same tasks under multiple conditions (no DEGEN, DEGEN installed,
and any custom conditions such as different effort/thinking settings), each
in a fresh temporary workspace, and compares wall time, agent-reported
duration, turns, output tokens, and cost.

Usage:
  bench/degen_bench.py run                          # baseline vs degen, default tasks
  bench/degen_bench.py run --repeats 5
  bench/degen_bench.py run --conditions bench/conditions.example.json
  bench/degen_bench.py run --agent-cmd 'python3 {mock_agent} {task}'
  bench/degen_bench.py report bench/results/<file>.jsonl

The default agent command is:
  claude -p {task} --output-format json --max-turns 8

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
import time
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
        usage = data.get("usage") or {}
        rec["out_tokens"] = usage.get("output_tokens")
        rec["is_error"] = data.get("is_error", rec.get("exit_code") not in (0, None))

        if task.get("check") and not rec["is_error"]:
            answer_text = data.get("result", stdout)
            rec["check_pass"] = run_check(task["check"], answer_text)
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
            "out_tokens": med(rs, "out_tokens"),
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
    header = "| condition | runs | err | wall s | Δ | agent s | Δ | turns | out tok | Δ | cost $ |"
    sep = "|---|---|---|---|---|---|---|---|---|---|---|"
    if has_checks:
        header += " check% |"
        sep += "---|"
    print(header)
    print(sep)
    for r in rows:
        line = "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["condition"], r["runs"], r["errors"],
            fmt(r["wall_s"]), delta(r["wall_s"], base["wall_s"]),
            fmt(r["agent_s"]), delta(r["agent_s"], base["agent_s"]),
            fmt(r["turns"], ".0f"),
            fmt(r["out_tokens"], ".0f"), delta(r["out_tokens"], base["out_tokens"]),
            fmt(r["cost_usd"], ".4f"),
        )
        if has_checks:
            rate = r["check_pass_rate"]
            line += " {} |".format("-" if rate is None else f"{rate * 100:.0f}%")
        print(line)
    print("\nLower is faster/cheaper. Judge by turns and tokens as well as time —")
    print("the DEGEN block changes behavior (fewer turns, shorter output), not just latency.")
    if has_checks:
        print("check% is the share of runs whose answer passed its quality check —")
        print("a speed or token win does not count if quality drops.")


def cmd_run(args):
    tasks = load_tasks(args.tasks)
    conditions = load_conditions(args.conditions)
    out = Path(args.out) if args.out else (
        BENCH_DIR / "results" / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    total = len(tasks) * len(conditions) * args.repeats
    print(f"degen-bench: {len(tasks)} task(s) x {len(conditions)} condition(s) "
          f"x {args.repeats} repeat(s) = {total} runs -> {out}")

    records = []
    with out.open("w") as f:
        i = 0
        for rep in range(args.repeats):
            for task in tasks:
                for cond in conditions:  # interleaved to spread warmup/load bias
                    i += 1
                    rec = run_once(task, cond, args.agent_cmd, args.timeout)
                    records.append(rec)
                    f.write(json.dumps(rec) + "\n")
                    f.flush()
                    flag = " ERR" if rec.get("is_error") or rec.get("timed_out") else ""
                    print(f"  [{i}/{total}] {cond['name']:<16} wall={rec['wall_s']:.1f}s"
                          f" turns={rec.get('turns') or '-'}{flag}")
    print_report(summarize(records))


def cmd_report(args):
    records = [json.loads(l) for l in Path(args.results).read_text().splitlines() if l.strip()]
    if not records:
        sys.exit("error: no records in results file")
    print_report(summarize(records))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the benchmark")
    r.add_argument("--tasks", default=str(BENCH_DIR / "tasks.txt"),
                   help="file with one task prompt per line (# comments allowed)")
    r.add_argument("--conditions", default=None,
                   help="JSON file of conditions (default: baseline vs degen)")
    r.add_argument("--repeats", type=int, default=3, help="runs per task per condition")
    r.add_argument("--agent-cmd", default=DEFAULT_AGENT_CMD,
                   help="agent command template; {task} is replaced with the prompt")
    r.add_argument("--timeout", type=int, default=600, help="per-run timeout in seconds")
    r.add_argument("--out", default=None, help="results .jsonl path")
    r.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="re-print the summary for a results file")
    p.add_argument("results", help="path to a results .jsonl file")
    p.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
