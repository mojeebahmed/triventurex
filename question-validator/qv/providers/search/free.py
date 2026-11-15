"""Free sources without keys: Wikipedia search API and alislam.org site search."""

from __future__ import annotations

import html
import re
import time
from urllib.parse import quote, urljoin

import httpx

from qv.providers.search.base import SearchError, SearchHit, domain_of
from qv.providers.search.web import USER_AGENT
from qv.providers.search.web import wikimedia_user_agent
from qv.providers.usage import CallContext, UsageRecorder

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


class WikipediaSearch:
    """Full-text search over English Wikipedia (MediaWiki API, no key)."""

    name = "wikipedia"

    def __init__(self, recorder: UsageRecorder, contact: str, *, client: httpx.Client | None = None,
                 timeout_s: float = 20) -> None:
        """Wikimedia requires a user agent with contact details (QV_CONTACT); raises SearchError without one."""
        ua = wikimedia_user_agent(contact)
        if ua is None:
            raise SearchError("wikipedia: set QV_CONTACT (a URL or email) — Wikimedia requires contact details")
        self._recorder = recorder
        self._client = client or httpx.Client(timeout=timeout_s, headers={"User-Agent": ua})

    def search(self, query: str, *, max_results: int, ctx: CallContext,
               objective: str | None = None) -> list[SearchHit]:
        """Titles matching `query`, as article URLs."""
        start = time.monotonic()
        try:
            resp = self._client.get(WIKIPEDIA_API, params={
                "action": "query", "list": "search", "srsearch": query, "srlimit": max_results,
                "format": "json", "formatversion": 2})
            resp.raise_for_status()
            items = resp.json().get("query", {}).get("search", [])
        except (httpx.HTTPError, ValueError) as exc:
            self._recorder.record(provider=self.name, kind="search", status="error", ctx=ctx, error=str(exc),
                                  latency_ms=int((time.monotonic() - start) * 1000))
            raise SearchError(f"wikipedia: {exc}") from exc
        self._recorder.record(provider=self.name, kind="search", status="ok", ctx=ctx, http_status=200,
                              latency_ms=int((time.monotonic() - start) * 1000))
        return [SearchHit(url=wikipedia_url(it["title"]), title=it["title"],
                          snippet=html.unescape(re.sub(r"<[^>]+>", "", it.get("snippet", ""))), rank=i + 1,
                          provider=self.name)
                for i, it in enumerate(items)]


def wikipedia_url(title: str) -> str:
    """Canonical article URL for a title."""
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="_()',-")


class AlislamSearch:
    """alislam.org site search (WordPress `?s=`). The edition's official Ahmadiyya source."""

    name = "alislam"
    BASE = "https://www.alislam.org/"
    _RESULT = re.compile(r"<h[23][^>]*>\s*<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.S)

    def __init__(self, recorder: UsageRecorder, *, client: httpx.Client | None = None, timeout_s: float = 20) -> None:
        """No key; keep request rates low (config: search.alislam.rpm)."""
        self._recorder = recorder
        self._client = client or httpx.Client(timeout=timeout_s, headers={"User-Agent": USER_AGENT},
                                              follow_redirects=True)

    def search(self, query: str, *, max_results: int, ctx: CallContext,
               objective: str | None = None) -> list[SearchHit]:
        """Result links from the site's search page."""
        start = time.monotonic()
        try:
            resp = self._client.get(self.BASE, params={"s": query})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            self._recorder.record(provider=self.name, kind="search", status="error", ctx=ctx, error=str(exc),
                                  latency_ms=int((time.monotonic() - start) * 1000))
            raise SearchError(f"alislam: {exc}") from exc
        self._recorder.record(provider=self.name, kind="search", status="ok", ctx=ctx, http_status=200,
                              latency_ms=int((time.monotonic() - start) * 1000))
        return parse_alislam_results(resp.text, self.BASE)[:max_results]


def parse_alislam_results(page: str, base: str = AlislamSearch.BASE) -> list[SearchHit]:
    """Article links in a search results page (navigation and search links excluded)."""
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for m in AlislamSearch._RESULT.finditer(page):
        url = urljoin(base, html.unescape(m.group(1)))
        if domain_of(url) != "alislam.org" or "/search/" in url or "?s=" in url or url in seen:
            continue
        seen.add(url)
        title = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        hits.append(SearchHit(url=url, title=title, snippet="", rank=len(hits) + 1, provider="alislam"))
    return hits
