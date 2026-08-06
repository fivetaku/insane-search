#!/usr/bin/env python3
"""U1 regression tests — validator v2 + diversity scheduler.

Deterministic, network-free. Locks in the multi-AI-review fixes:
  * grid diversity under a small cap (all TLS families + both transforms)
  * avoid targets deprioritized, NOT deleted
  * validator: small JSON ok, _abck-unresolved non-terminal, soft-marker
    overridden by selector, status semantics.

Run:  python3 engine/tests/test_u1.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from engine.validators import validate, Verdict  # noqa: E402
from engine.waf_detector import _load_profiles  # noqa: E402
from engine.fetch_chain import _build_plan, _family  # noqa: E402


class _Ck:
    def __init__(self, name, value):
        self.name, self.value = name, value


class _Jar:
    def __init__(self, d):
        self.jar = [_Ck(k, v) for k, v in d.items()]


class _Resp:
    def __init__(self, status=200, text="", headers=None, cookies=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self.cookies = _Jar(cookies or {})


class _Hit:
    def __init__(self, pid):
        self.profile_id = pid
        self.confidence = 0.9
        self.signals = []


# ---------- scheduler ----------
def t_scheduler_diversity_under_cap():
    profiles = _load_profiles()
    plan = _build_plan("https://www.example.com/p", [_Hit("akamai_bot_manager")],
                       profiles, "auto", "safari", "self_root")
    budget = 11  # max_attempts 12 - probe
    head = plan[:budget]
    fams = set(_family(c.impersonate) for c in head)
    transforms = set(c.transform for c in head)
    assert fams == {"safari", "safari_ios", "chrome", "chrome_android", "edge"}, fams
    assert transforms == {"original", "mobile_subdomain"}, transforms
    print(f"  ✓ first {budget} cover all families {sorted(fams)} + transforms {sorted(transforms)}")


def t_scheduler_avoid_deprioritized_not_deleted():
    profiles = _load_profiles()
    plan = _build_plan("https://www.example.com/p", [_Hit("akamai_bot_manager")],
                       profiles, "auto", "safari", "self_root")
    imps = [c.impersonate for c in plan]
    # chrome145/146 are in avoid; must still be present (exhaustive) but late.
    assert "chrome145" in imps and "chrome146" in imps, "avoid targets were deleted!"
    pos145 = min(i for i, x in enumerate(imps) if x == "chrome145")
    early = imps[: len(imps) // 2]
    assert "chrome145" not in early, "avoid target not deprioritized"
    print(f"  ✓ avoid targets retained but late (chrome145 idx={pos145}/{len(imps)})")


def t_scheduler_desktop_drops_mobile_transform():
    profiles = _load_profiles()
    plan = _build_plan("https://www.example.com/p", [_Hit("akamai_bot_manager")],
                       profiles, "desktop", "safari", "self_root")
    transforms = set(c.transform for c in plan)
    fams = set(_family(c.impersonate) for c in plan)
    assert "mobile_subdomain" not in transforms, transforms
    assert "safari_ios" not in fams and "chrome_android" not in fams, fams
    print(f"  ✓ desktop drops mobile transform & mobile TLS (transforms={sorted(transforms)})")


# ---------- validator v2 ----------
def t_validator_small_json_ok():
    r = _Resp(200, '{"items":[{"id":1}],"total":1}', headers={"Content-Type": "application/json"})
    v = validate(r)
    assert v.verdict == Verdict.WEAK_OK, v.verdict
    assert not (v.verdict == Verdict.CHALLENGE)
    print(f"  ✓ small JSON → {v.verdict.value} (was challenge)")


def t_validator_abck_unresolved_is_non_terminal():
    r = _Resp(200, "<html>" + "x" * 5000 + "</html>", cookies={"_abck": "AA~-1~bb"})
    v = validate(r)
    assert v.verdict == Verdict.SUSPECT_OK, v.verdict
    assert v.ok is False, "SUSPECT_OK must not count as terminal success"
    print(f"  ✓ _abck unresolved → {v.verdict.value}, ok={v.ok} (was weak_ok/ok=True)")


def t_validator_soft_marker_overridden_by_selector():
    html = "<html><script>var s='captcha';</script><body>" + "x" * 5000 + "<main id='c'>real</main></body></html>"
    v = validate(_Resp(200, html), success_selectors=["#c"])
    assert v.verdict == Verdict.STRONG_OK, v.verdict
    print(f"  ✓ 'captcha' word + matching selector → {v.verdict.value} (was challenge)")


def t_validator_hard_marker_still_challenge():
    v = validate(_Resp(200, "<html>" + "x" * 5000 + " sec-if-cpt-container </html>"))
    assert v.verdict == Verdict.CHALLENGE, v.verdict
    print(f"  ✓ hard marker still → {v.verdict.value}")


def t_validator_status_semantics():
    assert validate(_Resp(429, "slow down")).verdict == Verdict.RATE_LIMITED
    assert validate(_Resp(401, "nope")).verdict == Verdict.AUTH_REQUIRED
    assert validate(_Resp(404, "gone")).verdict == Verdict.NOT_FOUND
    assert validate(_Resp(503, "later")).verdict == Verdict.BLOCKED
    print("  ✓ status semantics 429/401/404/503 differentiated")


def t_validator_byte_size_not_char_count():
    # 1500 Korean chars = 1500 chars but 4500 bytes (>threshold) → not tiny.
    body = "가" * 1500
    v = validate(_Resp(200, body, headers={"Content-Type": "text/html"}))
    # 4500 bytes ≥ 3000 → not tiny_body; no markers/selectors → weak_ok
    assert v.body_size >= 3000, v.body_size
    assert v.verdict == Verdict.WEAK_OK, (v.verdict, v.body_size)
    print(f"  ✓ byte size counts UTF-8 bytes ({v.body_size}B from 1500 chars) → {v.verdict.value}")


def t_validator_small_complete_page_is_weak_ok():
    # example.com is a complete ~600B HTML document with real text — a small but
    # genuine page must NOT be mislabelled a challenge stub (regression guard).
    body = ('<!doctype html><html lang="en"><head><title>Example Domain</title>'
            '</head><body><div><h1>Example Domain</h1><p>This domain is for use in '
            'documentation examples without needing permission.</p>'
            '<p><a href="https://iana.org/domains/example">Learn more</a></p>'
            '</div></body></html>')
    v = validate(_Resp(200, body, headers={"Content-Type": "text/html"}))
    assert v.body_size < 3000, v.body_size
    assert v.verdict == Verdict.WEAK_OK, (v.verdict, v.reasons)
    print(f"  ✓ small complete page → {v.verdict.value} ({v.reasons})")


def t_validator_small_script_stub_still_challenge():
    # Script-only tiny body (no visible text) is still a suspicious stub.
    body = '<html><head></head><body><script src="/cdn-cgi/challenge.js"></script></body></html>'
    v = validate(_Resp(200, body, headers={"Content-Type": "text/html"}))
    assert v.verdict == Verdict.CHALLENGE, (v.verdict, v.reasons)
    print(f"  ✓ script-only tiny body → {v.verdict.value}")


def t_validator_small_fragment_still_challenge():
    # Incomplete fragment (no closing </html>/</body>) stays suspicious.
    v = validate(_Resp(200, "<div>loading", headers={"Content-Type": "text/html"}))
    assert v.verdict == Verdict.CHALLENGE, (v.verdict, v.reasons)
    print(f"  ✓ incomplete fragment → {v.verdict.value}")


ALL = [
    ("scheduler_diversity_under_cap", t_scheduler_diversity_under_cap),
    ("scheduler_avoid_deprioritized_not_deleted", t_scheduler_avoid_deprioritized_not_deleted),
    ("scheduler_desktop_drops_mobile_transform", t_scheduler_desktop_drops_mobile_transform),
    ("validator_small_json_ok", t_validator_small_json_ok),
    ("validator_abck_unresolved_is_non_terminal", t_validator_abck_unresolved_is_non_terminal),
    ("validator_soft_marker_overridden_by_selector", t_validator_soft_marker_overridden_by_selector),
    ("validator_hard_marker_still_challenge", t_validator_hard_marker_still_challenge),
    ("validator_status_semantics", t_validator_status_semantics),
    ("validator_byte_size_not_char_count", t_validator_byte_size_not_char_count),
    ("validator_small_complete_page_is_weak_ok", t_validator_small_complete_page_is_weak_ok),
    ("validator_small_script_stub_still_challenge", t_validator_small_script_stub_still_challenge),
    ("validator_small_fragment_still_challenge", t_validator_small_fragment_still_challenge),
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
