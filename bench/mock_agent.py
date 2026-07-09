#!/usr/bin/env python3
"""Mock agent for testing degen-bench without API cost.

Sleeps for a task-dependent time and emits Claude-CLI-style JSON. If a DEGEN
instruction file is present in the cwd (CLAUDE.md / AGENTS.md), it simulates
the intended effect: fewer turns, shorter output, less time. Purely synthetic —
use it to verify the harness, not to draw conclusions.
"""

import json
import os
import random
import sys
import time

task = " ".join(sys.argv[1:])
degen = any(os.path.exists(f) for f in ("CLAUDE.md", "AGENTS.md"))

rng = random.Random(hash(task) ^ os.getpid())
base = 1.5 + (len(task) % 5) * 0.2
factor = 0.65 if degen else 1.0
dur = base * factor * rng.uniform(0.9, 1.1)
time.sleep(dur)

turns = 3 if degen else 5
out_tokens = int(320 * factor * rng.uniform(0.85, 1.15))
print(json.dumps({
    "type": "result",
    "is_error": False,
    "duration_ms": int(dur * 1000),
    "duration_api_ms": int(dur * 900),
    "num_turns": turns,
    "total_cost_usd": round(out_tokens * 3e-5, 5),
    "usage": {"input_tokens": 1200, "output_tokens": out_tokens},
    "result": "done",
}))
