"""Capability-routed X discovery: free routes plus optional xAI, then Phase-0 validation."""
from __future__ import annotations

import importlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import quote_plus, unquote

from .phase0 import route
from .x_search_types import XPost, XSearchResult

_io = importlib.import_module(".x_search_io", __package__)
_http_get = _io.http_get
_http_post_json = _io.http_post_json
_resolve_xai_credential = _io.resolve_xai_credential


_X_STATUS_RE = re.compile(  # NOTE-BIAS-OK — sanctioned X Phase-0 discovery adapter
    r"https?://(?:www\.)?(?:x|twitter)\.com/([^/?#]+)/status(?:es)?/(\d+)",
    re.IGNORECASE,
)
_BRAVE_SEARCH_URL = "https://search.brave.com/search?q="  # NOTE-BIAS-OK
_YAHOO_SEARCH_URL = "https://search.yahoo.com/search?p="  # NOTE-BIAS-OK
_XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"  # NOTE-BIAS-OK
_XAI_MODEL = "grok-4.20-0309-non-reasoning"
_SEARCH_QUERIES = ('site:x.com "{query}"', '"{query}" x.com/status')  # NOTE-BIAS-OK


class XSearchError(RuntimeError):
    pass


def search_x(
    query: str,
    *,
    limit: int = 10,
    timeout: int = 20,
    use_xai: bool | None = None,
) -> XSearchResult:
    """Discover X posts through every available route and validate the originals."""
    query = query.strip()
    if not query:
        raise XSearchError("query must not be blank")
    if use_xai is None:
        use_xai = os.environ.get("INSANE_SEARCH_XAI", "auto").lower() not in {"0", "false", "off", "no"}
    credential = _resolve_xai_credential() if use_xai else None
    discovered: list[tuple[str, list[str]]] = []
    discovery_errors: dict[str, str] = {}
    degraded_reason = ""

    with ThreadPoolExecutor(max_workers=3) as pool:
        free_futures = {
            "brave": pool.submit(_discover_with_brave, query, limit, timeout),
            "yahoo": pool.submit(_discover_with_yahoo, query, limit, timeout),
        }
        xai_future = (
            pool.submit(_discover_with_xai, query, limit, timeout, credential)
            if credential
            else None
        )

        free_failures = 0
        for source, future in free_futures.items():
            try:
                free_urls = future.result()
            except XSearchError as error:
                free_urls = []
                free_failures += 1
                discovery_errors[source] = str(error)
            if free_urls:
                discovered.append((source, free_urls))

        if not use_xai:
            degraded_reason = "xai_disabled"
        elif xai_future is None:
            degraded_reason = "xai_unavailable"
        else:
            try:
                xai_urls = xai_future.result()
            except XSearchError as error:
                xai_urls = []
                degraded_reason = "xai_error"
                discovery_errors["xai"] = str(error)
            if xai_urls:
                discovered.insert(0, ("xai", xai_urls))
        if free_failures == len(free_futures) and xai_future is not None and degraded_reason != "xai_error":
            degraded_reason = "free_error"

    source_by_url: dict[str, list[str]] = {}
    for source, urls in discovered:
        for url in urls:
            if url not in source_by_url:
                source_by_url[url] = []
            if source not in source_by_url[url]:
                source_by_url[url].append(source)

    ordered_urls = _interleave_discoveries(discovered)

    posts = _validate_urls(ordered_urls[:limit], timeout)
    enriched = tuple(
        XPost(
            url=post.url,
            tweet_id=post.tweet_id,
            author_name=post.author_name,
            author_handle=post.author_handle,
            text=post.text,
            created_at=post.created_at,
            likes=post.likes,
            replies=post.replies,
            discovered_by=tuple(source_by_url.get(post.url, post.discovered_by)),
        )
        for post in posts
    )
    validated_urls = {post.url for post in enriched}
    rejected = tuple(url for url in ordered_urls[:limit] if url not in validated_urls)
    sources = tuple(source for source, urls in discovered if urls)
    return XSearchResult(
        ok=bool(enriched),
        query=query,
        posts=enriched,
        discovery_sources=sources,
        degraded_reason=degraded_reason,
        discovery_errors=discovery_errors,
        rejected_urls=rejected,
    )


def _discover_with_brave(query: str, limit: int, timeout: int) -> list[str]:
    return _discover_with_search_engine(_BRAVE_SEARCH_URL, query, limit, timeout, "Brave")


def _discover_with_yahoo(query: str, limit: int, timeout: int) -> list[str]:
    return _discover_with_search_engine(_YAHOO_SEARCH_URL, query, limit, timeout, "Yahoo")


