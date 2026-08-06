#!/usr/bin/env python3
"""Before/after benchmark for the insane-search engine.

Runs each target through `python3 -m engine <url> --json` twice (run1 cold,
run2 warm — run2 exercises the after-engine's success cache) and records
verdict / wall time / attempt count / winning executor per cell.

Usage: bench.py <engine_dir> <out.json> <label>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# Generic controls + PUBLIC bot-detection TEST sandboxes only (sites built to
# be tested against). No third-party commercial or community sites — per the
# No-Site-Name Rule and the acceptable-use scope in DISCLAIMER.md.
TARGETS = [
    # --- controls (expect ok everywhere; public / official-API sites) ---
    ("control_example", "https://example.com/"),
    ("control_hn", "https://news.ycombinator.com/"),
    ("control_github", "https://github.com/explore"),
    ("control_stackoverflow", "https://stackoverflow.com/questions"),
    # --- public bot-detection test sandboxes (exist for this purpose) ---
    ("botcheck_nowsecure", "https://nowsecure.nl/"),
    ("botcheck_incolumitas", "https://bot.incolumitas.com/"),
]

ATTEMPT_TIMEOUT = "15"
PROC_TIMEOUT = 300
WORKERS = 4


def run_one(engine_dir: str, url: str, extra_env: dict) -> dict:
    env = os.environ.copy()
    env.update(extra_env)
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "engine", url, "--json", "--timeout", ATTEMPT_TIMEOUT],
            cwd=engine_dir, env=env, capture_output=True, text=True, timeout=PROC_TIMEOUT,
        )
        wall = round(time.time() - t0, 2)
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
        trace = payload.get("trace") or []
        winner = next((a for a in reversed(trace) if a.get("verdict") in ("strong_ok", "weak_ok")), None)
        return {
            "ok": bool(payload.get("ok")),
            "verdict": payload.get("verdict") or "cli_error",
            "profile": payload.get("profile_used"),
            "attempts": len(trace),
            "wall_s": wall,
            "winner_executor": (winner or {}).get("executor"),
            "winner_phase": (winner or {}).get("phase"),
            "content_length": payload.get("content_length", 0),
            "exit": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "verdict": "harness_timeout", "wall_s": PROC_TIMEOUT, "attempts": -1}
    except Exception as e:
        return {"ok": False, "verdict": f"harness_error:{type(e).__name__}", "wall_s": round(time.time() - t0, 2), "attempts": -1}


def sweep(engine_dir: str, extra_env: dict) -> dict:
    results = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {name: pool.submit(run_one, engine_dir, url, extra_env) for name, url in TARGETS}
        for name, fut in futs.items():
            results[name] = fut.result()
            r = results[name]
            print(f"  {name:<26} ok={r['ok']!s:<5} verdict={r.get('verdict','?'):<10} "
                  f"wall={r.get('wall_s','?'):>7}s attempts={r.get('attempts','?'):>3} "
                  f"via={r.get('winner_executor') or '-'}", flush=True)
    return results


def main() -> None:
    engine_dir, out_path, label = sys.argv[1], sys.argv[2], sys.argv[3]
    extra_env = {
        "INSANE_OBSERVATIONS_DIR": "/tmp/insane-bench/obs",
        "INSANE_CACHE_DIR": f"/tmp/insane-bench/cache_{label}",
    }
    print(f"[{label}] run1 (cold)", flush=True)
    run1 = sweep(engine_dir, extra_env)
    print(f"[{label}] run2 (warm)", flush=True)
    run2 = sweep(engine_dir, extra_env)
    summary = {"label": label, "targets": [t[0] for t in TARGETS], "run1": run1, "run2": run2}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    ok1 = sum(1 for r in run1.values() if r["ok"])
    ok2 = sum(1 for r in run2.values() if r["ok"])
    print(f"[{label}] run1 ok={ok1}/{len(TARGETS)}  run2 ok={ok2}/{len(TARGETS)}  -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
