"""Search providers (recorded responses), router, fetcher, registry and the Qur'an source."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from qv.config import FetchConfig, load_profile
from qv.db.models import Document
from qv.db.session import Database
from qv.providers.fetch import Fetcher
from qv.providers.quran import QuranRefError, QuranSource, parse_refs, parse_verse_page
from qv.providers.search.base import SearchError, SearchHit, SearchQuotaError
from qv.providers.search.free import AlislamSearch, WikipediaSearch, parse_alislam_results
from qv.providers.search.router import Pool, SearchRouter
from qv.providers.search.web import ExaSearch, ParallelMCPSearch, TavilySearch, parse_parallel_results
from qv.providers.usage import CallContext, Limit, Metering, QuotaExhausted, QuotaLedger, RateLimiter, UsageRecorder
from qv.sources import effective_tier, is_frame_authority, load_registry

FIX = Path(__file__).parent / "fixtures"


def metering(db: Database) -> Metering:
    return Metering(QuotaLedger(db, reserve_fraction=0), RateLimiter(sleep=lambda s: None), UsageRecorder(db))


# --- providers --------------------------------------------------------------------

@respx.mock
def test_tavily(db: Database) -> None:
    route = respx.post(TavilySearch.URL).mock(return_value=httpx.Response(200, json={"results": [
        {"url": "https://a.org/x", "title": "A", "content": "snippet"}, {"title": "no url"}]}))
    hits = TavilySearch("k", UsageRecorder(db)).search("q", max_results=3, ctx=CallContext())
    assert [h.url for h in hits] == ["https://a.org/x"]
    body = json.loads(route.calls.last.request.content)
    assert body["search_depth"] == "basic" and route.calls.last.request.headers["authorization"] == "Bearer k"


@respx.mock
def test_tavily_credit_limit_is_a_quota_error(db: Database) -> None:
    respx.post(TavilySearch.URL).mock(return_value=httpx.Response(432, json={"detail": "plan limit"}))
    with pytest.raises(SearchQuotaError):
        TavilySearch("k", UsageRecorder(db)).search("q", max_results=3, ctx=CallContext())


@respx.mock
def test_exa_reports_its_cost(db: Database) -> None:
    respx.post(ExaSearch.URL).mock(return_value=httpx.Response(200, json={
        "results": [{"url": "https://b.org", "title": "B"}], "costDollars": {"total": 0.007}}))
    exa = ExaSearch("k", UsageRecorder(db))
    assert exa.search("q", max_results=3, ctx=CallContext())[0].url == "https://b.org"
    assert exa.last_cost_usd == 0.007


@respx.mock
def test_parallel_mcp_session_and_results(db: Database) -> None:
    result = {"structuredContent": {"results": [
        {"url": "https://www.britannica.com/place/Kilimanjaro", "title": "Kilimanjaro", "excerpts": ["e1", "e2"]}]},
        "content": [], "isError": False}

    def reply(request: httpx.Request) -> httpx.Response:
        msg = json.loads(request.content)
        if msg.get("method") == "initialize":
            return httpx.Response(200, headers={"mcp-session-id": "S1"},
                                  json={"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2025-06-18"}})
        if msg.get("method") == "tools/call":
            assert request.headers["mcp-session-id"] == "S1"
            assert msg["params"]["arguments"]["objective"] == "the need"
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  text="event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                                                                              "result": result}) + "\n\n")
        return httpx.Response(202)

    respx.post(ParallelMCPSearch.URL).mock(side_effect=reply)
    hits = ParallelMCPSearch(UsageRecorder(db)).search("q", max_results=5, ctx=CallContext(), objective="the need")
    assert hits[0].url.endswith("Kilimanjaro") and hits[0].snippet == "e1 e2"


def test_parse_parallel_text_fallback() -> None:
    res = {"content": [{"type": "text", "text": json.dumps({"results": [{"url": "https://x.org"}]})}]}
    assert parse_parallel_results(res)[0].url == "https://x.org"


def test_alislam_results_parser() -> None:
    page = ('<h3><a href="https://www.alislam.org/articles/lost-tribes/">The Lost &#8220;Tribes&#8221;</a></h3>'
            '<h2><a href="https://www.alislam.org/search/x/feed/">feed</a></h2>'
            '<h3><a href="https://elsewhere.com/a">Other site</a></h3>')
    hits = parse_alislam_results(page)
    assert [(h.url, h.title) for h in hits] == [("https://www.alislam.org/articles/lost-tribes/",
                                                 "The Lost “Tribes”")]


def test_wikipedia_needs_contact(db: Database) -> None:
    with pytest.raises(SearchError, match="QV_CONTACT"):
        WikipediaSearch(UsageRecorder(db), "")


# --- router -----------------------------------------------------------------------

class FakeSearch:
    def __init__(self, name: str, result: list[SearchHit] | Exception) -> None:
        self.name, self.result, self.calls = name, result, 0

    def search(self, query, *, max_results, ctx, objective=None):  # noqa: ANN001, ANN201
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


HIT = [SearchHit("https://a.org", "A", "", 1, "x")]


def test_router_cache_and_fallback(db: Database) -> None:
    first = FakeSearch("parallel", SearchQuotaError("limit"))
    second = FakeSearch("tavily", HIT)
    m = metering(db)
    router = SearchRouter(db, [Pool(first, [Limit("day", 10)], 1, 100), Pool(second, [Limit("month", 10)], 1, 100)], m)
    r1 = router.search("Query  One", max_results=5, ctx=CallContext())
    assert (r1.provider, r1.cached) == ("tavily", False)
    r2 = router.search("query one", max_results=5, ctx=CallContext())
    assert r2.cached and second.calls == 1
    assert m.ledger.remaining("tavily", "", Limit("month", 10)) == 9
    assert m.ledger.remaining("parallel", "", Limit("day", 10)) == 0  # marked exhausted


def test_router_raises_quota_exhausted(db: Database) -> None:
    m = metering(db)
    m.ledger.record("tavily", "", 10, [Limit("month", 10)])
    router = SearchRouter(db, [Pool(FakeSearch("tavily", HIT), [Limit("month", 10)], 1, 100)], m)
    with pytest.raises(QuotaExhausted):
        router.search("q", max_results=5, ctx=CallContext())


def test_router_reports_errors_that_are_not_quota(db: Database) -> None:
    router = SearchRouter(db, [Pool(FakeSearch("p", SearchError("boom")), [Limit("day", 10)], 1, 100)], metering(db))
    with pytest.raises(SearchError, match="boom"):
        router.search("q", max_results=5, ctx=CallContext())


# --- registry -----------------------------------------------------------------------

def test_registry_tiers() -> None:
    reg = load_registry()
    assert reg.tier("https://kids.britannica.com/x") == "T"
    assert reg.tier("https://www.fifa.com/a") == "P"
    assert reg.tier("https://www.nps.gov/a") == "S"
    assert reg.tier("https://unknown.example") == "T"
    assert reg.is_excluded("https://www.sporcle.com/games/x")
    assert effective_tier("P", "quiz_or_trivia") == "X"
    assert effective_tier("S", "encyclopedia_wiki") == "T"
    assert effective_tier("T", "news") == "T"  # never raised
    assert effective_tier("P", "official_record") == "P"


def test_frame_authority_from_profile() -> None:
    assert is_frame_authority("https://www.alislam.org/x", load_profile("prophets-stories"))
    assert not is_frame_authority("https://www.alislam.org/x", load_profile("world-tour"))


# --- fetcher ---------------------------------------------------------------------------

def fetcher(db: Database, **cfg) -> Fetcher:  # noqa: ANN003
    return Fetcher(db, UsageRecorder(db), RateLimiter(sleep=lambda s: None), FetchConfig(**cfg),
                   client=httpx.Client(follow_redirects=True))


@respx.mock
def test_fetch_extracts_main_text_and_caches(db: Database) -> None:
    respx.get("https://enc.org/robots.txt").mock(return_value=httpx.Response(404))
    page = respx.get("https://enc.org/kili").mock(return_value=httpx.Response(
        200, headers={"content-type": "text/html; charset=utf-8"}, text=(FIX / "article.html").read_text()))
    f = fetcher(db)
    res = f.fetch("https://enc.org/kili")
    assert res.ok
    with db.session() as s:
        doc = s.get(Document, res.document_id)
        assert "dormant volcano in Tanzania" in doc.text and "Home · About" not in doc.text
        assert doc.domain == "enc.org" and doc.extract_method.startswith("trafilatura")
    assert f.fetch("https://enc.org/kili").document_id == res.document_id
    assert page.call_count == 1


@respx.mock
def test_fetch_respects_robots(db: Database) -> None:
    respx.get("https://private.org/robots.txt").mock(return_value=httpx.Response(
        200, text="User-agent: *\nDisallow: /secret/\n"))
    res = fetcher(db).fetch("https://private.org/secret/page")
    assert res.status == "robots_disallowed" and not res.ok


@respx.mock
def test_fetch_failures_are_cached_and_typed(db: Database) -> None:
    respx.get("https://x.org/robots.txt").mock(return_value=httpx.Response(404))
    pdf = respx.get("https://x.org/a.pdf").mock(return_value=httpx.Response(
        200, headers={"content-type": "application/pdf"}, content=b"%PDF"))
    respx.get("https://x.org/big").mock(return_value=httpx.Response(
        200, headers={"content-type": "text/html"}, text="x" * 5000))
    respx.get("https://x.org/gone").mock(return_value=httpx.Response(404))
    f = fetcher(db, max_bytes=1000)
    assert f.fetch("https://x.org/a.pdf").status == "not_text"
    assert f.fetch("https://x.org/a.pdf").status == "not_text" and pdf.call_count == 1
    assert f.fetch("https://x.org/big").status == "too_large"
    assert f.fetch("https://x.org/gone").status == "error"


def test_wikipedia_skipped_without_contact(db: Database) -> None:
    res = fetcher(db).fetch("https://en.wikipedia.org/wiki/Kilimanjaro")
    assert res.status == "skipped" and "QV_CONTACT" in res.error


def test_documents_are_immutable(db: Database) -> None:
    f = fetcher(db)
    doc_id = f.store_text(url="u", final_url="https://a.org", title="t", text="some text", source_kind="web",
                          extract_method="plain")
    assert f.store_text(url="u", final_url="https://a.org", title="t", text="some text", source_kind="web",
                        extract_method="plain") == doc_id
    with pytest.raises((IntegrityError, OperationalError), match="immutable"):
        with db.session() as s:
            s.execute(text("UPDATE documents SET text = 'changed'"))


# --- Qur'an ------------------------------------------------------------------------------

@pytest.mark.parametrize("ref,scheme,expected", [
    ("2:32", None, ["2:32"]),
    ("Surah Al-Baqarah 2:32", "bismillah_is_verse_1", ["2:32"]),
    ("2:31", "common", ["2:32"]),
    ("1:1", "hafs", ["1:1"]),          # Al-Fatiha: the Bismillah is 1:1 in both schemes
    ("9:5", "common", ["9:5"]),        # At-Tawba has no Bismillah
    ("quran:2:31@hafs", None, ["2:32"]),
    ("18:66-68", None, ["18:66", "18:67", "18:68"]),
    ("2:1-50", None, ["2:1", "2:2", "2:3", "2:4", "2:5", "2:6"]),  # capped
])
def test_parse_refs(ref: str, scheme: str | None, expected: list[str]) -> None:
    assert [v.label for v in parse_refs(ref, scheme)] == expected


@pytest.mark.parametrize("ref", ["Surah Yusuf", "115:1", "2:5-3"])
def test_bad_refs(ref: str) -> None:
    with pytest.raises(QuranRefError):
        parse_refs(ref)


def test_parse_verse_page() -> None:
    heading, arabic, english = parse_verse_page((FIX / "alislam_quran_2_32.html").read_text())
    assert heading.startswith("The Holy Quran 2:32")
    assert english.startswith("And He taught Adam all the names, then He put the objects of these names")
    assert arabic.endswith("﴿۳۲﴾") and len(arabic) > 50


@respx.mock
def test_quran_source_stores_a_primary_document(db: Database) -> None:
    respx.get("https://www.alislam.org/robots.txt").mock(return_value=httpx.Response(
        200, text="User-agent: *\ndisallow: /quran/view/*\n"))
    respx.get("https://www.alislam.org/quran/app/2:32").mock(return_value=httpx.Response(
        200, text=(FIX / "alislam_quran_2_32.html").read_text()))
    results = QuranSource(fetcher(db)).lookup("2:31", "common")
    assert len(results) == 1 and results[0].ok
    with db.session() as s:
        doc = s.scalar(select(Document))
        assert doc.source_kind == "quran" and doc.ref == "2:32@bismillah_is_verse_1"
        assert "English translation by Maulawi Sher Ali: And He taught Adam all the names" in doc.text


def test_alislam_search_class_has_polite_name() -> None:
    assert AlislamSearch.name == "alislam"


def test_extraction_falls_back_when_precision_mode_keeps_only_the_header() -> None:
    from qv.providers.fetch import extract_main_text
    body = "".join(f"<p>Hazrat Mirza Nasir Ahmad was the third Khalifa; paragraph {i} of the biography "
                   "describes his life and work in some detail.</p>" for i in range(30))
    page = (f"<html><body><div class='header'><h1>Al Islam</h1><p>The Official Website of the Ahmadiyya Muslim "
            f"Community. Muslims who believe in the Messiah.</p></div><div class='x'>{body}</div></body></html>")
    text, _ = extract_main_text(page, "https://www.alislam.org/articles/x/")
    assert "third Khalifa" in text and len(text) > 2000
