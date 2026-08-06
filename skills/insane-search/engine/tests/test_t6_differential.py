#!/usr/bin/env python3
"""M4 regression — differential block classification (route-outcome comparison).

Deterministic, network-free. Locks in (Bamberg arXiv:2606.14525 §5.3 idea:
compare outcomes ACROSS routes to tell a bypassable bot-wall from a hard wall):
  * routes disagree (different statuses/verdicts) -> "bot_detection" (bypassable)
  * uniform auth_required / not_found -> "infra_or_auth" (stealth won't help)
  * uniform challenge/blocked across every route -> "bot_detection" (browser may help)
  * insufficient signal -> "" (no over-claim)
  * FetchResult exposes block_class via to_dict; success carries "".

Run:  python3 engine/tests/test_t6_differential.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from engine.fetch_chain import Attempt, FetchResult, _classify_block  # noqa: E402
from engine.validators import Verdict  # noqa: E402


def _att(verdict, status, executor="curl_cffi", phase="grid"):
    return Attempt(phase=phase, executor=executor, url="https://x.test/",
                   url_transform="original", impersonate="chrome", referer="none",
                   status=status, verdict=verdict)


def t_disagreeing_routes_bot_detection() -> None:
    trace = [_att(Verdict.CHALLENGE.value, 403), _att(Verdict.BLOCKED.value, 429),
             _att(Verdict.SUSPECT_OK.value, 200)]
    assert _classify_block(trace) == "bot_detection", _classify_block(trace)
    print("  ✓ routes disagree -> bot_detection (bypassable)")


def t_uniform_auth_infra() -> None:
    trace = [_att(Verdict.AUTH_REQUIRED.value, 401), _att(Verdict.AUTH_REQUIRED.value, 401)]
    assert _classify_block(trace) == "infra_or_auth", _classify_block(trace)
    print("  ✓ uniform auth_required -> infra_or_auth (not stealth-bypassable)")


def t_uniform_notfound_infra() -> None:
    trace = [_att(Verdict.NOT_FOUND.value, 404), _att(Verdict.NOT_FOUND.value, 404)]
    assert _classify_block(trace) == "infra_or_auth", _classify_block(trace)
    print("  ✓ uniform not_found -> infra_or_auth")


def t_uniform_challenge_bot_detection() -> None:
    trace = [_att(Verdict.CHALLENGE.value, 403), _att(Verdict.CHALLENGE.value, 403),
             _att(Verdict.CHALLENGE.value, 403)]
    assert _classify_block(trace) == "bot_detection", _classify_block(trace)
    print("  ✓ uniform challenge -> bot_detection (browser escalation may help)")


def t_insufficient_signal_empty() -> None:
    # only diagnostic / errored attempts with no status and unknown verdict
    trace = [_att(Verdict.UNKNOWN.value, 0, executor="profile_loader", phase="probe")]
    assert _classify_block(trace) == "", repr(_classify_block(trace))
    print("  ✓ insufficient signal -> '' (no over-claim)")


def t_success_carries_empty_block_class() -> None:
    r = FetchResult(ok=True, content="x")
    assert r.block_class == "" and r.to_dict()["block_class"] == ""
    print("  ✓ success result -> block_class '' exposed in to_dict")


def t_fetchresult_exposes_block_class() -> None:
    r = FetchResult(ok=False, content="", block_class="bot_detection")
    d = r.to_dict()
    assert d["block_class"] == "bot_detection"
    print("  ✓ FetchResult.to_dict exposes block_class")


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
