#!/usr/bin/env python3
"""U7 tests — SSRF / redirect guard. Offline & deterministic.

Run:  python3 engine/tests/test_u7.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from engine.safety import classify_url            # noqa: E402
from engine.transport import SessionPool          # noqa: E402


def t_classify_blocks_internal():
    blocked = [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata
        "http://10.0.0.1/",
        "http://192.168.1.1/admin",
        "http://172.16.0.1/",
        "http://[::1]/",
        "http://0.0.0.0/",
        "ftp://example.com/",                          # scheme
        "file:///etc/passwd",                          # scheme
        "http://localhost/",                           # resolves to loopback
    ]
    for u in blocked:
        ok, reason = classify_url(u, allow_private=False)
        assert not ok, f"should block {u} (got ok, reason={reason})"
    print(f"  ✓ blocks {len(blocked)} internal/metadata/scheme targets")


def t_classify_allows_public():
    for u in ["https://1.1.1.1/", "http://8.8.8.8/"]:   # public IP literals (no DNS)
        ok, reason = classify_url(u, allow_private=False)
        assert ok, f"should allow public {u} ({reason})"
    print("  ✓ allows public IP literals")


def t_allow_private_optin():
    ok, _ = classify_url("http://127.0.0.1:8080/", allow_private=True)
    assert ok, "allow_private=True must permit loopback"
    print("  ✓ allow_private=True opt-in permits loopback (local testing)")


def t_request_blocks_localhost_by_default():
    p = SessionPool()
    resp, err = p.request("http://127.0.0.1:9/", impersonate="chrome")  # no fetch happens
    assert resp is None and err and err.startswith("ssrf_blocked"), (resp, err)
    print(f"  ✓ POOL.request blocks loopback pre-fetch: {err}")


class _FakeResp:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.text = "ok"


def t_redirect_to_metadata_blocked():
    def do_get(u):
        if "evil" in u:
            return _FakeResp(302, {"Location": "http://169.254.169.254/latest/meta-data/"})
        return _FakeResp(200)
    resp, err = SessionPool._fetch_following(do_get, "https://evil.test/", False, 5, None)
    assert resp is None and err and err.startswith("ssrf_redirect_blocked"), (resp, err)
    print(f"  ✓ redirect into metadata IP blocked: {err}")


def t_safe_redirect_followed():
    hops = {"n": 0}
    def do_get(u):
        hops["n"] += 1
        if "start" in u:
            return _FakeResp(302, {"Location": "http://1.1.1.1/landing"})  # public
        return _FakeResp(200)
    resp, err = SessionPool._fetch_following(do_get, "https://start.test/", False, 5, None)
    assert err is None and resp is not None and resp.status_code == 200, (resp, err)
    assert hops["n"] == 2, hops
    print(f"  ✓ safe redirect to public IP followed ({hops['n']} hops → 200)")


def t_too_many_redirects():
    def do_get(u):
        return _FakeResp(302, {"Location": "http://1.1.1.1/loop"})
    resp, err = SessionPool._fetch_following(do_get, "http://1.1.1.1/loop", False, 3, None)
    assert resp is None and err == "too_many_redirects", (resp, err)
    print("  ✓ redirect loop capped (too_many_redirects)")


ALL = [
    ("classify_blocks_internal", t_classify_blocks_internal),
    ("classify_allows_public", t_classify_allows_public),
    ("allow_private_optin", t_allow_private_optin),
    ("request_blocks_localhost_by_default", t_request_blocks_localhost_by_default),
    ("redirect_to_metadata_blocked", t_redirect_to_metadata_blocked),
    ("safe_redirect_followed", t_safe_redirect_followed),
    ("too_many_redirects", t_too_many_redirects),
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
