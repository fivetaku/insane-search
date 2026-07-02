"""Phase 0 — official public-API router (the SANCTIONED exception to No-Site-Name).

Per SKILL.md R5, platforms that publish official no-auth public endpoints get a
deterministic route tried BEFORE the generic WAF grid. This is the *enforced,
in-engine* version of what used to be agent-driven curl snippets in SKILL.md —
so the agent can no longer silently skip it (which is exactly how Reddit/X were
wrongly declared "blocked": the grid 403'd on `.json` and nobody tried `.rss`).

This file is the ONLY engine/ module allowed to name platform hosts; it is
exempted in `bias_check.EXPLICIT_ALLOW_FILES`. Do NOT add per-site logic to any
other engine file — generic WAF handling stays site-agnostic.

Contract:
    route(url) -> Optional[dict]
      None              → url is not a recognised Phase-0 platform; caller runs
                          the generic grid as usual.
      {"platform","ok","route","content","final_url","attempts":[...]}
                        → recognised platform. `ok` says whether an official
                          route succeeded. Even on ok=False the caller should
                          fall through to the grid, but `attempts` is recorded
                          so failure is never silent.

Each attempt dict: {"route","platform","ok","status","bytes","note"}.
"""
from __future__ import annotations

import re
import subprocess
from typing import Optional
from urllib.parse import urlsplit


# --- low-level helpers -------------------------------------------------------
def _cffi_get(url: str, *, impersonate: str = "safari", timeout: int = 15):
    from curl_cffi import requests as r  # lazy: engine works even if missing
    return r.get(
        url,
        impersonate=impersonate,  # type: ignore[arg-type]
        timeout=timeout,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
        },
        allow_redirects=True,
    )


def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h  # strip the literal "www." prefix only


def _attempt(platform: str, route: str, ok: bool, status: int, body: str, note: str = "") -> dict:
    return {"platform": platform, "route": route, "ok": ok, "status": status,
            "bytes": len(body or ""), "note": note}


# --- platform detectors ------------------------------------------------------
def _detect(url: str) -> Optional[str]:
    h = _host(url)
    if not h:
        return None
    if "reddit.com" in h or h == "redd.it":
        return "reddit"
    if h in ("x.com", "twitter.com") or h.endswith(".x.com") or h.endswith(".twitter.com"):
        return "x"
    if "youtube.com" in h or h == "youtu.be":
        return "youtube"
    if h == "news.ycombinator.com":
        return "hackernews"
    if h == "bsky.app":
        return "bluesky"
    if h.endswith("wikipedia.org"):
        return "wikipedia"
    if h == "arxiv.org":
        return "arxiv"
    if h == "github.com":
        return "github"
    if h == "stackoverflow.com":
        return "stackoverflow"
    if h in ("blog.naver.com", "m.blog.naver.com"):
        return "naver_blog"
    return None


