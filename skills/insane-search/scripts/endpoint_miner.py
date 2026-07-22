#!/usr/bin/env python3
"""endpoint_miner — generic API discovery for a given page URL.

Pipeline (all generic, no site names — No-Site-Name Rule):
  1. fetch the page HTML through the insane-search engine (curl grid)
  2. collect <script src> bundles, fetch each (curl_cffi, same session shape)
  3. regex-mine endpoint candidates from HTML + JS
     ("/api/...", "/front-api/...", "/graphql", "*.json" paths, absolute URLs)
  4. probe GET-able candidates with curl_cffi and classify the response
     (json / html / challenge / blocked)
  5. write a ranked report to recipes/<domain>/miner-report.json

Usage:
  python3 scripts/endpoint_miner.py <URL> [--max-bundles N] [--max-probes N] [--timeout S]

Exit codes: 0 ok, 1 page fetch failed, 2 arg error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))

ENDPOINT_RE = re.compile(
    r"""["'`](/(?:api|front-api|frontApi|graphql|gql|v\d+/api|web-api|api-web|rest|svc|service|ajax|rpc|openapi|internal|gateway)s?/[^"'`\s<>\\]{2,120})["'`]""",
    re.IGNORECASE,
)
ABS_ENDPOINT_RE = re.compile(
    r"""["'`](https?://[^"'`\s<>\\]*(?:api|ajax|graphql|rpc)[^"'`\s<>\\]{2,100})["'`]""",
    re.IGNORECASE,
)
JSON_PATH_RE = re.compile(r"""["'`](/[a-zA-Z0-9_\-/]{3,80}\.(?:json|geojson))["'`]""")
SCRIPT_SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _classify(status: int, ctype: str, body: bytes) -> str:
    text = body[:4000].decode("utf-8", errors="ignore")
    low = text.lower()
    if status >= 400:
        return "blocked"
    if "window._cf_chl_opt" in low or "orchestrate/chl_page" in low:
        return "challenge"
    if "json" in ctype or text.lstrip()[:1] in ("{", "["):
        try:
            json.loads(text if len(body) <= 4000 else body.decode("utf-8", errors="ignore"))
            return "json"
        except Exception:
            return "json-partial"
    if "<html" in low:
        return "html"
    return "other"


def mine(url: str, *, max_bundles: int, max_probes: int, timeout: int) -> dict:
    from engine import fetch

    result = fetch(url, timeout=timeout, enable_playwright=False)
    report = {"url": url, "page_ok": result.ok, "page_verdict": result.verdict,
              "profile_used": result.profile_used, "candidates": [], "probed": []}
    if not result.ok:
        return report

    html = result.content
    base = result.final_url or url

    found: list[str] = []
    for m in ENDPOINT_RE.finditer(html):
        found.append(m.group(1))
    for m in JSON_PATH_RE.finditer(html):
        found.append(m.group(1))
    for m in ABS_ENDPOINT_RE.finditer(html):
        found.append(m.group(1))

    # App code usually lives on CDN hosts — no same-origin filter.
    bundle_urls: list[str] = [
        urljoin(base, src) for src in SCRIPT_SRC_RE.findall(html)
        if urljoin(base, src).split("?")[0].endswith(".js")
    ]
    report["bundles_seen"] = len(bundle_urls)

    try:
        from curl_cffi import requests as cffi_requests
        for burl in bundle_urls[:max_bundles]:
            try:
                r = cffi_requests.get(burl, impersonate="chrome", timeout=timeout)
                if r.status_code == 200:
                    for m in ENDPOINT_RE.finditer(r.text):
                        found.append(m.group(1))
                    for m in JSON_PATH_RE.finditer(r.text):
                        found.append(m.group(1))
                    for m in ABS_ENDPOINT_RE.finditer(r.text):
                        found.append(m.group(1))
            except Exception:
                continue
    except ImportError:
        report["note"] = "curl_cffi missing — bundle mining skipped"

    uniq = sorted({f.split("?")[0] for f in found if not f.endswith((".js", ".css", ".map"))})
    report["candidates"] = uniq

    from curl_cffi import requests as cffi_requests
    for path in uniq[:max_probes]:
        probe_url = urljoin(base, path)
        try:
            r = cffi_requests.get(probe_url, impersonate="chrome", timeout=timeout,
                                  headers={"Accept": "application/json,text/plain,*/*"})
            kind = _classify(r.status_code, r.headers.get("content-type", ""), r.content)
            report["probed"].append({"path": path, "status": r.status_code,
                                     "bytes": len(r.content), "kind": kind})
        except Exception as e:
            report["probed"].append({"path": path, "status": 0, "bytes": 0,
                                     "kind": f"error:{type(e).__name__}"})
        time.sleep(0.25)

    rank = {"json": 0, "json-partial": 1, "other": 2, "html": 3, "challenge": 4, "blocked": 5}
    report["probed"].sort(key=lambda p: (rank.get(p["kind"], 9), -p["bytes"]))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--max-bundles", type=int, default=8)
    ap.add_argument("--max-probes", type=int, default=25)
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    try:
        report = mine(args.url, max_bundles=args.max_bundles,
                      max_probes=args.max_probes, timeout=args.timeout)
    except Exception as e:
        print(f"miner fatal: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    domain = (urlparse(args.url).hostname or "unknown").lower()
    out_dir = SKILL_DIR / "recipes" / domain
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "miner-report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    json_hits = [p for p in report["probed"] if p["kind"] == "json"]
    print(f"page_ok={report['page_ok']} verdict={report['page_verdict']} "
          f"candidates={len(report['candidates'])} json_endpoints={len(json_hits)}")
    for p in json_hits[:10]:
        print(f"  [json] {p['path']} ({p['bytes']}B)")
    print(f"report: {out_path}")
    return 0 if report["page_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
