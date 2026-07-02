#!/usr/bin/env python3
"""Coverage battery — prove, per platform, which public-access route actually works.

Why this exists
---------------
The engine (`fetch_chain.py`) is a *generic* WAF grid. Phase-0 platform routes
(RSS / oEmbed / syndication / yt-dlp / official JSON) live only as agent-driven
snippets in SKILL.md, so they are easy to skip and silently rot (e.g. Reddit's
`hot.json` + mobile-UA started returning 403). This battery hits each platform
through ALL of its candidate routes and reports PASS/FAIL per route, so:

  1. "did we actually try every method?" becomes an evidence artifact, and
  2. a route that rots (was PASS, now FAIL) is caught the next time this runs.

It is intentionally network-live and dependency-light: curl_cffi for HTTP,
yt-dlp for media. No site names are branched in engine/** — this is a *test*,
so concrete targets are allowed here (same exemption as SKILL.md examples).

Run:  python3 tests/coverage_battery.py            # all platforms
      python3 tests/coverage_battery.py reddit x   # subset
      python3 tests/coverage_battery.py --json      # machine-readable
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from typing import Callable, Optional


# --- result schema -----------------------------------------------------------
@dataclass
class RouteResult:
    platform: str
    route: str
    ok: bool
    status: int = 0
    bytes: int = 0
    sample: str = ""
    error: Optional[str] = None
    elapsed_s: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _cffi_get(url: str, *, impersonate: str = "safari", timeout: int = 15, headers: Optional[dict] = None):
    from curl_cffi import requests as r
    return r.get(url, impersonate=impersonate, timeout=timeout,  # type: ignore[arg-type]
                 headers=headers or {}, allow_redirects=True)


def _route(platform: str, route: str, fn: Callable[[], RouteResult]) -> RouteResult:
    t0 = time.time()
    try:
        res = fn()
    except Exception as e:
        res = RouteResult(platform, route, ok=False, error=f"{type(e).__name__}:{str(e)[:120]}")
    res.elapsed_s = round(time.time() - t0, 2)
    return res


# --- platform route batteries ------------------------------------------------
def reddit_routes(sub: str = "LocalLLaMA") -> list[RouteResult]:
    out = []

    def rss():
        x = _cffi_get(f"https://www.reddit.com/r/{sub}/.rss")
        titles = re.findall(r"<title>(.*?)</title>", x.text)[1:4]
        return RouteResult("reddit", "rss(curl_cffi)", ok=(x.status_code == 200 and len(titles) > 0),
                           status=x.status_code, bytes=len(x.text), sample=" | ".join(t[:40] for t in titles))

    def json_plain_ua():
        import urllib.request
        req = urllib.request.Request(f"https://www.reddit.com/r/{sub}/hot.json?limit=5",
                                     headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"})
        try:
            body = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", "replace")
            ok = body.lstrip().startswith("{")
            return RouteResult("reddit", "json+iPhoneUA(SKILL example)", ok=ok, status=200, bytes=len(body),
                               sample="json" if ok else body[:40])
        except Exception as e:
            code = getattr(e, "code", 0)
            return RouteResult("reddit", "json+iPhoneUA(SKILL example)", ok=False, status=code, error=f"{type(e).__name__}:{code}")

    def json_cffi():
        x = _cffi_get(f"https://www.reddit.com/r/{sub}/hot.json?limit=5")
        ok = x.status_code == 200 and x.text.lstrip().startswith("{")
        return RouteResult("reddit", "json(curl_cffi)", ok=ok, status=x.status_code, bytes=len(x.text),
                           sample="json" if ok else x.text[:40])

    out.append(_route("reddit", "rss(curl_cffi)", rss))
    out.append(_route("reddit", "json+iPhoneUA(SKILL example)", json_plain_ua))
    out.append(_route("reddit", "json(curl_cffi)", json_cffi))
    return out


def x_routes(handle: str = "AnthropicAI", tweet_id: str = "1976332881409737124") -> list[RouteResult]:
    out = []

    def syndication_timeline():
        x = _cffi_get(f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}")
        ok = x.status_code == 200 and "__NEXT_DATA__" in x.text
        return RouteResult("x", "syndication-timeline(handle)", ok=ok, status=x.status_code, bytes=len(x.text),
                           sample="timeline json embedded" if ok else x.text[:40])

    def tweet_result():
        x = _cffi_get(f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=a")
        try:
            d = x.json(); txt = (d.get("text") or "")[:50]
            return RouteResult("x", "cdn.syndication tweet-result(id)", ok=bool(txt), status=x.status_code, bytes=len(x.text), sample=txt)
        except Exception:
            return RouteResult("x", "cdn.syndication tweet-result(id)", ok=False, status=x.status_code, bytes=len(x.text))

    def oembed():
        x = _cffi_get(f"https://publish.twitter.com/oembed?url=https://twitter.com/i/status/{tweet_id}&omit_script=1")
        try:
            d = x.json(); txt = re.sub("<[^>]+>", " ", d.get("html", "")); txt = " ".join(txt.split())[:50]
            return RouteResult("x", "publish oembed(url)", ok=bool(txt), status=x.status_code, bytes=len(x.text), sample=txt)
        except Exception:
            return RouteResult("x", "publish oembed(url)", ok=False, status=x.status_code, bytes=len(x.text))

    out.append(_route("x", "syndication-timeline(handle)", syndication_timeline))
    out.append(_route("x", "cdn.syndication tweet-result(id)", tweet_result))
    out.append(_route("x", "publish oembed(url)", oembed))
    return out


def _ytdlp_cmd() -> list[str]:
    """`yt-dlp` on PATH, else `<python> -m yt_dlp` (pip --user / venv / Windows)."""
    import importlib.util
    import shutil
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    return ["yt-dlp"]  # last resort: let subprocess raise a clear FileNotFoundError


def youtube_routes(vid: str = "dQw4w9WgXcQ") -> list[RouteResult]:
    def ytdlp():
        p = subprocess.run(_ytdlp_cmd() + ["--dump-json", "--skip-download", f"https://www.youtube.com/watch?v={vid}"],
                           capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            return RouteResult("youtube", "yt-dlp --dump-json", ok=False, error=(p.stderr or "")[:120])
        d = json.loads(p.stdout)
        subs = list((d.get("subtitles") or {}).keys())[:4]
        return RouteResult("youtube", "yt-dlp --dump-json", ok=True, status=200, bytes=len(p.stdout),
                           sample=f"{d.get('title','')[:35]} | subs:{subs}")
    return [_route("youtube", "yt-dlp --dump-json", ytdlp)]


def hn_routes() -> list[RouteResult]:
    def firebase():
        x = _cffi_get("https://hacker-news.firebaseio.com/v0/topstories.json?limitToFirst=3&orderBy=%22%24key%22")
        ok = x.status_code == 200 and x.text.strip().startswith("[")
        return RouteResult("hn", "firebase topstories", ok=ok, status=x.status_code, bytes=len(x.text), sample=x.text[:40])

    def algolia():
        x = _cffi_get("https://hn.algolia.com/api/v1/search?query=claude&tags=story&hitsPerPage=3")
        try:
            d = x.json(); n = len(d.get("hits", []))
            return RouteResult("hn", "algolia search", ok=(n > 0), status=x.status_code, bytes=len(x.text), sample=f"{n} hits")
        except Exception:
            return RouteResult("hn", "algolia search", ok=False, status=x.status_code)
    return [_route("hn", "firebase topstories", firebase), _route("hn", "algolia search", algolia)]


def arxiv_routes() -> list[RouteResult]:
    def atom():
        x = _cffi_get("http://export.arxiv.org/api/query?search_query=all:large+language+model&max_results=3")
        n = len(re.findall(r"<entry>", x.text))
        return RouteResult("arxiv", "atom api", ok=(x.status_code == 200 and n > 0), status=x.status_code, bytes=len(x.text), sample=f"{n} entries")
    return [_route("arxiv", "atom api", atom)]


def naver_routes() -> list[RouteResult]:
    def search():
        x = _cffi_get("https://search.naver.com/search.naver?query=claude+code", impersonate="safari")
        ok = x.status_code == 200 and len(x.text) > 5000
        return RouteResult("naver", "search.naver(curl_cffi)", ok=ok, status=x.status_code, bytes=len(x.text),
                           sample="html ok" if ok else x.text[:40])
    return [_route("naver", "search.naver(curl_cffi)", search)]


def linkedin_routes() -> list[RouteResult]:
    # LinkedIn full-article extraction normally needs identity spoofing via the engine
    # or JSON-LD parsing of a public pulse URL; here we probe a public pulse page reachably.
    def pulse_jsonld():
        x = _cffi_get("https://www.linkedin.com/pulse/", impersonate="chrome")
        ok = x.status_code == 200 and len(x.text) > 3000 and "Just a moment" not in x.text
        return RouteResult("linkedin", "pulse(curl_cffi chrome)", ok=ok, status=x.status_code, bytes=len(x.text),
                           sample="reachable" if ok else x.text[:40])
    return [_route("linkedin", "pulse(curl_cffi chrome)", pulse_jsonld)]


BATTERIES = {
    "reddit": reddit_routes,
    "x": x_routes,
    "youtube": youtube_routes,
    "hn": hn_routes,
    "arxiv": arxiv_routes,
    "naver": naver_routes,
    "linkedin": linkedin_routes,
}


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    wanted = [a for a in argv if not a.startswith("-")]
    platforms = [p for p in BATTERIES if (not wanted or p in wanted)]

    results: list[RouteResult] = []
    for p in platforms:
        results.extend(BATTERIES[p]())

    if as_json:
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        # group by platform; a platform PASSES if >=1 route works
        print(f"\n{'PLATFORM':<10} {'ROUTE':<34} {'OK':<4} {'HTTP':<5} {'BYTES':>8}  SAMPLE")
        print("-" * 100)
        by_plat: dict[str, list[RouteResult]] = {}
        for r in results:
            by_plat.setdefault(r.platform, []).append(r)
            flag = "✅" if r.ok else "❌"
            print(f"{r.platform:<10} {r.route:<34} {flag:<4} {r.status:<5} {r.bytes:>8}  {(r.sample or r.error or '')[:42]}")
        print("-" * 100)
        passed = [p for p, rs in by_plat.items() if any(x.ok for x in rs)]
        failed = [p for p, rs in by_plat.items() if not any(x.ok for x in rs)]
        print(f"\nPLATFORM COVERAGE: {len(passed)}/{len(by_plat)} reachable")
        print(f"  ✅ reachable: {', '.join(passed) or '(none)'}")
        if failed:
            print(f"  ❌ NO working route: {', '.join(failed)}")
        # surface stale routes (a route that failed but a sibling passed = the example may need updating)
        stale = [f"{r.platform}:{r.route}" for r in results
                 if not r.ok and any(x.ok for x in by_plat[r.platform])]
        if stale:
            print(f"  ⚠️  failed routes w/ working sibling (candidate stale examples): {', '.join(stale)}")

    any_total_fail = any(not any(x.ok for x in rs) for rs in
                         {r.platform: [y for y in results if y.platform == r.platform] for r in results}.values())
    return 1 if any_total_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
