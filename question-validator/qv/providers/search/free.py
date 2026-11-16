"""Free sources without keys: Wikipedia search API, alislam.org site search, sitemap search (alhakam.org)."""

from __future__ import annotations

import html
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

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


_STOPWORDS = frozenset(
    "a an and are as at be by did do does for from had has he her his how in is it its of on or she that the "
    "their them they this to was were what when where which who whom whose why with".split())
_SITEMAP_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]+)\s*</lastmod>)?")


def slug_words(url: str) -> set[str]:
    """Lower-case words in a URL's path (`/prophets-of-allah-solomon/` → {prophets, of, allah, solomon})."""
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", urlsplit(url).path.lower())}


def query_words(query: str) -> set[str]:
    """Content words of a query (stop words and 1-letter words dropped)."""
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 1 and w not in _STOPWORDS}


def _stem(word: str) -> str:
    """Crude plural/possessive folding so "josephs" and "joseph's" match "joseph"."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def rank_by_slug(urls: list[str], query: str, max_results: int) -> list[str]:
    """URLs whose path shares the most content words with the query.

    A URL needs at least two shared words (one when the query has only one), so a lone common word
    such as "prophet" does not match thousands of articles. Ties keep sitemap order (newest first).
    """
    words = query_words(query)
    if not words:
        return []
    need = 1 if len(words) == 1 else 2
    scored = [(len(words & slug_words(u)), i, u) for i, u in enumerate(urls)]
    scored = [x for x in scored if x[0] >= need]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [u for _, _, u in scored[:max_results]]


class SitemapSearch:
    """Search a site through the words in its article URLs, read from its sitemap.

    For sites whose own search page is built in the browser (no results in the HTML), e.g. alhakam.org.
    The sitemap index is fetched at most once per `refresh_days`; a sub-sitemap is fetched again only
    when its <lastmod> changed. The URL list is cached as JSON in `cache_path`.
    """

    def __init__(self, name: str, sitemap_url: str, cache_path: Path, recorder: UsageRecorder, *,
                 include: str = "post-sitemap", refresh_days: float = 7, wait: Callable[[], object] | None = None,
                 client: httpx.Client | None = None, timeout_s: float = 20, clock: Callable[[], float] = time.time
                 ) -> None:
        """`include` picks the sub-sitemaps to read; `wait` is called before every HTTP request (politeness)."""
        self.name = name
        self._index_url = sitemap_url
        self._cache_path = cache_path
        self._recorder = recorder
        self._include = include
        self._refresh_s = refresh_days * 86400
        self._wait = wait or (lambda: None)
        self._clock = clock
        self._client = client or httpx.Client(timeout=timeout_s, headers={"User-Agent": USER_AGENT},
                                              follow_redirects=True)
        self._urls: list[str] | None = None

    def search(self, query: str, *, max_results: int, ctx: CallContext,
               objective: str | None = None) -> list[SearchHit]:
        """Article URLs whose path best matches the query's words (no title or snippet)."""
        urls = self.urls(ctx)
        return [SearchHit(url=u, title=_title_from_slug(u), snippet="", rank=i + 1, provider=self.name)
                for i, u in enumerate(rank_by_slug(urls, query, max_results))]

    def urls(self, ctx: CallContext) -> list[str]:
        """All article URLs (cached; refreshed when older than `refresh_days`)."""
        if self._urls is not None:
            return self._urls
        cache = self._read_cache()
        if cache and self._clock() - cache.get("checked_at", 0) < self._refresh_s:
            self._urls = _flatten(cache)
            return self._urls
        try:
            cache = self._refresh(cache or {}, ctx)
        except SearchError:
            if cache:          # keep working from the old list when the site is down
                self._urls = _flatten(cache)
                return self._urls
            raise
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(cache), encoding="utf-8")
        self._urls = _flatten(cache)
        return self._urls

    def _read_cache(self) -> dict | None:
        try:
            return json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _refresh(self, old: dict, ctx: CallContext) -> dict:
        index = _SITEMAP_LOC.findall(self._get(self._index_url, ctx))
        old_maps = old.get("sitemaps", {})
        maps: dict[str, dict] = {}
        for loc, lastmod in index:
            if self._include not in loc:
                continue
            prev = old_maps.get(loc)
            if prev and lastmod and prev.get("lastmod") == lastmod:
                maps[loc] = prev
                continue
            urls = [u for u, _ in _SITEMAP_LOC.findall(self._get(loc, ctx))]
            maps[loc] = {"lastmod": lastmod, "urls": urls}
        return {"checked_at": self._clock(), "sitemaps": maps}

    def _get(self, url: str, ctx: CallContext) -> str:
        self._wait()
        start = time.monotonic()
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            self._recorder.record(provider=self.name, kind="search", status="error", ctx=ctx, error=str(exc),
                                  latency_ms=int((time.monotonic() - start) * 1000))
            raise SearchError(f"{self.name}: {exc}") from exc
        self._recorder.record(provider=self.name, kind="search", status="ok", ctx=ctx, http_status=200,
                              latency_ms=int((time.monotonic() - start) * 1000))
        return resp.text


def _flatten(cache: dict) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in cache.get("sitemaps", {}).values():
        for u in m.get("urls", []):
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def _title_from_slug(url: str) -> str:
    slug = [p for p in urlsplit(url).path.split("/") if p]
    return slug[-1].replace("-", " ").capitalize() if slug else url
