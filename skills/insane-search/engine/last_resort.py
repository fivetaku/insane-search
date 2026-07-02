"""Last-resort readable-content fallbacks (generic infrastructure, any URL).

When the grid AND the browser fallback both fail but the caller would accept
*readable* content (not the live interactive page), two universal services can
still return the text:

  * a reader-proxy that renders a URL and returns clean markdown;
  * the public web archive's most recent snapshot of the URL.

Both work for ANY url (they are content-retrieval infrastructure, not a
site preference — same category as a generic Google referer), so their hosts
are allow-listed in bias_check, not treated as site bias.

Gated by INSANE_LAST_RESORT (default on). Returns degraded content marked so the
caller knows it is a snapshot/rendered proxy, never the live page.
"""
from __future__ import annotations

import os
from typing import Optional

# Generic content-retrieval infrastructure (valid for every URL). Kept as
# constants so bias_check's allowlist has a single obvious pairing.
_READER_PREFIX = "https://r.jina.ai/"
_WAYBACK_AVAILABLE = "https://archive.org/wayback/available?url="


def enabled() -> bool:
    return os.environ.get("INSANE_LAST_RESORT", "1") not in ("0", "false", "no")


def _get(url: str, timeout: int):
    from curl_cffi import requests as r
    return r.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)


def try_reader(url: str, timeout: int = 25) -> Optional[dict]:
    """Reader-proxy render → markdown. Returns {content, final_url, route} or None."""
    try:
        resp = _get(_READER_PREFIX + url, timeout=timeout)
        if resp.status_code == 200 and len((resp.text or "").strip()) > 200:
            return {"content": resp.text, "final_url": _READER_PREFIX + url, "route": "reader_proxy"}
    except Exception:
        pass
    return None


def try_archive(url: str, timeout: int = 25) -> Optional[dict]:
    """Public web-archive latest snapshot. Returns {content, final_url, route} or None."""
    try:
        meta = _get(_WAYBACK_AVAILABLE + url, timeout=timeout)
        snap = (meta.json() or {}).get("archived_snapshots", {}).get("closest", {})
        if not snap.get("available") or not snap.get("url"):
            return None
        snap_url = snap["url"]
        resp = _get(snap_url, timeout=timeout)
        if resp.status_code == 200 and len((resp.text or "").strip()) > 200:
            return {"content": resp.text, "final_url": snap_url, "route": "web_archive"}
    except Exception:
        pass
    return None


def run(url: str, timeout: int = 25) -> Optional[dict]:
    """Try reader-proxy then archive. Returns the first hit, or None."""
    if not enabled():
        return None
    return try_reader(url, timeout=timeout) or try_archive(url, timeout=timeout)
