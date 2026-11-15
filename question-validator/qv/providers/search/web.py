"""Web search providers: Parallel (free MCP), Tavily and Exa (free credits)."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from qv.providers.search.base import SearchError, SearchHit, SearchQuotaError
from qv.providers.usage import CallContext, UsageRecorder

USER_AGENT = "TriventurexQuestionValidator/0.1 (personal quiz fact-checking tool)"


def wikimedia_user_agent(contact: str) -> str | None:
    """User agent for Wikimedia APIs, which require contact details; None when no contact is configured."""
    contact = contact.strip()
    return f"TriventurexQuestionValidator/0.1 ({contact}) httpx/{httpx.__version__}" if contact else None


class _Logged:
    """Shared call logging for search providers."""

    name = ""

    def __init__(self, recorder: UsageRecorder, client: httpx.Client | None, timeout_s: float) -> None:
        self._recorder = recorder
        self._client = client or httpx.Client(timeout=timeout_s, headers={"User-Agent": USER_AGENT})

    def _log(self, ctx: CallContext, status: str, start: float, *, http_status: int | None = None,
             credits: float = 0.0, cost_usd: float = 0.0, error: str | None = None) -> None:
        self._recorder.record(provider=self.name, kind="search", status=status, ctx=ctx, http_status=http_status,
                              credits=credits, cost_usd=cost_usd, error=error,
                              latency_ms=int((time.monotonic() - start) * 1000))

    def _post(self, url: str, ctx: CallContext, start: float, **kw: Any) -> httpx.Response:
        try:
            resp = self._client.post(url, **kw)
        except httpx.HTTPError as exc:
            self._log(ctx, "error", start, error=str(exc))
            raise SearchError(f"{self.name}: {exc}") from exc
        if resp.status_code in (401, 403):
            self._log(ctx, "error", start, http_status=resp.status_code, error=resp.text[:300])
            raise SearchError(f"{self.name}: not authorised (check the API key)")
        if resp.status_code in (429, 432, 433):  # Tavily uses 432/433 for plan/credit limits
            self._log(ctx, "quota", start, http_status=resp.status_code, error=resp.text[:300])
            raise SearchQuotaError(f"{self.name}: quota or rate limit reached (HTTP {resp.status_code})")
        if resp.status_code != 200:
            self._log(ctx, "error", start, http_status=resp.status_code, error=resp.text[:300])
            raise SearchError(f"{self.name}: HTTP {resp.status_code}")
        return resp


class TavilySearch(_Logged):
    """Tavily search API (basic depth = 1 credit)."""

    name = "tavily"
    URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str, recorder: UsageRecorder, *, credits_per_search: float = 1,
                 client: httpx.Client | None = None, timeout_s: float = 30) -> None:
        """Needs TAVILY_API_KEY."""
        if not api_key:
            raise SearchError("TAVILY_API_KEY is not set")
        super().__init__(recorder, client, timeout_s)
        self._key = api_key
        self.credits_per_search = credits_per_search

    def search(self, query: str, *, max_results: int, ctx: CallContext,
               objective: str | None = None) -> list[SearchHit]:
        """One basic search."""
        start = time.monotonic()
        resp = self._post(self.URL, ctx, start, headers={"Authorization": f"Bearer {self._key}"},
                          json={"query": query, "max_results": max_results, "search_depth": "basic",
                                "include_answer": False, "include_raw_content": False})
        data = resp.json()
        self._log(ctx, "ok", start, http_status=200, credits=self.credits_per_search)
        return [SearchHit(url=r["url"], title=r.get("title") or "", snippet=r.get("content") or "", rank=i + 1,
                          provider=self.name, published=r.get("published_date"))
                for i, r in enumerate(data.get("results", [])) if r.get("url")]


class ExaSearch(_Logged):
    """Exa search API; the response reports its own cost, which is what we meter."""

    name = "exa"
    URL = "https://api.exa.ai/search"

    def __init__(self, api_key: str, recorder: UsageRecorder, *, est_usd_per_search: float = 0.005,
                 client: httpx.Client | None = None, timeout_s: float = 30) -> None:
        """Needs EXA_API_KEY."""
        if not api_key:
            raise SearchError("EXA_API_KEY is not set")
        super().__init__(recorder, client, timeout_s)
        self._key = api_key
        self.est_usd_per_search = est_usd_per_search
        self.last_cost_usd = 0.0

    def search(self, query: str, *, max_results: int, ctx: CallContext,
               objective: str | None = None) -> list[SearchHit]:
        """One 'auto' search without page contents (we fetch pages ourselves)."""
        start = time.monotonic()
        resp = self._post(self.URL, ctx, start, headers={"x-api-key": self._key},
                          json={"query": query, "numResults": max_results, "type": "auto"})
        data = resp.json()
        cost = float((data.get("costDollars") or {}).get("total") or self.est_usd_per_search)
        self.last_cost_usd = cost
        self._log(ctx, "ok", start, http_status=200, credits=cost, cost_usd=0.0)
        return [SearchHit(url=r["url"], title=r.get("title") or "", snippet=r.get("text") or "", rank=i + 1,
                          provider=self.name, published=r.get("publishedDate"))
                for i, r in enumerate(data.get("results", [])) if r.get("url")]


class ParallelMCPSearch(_Logged):
    """Parallel's free hosted search MCP server (https://search.parallel.ai/mcp), anonymous.

    Spoken to with plain JSON-RPC over Streamable HTTP: initialize → tools/call web_search.
    Its excerpts are LLM-friendly summaries of pages: like any snippet they only choose
    what we fetch; evidence always comes from our own stored copy of the page.
    """

    name = "parallel"
    URL = "https://search.parallel.ai/mcp"
    PROTOCOL = "2025-06-18"

    def __init__(self, recorder: UsageRecorder, *, client: httpx.Client | None = None,
                 timeout_s: float = 60) -> None:
        """No key needed (anonymous free tier)."""
        super().__init__(recorder, client, timeout_s)
        self._session: str | None = None
        self._next_id = 1

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
             "mcp-protocol-version": self.PROTOCOL}
        if self._session:
            h["mcp-session-id"] = self._session
        return h

    def _rpc(self, method: str, params: dict, ctx: CallContext, start: float) -> dict:
        self._next_id += 1
        resp = self._post(self.URL, ctx, start, headers=self._headers(),
                          json={"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params})
        if method == "initialize":
            self._session = resp.headers.get("mcp-session-id")
        msg = _parse_mcp_response(resp)
        if "error" in msg:
            err = msg["error"]
            self._log(ctx, "error", start, http_status=200, error=json.dumps(err)[:300])
            raise SearchError(f"parallel: {err.get('message', err)}")
        return msg.get("result", {})

    def _ensure_session(self, ctx: CallContext) -> None:
        if self._session is not None:
            return
        start = time.monotonic()
        self._rpc("initialize", {"protocolVersion": self.PROTOCOL, "capabilities": {},
                                 "clientInfo": {"name": "question-validator", "version": "0.1"}}, ctx, start)
        try:
            self._client.post(self.URL, headers=self._headers(),
                              json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        except httpx.HTTPError:
            pass

    def search(self, query: str, *, max_results: int, ctx: CallContext,
               objective: str | None = None) -> list[SearchHit]:
        """web_search with one keyword query (and the information need as objective)."""
        self._ensure_session(ctx)
        start = time.monotonic()
        try:
            result = self._rpc("tools/call", {"name": "web_search", "arguments": {
                "objective": objective or query, "search_queries": [query]}}, ctx, start)
        except SearchError:
            self._session = None  # sessions can expire; start a new one next time
            raise
        if result.get("isError"):
            text = _content_text(result)
            status = "quota" if "rate" in text.lower() or "limit" in text.lower() else "error"
            self._log(ctx, status, start, http_status=200, error=text[:300])
            if status == "quota":
                raise SearchQuotaError(f"parallel: {text[:200]}")
            raise SearchError(f"parallel: {text[:200]}")
        hits = parse_parallel_results(result, self.name)[:max_results]
        self._log(ctx, "ok", start, http_status=200, credits=1)
        return hits


def _parse_mcp_response(resp: httpx.Response) -> dict:
    """A JSON-RPC message from a JSON or SSE response body."""
    if "text/event-stream" in resp.headers.get("content-type", ""):
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:])
        raise SearchError("parallel: empty event stream")
    return resp.json()


def _content_text(result: dict) -> str:
    """Joined text content of an MCP tool result."""
    return "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")


def parse_parallel_results(result: dict, provider: str = "parallel") -> list[SearchHit]:
    """Hits from a web_search tool result (structuredContent if present, else JSON in text content)."""
    data: Any = result.get("structuredContent")
    if data is None:
        text = _content_text(result)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
    items = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    hits: list[SearchHit] = []
    for i, r in enumerate(items):
        url = r.get("url") if isinstance(r, dict) else None
        if not url:
            continue
        excerpts = r.get("excerpts") or []
        snippet = " ".join(excerpts) if isinstance(excerpts, list) else str(excerpts)
        hits.append(SearchHit(url=url, title=r.get("title") or "", snippet=snippet[:1000], rank=i + 1,
                              provider=provider, published=r.get("publish_date")))
    return hits
