"""File-backed per-host cookie store — makes the browser→curl bridge DURABLE.

The in-memory SessionPool bridge only helps within a single process: a browser
pass that clears a challenge seeds cookies that later same-host pages in the
*same* `fetch_many` run reuse. But the agent's MCP browser and a
`python3 -m engine` subprocess are DIFFERENT processes, so MCP-harvested cookies
(or a durable logged-in profile's cookies) would be lost.

This module persists harvested cookies to disk per host, keyed by a SHA1 host
hash (No-Site-Name Rule: no site names on disk paths), so:

  * a browser/MCP pass that clears Cloudflare/Akamai → cheap curl throughput on
    the NEXT CLI invocation, not just the current one;
  * a logged-in profile's cookies, dumped once, make the grid fetch AS the
    logged-in user.

Entries carry a TTL (default 6h — WAF clearance cookies are short-lived) and are
pruned on read. Best-effort throughout: any error is swallowed so cookies can
never break a fetch.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Optional
from urllib.parse import urlsplit

TTL_SECONDS = int(os.environ.get("INSANE_COOKIE_TTL_SEC", str(6 * 3600)))


def enabled() -> bool:
    return os.environ.get("INSANE_COOKIEJAR", "1") not in ("0", "false", "no")


def _dir() -> str:
    p = os.environ.get("INSANE_COOKIEJAR_DIR")
    if p:
        return p
    return os.path.join(os.path.expanduser("~"), ".insane_search", "cookies")


def _host(url_or_host: str) -> str:
    h = (urlsplit(url_or_host).hostname or url_or_host or "").lower()
    return h[4:] if h.startswith("www.") else h


def _path(host: str) -> str:
    hh = hashlib.sha1(host.encode("utf-8", "ignore")).hexdigest()[:16]
    return os.path.join(_dir(), f"{hh}.json")


def save(url_or_host: str, cookies: list[dict], user_agent: Optional[str] = None) -> bool:
    """Persist cookies ([{name,value,domain?}, ...]) for a host. Merges with any
    existing set (new values win). Returns True on write."""
    if not enabled() or not cookies:
        return False
    host = _host(url_or_host)
    if not host:
        return False
    try:
        existing = load(host) or {}
        merged = {c.get("name"): c for c in (existing.get("cookies") or []) if c.get("name")}
        for c in cookies:
            if c.get("name"):
                merged[c["name"]] = {"name": c["name"], "value": c.get("value", ""),
                                     "domain": c.get("domain") or host}
        payload = {
            "ts": time.time(),
            "user_agent": user_agent or (existing or {}).get("user_agent"),
            "cookies": list(merged.values()),
        }
        os.makedirs(_dir(), exist_ok=True)
        path = _path(host)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def load(url_or_host: str) -> Optional[dict]:
    """Return {ts, user_agent, cookies:[...]} for a host, or None if absent/expired."""
    if not enabled():
        return None
    host = _host(url_or_host)
    if not host:
        return None
    try:
        with open(_path(host), "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        if time.time() - float(data.get("ts", 0)) > TTL_SECONDS:
            return None
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return None
