#!/usr/bin/env python3
"""M1 regression — optional markdownify structure-preserving markdownification.

Deterministic, network-free. Locks in:
  * a raw-HTML success is markdownified: <table> -> pipe table, <pre><code> -> fence
  * extraction_source gains "+md" only on the raw-HTML path
  * script/style/head noise is stripped before conversion (no junk in markdown)
  * markdownify absent -> content stays raw HTML, source == "raw" (graceful)
  * json_ld / inner_text (already plain text) are NOT markdownified
  * FetchResult still constructs and exposes extraction_source

Run:  python3 engine/tests/test_t3_markdown.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import engine.fetch_chain as fc  # noqa: E402
from engine.fetch_chain import FetchResult, _extract_response  # noqa: E402


class _FakeResp:
    def __init__(self, text="", headers=None, url="https://x.test/"):
        self.text = text
        self.content = text.encode("utf-8", "ignore")
        self.headers = headers or {"content-type": "text/html"}
        self.status_code = 200
        self.url = url


_TABLE_HTML = (
    "<html><head><title>T</title><style>.x{color:red}</style></head><body>"
    "<article><p>" + ("Real article body sentence with substance. " * 30) + "</p>"
    "<table><thead><tr><th>Name</th><th>Qty</th></tr></thead>"
    "<tbody><tr><td>Apple</td><td>3</td></tr><tr><td>Pear</td><td>5</td></tr></tbody></table>"
    "</article><script>var tracking='SHOULD_NOT_APPEAR';</script></body></html>")

_CODE_HTML = (
    "<html><head><title>C</title></head><body><article><p>"
    + ("Explanatory prose sentence with enough length to be real content. " * 25)
    + "</p><pre><code>def hello():\n    return 42</code></pre></article></body></html>")


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


def t_table_becomes_pipe_table() -> None:
    _t, content, _q, meta = _extract_response(_FakeResp(_TABLE_HTML), "https://x.test/t", enable_markdown=True)
    assert meta["source"].endswith("+md"), f"raw HTML should be markdownified; source={meta['source']}"
    assert "| Name | Qty |" in content or "| Name  | Qty |" in content or "|Name|Qty|" in content.replace(" ", ""), \
        f"expected a markdown pipe table, got:\n{content[:400]}"
    assert "Apple" in content and "Pear" in content
    print("  ✓ <table> -> markdown pipe table (source=%s)" % meta["source"])


def t_code_fence_preserved() -> None:
    _t, content, _q, meta = _extract_response(_FakeResp(_CODE_HTML), "https://x.test/c", enable_markdown=True)
    assert meta["source"].endswith("+md")
    assert "```" in content and "def hello():" in content, f"expected fenced code, got:\n{content[:400]}"
    print("  ✓ <pre><code> -> fenced code block")


def t_script_style_noise_stripped() -> None:
    _t, content, _q, meta = _extract_response(_FakeResp(_TABLE_HTML), "https://x.test/t", enable_markdown=True)
    assert "SHOULD_NOT_APPEAR" not in content, "inline <script> text leaked into markdown"
    assert "color:red" not in content, "inline <style> text leaked into markdown"
    print("  ✓ script/style/head noise stripped before markdownify")


def t_markdownify_absent_keeps_raw() -> None:
    with _patched(_markdownify=None):
        _t, content, _q, meta = _extract_response(_FakeResp(_TABLE_HTML), "https://x.test/t", enable_markdown=True)
    assert meta["source"] == "raw", f"absent markdownify must keep raw; source={meta['source']}"
    assert content == _TABLE_HTML, "content must be the untouched raw HTML when markdownify is absent"
    print("  ✓ markdownify absent -> raw HTML retained (graceful)")


def t_json_ld_not_markdownified() -> None:
    body = ('<html><head><title>S</title></head><body><div id="root"></div>'
            '<script type="application/ld+json">{"@type":"NewsArticle","articleBody":"'
            + ("JSON-LD article body only. " * 20) + '"}</script></body></html>')
    _t, content, _q, meta = _extract_response(_FakeResp(body), "https://x.test/s", enable_markdown=True)
    assert meta["source"] == "json_ld", f"got {meta['source']}"
    assert "+md" not in meta["source"], "plain-text json_ld must not be markdownified"
    print("  ✓ json_ld (plain text) not markdownified")


def t_default_on_markdownifies() -> None:
    # markdown is now the DEFAULT (agent-fetch engine wants clean markdown).
    _t, content, _q, meta = _extract_response(_FakeResp(_TABLE_HTML), "https://x.test/t")
    assert meta["source"] == "raw+md", f"default should markdownify; source={meta['source']}"
    print("  ✓ default (no flag) markdownifies — clean output by default")


def t_explicit_disable_keeps_raw() -> None:
    # enable_markdown=False restores the raw-HTML content contract.
    _t, content, _q, meta = _extract_response(_FakeResp(_TABLE_HTML), "https://x.test/t", enable_markdown=False)
    assert meta["source"] == "raw" and content == _TABLE_HTML, \
        f"enable_markdown=False must keep raw; source={meta['source']}"
    print("  ✓ enable_markdown=False keeps raw HTML (opt-out works)")


def t_fetchresult_exposes_source() -> None:
    r = FetchResult(ok=True, content="x", extraction_source="raw+md",
                    extraction_meta={"source": "raw+md"})
    assert r.to_dict()["extraction_source"] == "raw+md"
    print("  ✓ FetchResult.to_dict exposes extraction_source (raw+md)")


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
