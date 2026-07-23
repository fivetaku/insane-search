#!/usr/bin/env python3
"""M2 regression — optional resiliparse main-content extraction (boilerplate removal).

Deterministic, network-free. Locks in:
  * enable_maincontent + resiliparse present -> nav/footer/ads stripped, source="maincontent"
  * the extracted main text keeps the article body, drops boilerplate
  * resiliparse absent -> raw HTML retained (graceful), source stays "raw"
  * default (enable_maincontent=False) -> raw content contract preserved
  * a near-empty extraction is rejected (keeps raw) so we never surface a blank
  * maincontent takes precedence over markdown when both are enabled

Run:  python3 engine/tests/test_t4_maincontent.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import engine.fetch_chain as fc  # noqa: E402
from engine.fetch_chain import _extract_response  # noqa: E402


class _FakeResp:
    def __init__(self, text="", headers=None, url="https://x.test/"):
        self.text = text
        self.content = text.encode("utf-8", "ignore")
        self.headers = headers or {"content-type": "text/html"}
        self.status_code = 200
        self.url = url


_BOILERPLATE_HTML = (
    "<html><head><title>Art</title></head><body>"
    "<nav>Home About Contact SHOULD_DROP_NAV</nav>"
    "<aside>Ad: SHOULD_DROP_ASIDE buy now</aside>"
    "<article><h1>Real Title</h1><p>"
    + ("This is the genuine article body carrying the real signal. " * 25)
    + "KEEP_THIS_BODY</p></article>"
    "<footer>Copyright SHOULD_DROP_FOOTER 2026</footer></body></html>")


class _patched:
    def __init__(self, **kw):
        self.kw = kw; self.saved = {}
    def __enter__(self):
        for k, v in self.kw.items():
            self.saved[k] = getattr(fc, k); setattr(fc, k, v)
        return self
    def __exit__(self, *a):
        for k, v in self.saved.items():
            setattr(fc, k, v)


def _resiliparse_available() -> bool:
    return fc._extract_plain_text is not None


def t_maincontent_strips_boilerplate() -> None:
    if not _resiliparse_available():
        print("  ⚠ skipped: resiliparse not installed"); return
    _t, content, _q, meta = _extract_response(
        _FakeResp(_BOILERPLATE_HTML), "https://x.test/a", enable_maincontent=True)
    assert meta["source"] == "maincontent", f"expected maincontent, got {meta['source']}"
    assert "KEEP_THIS_BODY" in content, "article body must survive"
    assert "SHOULD_DROP_NAV" not in content and "SHOULD_DROP_FOOTER" not in content, \
        f"boilerplate leaked:\n{content[:300]}"
    print(f"  ✓ resiliparse main-content strips nav/footer/aside (len={len(content)})")


def t_maincontent_absent_keeps_raw() -> None:
    with _patched(_extract_plain_text=None):
        _t, content, _q, meta = _extract_response(
            _FakeResp(_BOILERPLATE_HTML), "https://x.test/a",
            enable_maincontent=True, enable_markdown=False)
    assert meta["source"] == "raw", f"absent resiliparse must keep raw; got {meta['source']}"
    assert content == _BOILERPLATE_HTML
    print("  ✓ resiliparse absent -> raw HTML retained (graceful)")


def t_maincontent_default_off() -> None:
    # maincontent is opt-in: default must NOT strip to main content (markdown is
    # the default post-step, so source is raw+md, never "maincontent").
    _t, content, _q, meta = _extract_response(_FakeResp(_BOILERPLATE_HTML), "https://x.test/a")
    assert meta["source"] != "maincontent", f"maincontent must be opt-in; got {meta['source']}"
    print(f"  ✓ maincontent off by default (source={meta['source']})")


def t_near_empty_extraction_rejected() -> None:
    if not _resiliparse_available():
        print("  ⚠ skipped: resiliparse not installed"); return
    # A page with no real main content -> resiliparse yields little; keep raw.
    thin = "<html><body><div id='root'></div></body></html>"
    _t, content, _q, meta = _extract_response(
        _FakeResp(thin), "https://x.test/thin", enable_maincontent=True)
    assert meta["source"] == "raw", f"near-empty extraction must fall back to raw; got {meta['source']}"
    print("  ✓ near-empty main-content extraction rejected -> raw kept")


def t_maincontent_precedence_over_markdown() -> None:
    if not _resiliparse_available():
        print("  ⚠ skipped: resiliparse not installed"); return
    _t, content, _q, meta = _extract_response(
        _FakeResp(_BOILERPLATE_HTML), "https://x.test/a",
        enable_maincontent=True, enable_markdown=True)
    assert meta["source"] == "maincontent", \
        f"maincontent should win over markdown when both on; got {meta['source']}"
    assert "SHOULD_DROP_NAV" not in content
    print("  ✓ maincontent takes precedence over markdown when both enabled")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}"); failed += 1
    print(f"\n{'OK' if failed == 0 else 'FAIL'}: {len(tests)-failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
