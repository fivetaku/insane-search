#!/usr/bin/env python3
"""U9 regression tests — omo-senpi merge (2026-07-20).

Deterministic, network-free. Locks in the merged delta:
  * marker false-positive fixes (lookbehind, structural, soft-mention)
  * curl_cffi runtime target filter
  * recipe loader match/rewrite (scraper-forge output)
  * protocol-stealth executor routing + graceful driver-absence

Run:  python3 engine/tests/test_u9_merge.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from engine.validators import validate, Verdict  # noqa: E402
from engine.transport import filter_available, available_impersonates  # noqa: E402
from engine.executor import _pick_executor, run_playwright_fallback  # noqa: E402
from engine import recipe_loader  # noqa: E402


class _Resp:
    def __init__(self, text, status=200, ctype="text/html"):
        self.text = text
        self.status_code = status
        self.url = "https://x/"
        self.headers = {"content-type": ctype}
        self.content = text.encode("utf-8", "ignore")
        jar = [type("c", (), {"name": "_x", "value": "1"})()]
        self.cookies = type("C", (), {"jar": jar})()


_P = 0
_F = 0


def check(label, cond):
    global _P, _F
    if cond:
        _P += 1
        print(f"  \u2713 {label}")
    else:
        _F += 1
        print(f"  \u2717 {label}")


def _v(text, **k):
    return validate(_Resp(text), **k).verdict


def run() -> None:
    print("[markers]")
    big = "<html><body>" + ("x" * 5000) + ' "octocaptcha_origin_optimization" ' + "</body></html>"
    check("octocaptcha token is not a challenge", _v(big) != Verdict.CHALLENGE)
    inter = ("<html><head><title>x</title></head><body>" + ("x" * 240000)
             + ' window._cf_chl_opt = {}; "/cdn-cgi/challenge-platform/h/g/orchestrate/chl_page" ' + "</body></html>")
    check("CF interstitial is CHALLENGE at any size", _v(inter) == Verdict.CHALLENGE)
    info = "<html><body>" + ("x" * 44000) + " his datadome detection page " + "</body></html>"
    check("single soft marker in large body is a mention", _v(info) == Verdict.WEAK_OK)
    small = "<html><body>" + ("x" * 1000) + " datadome " + "</body></html>"
    check("single soft marker in small body stays CHALLENGE", _v(small) == Verdict.CHALLENGE)
    two = "<html><body>" + ("x" * 44000) + " datadome and captcha here " + "</body></html>"
    check("two soft markers stay CHALLENGE", _v(two) == Verdict.CHALLENGE)

    print("[tls-filter]")
    check("bogus target dropped, real kept", filter_available(["bogus_tls_xyz", "chrome"]) == ["chrome"])
    check("empty intersection keeps original", filter_available(["bogus_tls_xyz"]) == ["bogus_tls_xyz"])
    av = available_impersonates()
    check("available set has chrome alias (or curl_cffi absent)", av is None or "chrome" in av)

    print("[recipe-loader]")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["INSANE_RECIPES_DIR"] = tmp
        os.makedirs(os.path.join(tmp, "example.com"))
        with open(os.path.join(tmp, "example.com", "recipe.yaml"), "w", encoding="utf-8") as f:
            f.write("domain: example.com\nurl_rewrites:\n  - name: item\n    pattern: /item/(\\d+)\n    replacement: /api/items/\\1.json\n    expect: json\n")
        rec = recipe_loader.load_recipe("https://example.com/item/42")
        check("recipe loads for domain", rec is not None)
        rule = recipe_loader.match_rewrite("https://example.com/item/42", rec)
        check("rewrite maps page URL to API URL",
              rule is not None and rule["rewritten_url"] == "https://example.com/api/items/42.json")
        check("no match returns None",
              recipe_loader.match_rewrite("https://example.com/other", rec) is None)
        os.environ["INSANE_NO_RECIPE"] = "1"
        check("INSANE_NO_RECIPE disables loading",
              recipe_loader.load_recipe("https://example.com/item/42") is None)
        os.environ.pop("INSANE_NO_RECIPE", None)
        os.environ.pop("INSANE_RECIPES_DIR", None)

    print("[protocol-stealth]")
    check("needs_protocol_stealth routes to protocol_stealth_chrome",
          _pick_executor(["needs_protocol_stealth", "needs_real_tls_stack"], "auto") == "protocol_stealth_chrome")
    check("mobile still routes to mobile executor",
          _pick_executor(["needs_protocol_stealth", "needs_real_tls_stack"], "mobile") == "playwright_mobile_chrome")
    with patch("engine.executor._module_available", return_value=False):
        att, content = run_playwright_fallback(
            "https://example.com", profile_id="unknown_challenge", force_executor="protocol_stealth_chrome")
    check("missing drivers report actionable error", content == "" and "nodriver" in (att.error or ""))

    print(f"\n{_P} passed, {_F} failed")
    if _F:
        sys.exit(1)


if __name__ == "__main__":
    run()
