#!/usr/bin/env python3
"""Offline tests for the `m_prefix_subdomain` URL transform.

Background: portal hosts like blog.naver.com / cafe.daum.net answer desktop
requests with a ~2KB frameset shell (verdict `tiny_body` → challenge) while
the `m.`-prefixed twin is full SSR. Neither `mobile_subdomain` (www.* only)
nor `am_prefix` (apex only) covered subdomained hosts, so the grid never
tried the mobile twin — 18 attempts, all challenge (2026-09-03 measurement).

Run manually:
    python3 engine/tests/test_m_prefix_subdomain.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from engine.url_transforms import apply_transform, iter_transformed  # noqa: E402
from engine.fetch_chain import _plan_for_profile  # noqa: E402
from engine.waf_detector import _DEFAULT_PROFILES, load_profile  # noqa: E402


def t_subdomained_host_gets_m_prefix():
    got = apply_transform("m_prefix_subdomain", "https://blog.naver.com/naver_diary?x=1")
    assert got == "https://m.blog.naver.com/naver_diary?x=1", got
    got = apply_transform("m_prefix_subdomain", "https://cafe.daum.net/ok211")
    assert got == "https://m.cafe.daum.net/ok211", got


def t_skips_www_m_and_apex():
    # www.* belongs to mobile_subdomain, apex to am_prefix, m.* is already mobile
    for u in ("https://www.example.com/a", "https://example.com/a", "https://m.blog.naver.com/a"):
        assert apply_transform("m_prefix_subdomain", u) is None, u


def t_keeps_port():
    got = apply_transform("m_prefix_subdomain", "https://blog.example.com:8443/a")
    assert got == "https://m.blog.example.com:8443/a", got


def t_no_overlap_between_mobile_transforms():
    # For any host exactly one of the three mobile transforms applies (or none).
    for u in ("https://www.x.com/", "https://x.com/", "https://blog.x.com/", "https://m.x.com/"):
        hits = [n for n in ("mobile_subdomain", "am_prefix", "m_prefix_subdomain")
                if apply_transform(n, u) is not None]
        assert len(hits) <= 1, (u, hits)


def t_iter_order_dedupes():
    pairs = iter_transformed("https://blog.naver.com/p",
                             ["original", "mobile_subdomain", "m_prefix_subdomain", "am_prefix"])
    names = [n for n, _ in pairs]
    assert names == ["original", "m_prefix_subdomain"], names


def _profile():
    return {
        "tls_impersonate_candidates": [["safari", "chrome"], ["safari_ios", "chrome_android"]],
        "url_transform_order": ["original", "mobile_subdomain", "m_prefix_subdomain"],
        "referer_strategies": ["self_root"],
    }


def t_plan_auto_includes_mobile_twin_for_subdomained_host():
    plan = _plan_for_profile("https://blog.naver.com/naver_diary", "generic", _profile(), "auto")
    transforms = {c.transform for c in plan}
    assert "m_prefix_subdomain" in transforms, transforms
    urls = {c.url for c in plan}
    assert "https://m.blog.naver.com/naver_diary" in urls, urls


def t_plan_mobile_adds_it_even_if_profile_omits():
    prof = _profile(); prof["url_transform_order"] = ["original"]
    plan = _plan_for_profile("https://blog.naver.com/naver_diary", "generic", prof, "mobile")
    assert "m_prefix_subdomain" in {c.transform for c in plan}


def t_generic_profiles_list_the_transform():
    # Regression: the transform existed but the profile a portal actually lands
    # in (unknown_challenge) did not list it, so it never ran (2026-09-05 live).
    yaml_order = load_profile("unknown_challenge").get("url_transform_order") or []
    assert "m_prefix_subdomain" in yaml_order, yaml_order
    code_order = _DEFAULT_PROFILES["unknown_challenge"]["url_transform_order"]
    assert "m_prefix_subdomain" in code_order, code_order


def t_plan_desktop_drops_it():
    plan = _plan_for_profile("https://blog.naver.com/naver_diary", "generic", _profile(), "desktop")
    assert "m_prefix_subdomain" not in {c.transform for c in plan}


if __name__ == "__main__":
    _failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("t_") and callable(fn):
            try:
                fn(); print(f"  ✓ {name}")
            except AssertionError as e:
                _failed += 1; print(f"  ✗ {name}: {e}")
    print("FAIL" if _failed else "OK")
    sys.exit(1 if _failed else 0)
