"""Append-only operational observations for profile tuning.

Route learning remains exclusively in ``learning.py``. This module only
records outcomes to ``observations/fetch-YYYY-MM-DD.jsonl`` so repeated
cross-site evidence can be reviewed before changing WAF profiles.

Env override: ``INSANE_OBSERVATIONS_DIR``.
Logging is best-effort and never changes a fetch outcome.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from .url_masking import mask_url

_SKILL_DIR = Path(__file__).resolve().parent.parent


def _obs_dir() -> Path:
    override = os.environ.get("INSANE_OBSERVATIONS_DIR")
    return Path(override) if override else _SKILL_DIR / "observations"


def log_fetch(url: str, result) -> None:
    try:
        trace = getattr(result, "trace", []) or []
        winner = next(
            (a for a in reversed(trace) if getattr(a, "verdict", "") in ("strong_ok", "weak_ok")),
            None,
        )
        entry = {
            "ts": int(time.time()),
            "url": mask_url(url),
            "domain": (urlparse(url).hostname or "").lower(),
            "ok": bool(getattr(result, "ok", False)),
            "verdict": getattr(result, "verdict", ""),
            "profile_used": getattr(result, "profile_used", None),
            "attempts": len(trace),
            "planned_attempts": getattr(result, "planned_attempts", 0),
            "stop_reason": getattr(result, "stop_reason", ""),
        }
        if winner is not None:
            entry["winner"] = {
                "phase": getattr(winner, "phase", ""),
                "executor": getattr(winner, "executor", ""),
                "transform": getattr(winner, "url_transform", ""),
                "impersonate": getattr(winner, "impersonate", None),
                "referer": mask_url(getattr(winner, "referer", "")),
                "status": getattr(winner, "status", 0),
                "body_size": getattr(winner, "body_size", 0),
            }
        directory = _obs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        day = time.strftime("%Y-%m-%d", time.gmtime())
        with open(directory / f"fetch-{day}.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return
