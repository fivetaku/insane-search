"""U5 self-learning store — unit coverage (no network).

Run:  python3 -m engine.tests.test_u5
Covers: round-trip, win counting, failure striking + eviction at 2,
transient vs real-failure classification, TTL prune, LRU cap, key scoping,
grid priority reordering, and winning-route extraction from a trace."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone, timedelta

from engine import learning
from engine.fetch_chain import _build_plan, _winning_route, _load_profiles, FetchResult, Attempt
from engine.validators import Verdict

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = ""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"[{name}]\n  ✓ {detail or 'ok'}")
    else:
        _failed += 1
        print(f"[{name}]\n  ✗ FAIL {detail}")


def _tmp() -> str:
    fd, path = tempfile.mkstemp(suffix="_learned.json")
    os.close(fd)
    os.unlink(path)  # start empty
    return path


U = "https://example.com/some/page"
ROUTE_A = {"transform": "original", "impersonate": "chrome", "referer": "self_root", "phase": "grid"}
ROUTE_B = {"transform": "mobile_subdomain", "impersonate": "safari_ios", "referer": "none", "phase": "grid"}


# 1) round-trip + win counting
p = _tmp()
learning.record_success(U, "desktop", ROUTE_A, path=p)
check("roundtrip_lookup", learning.lookup(U, "desktop", path=p) == ROUTE_A,
      f"learned route returned: {learning.lookup(U, 'desktop', path=p)}")
learning.record_success(U, "desktop", ROUTE_A, path=p)
data = learning.load(p)
check("wins_increment_same_route", data[learning.key_for(U, "desktop")]["wins"] == 2,
      f"wins={data[learning.key_for(U, 'desktop')]['wins']}")
learning.record_success(U, "desktop", ROUTE_B, path=p)
data = learning.load(p)
check("wins_reset_on_new_route", data[learning.key_for(U, "desktop")]["wins"] == 1
      and learning.lookup(U, "desktop", path=p) == ROUTE_B, "new route replaces, wins=1")

# 2) transient failure does NOT strike; refreshes last_used
p = _tmp()
learning.record_success(U, "desktop", ROUTE_A, path=p)
learning.record_failure(U, "desktop", penalize=False, path=p)
data = learning.load(p)
k = learning.key_for(U, "desktop")
check("transient_no_strike", k in data and data[k]["consecutive_fails"] == 0,
      "entry kept, consecutive_fails stays 0 on transient")

# 3) real failure strikes; evicts after 2
p = _tmp()
learning.record_success(U, "desktop", ROUTE_A, path=p)
learning.record_failure(U, "desktop", penalize=True, path=p)
data = learning.load(p)
check("real_failure_strike_1", data[k]["consecutive_fails"] == 1, "1st strike kept, fails=1")
learning.record_failure(U, "desktop", penalize=True, path=p)
check("evict_after_2_strikes", learning.lookup(U, "desktop", path=p) is None,
      "evicted after 2nd consecutive real failure")

# 3b) success resets the strike counter
p = _tmp()
learning.record_success(U, "desktop", ROUTE_A, path=p)
learning.record_failure(U, "desktop", penalize=True, path=p)
learning.record_success(U, "desktop", ROUTE_A, path=p)
data = learning.load(p)
check("success_resets_strikes", data[k]["consecutive_fails"] == 0, "strike reset to 0 after a win")

# 4) is_real_failure classification
real = all(learning.is_real_failure(r) for r in ("exhausted", "challenge", "blocked"))
nonreal = not any(learning.is_real_failure(r) for r in
                  ("rate_limited", "unknown", "budget", "auth_required", "not_found", "success", ""))
check("classify_real_failures", real and nonreal,
      "exhausted/challenge/blocked strike; 429/unknown/budget/auth/404 do not")

# 5) TTL prune on load (monkeypatch a small TTL)
p = _tmp()
old_ttl = learning.TTL_DAYS
learning.TTL_DAYS = 30
stale_ts = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
fresh_ts = datetime.now(timezone.utc).isoformat()
learning.save({
    "stale.com::desktop": {"route": ROUTE_A, "wins": 1, "consecutive_fails": 0,
                           "last_used": stale_ts, "last_success": stale_ts},
    "fresh.com::desktop": {"route": ROUTE_B, "wins": 1, "consecutive_fails": 0,
                           "last_used": fresh_ts, "last_success": fresh_ts},
}, path=p)
data = learning.load(p)
check("ttl_prunes_stale", "stale.com::desktop" not in data and "fresh.com::desktop" in data,
      f"31-day-old dropped, fresh kept (kept={list(data)})")
learning.TTL_DAYS = old_ttl

# 6) LRU cap (monkeypatch small cap)
p = _tmp()
old_max = learning.MAX_ENTRIES
learning.MAX_ENTRIES = 5
now = datetime.now(timezone.utc)
big = {}
for i in range(12):
    ts = (now - timedelta(minutes=i)).isoformat()  # i=0 newest
    big[f"h{i}.com::desktop"] = {"route": ROUTE_A, "wins": 1, "consecutive_fails": 0,
                                 "last_used": ts, "last_success": ts}
learning.save(big, path=p)
data = learning.load(p)
kept_newest = all(f"h{i}.com::desktop" in data for i in range(5))
check("lru_cap", len(data) == 5 and kept_newest,
      f"capped to 5, kept 5 most-recent (n={len(data)})")
learning.MAX_ENTRIES = old_max

# 7) key scoping: desktop vs mobile distinct; auto == desktop
check("key_scoping",
      learning.key_for(U, "mobile") != learning.key_for(U, "desktop")
      and learning.key_for(U, "auto") == learning.key_for(U, "desktop"),
      "mobile/desktop separate; auto folds into desktop")

# 8) grid priority reordering (no network)
profiles = _load_profiles()
hits = [type("H", (), {"profile_id": "unknown_challenge", "confidence": 0.5})()]
plan = _build_plan(U, hits, profiles, "desktop", "safari", "self_root")
target = plan[min(3, len(plan) - 1)]
prio = {"transform": target.transform, "impersonate": target.impersonate, "referer": target.referer}
plan2 = _build_plan(U, hits, profiles, "desktop", "safari", "self_root", priority=prio)
check("priority_moves_to_front",
      plan2[0].transform == target.transform and plan2[0].impersonate == target.impersonate
      and plan2[0].referer == target.referer and len(plan2) == len(plan),
      "learned candidate promoted to plan[0], no items lost")

# 9) winning-route extraction from trace
r_ok = FetchResult(ok=True, trace=[
    Attempt(phase="probe", executor="curl_cffi", url=U, url_transform="original",
            impersonate="safari", referer="self_root", verdict=Verdict.CHALLENGE.value),
    Attempt(phase="grid", executor="curl_cffi", url=U, url_transform="mobile_subdomain",
            impersonate="chrome", referer="none", verdict=Verdict.STRONG_OK.value),
])
check("winning_route_from_grid",
      _winning_route(r_ok) == {"transform": "mobile_subdomain", "impersonate": "chrome",
                               "referer": "none", "phase": "grid"},
      f"extracted: {_winning_route(r_ok)}")
r_browser = FetchResult(ok=True, trace=[
    Attempt(phase="fallback", executor="playwright_real_chrome", url=U, url_transform="original",
            impersonate=None, referer="", verdict=Verdict.STRONG_OK.value),
])
check("winning_route_skips_browser", _winning_route(r_browser) is None,
      "browser-only win is not learnable (None)")

print(f"\n{_passed} passed, {_failed} failed")
import sys
sys.exit(1 if _failed else 0)
