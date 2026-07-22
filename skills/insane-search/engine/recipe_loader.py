"""Recipe loader — per-domain recipes take precedence over the generic grid.

A recipe is runtime DATA under ``recipes/<domain>/recipe.yaml`` (same
No-Site-Name exemption class as observations): it encodes what a completed
scraper-forge run learned about one domain. Two machine-usable entry types:

  url_rewrites:  page-URL pattern → API URL rewrite rules. The loader applies
                 the first matching rule, fetches the rewritten URL with the
                 rule's headers/cookies, and accepts JSON (or non-challenge
                 HTML when expect=html).
  endpoints:     documented API surface for the agent (not auto-fetched).

Env overrides:
  INSANE_RECIPES_DIR   — recipes root (default: <skill>/recipes)
  INSANE_NO_RECIPE=1   — bypass recipes entirely

Best-effort: any failure returns None and the generic chain proceeds.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

_SKILL_DIR = Path(__file__).resolve().parent.parent


def _recipes_dir() -> Path:
    override = os.environ.get("INSANE_RECIPES_DIR")
    return Path(override) if override else _SKILL_DIR / "recipes"


def recipes_enabled() -> bool:
    return os.environ.get("INSANE_NO_RECIPE", "").strip() not in ("1", "true", "yes")


def load_recipe(url: str) -> Optional[dict]:
    """Return the parsed recipe for this URL's domain, or None."""
    if not recipes_enabled():
        return None
    try:
        domain = (urlparse(url).hostname or "").lower()
        if not domain:
            return None
        path = _recipes_dir() / domain / "recipe.yaml"
        if not path.is_file():
            return None
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def match_rewrite(url: str, recipe: dict) -> Optional[dict]:
    """First url_rewrites rule whose pattern matches, with the rewritten URL."""
    for rule in recipe.get("url_rewrites") or []:
        pattern = rule.get("pattern")
        replacement = rule.get("replacement")
        if not pattern or replacement is None:
            continue
        try:
            if re.search(pattern, url):
                rewritten = re.sub(pattern, replacement, url)
                if not rewritten.startswith("http"):
                    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    rewritten = urljoin(base, rewritten)
                return {**rule, "rewritten_url": rewritten}
        except re.error:
            continue
    return None


def try_rewrite(rule: dict, *, timeout: int = 20) -> Optional[dict]:
    """Fetch a rewritten URL; return {content, status, kind} on success."""
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        return None
    headers = {"Accept": "application/json,text/plain,*/*"}
    headers.update(rule.get("headers") or {})
    try:
        resp = cffi_requests.get(
            rule["rewritten_url"],
            impersonate=rule.get("impersonate") or "chrome",
            headers=headers,
            cookies=rule.get("cookies") or None,
            timeout=timeout,
            allow_redirects=True,
        )
    except Exception:
        return None
    if resp.status_code >= 400:
        return None
    body = resp.text or ""
    low = body.lower()
    if "window._cf_chl_opt" in low or "orchestrate/chl_page" in low:
        return None
    expect = rule.get("expect") or "json"
    if expect == "json":
        try:
            json.loads(body)
        except Exception:
            # Standard anti-XSSI guard (`)]}',` first line) — strip and retry.
            stripped = body.split("\n", 1)[1] if body.startswith(")]}'") and "\n" in body else ""
            try:
                json.loads(stripped)
                body = stripped
            except Exception:
                return None
        return {"content": body, "status": resp.status_code, "kind": "json"}
    if len(body) < 300:
        return None
    return {"content": body, "status": resp.status_code, "kind": "html"}
