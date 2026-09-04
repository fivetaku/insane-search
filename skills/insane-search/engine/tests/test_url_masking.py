#!/usr/bin/env python3
"""Offline tests for URL masking at the three output sinks.

Run manually:
    python3 engine/tests/test_url_masking.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from engine.content_safety import wrap_untrusted_content  # noqa: E402
from engine.url_masking import REDACTED, mask_url  # noqa: E402


def t_masks_sensitive_params():
    got = mask_url("https://api.example.com/v1/items?access_token=abc123&page=2")
    assert REDACTED in got, got
    assert "abc123" not in got, got
    assert "page=2" in got, got


def t_keeps_benign_lookalikes():
    got = mask_url("https://example.com/s?keyword=token&country_code=kr")
    assert REDACTED not in got, got
    assert "keyword=token" in got, got


def t_masks_userinfo():
    got = mask_url("https://user:hunter2@example.com/path")
    assert "hunter2" not in got, got
    assert "example.com/path" in got, got


def t_plain_url_untouched():
    url = "https://example.com/a/b"
    assert mask_url(url) == url


def t_unparseable_is_returned_as_is():
    # Must never raise: logging cannot change a fetch outcome.
    assert mask_url("") == ""
    assert mask_url("not a url ? @ [") == "not a url ? @ ["


def t_opaque_query_preserved():
    url = "https://example.com/cb#fragment?notapair"
    assert mask_url(url) == url


def t_source_url_header_is_masked():
    wrapped = wrap_untrusted_content(
        "hello", source_url="https://example.com/?api_key=SEKRIT&q=cats"
    )
    assert "SEKRIT" not in wrapped, wrapped
    assert "q=cats" in wrapped, wrapped


def t_observations_entry_is_masked():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["INSANE_OBSERVATIONS_DIR"] = tmp
        try:
            from engine import observations_log

            class _Att:
                verdict = "strong_ok"
                phase = "p1"
                executor = "curl"
                url_transform = "none"
                impersonate = None
                referer = "https://ref.example.com/?session=SEKRIT2"
                status = 200
                body_size = 10

            class _Res:
                trace = [_Att()]
                ok = True
                verdict = "strong_ok"
                profile_used = None
                planned_attempts = 1
                stop_reason = ""

            observations_log.log_fetch(
                "https://example.com/?token=SEKRIT1&page=3", _Res()
            )
            written = "".join(
                open(os.path.join(tmp, name), encoding="utf-8").read()
                for name in os.listdir(tmp)
            )
        finally:
            os.environ.pop("INSANE_OBSERVATIONS_DIR", None)

    assert written.strip(), "no observation written"
    entry = json.loads(written.strip().splitlines()[-1])
    assert "SEKRIT1" not in written, written
    assert "SEKRIT2" not in written, written
    assert "page=3" in entry["url"], entry
    assert entry["domain"] == "example.com", entry


def main() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("t_") or not callable(fn):
            continue
        try:
            fn()
            print(f"ok   {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
