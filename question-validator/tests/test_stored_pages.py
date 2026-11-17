"""KB phase 3 — stored pages first (+ web PDFs). No network: respx guard, fake model, fake search, fake PDF reader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select

import qv.services.research as research
from qv.config import FetchConfig
from qv.db.models import Document, Fetch, Passage, QuestionDocument, RunQuestion
from qv.db.session import Database
from qv.kb.index import KnowledgeIndex, index_path, update_index
from qv.library import Library, LibraryConfig
from qv.providers.fetch import Fetcher
from qv.providers.llm.base import RawResponse
from qv.providers.search.base import SearchHit
from qv.providers.search.router import Pool, SearchRouter
from qv.providers.usage import Limit, Metering, QuotaLedger, RateLimiter, UsageRecorder
from qv.services.datasets import import_dataset
from qv.services.research import execute_run, search_summary, start_run
from qv.sources import load_registry
from tests.test_research import CSV, FakeLLM, build, mock_web, s1a_json, s1b_json

S1A_QUERIES = [q["q"] for q in s1a_json("")["queries"]]
CHALLENGE = s1b_json(False)["challenge_queries"][0]["q"]
LEAK = "LEAK-ANSWER-MARKER"


def _index(db: Database, data_dir: Path) -> None:
    update_index(db, data_dir, registry=load_registry(), library=Library(data_dir, LibraryConfig(books=[])))


@pytest.fixture
def stored(db: Database, tmp_path: Path) -> Path:
    """Question #135 researched once in edition A (web), one of its passages carrying a marker answer that is NOT
    in the page text, then the knowledge index built; edition B has the same question, not researched yet."""
    with respx.mock:
        mock_web()
        with db.session() as s:
            import_dataset(s, CSV, dataset_name="mini", source_filename="mini.csv", profile_name="prophets-stories")
            import_dataset(s, CSV, dataset_name="other", source_filename="o.csv", profile_name="world-tour")
        execute_run(build(db, FakeLLM()), start_run(db, "mini", ["135"]))
    with db.session() as s:
        p = s.scalar(select(Passage).where(Passage.target == "need"))
        cols = {c.name: getattr(p, c.name) for c in Passage.__table__.columns if c.name not in ("id", "created_at")}
        s.add(Passage(**{**cols, "asserted_answer": LEAK, "qualifiers": LEAK}))
    _index(db, tmp_path)
    return tmp_path


def _deps(db: Database, data_dir: Path | None, llm: FakeLLM | None = None, **cfg: Any):  # noqa: ANN202
    deps = build(db, llm or FakeLLM(), **cfg)
    deps.data_dir = data_dir
    return deps


def _stats(db: Database, run_id: int) -> dict:
    with db.session() as s:
        return s.scalar(select(RunQuestion.stats_json).where(RunQuestion.run_id == run_id)) or {}


def _stored_reads(db: Database, run_id: int) -> list[tuple[QuestionDocument, Document]]:
    with db.session() as s:
        rows = s.execute(select(QuestionDocument, Document).join(Document)
                         .where(QuestionDocument.run_id == run_id)).all()
        return [(qd, d) for qd, d in rows if any(fb.get("via") == "stored" for fb in qd.found_by_json)]


class OtherNeedLLM(FakeLLM):
    """S1a with a differently worded information need (same blind queries)."""

    def generate_json(self, **kw: Any) -> RawResponse:  # noqa: D102
        if kw["ctx"].stage == "s1a":
            self.prompts.append(("s1a", kw["messages"][0].text))
            out = {**s1a_json(""), "information_need": "Which country is the mountain in?"}
            return RawResponse(text=json.dumps(out), model=kw["model"], finish_reason="STOP")
        return super().generate_json(**kw)


@respx.mock
def test_stored_pages_use_blind_queries_and_never_other_questions_passages(
        db: Database, stored: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_web()
    asked: list[str] = []
    real = research.kb_search
    monkeypatch.setattr(research, "kb_search", lambda idx, q, **kw: asked.append(q) or real(idx, q, **kw))
    llm = OtherNeedLLM()      # another need → S3 is really called (not reused from the first question's cache)
    run_id = start_run(db, "other", ["135"])
    execute_run(_deps(db, stored, llm, max_web_queries_per_question=0), run_id)

    assert asked and set(asked) == set(S1A_QUERIES) and CHALLENGE not in asked      # S1a only, never S1b
    reads = _stored_reads(db, run_id)
    kili = [(qd, d) for qd, d in reads if d.final_url == "https://enc.org/kili"]
    assert kili, "the page read for the same question in another edition is found in stored pages"
    qd, d = kili[0]
    fb = qd.found_by_json[0]
    assert fb["via"] == "stored" and fb["query"] in S1A_QUERIES and fb["doc_key"] == f"doc:{d.id}" and fb["rank"] >= 1
    assert qd.mode == "A" and qd.status == "extracted"
    # the S3 prompt for the stored page is built from the page and this question only
    s3 = [u for st, u in llm.prompts if st == "s3" and "enc.org/kili" in u]
    assert s3 and all(LEAK not in u and "Expected answer" not in u and "NOTE-MARKER" not in u for u in s3)
    with db.session() as s:
        mine = list(s.scalars(select(Passage).where(Passage.run_id == run_id)))
        assert mine and all(LEAK not in (p.asserted_answer or "") + (p.qualifiers or "") for p in mine)
    st = _stats(db, run_id)
    assert st["stored_pages"] == len(reads) <= 2 and st["stored_searches"] == len(S1A_QUERIES)
    assert search_summary(db, run_id)["stored_pages_per_question"] == st["stored_pages"]


@respx.mock
def test_pages_already_read_for_the_question_are_not_added_again(db: Database, stored: Path) -> None:
    mock_web()
    run_id = start_run(db, "mini", ["135"])                  # the question that read them in the first place
    execute_run(_deps(db, stored, max_web_queries_per_question=0), run_id)
    assert all(d.final_url != "https://enc.org/kili" for _, d in _stored_reads(db, run_id))
    assert _stats(db, run_id).get("stored_already_read", 0) >= 1


class TimeSensitiveLLM(FakeLLM):
    """S1a says the claim is a sports record (answer can change)."""

    def generate_json(self, **kw: Any) -> RawResponse:  # noqa: D102
        if kw["ctx"].stage == "s1a":
            self.prompts.append(("s1a", kw["messages"][0].text))
            out = {**s1a_json(""), "claim_type": "sports_record"}
            return RawResponse(text=json.dumps(out), model=kw["model"], finish_reason="STOP")
        return super().generate_json(**kw)


@respx.mock
@pytest.mark.parametrize("max_age, expect_stored", [(0, False), (365, True)])
def test_time_sensitive_questions_skip_old_stored_pages(db: Database, stored: Path, max_age: int,
                                                        expect_stored: bool) -> None:
    mock_web()
    run_id = start_run(db, "other", ["135"])
    execute_run(_deps(db, stored, TimeSensitiveLLM(), max_web_queries_per_question=0,
                      stored_max_age_days=max_age), run_id)
    assert bool(_stored_reads(db, run_id)) is expect_stored
    if not expect_stored:
        assert _stats(db, run_id)["stored_too_old"] >= 1


@respx.mock
def test_old_pages_are_fine_when_not_time_sensitive(db: Database, stored: Path) -> None:
    mock_web()
    run_id = start_run(db, "other", ["135"])
    execute_run(_deps(db, stored, max_web_queries_per_question=0, stored_max_age_days=0), run_id)
    assert _stored_reads(db, run_id)


@respx.mock
@pytest.mark.parametrize("switch", [False, True])
def test_skip_web_switch(db: Database, stored: Path, switch: bool) -> None:
    mock_web()
    run_id = start_run(db, "other", ["135"])
    execute_run(_deps(db, stored, stored_first_skip_web=switch, stored_skip_web_min=1), run_id)
    st = _stats(db, run_id)
    web = st.get("searches_run", 0) + st.get("searches_cached", 0)
    if switch:
        assert web == 0 and st["web_searches_skipped"] == 1 and st["stored_pages"] >= 1
    else:
        assert web > 0 and "web_searches_skipped" not in st


def test_skip_web_is_off_by_default() -> None:
    from qv.config import ResearchConfig, load_research_config
    assert ResearchConfig().stored_first_skip_web is False and load_research_config().stored_first_skip_web is False


@respx.mock
def test_missing_or_broken_index_never_fails_research(db: Database, tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    mock_web()
    with db.session() as s:
        import_dataset(s, CSV, dataset_name="mini", source_filename="mini.csv", profile_name="prophets-stories")
    data_dir = tmp_path / "data"
    r1 = start_run(db, "mini", ["135"])                                     # no index at all
    assert execute_run(_deps(db, data_dir), r1).done == 1
    assert _stats(db, r1)["stored_index_unavailable"] == 1
    assert not index_path(data_dir).exists()                                # research never creates it
    index_path(data_dir).parent.mkdir(parents=True)
    index_path(data_dir).write_bytes(b"this is not a sqlite file" * 100)    # broken file
    r2 = start_run(db, "mini", ["135"])
    assert execute_run(_deps(db, data_dir), r2).done == 1
    assert _stats(db, r2)["stored_index_unavailable"] == 1
    index_path(data_dir).unlink()
    _index(db, data_dir)                                                    # a good index, but search fails
    monkeypatch.setattr(research, "kb_search", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r3 = start_run(db, "mini", ["135"])
    assert execute_run(_deps(db, data_dir), r3).done == 1
    st = _stats(db, r3)
    assert st["stored_errors"] == 1 and any("boom" in e for e in st["errors"])


# --- web PDFs ---------------------------------------------------------------------------------------

GOOD = "Kilimanjaro location country: the mountain lies in northern Tanzania near the Kenyan border. " * 3
OTHER = "Annual report of the survey: budgets, staff and the list of field offices in every region. " * 3
GARBAGE = "".join(chr(0x91 + i % 10) + "ab"[i % 2] + str(i) for i in range(80))   # broken font encoding


def _fetcher(db: Database, pages: list[str] | Exception, **cfg: Any) -> tuple[Fetcher, list[int]]:
    calls: list[int] = []

    def reader(body: bytes) -> list[str]:
        calls.append(len(body))
        if isinstance(pages, Exception):
            raise pages
        return pages
    m = Metering(QuotaLedger(db, reserve_fraction=0), RateLimiter(sleep=lambda s: None), UsageRecorder(db))
    return Fetcher(db, m.recorder, m.limiter, FetchConfig(**cfg), client=httpx.Client(follow_redirects=True),
                   pdf_reader=reader), calls


def _mock_pdf(url: str) -> respx.Route:
    host = url.split("/")[2]
    respx.get(f"https://{host}/robots.txt").mock(return_value=httpx.Response(404))
    return respx.get(url).mock(return_value=httpx.Response(200, headers={"content-type": "application/pdf"},
                                                           content=b"%PDF-1.4 fake"))


@respx.mock
def test_web_pdf_is_stored_page_by_page_and_unreadable_pages_need_ocr(db: Database) -> None:
    url = "https://www.usgs.gov/files/report.pdf"
    route = _mock_pdf(url)
    f, calls = _fetcher(db, ["", "Title page", OTHER, GARBAGE, GOOD])
    res = f.fetch(url)
    assert res.ok and res.status == "ok" and len(res.page_ids) == 2 and res.document_id == res.page_ids[0]
    with db.session() as s:
        docs = [s.get(Document, i) for i in res.page_ids]
        assert [d.final_url for d in docs] == [f"{url}#page=3", f"{url}#page=5"]
        assert {d.source_kind for d in docs} == {"pdf"} and docs[1].title == "report.pdf, page 5"
        assert all(d.url == url and d.domain == "usgs.gov" for d in docs)
        assert GARBAGE not in " ".join(d.text for d in docs)
        assert s.scalar(select(Fetch.error).where(Fetch.url == url)) == "pdf: 2 of 5 pages stored, 1 need OCR"
    again = f.fetch(url)                                     # cached: same pages, not downloaded or read again
    assert again.page_ids == res.page_ids and route.call_count == 1 and len(calls) == 1


@respx.mock
def test_pdf_without_readable_text_needs_ocr_and_stores_nothing(db: Database) -> None:
    from qv.services.views import pdfs_found_on_web
    _mock_pdf("https://x.org/scan.pdf")
    _mock_pdf("https://y.org/book.pdf")
    assert _fetcher(db, [GARBAGE, GARBAGE + "x"])[0].fetch("https://x.org/scan.pdf").status == "needs_ocr"
    assert _fetcher(db, [GOOD])[0].fetch("https://y.org/book.pdf").ok
    with db.session() as s:
        assert s.scalar(select(Document).where(Document.url == "https://x.org/scan.pdf")) is None
    rows = {r["file"]: r["read"] for r in pdfs_found_on_web(db)}
    assert rows == {"scan.pdf": "needs OCR (no readable text)", "book.pdf": "1 of 1 pages stored"}


@respx.mock
def test_pdf_size_cap_and_broken_pdf(db: Database) -> None:
    _mock_pdf("https://x.org/big.pdf")
    _mock_pdf("https://x.org/bad.pdf")
    assert _fetcher(db, [GOOD], max_pdf_bytes=5)[0].fetch("https://x.org/big.pdf").status == "too_large"
    res = _fetcher(db, ValueError("bad xref"))[0].fetch("https://x.org/bad.pdf")
    assert res.status == "not_text" and res.error == "pdf: could not be read (ValueError)"


class PdfSearch:
    name = "pdfsearch"

    def search(self, query, *, max_results, ctx, objective=None):  # noqa: ANN001, ANN201
        return [SearchHit("https://www.usgs.gov/files/report.pdf", "Report", "", 1, self.name)]


@respx.mock
def test_research_reads_the_best_pdf_page_with_the_sites_trust_and_indexes_pages(db: Database,
                                                                                 tmp_path: Path) -> None:
    mock_web()
    _mock_pdf("https://www.usgs.gov/files/report.pdf")
    with db.session() as s:
        import_dataset(s, CSV, dataset_name="mini", source_filename="mini.csv", profile_name="prophets-stories")
    deps = _deps(db, None, stored_pages_per_question=0)
    deps.router = SearchRouter(db, [Pool(PdfSearch(), [Limit("day", 1000)], 1, 1000)], deps.metering)
    deps.fetcher.pdf_reader = lambda body: [OTHER, GOOD, OTHER + " more"]
    run_id = start_run(db, "mini", ["135"])
    execute_run(deps, run_id)
    with db.session() as s:
        qd, d = s.execute(select(QuestionDocument, Document).join(Document)
                          .where(Document.source_kind == "pdf")).one()
        assert d.final_url.endswith("#page=2")                                 # the page matching the query
        assert qd.registry_tier == load_registry().tier("usgs.gov") == "P"     # the site's trust
        assert qd.found_by_json[0]["pdf_page"] == 2
        pages = list(s.scalars(select(Document.id).where(Document.source_kind == "pdf")))
    assert len(pages) == 3
    _index(db, tmp_path)
    idx = KnowledgeIndex(index_path(tmp_path))
    try:
        rows = [idx.doc(f"doc:{i}") for i in pages]
        assert all(r is not None and r["is_current"] == 1 and r["tier"] == "P" for r in rows)  # pages, not versions
        assert len({r["canon_key"] for r in rows}) == 3
    finally:
        idx.close()


def test_stored_page_recall_in_benchmark(db: Database, stored: Path) -> None:
    from qv.kb.benchmark import run_benchmark, summary_lines
    report, _ = run_benchmark(db, stored, save=False, stored_n=2)
    sp = report["stored_pages"]
    assert sp["n"] == 2 and sp["questions"] >= 1 and 0 <= sp["recall"] <= sp["hit"] <= 1
    assert any(line.startswith("Stored-page recall") for line in summary_lines(report))
