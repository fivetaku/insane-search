"""auto_forge — on-demand autonomous API discovery for one page.

When the generic chain cannot read a page, this renders it once (capturing
XHR/fetch traffic), picks the endpoint that most likely carries the page's
DATA, confirms it is replayable with a plain curl_cffi request, and returns
that JSON. On success it also writes a recipe so the domain is instant next
time (the forge loop closes itself).

Honest limits (returns None, generic chain proceeds):
  * server-rendered pages with no underlying JSON API
  * endpoints that need browser-only cookies / auth / a challenge token
  * POST/GraphQL endpoints with non-trivial request bodies

Env: INSANE_AUTO_FORGE=1 enables it as a fallback tier.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

_SKILL_DIR = Path(__file__).resolve().parent.parent
_API_HINT = re.compile(r"/(api|ajax|front-api|graphql|gql|web-api|api-web|rest|svc|service|gateway|internal)s?/", re.I)
# Ad / analytics / telemetry / config endpoints return JSON but are never the
# page's DATA. Selecting by size alone keeps picking these, so deny them.
_AD_TELEMETRY = re.compile(
    r"(gfp|sodar|doubleclick|googlesyndication|google-analytics|googletag|/gtm|/gtag|"
    r"/collect|/beacon|/log(ging|s)?\b|/metric|/telemetry|/track|/pixel|criteo|taboola|"
    r"outbrain|adsystem|/ads?/|revenuesourcemap|login-status|/config\b|/csp|/sentry|"
    r"amplitude|mixpanel|segment|/consent|/geo\b|/ping\b|onetrust|cookielaw|"
    r"scripttemplates|/otSDKStub|hotjar|clarity\.ms|/rum\b|newrelic|datadog|"
    r"fastlane|prebid|pubmatic|rubicon|openx|indexexchange|adnxs|adservice|/gampad|/hb\b)", re.I)
_WORD = re.compile(r"[A-Za-z\uac00-\ud7a3][A-Za-z0-9\uac00-\ud7a3]{2,}")
_MIN_OVERLAP = 8


def auto_forge_enabled() -> bool:
    return os.environ.get("INSANE_AUTO_FORGE", "").strip() in ("1", "true", "yes")


def _capture(url: str, timeout: int) -> tuple[str, list[dict]]:
    """Render the page; return (rendered_html, JSON XHR/fetch GET metadata)."""
    from .executor import _run_python_template
    args = {"url": url, "timeout": timeout * 1000, "scroll": True}
    rc, stdout, _ = _run_python_template("network_capture_patchright.py", args, timeout=timeout + 40)
    if rc != 0 or not stdout:
        return "", []
    try:
        data = json.loads(stdout)
    except Exception:
        return "", []
    out = []
    for n in data.get("network") or []:
        if (n.get("status") == 200 and "json" in (n.get("ctype") or "")
                and n.get("method", "GET") == "GET" and not _AD_TELEMETRY.search(n.get("url", ""))):
            out.append(n)
    return data.get("html", "") or "", out


def _tokens(text: str, cap: int) -> set:
    stripped = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
    return set(_WORD.findall(stripped.lower())[:cap])


def _overlap(body: str, page_tokens: set) -> int:
    return len(_tokens(body, 4000) & page_tokens)


def _rank(endpoints: list[dict]) -> list[dict]:
    def score(n: dict) -> tuple:
        return (1 if _API_HINT.search(n.get("url", "")) else 0, n.get("bytes", 0))
    return sorted(endpoints, key=score, reverse=True)


def _confirm(endpoint_url: str, page_url: str, timeout: int) -> tuple[str, dict] | None:
    """Replay the endpoint with plain curl + standard ajax headers."""
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        return None
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}/",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        resp = cffi_requests.get(endpoint_url, impersonate="chrome", headers=headers,
                                 timeout=timeout, allow_redirects=True)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    body = resp.text or ""
    stripped = body.split("\n", 1)[1] if body.startswith(")]}'") and "\n" in body else body
    try:
        json.loads(stripped)
    except Exception:
        return None
    return stripped, headers


def discover(url: str, *, timeout: int = 20, max_confirm: int = 6):
    """Return (content, endpoint_url, headers) for the endpoint whose JSON most
    overlaps the rendered page's text — the DATA API, not an ad/telemetry blob.
    None when nothing clears the overlap bar (server-rendered / auth-gated)."""
    html, endpoints = _capture(url, timeout)
    page_tokens = _tokens(html, 2000)
    best = None
    best_score = 0
    for n in _rank(endpoints)[:max_confirm]:
        confirmed = _confirm(n["url"], url, timeout)
        if confirmed is None:
            continue
        body, headers = confirmed
        if len(body) < 200:
            continue
        score = _overlap(body, page_tokens)
        if score > best_score:
            best_score, best = score, (body, n["url"], headers)
    if best is not None and best_score >= _MIN_OVERLAP:
        return best
    return None


def write_recipe(page_url: str, endpoint_url: str, headers: dict) -> None:
    """Persist an auto-discovered endpoint as a recipe (exact-URL rewrite)."""
    try:
        domain = (urlparse(page_url).hostname or "").lower()
        if not domain:
            return
        recipes_root = os.environ.get("INSANE_RECIPES_DIR")
        base = Path(recipes_root) if recipes_root else _SKILL_DIR / "recipes"
        target = base / domain
        target.mkdir(parents=True, exist_ok=True)
        path = target / "recipe.yaml"
        if path.exists():
            return  # never clobber a curated recipe
        import yaml
        endpoint_rel = endpoint_url.replace(f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}", "")
        # This is an exact-match rewrite with no capture groups, so the endpoint
        # is a literal replacement — escape backslashes so re.sub can't read a
        # stray `\1`/`\g<>` in the URL as a (nonexistent) group reference.
        replacement = endpoint_rel.replace("\\", "\\\\")
        doc = {
            "domain": domain,
            "verified_at": __import__("time").strftime("%Y-%m-%d"),
            "status": "auto",
            "url_rewrites": [{
                "name": "auto_discovered",
                "pattern": "^" + re.escape(page_url) + "$",
                "replacement": replacement,
                "headers": headers,
                "expect": "json",
            }],
            "notes": "auto_forge discovered endpoint; verify + generalise pattern before trusting widely.",
        }
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    except Exception:
        return