# --- reddit ------------------------------------------------------------------
def _reddit(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    base = url.split("?", 1)[0].rstrip("/")
    # Build an .rss / .json target from the path (works for /r/<sub> and post URLs).
    rss_url = base + ("/.rss" if "/comments/" not in base else ".rss")
    json_url = base + ("/.json" if "/comments/" not in base else ".json")

    # Route 1: RSS (the route that actually survives — Reddit gates the JSON API).
    try:
        x = _cffi_get(rss_url, timeout=timeout)
        ok = x.status_code == 200 and ("<rss" in x.text or "<feed" in x.text)
        attempts.append(_attempt("reddit", "rss", ok, x.status_code, x.text,
                                 "feed" if ok else "no-feed-markers"))
        if ok:
            return {"platform": "reddit", "ok": True, "route": "rss",
                    "content": x.text, "final_url": rss_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("reddit", "rss", False, 0, "", f"{type(e).__name__}"))

    # Route 2: JSON via curl_cffi (often 403 now, but try — cheap).
    try:
        x = _cffi_get(json_url, timeout=timeout)
        ok = x.status_code == 200 and x.text.lstrip().startswith(("{", "["))
        attempts.append(_attempt("reddit", "json", ok, x.status_code, x.text,
                                 "json" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "reddit", "ok": True, "route": "json",
                    "content": x.text, "final_url": json_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("reddit", "json", False, 0, "", f"{type(e).__name__}"))

    return {"platform": "reddit", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- x / twitter -------------------------------------------------------------
_TWEET_ID_RE = re.compile(r"/status(?:es)?/(\d+)")


def _x(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    m = _TWEET_ID_RE.search(url)

    if m:  # single tweet → tweet-result + oembed (both no-auth, reliable)
        tid = m.group(1)
        try:
            x = _cffi_get(f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&token=a", timeout=timeout)
            d = x.json() if x.status_code == 200 else {}
            ok = bool(d.get("text"))
            attempts.append(_attempt("x", "tweet-result", ok, x.status_code, x.text,
                                     "has-text" if ok else f"status={x.status_code}"))
            if ok:
                return {"platform": "x", "ok": True, "route": "tweet-result",
                        "content": x.text, "final_url": url, "attempts": attempts}
        except Exception as e:
            attempts.append(_attempt("x", "tweet-result", False, 0, "", f"{type(e).__name__}"))
        try:
            ourl = f"https://publish.twitter.com/oembed?url=https://twitter.com/i/status/{tid}&omit_script=1"
            x = _cffi_get(ourl, timeout=timeout)
            d = x.json() if x.status_code == 200 else {}
            ok = bool(d.get("html"))
            attempts.append(_attempt("x", "oembed", ok, x.status_code, x.text,
                                     "has-html" if ok else f"status={x.status_code}"))
            if ok:
                return {"platform": "x", "ok": True, "route": "oembed",
                        "content": x.text, "final_url": ourl, "attempts": attempts}
        except Exception as e:
            attempts.append(_attempt("x", "oembed", False, 0, "", f"{type(e).__name__}"))
    else:  # profile timeline → syndication (rate-limit-prone; retry once)
        handle = urlsplit(url).path.strip("/").split("/")[0]
        _reserved = {"i", "search", "home", "explore", "messages", "notifications", "settings", "hashtag"}
        if handle and handle.lower() not in _reserved:
            surl = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"
            for attempt_no in range(2):
                try:
                    x = _cffi_get(surl, timeout=timeout)
                    ok = x.status_code == 200 and "__NEXT_DATA__" in x.text
                    attempts.append(_attempt("x", f"syndication-timeline#{attempt_no+1}", ok,
                                             x.status_code, x.text,
                                             "timeline" if ok else f"status={x.status_code}"))
                    if ok:
                        return {"platform": "x", "ok": True, "route": "syndication-timeline",
                                "content": x.text, "final_url": surl, "attempts": attempts}
                except Exception as e:
                    attempts.append(_attempt("x", f"syndication-timeline#{attempt_no+1}", False, 0, "", f"{type(e).__name__}"))

    return {"platform": "x", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- youtube -----------------------------------------------------------------
def _youtube(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    try:
        p = subprocess.run(
            ["yt-dlp", "--dump-json", "--skip-download", url],
            capture_output=True, text=True, timeout=max(timeout, 60),
        )
        ok = p.returncode == 0 and p.stdout.strip().startswith("{")
        note = "json" if ok else (p.stderr or "").strip()[:80]
        attempts.append(_attempt("youtube", "yt-dlp", ok, 200 if ok else 0, p.stdout, note))
        if ok:
            return {"platform": "youtube", "ok": True, "route": "yt-dlp",
                    "content": p.stdout, "final_url": url, "attempts": attempts}
    except FileNotFoundError:
        attempts.append(_attempt("youtube", "yt-dlp", False, 0, "", "yt-dlp not installed"))
    except Exception as e:
        attempts.append(_attempt("youtube", "yt-dlp", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "youtube", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- hacker news -------------------------------------------------------------
_HN_ID_RE = re.compile(r"[?&]id=(\d+)")


def _hackernews(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    m = _HN_ID_RE.search(url)
    if not m:  # front-page / list view → top stories feed
        try:
            x = _cffi_get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=timeout)
            ok = x.status_code == 200 and x.text.lstrip().startswith("[")
            attempts.append(_attempt("hackernews", "firebase-top", ok, x.status_code, x.text,
                                     "topstories" if ok else f"status={x.status_code}"))
            if ok:
                return {"platform": "hackernews", "ok": True, "route": "firebase-top",
                        "content": x.text, "final_url": url, "attempts": attempts}
        except Exception as e:
            attempts.append(_attempt("hackernews", "firebase-top", False, 0, "", f"{type(e).__name__}"))
        return {"platform": "hackernews", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    hid = m.group(1)
    # Algolia returns the whole thread (item + comments) in one JSON doc.
    try:
        x = _cffi_get(f"https://hn.algolia.com/api/v1/items/{hid}", timeout=timeout)
        ok = x.status_code == 200 and x.text.lstrip().startswith("{")
        attempts.append(_attempt("hackernews", "algolia", ok, x.status_code, x.text,
                                 "item" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "hackernews", "ok": True, "route": "algolia",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("hackernews", "algolia", False, 0, "", f"{type(e).__name__}"))
    # Firebase per-item fallback.
    try:
        x = _cffi_get(f"https://hacker-news.firebaseio.com/v0/item/{hid}.json", timeout=timeout)
        ok = x.status_code == 200 and x.text.lstrip().startswith("{")
        attempts.append(_attempt("hackernews", "firebase-item", ok, x.status_code, x.text,
                                 "item" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "hackernews", "ok": True, "route": "firebase-item",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("hackernews", "firebase-item", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "hackernews", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- bluesky (AT Protocol public appview) ------------------------------------
_BSKY_POST_RE = re.compile(r"/profile/([^/]+)/post/([^/?#]+)")
_BSKY_PROFILE_RE = re.compile(r"/profile/([^/?#]+)")


def _bluesky(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    base = "https://public.api.bsky.app/xrpc"
    mp = _BSKY_POST_RE.search(url)
    if mp:  # single post → getPostThread via at:// uri (appview resolves handle)
        handle, rkey = mp.group(1), mp.group(2)
        api = f"{base}/app.bsky.feed.getPostThread?uri=at://{handle}/app.bsky.feed.post/{rkey}"
        try:
            x = _cffi_get(api, timeout=timeout)
            ok = x.status_code == 200 and '"thread"' in x.text
            attempts.append(_attempt("bluesky", "getPostThread", ok, x.status_code, x.text,
                                     "thread" if ok else f"status={x.status_code}"))
            if ok:
                return {"platform": "bluesky", "ok": True, "route": "getPostThread",
                        "content": x.text, "final_url": api, "attempts": attempts}
        except Exception as e:
            attempts.append(_attempt("bluesky", "getPostThread", False, 0, "", f"{type(e).__name__}"))
        return {"platform": "bluesky", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    mpr = _BSKY_PROFILE_RE.search(url)
    if mpr:  # profile → author feed
        handle = mpr.group(1)
        api = f"{base}/app.bsky.feed.getAuthorFeed?actor={handle}&limit=30"
        try:
            x = _cffi_get(api, timeout=timeout)
            ok = x.status_code == 200 and '"feed"' in x.text
            attempts.append(_attempt("bluesky", "getAuthorFeed", ok, x.status_code, x.text,
                                     "feed" if ok else f"status={x.status_code}"))
            if ok:
                return {"platform": "bluesky", "ok": True, "route": "getAuthorFeed",
                        "content": x.text, "final_url": api, "attempts": attempts}
        except Exception as e:
            attempts.append(_attempt("bluesky", "getAuthorFeed", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "bluesky", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- wikipedia (REST v1) -----------------------------------------------------
def _wikipedia(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()  # keep language subdomain (en./ko./...)
    path = parts.path
    if "/wiki/" not in path:
        return {"platform": "wikipedia", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    title = path.split("/wiki/", 1)[1]
    api = f"https://{host}/api/rest_v1/page/html/{title}"
    try:
        x = _cffi_get(api, timeout=timeout)
        ok = x.status_code == 200 and ("<html" in x.text or "<section" in x.text)
        attempts.append(_attempt("wikipedia", "rest-html", ok, x.status_code, x.text,
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "wikipedia", "ok": True, "route": "rest-html",
                    "content": x.text, "final_url": api, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("wikipedia", "rest-html", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "wikipedia", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- arxiv (Atom API) --------------------------------------------------------
_ARXIV_ID_RE = re.compile(r"/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/\d{7})")


def _arxiv(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    m = _ARXIV_ID_RE.search(url)
    if not m:
        return {"platform": "arxiv", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    aid = m.group(1)
    api = f"http://export.arxiv.org/api/query?id_list={aid}"
    try:
        x = _cffi_get(api, timeout=timeout)
        ok = x.status_code == 200 and "<entry>" in x.text
        attempts.append(_attempt("arxiv", "atom", ok, x.status_code, x.text,
                                 "entry" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "arxiv", "ok": True, "route": "atom",
                    "content": x.text, "final_url": api, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("arxiv", "atom", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "arxiv", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- github (REST v3) --------------------------------------------------------
_GH_ISSUE_RE = re.compile(r"^/([^/]+)/([^/]+)/(?:issues|pull)/(\d+)")
_GH_REPO_RE = re.compile(r"^/([^/]+)/([^/]+)/?$")


def _github(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    path = urlsplit(url).path
    mi = _GH_ISSUE_RE.search(path)
    if mi:  # issue / PR → issues API (PRs are issues in the REST model)
        owner, repo, num = mi.group(1), mi.group(2), mi.group(3)
        api = f"https://api.github.com/repos/{owner}/{repo}/issues/{num}"
        route = "issue"
    else:
        mr = _GH_REPO_RE.search(path)
        if not mr:
            return {"platform": "github", "ok": False, "route": None, "content": "",
                    "final_url": url, "attempts": attempts}
        owner, repo = mr.group(1), mr.group(2)
        api = f"https://api.github.com/repos/{owner}/{repo}"
        route = "repo"
    try:
        x = _cffi_get(api, timeout=timeout)
        ok = x.status_code == 200 and x.text.lstrip().startswith("{")
        attempts.append(_attempt("github", route, ok, x.status_code, x.text,
                                 route if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "github", "ok": True, "route": route,
                    "content": x.text, "final_url": api, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("github", route, False, 0, "", f"{type(e).__name__}"))
    return {"platform": "github", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- stackoverflow (Stack Exchange API v2.3) ---------------------------------
_SO_Q_RE = re.compile(r"/questions/(\d+)")


def _stackoverflow(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    m = _SO_Q_RE.search(url)
    if not m:
        return {"platform": "stackoverflow", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    qid = m.group(1)
    # withbody filter includes question + answer HTML bodies.
    api = (f"https://api.stackexchange.com/2.3/questions/{qid}"
           f"?site=stackoverflow&filter=withbody&order=desc&sort=votes")
    try:
        x = _cffi_get(api, timeout=timeout)
        ok = x.status_code == 200 and '"items"' in x.text
        attempts.append(_attempt("stackoverflow", "se-api", ok, x.status_code, x.text,
                                 "items" if ok else f"status={x.status_code}"))
        if ok:
            # Also pull answers so the doc is self-contained.
            try:
                ax = _cffi_get(
                    f"https://api.stackexchange.com/2.3/questions/{qid}/answers"
                    f"?site=stackoverflow&filter=withbody&order=desc&sort=votes",
                    timeout=timeout)
                body = x.text + ("\n" + ax.text if ax.status_code == 200 else "")
            except Exception:
                body = x.text
            return {"platform": "stackoverflow", "ok": True, "route": "se-api",
                    "content": body, "final_url": api, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("stackoverflow", "se-api", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "stackoverflow", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- naver blog --------------------------------------------------------------
_NAVER_BLOG_RE = re.compile(r"^/([^/?#]+)/(\d+)")


def _naver_blog(url: str, timeout: int) -> dict:
    """Naver blog content lives in the PostView frame; the mobile PostView URL
    returns it without the iframe wrapper. Best-effort — falls through to the
    generic grid (which also tries the m. subdomain transform) on failure."""
    attempts: list[dict] = []
    parts = urlsplit(url)
    m = _NAVER_BLOG_RE.search(parts.path)
    if not m:
        return {"platform": "naver_blog", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    blog_id, log_no = m.group(1), m.group(2)
    api = f"https://m.blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
    try:
        x = _cffi_get(api, timeout=timeout)
        ok = x.status_code == 200 and ("se-main-container" in x.text or "post_ct" in x.text
                                       or "postViewArea" in x.text)
        attempts.append(_attempt("naver_blog", "mobile-postview", ok, x.status_code, x.text,
                                 "postview" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "naver_blog", "ok": True, "route": "mobile-postview",
                    "content": x.text, "final_url": api, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("naver_blog", "mobile-postview", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "naver_blog", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


_ROUTERS = {
    "reddit": _reddit, "x": _x, "youtube": _youtube,
    "hackernews": _hackernews, "bluesky": _bluesky, "wikipedia": _wikipedia,
    "arxiv": _arxiv, "github": _github, "stackoverflow": _stackoverflow,
    "naver_blog": _naver_blog,
}


# --- public entrypoint -------------------------------------------------------
def route(url: str, *, timeout: int = 15) -> Optional[dict]:
    platform = _detect(url)
    if platform is None:
        return None
    return _ROUTERS[platform](url, timeout)
