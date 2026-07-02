"""Append-only observation log — the raw material for WAF-profile promotion.

`learning.py` remembers the single winning route PER HOST (to retry it first).
This module is the complementary AGGREGATE: every grid success appends one line
recording which (waf_profile, impersonate, transform, referer) actually worked.

Over many hosts this answers the question the profiles need: "for WAF product X,
which TLS families keep winning / keep failing?" — the evidence SKILL.md's
No-Site-Name section asks for before hand-tuning `waf_profiles.yaml` or adding a
new profile. It stores WAF-product + route facts, never a host→route mapping, so
it stays site-agnostic (append-only observations are explicitly allowed by R3).

JSONL at ~/.insane_search/observations/observed.jsonl (bounded by line cap).
Best-effort: any error is swallowed.
"""
from __future__ import annotations

import json
import os
from typing import Optional

MAX_LINES = int(os.environ.get("INSANE_OBS_MAX", "5000"))


def enabled() -> bool:
    return os.environ.get("INSANE_OBSERVE", "1") not in ("0", "false", "no")


def _path() -> str:
    p = os.environ.get("INSANE_OBS_PATH")
    if p:
        return p
    return os.path.join(os.path.expanduser("~"), ".insane_search", "observations", "observed.jsonl")


def record(*, profile: Optional[str], impersonate: Optional[str], transform: str,
           referer: str, verdict: str, phase: str, ts: float) -> bool:
    """Append one success observation. No host is stored (site-agnostic)."""
    if not enabled() or not impersonate:
        return False
    line = {
        "profile": profile or "unknown_challenge",
        "impersonate": impersonate,
        "transform": transform,
        "referer": referer,
        "verdict": verdict,
        "phase": phase,
        "ts": round(ts, 1),
    }
    try:
        path = _path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        _trim(path)
        return True
    except OSError:
        return False


def _trim(path: str) -> None:
    """Keep the file bounded: on overflow, retain the most recent MAX_LINES."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) <= MAX_LINES:
            return
        keep = lines[-MAX_LINES:]
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.writelines(keep)
        os.replace(tmp, path)
    except OSError:
        pass
