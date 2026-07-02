#!/usr/bin/env python3
"""U9 regression tests — engine power-ups (env-gated, all no-op when unset).

Deterministic, network-free. Covers the opt-in enhancement layer:
  * proxy pool: stable per-host pick, salt rotation, curl/playwright shaping
  * durable cookie jar: save/load roundtrip, merge, TTL expiry, host-agnostic key
  * Phase 0 router: detection + API-URL construction for the expanded platforms
  * parallel fetch_many: input order preserved, one failure can't sink the batch
  * last-resort gate: disabled → None
  * auth profile switch: opt-in durable profile vs per-host throwaway
  * observations: append-only success log, site-agnostic (no host stored)

Run:  python3 engine/tests/test_u9.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from engine import cookiejar, executor, fetch_chain, last_resort, observations, phase0, proxies  # noqa: E402


class _R:
    """Minimal response shim for monkeypatched phase0._cffi_get."""
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def json(self):
        import json
        return json.loads(self.text)


# --- proxies -----------------------------------------------------------------
def t_proxy_disabled_is_noop() -> None:
    os.environ.pop("INSANE_PROXIES", None)
    assert proxies.enabled() is False
    assert proxies.pick("example.com") is None
    assert proxies.as_curl_cffi(None) is None
    assert proxies.as_playwright(None) is None
    print("  ✓ no INSANE_PROXIES → every helper is a no-op")


def t_proxy_stable_and_salted() -> None:
    os.environ["INSANE_PROXIES"] = "socks5://a:1,http://b:2,http://c:3"
    try:
        a = proxies.pick("host.example")
        assert a == proxies.pick("host.example"), "pick must be stable per host"
        assert proxies.pick("host.example", 1) != a or len(proxies.proxy_list()) == 1
        assert proxies.as_curl_cffi("socks5://h:1") == {"http": "socks5://h:1", "https": "socks5://h:1"}
        pw = proxies.as_playwright("http://u:p@h:8080")
        assert pw == {"server": "http://h:8080", "username": "u", "password": "p"}, pw
        print("  ✓ proxy pick stable per host, salt rotates, curl/playwright shaping")
    finally:
        os.environ.pop("INSANE_PROXIES", None)


# --- cookie jar --------------------------------------------------------------
def t_cookiejar_roundtrip_and_merge() -> None:
    d = tempfile.mkdtemp()
    os.environ["INSANE_COOKIEJAR_DIR"] = d
    try:
        cookiejar.save("https://www.gated.example/a", [{"name": "cf", "value": "1"}], user_agent="UA/1")
        cookiejar.save("https://gated.example/b", [{"name": "bm", "value": "2"}])  # www-stripped same host
        data = cookiejar.load("gated.example")
        names = {c["name"]: c["value"] for c in data["cookies"]}
        assert names == {"cf": "1", "bm": "2"}, names
        assert data["user_agent"] == "UA/1"
        print("  ✓ cookiejar save/load merges by host (www-stripped), keeps UA")
    finally:
        os.environ.pop("INSANE_COOKIEJAR_DIR", None)


def t_cookiejar_ttl_expiry() -> None:
    d = tempfile.mkdtemp()
    os.environ["INSANE_COOKIEJAR_DIR"] = d
    os.environ["INSANE_COOKIE_TTL_SEC"] = "0"  # everything is already expired
    try:
        import importlib
        importlib.reload(cookiejar)  # re-read TTL env
        cookiejar.save("https://x.example/", [{"name": "k", "value": "v"}])
        assert cookiejar.load("x.example") is None, "TTL=0 → entry must read as expired"
        print("  ✓ cookiejar honours TTL expiry")
    finally:
        os.environ.pop("INSANE_COOKIE_TTL_SEC", None)
        os.environ.pop("INSANE_COOKIEJAR_DIR", None)
        import importlib
        importlib.reload(cookiejar)


# --- phase 0 expanded router -------------------------------------------------
def t_phase0_detection() -> None:
    cases = {
        "https://news.ycombinator.com/item?id=1": "hackernews",
        "https://bsky.app/profile/a/post/b": "bluesky",
        "https://en.wikipedia.org/wiki/Cat": "wikipedia",
        "https://arxiv.org/abs/2401.00001": "arxiv",
        "https://github.com/a/b": "github",
        "https://stackoverflow.com/questions/11227809/x": "stackoverflow",
        "https://blog.naver.com/id/223": "naver_blog",
    }
    for url, want in cases.items():
        got = phase0._detect(url)
        assert got == want, f"{url} → {got} (want {want})"
    print("  ✓ Phase 0 detects all expanded platforms")


def t_phase0_api_url_construction() -> None:
    seen = {}

    def fake(url, **kw):
        seen["url"] = url
        if "hn.algolia.com" in url:
            return _R('{"id":1,"title":"t"}')
        if "rest_v1/page/html" in url:
            return _R("<html><section>x</section></html>")
        if "export.arxiv.org" in url:
            return _R("<feed><entry>x</entry></feed>")
        if "api.github.com" in url:
            return _R('{"full_name":"a/b"}')
        if "api.stackexchange.com" in url:
            return _R('{"items":[1]}')
        if "getPostThread" in url:
            return _R('{"thread":{}}')
        return _R("", 404)

    orig = phase0._cffi_get
    phase0._cffi_get = fake
    try:
        assert phase0.route("https://news.ycombinator.com/item?id=42")["route"] == "algolia"
        assert phase0.route("https://en.wikipedia.org/wiki/Web_scraping")["route"] == "rest-html"
        assert phase0.route("https://arxiv.org/abs/1706.03762")["route"] == "atom"
        assert phase0.route("https://github.com/pytorch/pytorch")["route"] == "repo"
        assert phase0.route("https://stackoverflow.com/questions/11227809/x")["route"] == "se-api"
        r = phase0.route("https://bsky.app/profile/alice.test/post/abc")
        assert r["ok"] and "getPostThread?uri=at://alice.test/app.bsky.feed.post/abc" in r["final_url"], r
        print("  ✓ Phase 0 builds correct official-API URLs and validates them")
    finally:
        phase0._cffi_get = orig


def t_phase0_unknown_host_returns_none() -> None:
    assert phase0.route("https://some-random-blog.example/post/1") is None
    print("  ✓ non-platform host → None (caller runs the generic grid)")


# --- parallel fetch_many -----------------------------------------------------
def t_fetch_many_preserves_order_and_isolates_errors() -> None:
    urls = ["https://a.example/1", "https://b.example/1", "https://a.example/2", "https://boom.example/1"]

    def fake_fetch(u, **kw):
        if "boom" in u:
            raise RuntimeError("simulated")
        return fetch_chain.FetchResult(ok=True, final_url=u, content="x", verdict="weak_ok")

    orig = fetch_chain.fetch
    fetch_chain.fetch = fake_fetch
    os.environ["INSANE_MANY_WORKERS"] = "3"
    try:
        res = fetch_chain.fetch_many(urls)
        assert [r.final_url for r in res] == urls, [r.final_url for r in res]
        assert res[3].ok is False and res[3].stop_reason == "error", "failing URL must not sink the batch"
        assert res[0].ok is True
        print("  ✓ fetch_many preserves input order and isolates a per-URL failure")
    finally:
        fetch_chain.fetch = orig
        os.environ.pop("INSANE_MANY_WORKERS", None)


# --- last resort -------------------------------------------------------------
def t_last_resort_disabled_returns_none() -> None:
    os.environ["INSANE_LAST_RESORT"] = "0"
    try:
        assert last_resort.run("https://x.example/") is None
        print("  ✓ INSANE_LAST_RESORT=0 → run() is a no-op")
    finally:
        os.environ.pop("INSANE_LAST_RESORT", None)


# --- auth profile ------------------------------------------------------------
def t_auth_profile_switch() -> None:
    os.environ.pop("INSANE_AUTH_PROFILE", None)
    anon = executor._profile_dir_for("https://site.example/a", "playwright_real_chrome")
    assert executor.auth_enabled() is False
    assert ".insane_pw" in anon
    os.environ["INSANE_AUTH_PROFILE"] = "1"
    try:
        auth = executor._profile_dir_for("https://site.example/a", "playwright_real_chrome")
        assert executor.auth_enabled() is True
        assert auth == executor.auth_profile_dir()
        assert auth != anon
        print("  ✓ auth mode swaps throwaway profile for the durable one (opt-in)")
    finally:
        os.environ.pop("INSANE_AUTH_PROFILE", None)


# --- observations ------------------------------------------------------------
def t_observations_append_site_agnostic() -> None:
    d = tempfile.mkdtemp()
    path = os.path.join(d, "obs.jsonl")
    os.environ["INSANE_OBS_PATH"] = path
    try:
        import importlib
        importlib.reload(observations)
        ok = observations.record(profile="cloudflare_turnstile", impersonate="chrome",
                                  transform="original", referer="self_root",
                                  verdict="weak_ok", phase="grid", ts=1.0)
        assert ok
        line = open(path, encoding="utf-8").read()
        assert '"profile": "cloudflare_turnstile"' in line
        assert "host" not in line and "example" not in line, "observations must not store a host"
        print("  ✓ observations append a site-agnostic success record")
    finally:
        os.environ.pop("INSANE_OBS_PATH", None)
        import importlib
        importlib.reload(observations)


ALL = [
    ("proxy_disabled_is_noop", t_proxy_disabled_is_noop),
    ("proxy_stable_and_salted", t_proxy_stable_and_salted),
    ("cookiejar_roundtrip_and_merge", t_cookiejar_roundtrip_and_merge),
    ("cookiejar_ttl_expiry", t_cookiejar_ttl_expiry),
    ("phase0_detection", t_phase0_detection),
    ("phase0_api_url_construction", t_phase0_api_url_construction),
    ("phase0_unknown_host_returns_none", t_phase0_unknown_host_returns_none),
    ("fetch_many_preserves_order_and_isolates_errors", t_fetch_many_preserves_order_and_isolates_errors),
    ("last_resort_disabled_returns_none", t_last_resort_disabled_returns_none),
    ("auth_profile_switch", t_auth_profile_switch),
    ("observations_append_site_agnostic", t_observations_append_site_agnostic),
]


def main() -> int:
    p = f = 0
    for name, fn in ALL:
        try:
            print(f"[{name}]")
            fn()
            p += 1
        except AssertionError as e:
            f += 1
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            f += 1
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
