from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "engine" / "x_search.py"
_SPEC = importlib.util.spec_from_file_location("engine.x_search", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
x_search = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = x_search
_SPEC.loader.exec_module(x_search)


@dataclass(frozen=True, slots=True)
class FakeResponse:
    status_code: int
    text: str

    def json(self) -> dict[str, object]:
        return json.loads(self.text)


def test_search_uses_free_discovery_when_xai_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: no xAI credential and one URL from the free search route.
    monkeypatch.setattr(x_search, "_resolve_xai_credential", lambda: None)
    monkeypatch.setattr(
        x_search,
        "_discover_with_brave",
        lambda _query, _limit, _timeout: ["https://x.com/example/status/123"],
    )
    monkeypatch.setattr(x_search, "_discover_with_yahoo", lambda _query, _limit, _timeout: [])
    monkeypatch.setattr(x_search, "_discover_with_keenable", lambda _query, _limit, _timeout: [])
    monkeypatch.setattr(x_search, "_validate_urls", _validated_post)

    # When: X discovery runs with its default capability routing.
    result = x_search.search_x("Claude Code")

    # Then: the free route still returns a validated post.
    assert result.ok is True
    assert [post.url for post in result.posts] == ["https://x.com/example/status/123"]
    assert result.discovery_sources == ("brave",)
    assert result.degraded_reason == "xai_unavailable"


def test_search_rejects_blank_query() -> None:
    with pytest.raises(x_search.XSearchError, match="query must not be blank"):
        x_search.search_x("   ")


def test_search_merges_xai_and_free_urls_before_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: both discovery paths return overlapping URLs.
    monkeypatch.setattr(x_search, "_resolve_xai_credential", lambda: "token")
    monkeypatch.setattr(
        x_search,
        "_discover_with_xai",
        lambda _query, _limit, _timeout, _credential: [
            "https://x.com/first/status/1",
            "https://x.com/shared/status/2",
        ],
    )
    monkeypatch.setattr(
        x_search,
        "_discover_with_brave",
        lambda _query, _limit, _timeout: [
            "https://x.com/shared/status/2",
            "https://x.com/free/status/3",
        ],
    )
    monkeypatch.setattr(x_search, "_discover_with_yahoo", lambda _query, _limit, _timeout: [])
    monkeypatch.setattr(x_search, "_discover_with_keenable", lambda _query, _limit, _timeout: [])
    captured: list[str] = []

    def validate(urls: list[str], _timeout: int) -> list[object]:
        captured.extend(urls)
        return [_validated_post(urls[0], _timeout)[0]]

    monkeypatch.setattr(x_search, "_validate_urls", validate)

    # When: discovery runs.
    result = x_search.search_x("Claude Code")

    # Then: URLs are deduplicated and interleaved across independent sources.
    assert captured == [
        "https://x.com/first/status/1",
        "https://x.com/free/status/3",
        "https://x.com/shared/status/2",
    ]
    assert result.discovery_sources == ("xai", "brave")
    assert result.degraded_reason == ""


def test_search_falls_back_when_xai_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: xAI is configured but its request fails while free discovery works.
    monkeypatch.setattr(x_search, "_resolve_xai_credential", lambda: "token")
    monkeypatch.setattr(
        x_search,
        "_discover_with_xai",
        lambda _query, _limit, _timeout, _credential: (_ for _ in ()).throw(x_search.XSearchError("xai down")),
    )
    monkeypatch.setattr(
        x_search,
        "_discover_with_brave",
        lambda _query, _limit, _timeout: ["https://x.com/example/status/123"],
    )
    monkeypatch.setattr(x_search, "_discover_with_yahoo", lambda _query, _limit, _timeout: [])
    monkeypatch.setattr(x_search, "_discover_with_keenable", lambda _query, _limit, _timeout: [])
    monkeypatch.setattr(x_search, "_validate_urls", _validated_post)

    # When: discovery runs.
    result = x_search.search_x("Claude Code")

    # Then: the free result is returned with an explicit degraded reason.
    assert result.ok is True
    assert result.discovery_sources == ("brave",)
    assert result.degraded_reason == "xai_error"
    assert result.discovery_errors == {"xai": "xai down"}


def test_search_can_force_free_only_even_when_xai_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: xAI is ready but the caller explicitly disables paid discovery.
    monkeypatch.setattr(x_search, "_resolve_xai_credential", lambda: "token")
    monkeypatch.setattr(
        x_search,
        "_discover_with_xai",
        lambda *_args: (_ for _ in ()).throw(AssertionError("xAI must not be called")),
    )
    monkeypatch.setattr(
        x_search,
        "_discover_with_brave",
        lambda _query, _limit, _timeout: ["https://x.com/example/status/123"],
    )
    monkeypatch.setattr(x_search, "_discover_with_yahoo", lambda _query, _limit, _timeout: [])
    monkeypatch.setattr(x_search, "_discover_with_keenable", lambda _query, _limit, _timeout: [])
    monkeypatch.setattr(x_search, "_validate_urls", _validated_post)

    # When: discovery runs in free-only mode.
    result = x_search.search_x("Claude Code", use_xai=False)

    # Then: only the free route runs and the policy is explicit in provenance.
    assert result.ok is True
    assert result.discovery_sources == ("brave",)
    assert result.degraded_reason == "xai_disabled"


def test_search_records_free_route_failure_when_xai_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: xAI returns a URL while free discovery is temporarily unavailable.
    monkeypatch.setattr(x_search, "_resolve_xai_credential", lambda: "token")
    monkeypatch.setattr(
        x_search,
        "_discover_with_xai",
        lambda _query, _limit, _timeout, _credential: ["https://x.com/example/status/123"],
    )
    monkeypatch.setattr(
        x_search,
        "_discover_with_brave",
        lambda _query, _limit, _timeout: (_ for _ in ()).throw(x_search.XSearchError("free down")),
    )
    monkeypatch.setattr(
        x_search,
        "_discover_with_yahoo",
        lambda _query, _limit, _timeout: (_ for _ in ()).throw(x_search.XSearchError("free down")),
    )
    monkeypatch.setattr(
        x_search,
        "_discover_with_keenable",
        lambda _query, _limit, _timeout: (_ for _ in ()).throw(x_search.XSearchError("free down")),
    )
    monkeypatch.setattr(x_search, "_validate_urls", _validated_post)

    # When: discovery runs.
    result = x_search.search_x("Claude Code")

    # Then: the result works but reports loss of independent discovery.
    assert result.ok is True
    assert result.discovery_sources == ("xai",)
    assert result.degraded_reason == "free_error"
    assert result.discovery_errors == {"brave": "free down", "yahoo": "free down", "keenable": "free down"}


def test_brave_discovery_extracts_only_status_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: Brave HTML contains duplicate status URLs and unrelated links.
    html = """
    <a href="https://x.com/example/status/123">first</a>
    <a href="https://x.com/example/status/123?ref=dup">duplicate</a>
    <a href="https://x.com/example">profile</a>
    <a href="https://example.com/not-x">other</a>
    """
    monkeypatch.setattr(x_search, "_http_get", lambda _url, _timeout: FakeResponse(200, html))

    # When: the free discovery adapter parses the page.
    urls = x_search._discover_with_brave("Claude Code", 10, 15)

    # Then: only a canonical unique status URL remains.
    assert urls == ["https://x.com/example/status/123"]


def test_yahoo_discovery_is_a_free_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: Yahoo returns an X status URL in its public HTML.
    html = '<a href="https://x.com/example/status/456">post</a>'
    monkeypatch.setattr(x_search, "_http_get", lambda _url, _timeout: FakeResponse(200, html))

    # When: Yahoo discovery runs.
    urls = x_search._discover_with_yahoo("Claude Code", 10, 15)

    # Then: the status URL is available without xAI credentials.
    assert urls == ["https://x.com/example/status/456"]


def test_keenable_discovery_reads_status_urls_from_json(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the keyless Keenable API returns matching status URLs mixed with other results.
    payload = {
        "results": [
            {"url": "https://x.com/example/status/789?lang=en", "title": "post", "snippet": "New in Claude Code"},
            {"url": "https://x.com/example/status/789", "title": "Claude Code", "snippet": "duplicate"},
            {"url": "https://x.com/other/status/790", "title": "post", "snippet": "unrelated filler"},
            {"url": "https://x.com/example", "title": "Claude Code profile", "snippet": ""},
            {"url": "https://example.com/not-x", "title": "Claude Code elsewhere", "snippet": ""},
        ],
    }
    requests: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def post(url: str, body: dict[str, object], headers: dict[str, str], _timeout: int) -> FakeResponse:
        requests.append((url, body, headers))
        return FakeResponse(200, json.dumps(payload))

    monkeypatch.setattr(x_search, "_http_post_public_json", post)

    # When: Keenable discovery runs.
    urls = x_search._discover_with_keenable("Claude Code", 10, 15)

    # Then: one canonical matching status URL; both query templates are scoped to X and sent without a key.
    assert urls == ["https://x.com/example/status/789"]
    assert [body["query"] for _, body, _ in requests] == ['site:x.com "Claude Code"', '"Claude Code" x.com/status']
    assert all(url == "https://api.keenable.ai/v1/search/public" for url, _, _ in requests)
    assert all(body["site"] == "x.com" and body["max_results"] == 20 for _, body, _ in requests)
    assert all(headers == {"X-Keenable-Title": "insane-search"} for _, _, headers in requests)


def test_keenable_discovery_turns_transport_errors_into_route_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the first Keenable request cannot connect and the second is rate limited.
    responses: list[object] = [OSError("connection refused"), FakeResponse(429, "{}")]

    def post(*_args: object) -> FakeResponse:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(x_search, "_http_post_public_json", post)

    # When / Then: the adapter raises the per-route error that search_x records.
    with pytest.raises(x_search.XSearchError, match="Keenable X discovery failed"):
        x_search._discover_with_keenable("Claude Code", 10, 15)


def test_search_appends_keenable_after_existing_free_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: each free route discovers a different URL.
    monkeypatch.delenv("INSANE_SEARCH_KEENABLE", raising=False)
    monkeypatch.setattr(x_search, "_resolve_xai_credential", lambda: None)
    monkeypatch.setattr(
        x_search,
        "_discover_with_brave",
        lambda _query, _limit, _timeout: ["https://x.com/a/status/1"],
    )
    monkeypatch.setattr(
        x_search,
        "_discover_with_yahoo",
        lambda _query, _limit, _timeout: ["https://x.com/b/status/2"],
    )
    monkeypatch.setattr(
        x_search,
        "_discover_with_keenable",
        lambda _query, _limit, _timeout: ["https://x.com/c/status/3"],
    )
    captured: list[str] = []

    def validate(urls: list[str], _timeout: int) -> list[object]:
        captured.extend(urls)
        return _validated_post(urls, _timeout)

    monkeypatch.setattr(x_search, "_validate_urls", validate)

    # When: discovery runs.
    result = x_search.search_x("Claude Code")

    # Then: Keenable is interleaved last, after Brave and Yahoo.
    assert captured == [
        "https://x.com/a/status/1",
        "https://x.com/b/status/2",
        "https://x.com/c/status/3",
    ]
    assert result.discovery_sources == ("brave", "yahoo", "keenable")


def test_search_skips_keenable_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the Keenable route is switched off by environment.
    monkeypatch.setenv("INSANE_SEARCH_KEENABLE", "off")
    monkeypatch.setattr(x_search, "_resolve_xai_credential", lambda: None)
    monkeypatch.setattr(
        x_search,
        "_discover_with_brave",
        lambda _query, _limit, _timeout: ["https://x.com/example/status/123"],
    )
    monkeypatch.setattr(x_search, "_discover_with_yahoo", lambda _query, _limit, _timeout: [])
    monkeypatch.setattr(
        x_search,
        "_discover_with_keenable",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Keenable must not be called")),
    )
    monkeypatch.setattr(x_search, "_validate_urls", _validated_post)

    # When: discovery runs.
    result = x_search.search_x("Claude Code")

    # Then: no request leaves for Keenable and the other free routes are unchanged.
    assert result.ok is True
    assert result.discovery_sources == ("brave",)
    assert "keenable" not in result.discovery_errors


def test_xai_discovery_reads_final_citations_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: reasoning contains a fake URL while the final message cites a real URL.
    payload = {
        "output": [
            {"type": "reasoning", "summary": [{"text": "https://x.com/fake/status/9"}]},
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "result",
                        "annotations": [
                            {"type": "url_citation", "url": "https://x.com/real/status/7"},
                        ],
                    },
                ],
            },
        ],
    }
    monkeypatch.setattr(
        x_search,
        "_http_post_json",
        lambda _url, _payload, _credential, _timeout: FakeResponse(200, json.dumps(payload)),
    )

    # When: xAI discovery parses the response.
    urls = x_search._discover_with_xai("Claude Code", 10, 20, "token")

    # Then: only final-message citations are accepted.
    assert urls == ["https://x.com/real/status/7"]


def _validated_post(urls: list[str] | str, _timeout: int) -> list[object]:
    url = urls[0] if isinstance(urls, list) else urls
    return [
        x_search.XPost(
            url=url,
            tweet_id=url.rsplit("/", 1)[-1],
            author_name="Example",
            author_handle="example",
            text="post text",
            created_at="2026-08-22T00:00:00.000Z",
            likes=1,
            replies=2,
            discovered_by=("test",),
        ),
    ]
