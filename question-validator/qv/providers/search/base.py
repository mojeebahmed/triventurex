"""Search interface and hit model. Snippets only choose what to fetch; they are never evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from qv.providers.usage import CallContext


class SearchError(RuntimeError):
    """A search failed (network, server, unexpected response)."""


class SearchQuotaError(SearchError):
    """The provider says its free quota or rate limit is used up."""


@dataclass(frozen=True)
class SearchHit:
    """One search result."""

    url: str
    title: str
    snippet: str
    rank: int
    provider: str
    published: str | None = None

    @property
    def domain(self) -> str:
        """Lower-case host without a leading 'www.'."""
        return domain_of(self.url)

    def to_json(self) -> dict:
        """Serialisable form for the search cache."""
        return {"url": self.url, "title": self.title, "snippet": self.snippet, "rank": self.rank,
                "provider": self.provider, "published": self.published}

    @classmethod
    def from_json(cls, d: dict) -> SearchHit:
        """Inverse of to_json."""
        return cls(url=d["url"], title=d.get("title", ""), snippet=d.get("snippet", ""), rank=d.get("rank", 0),
                   provider=d.get("provider", ""), published=d.get("published"))


def domain_of(url: str) -> str:
    """Host of a URL, lower-cased, without 'www.'."""
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


class SearchProvider(Protocol):
    """A web search provider. Implementations log their own calls."""

    name: str

    def search(self, query: str, *, max_results: int, ctx: CallContext,
               objective: str | None = None) -> list[SearchHit]:
        """Return up to `max_results` hits. Raises SearchError / SearchQuotaError."""
        ...
