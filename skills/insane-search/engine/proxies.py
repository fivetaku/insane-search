"""Optional proxy pool (the one bypass axis TLS rotation can't cover).

TLS/UA rotation defeats *fingerprint* blocks; it does nothing against an
*IP-reputation* block or a 429 that follows the source IP. A proxy pool is the
missing axis: it changes the source address itself.

Config is env-only (no hosts in code → No-Site-Name Rule holds). Set
INSANE_PROXIES to a comma-separated list of proxy URLs — http(s) or socks5, each
optionally carrying user:pass@ credentials.

Selection is STABLE per host by default: a host always maps to the same proxy so
its session cookies / WAF sensors stay coherent across the grid. `salt` advances
the pick (used on a 429/persistent-block retry to deliberately change IP).

Empty / unset env → `proxy_list()` is [] and every helper is a no-op, so nothing
changes for callers that don't opt in.
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional


def _split(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def proxy_list() -> list[str]:
    """The configured proxy URLs, or [] when the feature is off."""
    return _split(os.environ.get("INSANE_PROXIES", ""))


def enabled() -> bool:
    return bool(proxy_list())


def pick(host: str, salt: int = 0) -> Optional[str]:
    """Stable per-host proxy URL, advanced by `salt`. None when disabled."""
    pool = proxy_list()
    if not pool:
        return None
    h = int(hashlib.sha1((host or "").encode("utf-8", "ignore")).hexdigest()[:8], 16)
    return pool[(h + max(0, salt)) % len(pool)]


def as_curl_cffi(proxy_url: Optional[str]) -> Optional[dict]:
    """curl_cffi wants a {"http":..., "https":...} mapping."""
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def as_playwright(proxy_url: Optional[str]) -> Optional[dict]:
    """Playwright wants {"server": ...} with optional username/password split out.

    Accepts scheme://user:pass@host:port and returns the server without creds
    plus separate username/password (Playwright rejects inline creds)."""
    if not proxy_url:
        return None
    from urllib.parse import urlsplit
    p = urlsplit(proxy_url)
    server = f"{p.scheme}://{p.hostname}" + (f":{p.port}" if p.port else "")
    out = {"server": server}
    if p.username:
        out["username"] = p.username
    if p.password:
        out["password"] = p.password
    return out
