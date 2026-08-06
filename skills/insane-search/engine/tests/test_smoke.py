#!/usr/bin/env python3
"""Smoke / regression test for the generic fetch chain.

These tests hit real endpoints — mark as online / integration. They verify
behaviour patterns, not content. No assertions on specific site brands.

Run manually:
    python3 engine/tests/test_smoke.py
"""
from __future__ import annotations

import json
import os
import sys
import time

# Allow running from anywhere.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from engine import fetch  # noqa: E402
from engine.validators import validate, Verdict  # noqa: E402
from engine.waf_detector import detect, _load_profiles  # noqa: E402
from engine.url_transforms import iter_transformed  # noqa: E402


# --- unit-level -------------------------------------------------------------
def t_validator_tiny_body_is_challenge():
    class R:
        status_code = 200
        text = "<html>short</html>"
        headers = {}
        cookies = type("C", (), {"jar": iter(())})()
    vr = validate(R())
    assert vr.verdict == Verdict.CHALLENGE, vr.verdict
    assert any("tiny_body" in r for r in vr.reasons)
    print("  ✓ tiny body → challenge")


def t_validator_marker_is_challenge():
    class R:
        status_code = 200
        text = "<html>" + ("x" * 5000) + " sec-if-cpt-container found </html>"
        headers = {}
        cookies = type("C", (), {"jar": iter(())})()
    vr = validate(R())
    assert vr.verdict == Verdict.CHALLENGE, vr.verdict
    print("  ✓ challenge marker → challenge")


def t_validator_weak_ok_without_selectors():
    class R:
        status_code = 200
        text = "<html>" + ("x" * 5000) + "</html>"
        headers = {}
        cookies = type("C", (), {"jar": iter(())})()
    vr = validate(R())
    assert vr.verdict == Verdict.WEAK_OK, vr.verdict
    print("  ✓ clean body w/o selectors → weak_ok")


def t_validator_strong_ok_with_selectors():
    class R:
        status_code = 200
        text = "<html><body>" + ("x" * 5000) + "<article>hello</article></body></html>"
        headers = {}
        cookies = type("C", (), {"jar": iter(())})()
    vr = validate(R(), success_selectors=["article"])
    assert vr.verdict == Verdict.STRONG_OK, vr.verdict
    assert "article" in vr.matched_selectors
    print("  ✓ selectors matched → strong_ok")


def t_profiles_load():
    p = _load_profiles()
    for required in ("akamai_bot_manager", "cloudflare_turnstile", "unknown_challenge"):
        assert required in p, f"missing profile: {required}"
    print(f"  ✓ profiles loaded ({len(p)} keys)")


def t_url_transforms():
    # www → m
    out = iter_transformed("https://www.example.com/a", ["original", "mobile_subdomain"])
    urls = [u for _, u in out]
    assert "https://www.example.com/a" in urls
    assert "https://m.example.com/a" in urls, urls
    # apex with am_prefix
    out2 = iter_transformed("https://example.com/", ["original", "am_prefix"])
    urls2 = [u for _, u in out2]
    assert "https://m.example.com/" in urls2, urls2
    print(f"  ✓ url_transforms produce expected forms")


# --- online (network) -------------------------------------------------------
def t_online_benign_site():
    """A simple, usually-open site should pass probe directly when selectors provided."""
    # example.com serves ~1.2KB content — below tiny_body threshold — but with
    # success_selectors we trust caller's "content exists" definition.
    r = fetch(
        "https://example.com/",
        success_selectors=["h1", "p"],
        timeout=15,
        max_attempts=3,
        enable_playwright=False,
    )
    assert r.ok, f"{r.summary} | trace: {[a.verdict for a in r.trace]}"
    assert r.verdict in ("strong_ok", "weak_ok"), r.verdict
    print(f"  ✓ benign site → verdict={r.verdict} size={len(r.content)}")


def t_online_trace_shape():
    """Even on failure, trace should be populated and well-formed."""
    r = fetch("https://httpbin.org/status/403", timeout=10, max_attempts=3, enable_playwright=False)
    assert isinstance(r.trace, list) and len(r.trace) >= 1
    for att in r.trace:
        d = att.to_dict()
        assert "phase" in d and "executor" in d and "verdict" in d
    print(f"  ✓ httpbin 403 → trace_len={len(r.trace)} final={r.verdict}")


ALL_TESTS = [
    ("validator_tiny_body_is_challenge", t_validator_tiny_body_is_challenge),
    ("validator_marker_is_challenge", t_validator_marker_is_challenge),
    ("validator_weak_ok_without_selectors", t_validator_weak_ok_without_selectors),
    ("validator_strong_ok_with_selectors", t_validator_strong_ok_with_selectors),
    ("profiles_load", t_profiles_load),
    ("url_transforms", t_url_transforms),
    ("online_benign_site", t_online_benign_site),
    ("online_trace_shape", t_online_trace_shape),
]


def main() -> int:
    passed, failed = 0, 0
    for name, fn in ALL_TESTS:
        try:
            print(f"[{name}]")
            fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            failed += 1
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
