"""Typed result contract for X keyword discovery."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class XPost:
    url: str
    tweet_id: str
    author_name: str
    author_handle: str
    text: str
    created_at: str
    likes: int
    replies: int
    discovered_by: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class XSearchResult:
    ok: bool
    query: str
    posts: tuple[XPost, ...]
    discovery_sources: tuple[str, ...]
    degraded_reason: str
    discovery_errors: dict[str, str]
    rejected_urls: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "query": self.query,
            "posts": [post.to_dict() for post in self.posts],
            "discovery_sources": list(self.discovery_sources),
            "degraded_reason": self.degraded_reason,
            "discovery_errors": self.discovery_errors,
            "rejected_urls": list(self.rejected_urls),
        }