def _discover_with_search_engine(
    base_url: str,
    query: str,
    limit: int,
    timeout: int,
    provider_name: str,
) -> list[str]:
    urls: list[str] = []
    successful_responses = 0
    for template in _SEARCH_QUERIES:
        response = _http_get(base_url + quote_plus(template.format(query=query)), timeout)
        if response.status_code != 200:
            continue
        successful_responses += 1
        for url in _extract_status_urls(response.text):
            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                return urls
    if successful_responses == 0:
        raise XSearchError(f"{provider_name} X discovery failed")
    return urls


def _discover_with_xai(query: str, limit: int, timeout: int, credential: str) -> list[str]:
    payload = {
        "model": _XAI_MODEL,
        "input": [{
            "role": "user",
            "content": f"Find up to {limit} recent public X posts about: {query}. Return citations.",
        }],
        "tools": [{"type": "x_search"}],
    }
    response = _http_post_json(_XAI_RESPONSES_URL, payload, credential, timeout)
    if response.status_code != 200:
        raise XSearchError(f"xAI X Search returned HTTP {response.status_code}")
    try:
        data = response.json()
    except (json.JSONDecodeError, TypeError) as error:
        raise XSearchError("xAI X Search returned invalid JSON") from error
    urls: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") != "output_text":
                continue
            for annotation in content.get("annotations", []):
                canonical = _canonical_status_url(annotation.get("url", ""))
                if annotation.get("type") == "url_citation" and canonical and canonical not in urls:
                    urls.append(canonical)
                    if len(urls) >= limit:
                        return urls
    return urls


def _validate_urls(urls: list[str], timeout: int) -> list[XPost]:
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(urls))) as pool:
        candidates = list(pool.map(lambda url: _validate_url(url, timeout), urls))
    return [post for post in candidates if post is not None]


def _validate_url(url: str, timeout: int) -> XPost | None:
    result = route(url, timeout=timeout)
    if not result or not result.get("ok") or result.get("route") != "tweet-result":
        return None
    try:
        tweet = json.loads(result.get("content", ""))
    except (json.JSONDecodeError, TypeError):
        return None
    user = tweet.get("user") or {}
    return XPost(
        url=url,
        tweet_id=str(tweet.get("id_str") or url.rsplit("/", 1)[-1]),
        author_name=str(user.get("name") or ""),
        author_handle=str(user.get("screen_name") or ""),
        text=str(tweet.get("text") or ""),
        created_at=str(tweet.get("created_at") or ""),
        likes=int(tweet.get("favorite_count") or 0),
        replies=int(tweet.get("conversation_count") or 0),
        discovered_by=(),
    )


def _extract_status_urls(text: str) -> list[str]:
    urls: list[str] = []
    decoded = unquote(unescape(text).replace("\\/", "/"))
    for match in _X_STATUS_RE.finditer(decoded):
        canonical = f"https://x.com/{match.group(1)}/status/{match.group(2)}"  # NOTE-BIAS-OK
        if canonical not in urls:
            urls.append(canonical)
    return urls


def _canonical_status_url(url: str) -> str | None:
    match = _X_STATUS_RE.search(url)
    if not match:
        return None
    return f"https://x.com/{match.group(1)}/status/{match.group(2)}"  # NOTE-BIAS-OK


def _interleave_discoveries(discovered: list[tuple[str, list[str]]]) -> list[str]:
    """Round-robin independent discovery routes so one provider cannot crowd out another."""
    occurrence_count: dict[str, int] = {}
    for _, urls in discovered:
        for url in set(urls):
            occurrence_count[url] = occurrence_count.get(url, 0) + 1

    unique_by_source = [
        (source, [url for url in urls if occurrence_count.get(url) == 1])
        for source, urls in discovered
    ]
    ordered: list[str] = []
    max_length = max((len(urls) for _, urls in unique_by_source), default=0)
    for index in range(max_length):
        for _, urls in unique_by_source:
            if index < len(urls) and urls[index] not in ordered:
                ordered.append(urls[index])
    for _, urls in discovered:
        for url in urls:
            if url not in ordered:
                ordered.append(url)
    return ordered


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Discover and validate public X posts by keyword.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--free-only", action="store_true", help="Disable optional xAI X Search discovery.")
    args = parser.parse_args()
    try:
        result = search_x(
            args.query,
            limit=max(1, args.limit),
            timeout=max(1, args.timeout),
            use_xai=False if args.free_only else None,
        )
    except XSearchError as error:
        parser.error(str(error))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
