#!/usr/bin/env python3
"""Browser-fallback envelope parsing must fail closed.

A Playwright template's stdout is a JSON envelope that includes the browser's
cookie jar. If that envelope is truncated or prefixed with stray output, the
old code promoted the raw stdout to page HTML, so the cookies flowed into the
wrapped content, ``--trace`` and the observations log. These tests pin the
fix: malformed stdout yields an UNKNOWN attempt with an empty body, and no
cookie value reaches the observations jsonl.

Run manually:
    python3 engine/tests/test_envelope_fail_closed.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import engine.executor as ex  # noqa: E402
from engine.validators import Verdict  # noqa: E402

COOKIE = "COOKIE_SEKRIT_VALUE_9f3a"
URL = "https://h.test/page"


def _envelope(html="<html><body>ok</body></html>") -> str:
    return json.dumps({
        "html": html, "finalUrl": URL, "status": 200,
        "cookies": [{"name": "cf_clearance", "value": COOKIE, "domain": ".h.test"}],
        "userAgent": "UA", "automation": None, "innerText": "ok",
    })


def t_well_formed_envelope_still_parses():
    got = ex._parse_envelope(_envelope(), URL)
    assert got is not None
    html, final_url, status, cookies, *_ = got
    assert html.startswith("<html>") and COOKIE not in html
    assert cookies and cookies[0]["value"] == COOKIE  # bridge still gets them


def t_truncated_envelope_is_rejected():
    assert ex._parse_envelope(_envelope()[:-5], URL) is None


def t_prefixed_envelope_is_rejected():
    assert ex._parse_envelope("stray warning\n" + _envelope(), URL) is None


def t_non_json_and_non_object_are_rejected():
    assert ex._parse_envelope("<html>legacy raw html</html>", URL) is None
    assert ex._parse_envelope("", URL) is None
    assert ex._parse_envelope('["not", "an", "object"]', URL) is None


def _run_fallback_with_stdout(stdout: str):
    """Drive run_playwright_fallback with the node runner stubbed out."""
    saved = (ex._run_node_template, ex._resolve_node_deps, ex.load_profile)
    ex._run_node_template = lambda *a, **k: (0, stdout, "")
    ex._resolve_node_deps = lambda: "/nonexistent-deps"
    ex.load_profile = lambda pid, profiles=None: {"capabilities_needed": []}
    try:
        return ex.run_playwright_fallback(
            URL, profile_id="generic", force_executor="playwright_real_chrome", timeout=5)
    finally:
        ex._run_node_template, ex._resolve_node_deps, ex.load_profile = saved


def t_fallback_returns_empty_body_on_broken_envelope():
    att, html = _run_fallback_with_stdout(_envelope()[:-5])
    assert html == "", html[:80]
    assert att.verdict == Verdict.UNKNOWN.value, att.verdict
    assert COOKIE not in (att.error or "")
    assert att.body_size == 0


def t_fallback_ok_on_good_envelope():
    att, html = _run_fallback_with_stdout(_envelope())
    assert "ok" in html and COOKIE not in html
    assert att.status == 200 and att.body_size == len(html)


def t_observations_log_has_no_cookie_after_broken_envelope():
    from types import SimpleNamespace
    from engine import observations_log

    att, html = _run_fallback_with_stdout(_envelope()[:-5])
    result = SimpleNamespace(trace=[att], ok=False, verdict=att.verdict,
                             profile_used="generic", planned_attempts=1,
                             stop_reason="exhausted", content=html)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["INSANE_OBSERVATIONS_DIR"] = tmp
        try:
            observations_log.log_fetch(URL, result)
            files = os.listdir(tmp)
            assert len(files) == 1, files
            text = open(os.path.join(tmp, files[0]), encoding="utf-8").read()
        finally:
            os.environ.pop("INSANE_OBSERVATIONS_DIR", None)
    assert COOKIE not in text, text
    assert "cf_clearance" not in text, text


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("t_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"\n{fails} failure(s)")
    sys.exit(1 if fails else 0)
