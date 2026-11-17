"""End-to-end research pipeline with a fake model, fake search and recorded pages (no network)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import func, select

from qv.config import FetchConfig, ResearchConfig
from qv.db.models import Document, Passage, QuestionDocument, Run, RunQuestion, StageOutput
from qv.db.session import Database
from qv.pipeline.stages import StageRunner
from qv.providers.fetch import Fetcher
from qv.providers.llm.base import DailyQuotaError, Message, ModelPool, RawResponse
from qv.providers.quran import QuranSource
from qv.providers.search.base import SearchHit
from qv.providers.search.router import Pool, SearchRouter
from qv.providers.usage import CallContext, Limit, Metering, QuotaLedger, RateLimiter, UsageRecorder
from qv.services.datasets import import_dataset
from qv.services.research import ResearchDeps, _plan_web_queries, execute_run, start_run
from qv.sources import load_registry
from tests.conftest import make_csv

FIX = Path(__file__).parent / "fixtures"
CSV = make_csv(
    '135,"In which country is Mount Kilimanjaro, Africa\'s highest mountain?",multi,2,Ethiopia,Tanzania,Uganda,Kenya,'
    'hard,Wonders,Natural,Africa,NOTE-MARKER the roof of Africa',
    "3,What did Allah teach Hadhrat Adam (as)?,open,The names of all things,,,,,hard,Adam,Story,Story,"
    "Surah Al-Baqarah 2:32",
)
GOOD_QUOTE = "Mount Kilimanjaro is a dormant volcano in Tanzania."
PRESUP_QUOTE = "It is the highest mountain in Africa, rising about 5,895 metres above sea level."


def s1a_json(question: str) -> dict:
    return {
        "information_need": "Which country contains the mountain?", "answer_type": "place",
        "subject_entities": ["Mount Kilimanjaro"], "claim_type": "geography_fact", "frame_class": "universal",
        "presuppositions": [{"id": "PR1", "text": "Kilimanjaro is Africa's highest mountain.",
                             "claim_type": "measurement_or_superlative", "frame_class": "universal", "material": True}],
        "time_sensitivity": {"is_time_sensitive": False, "as_of_in_question": None, "reason": "fixed"},
        "conventions": [], "interpretations": [],
        "superlative": {"is_superlative": False, "dimension": None, "competitor_check_needed": False},
        "queries": [{"q": "Kilimanjaro location country", "purpose": "core", "target": "need"},
                    {"q": "highest mountain in Africa", "purpose": "presupposition", "target": "PR1"},
                    {"q": "Kilimanjaro facts", "purpose": "core", "target": "need"}],
        "direct_lookups": [], "researchable": True, "researchable_note": None}


def s1b_json(note_ref: bool) -> dict:
    return {"key_claim": "k", "key_components": [{"id": "K1", "text": "t", "value": "v"}],
            "answer_equivalents": [],
            "note_claims": ([{"id": "N1", "text": "2:32 says Allah taught Adam the names", "kind": "scripture_reference",
                              "reference": "2:32", "scheme": "bismillah_is_verse_1"}] if note_ref else []),
            "direct_lookups": ([{"for_claim": "N1", "source": "quran", "ref": "2:32", "scheme": None},
                                {"for_claim": "N1", "source": "quran", "ref": "7:11", "scheme": None}]
                               if note_ref else []),
            "challenge_queries": [{"q": "Kilimanjaro Kenya or Tanzania", "angle": "commonly_confused"}],
            "note_queries": []}


def page(kind: str = "reference_work", right: bool = True) -> dict:
    return {"page_kind": kind, "about_right_subject": right, "publisher": None, "author": None,
            "publication_date": None, "concerns": []}


def passage(quote: str, target: str = "need", answer: str | None = None, option: str | None = None,
            stance: str | None = None) -> dict:
    return {"quote": quote, "target": target, "asserted_answer": answer, "matches_option": option, "stance": stance,
            "qualifiers": None, "as_of": None, "attributed_origin": None, "is_primary_for_claim": False}


class FakeLLM:
    """Answers by stage; records every prompt; can run out of quota after N calls."""

    name = "fake"

    def __init__(self, budget: int | None = None) -> None:
        self.prompts: list[tuple[str, str]] = []
        self.budget = budget

    def generate_json(self, *, model: str, system: str, messages: Sequence[Message], schema: dict[str, Any],
                      ctx: CallContext) -> RawResponse:
        if self.budget is not None:
            if self.budget <= 0:
                raise DailyQuotaError("fake daily quota used up")
            self.budget -= 1
        user = messages[0].text
        self.prompts.append((ctx.stage, user))
        if ctx.stage == "s1a":
            out = s1a_json(user)
        elif ctx.stage == "s1b":
            out = s1b_json("2:32" in user)
        elif "enc.org/kili" in user:
            out = {"page": page(), "no_relevant_content_reason": None, "passages": [
                passage(GOOD_QUOTE, answer="Tanzania", option="B"),
                passage(PRESUP_QUOTE, target="PR1", stance="supports"),
                passage("This sentence is not in the document at all.", answer="Kenya", option="D"),
                passage(GOOD_QUOTE, target="PR9", stance="supports")]}  # unknown target → dropped
        elif "news.org" in user:
            out = {"page": page("news", right=False), "no_relevant_content_reason": None,
                   "passages": [passage("Kilimanjaro is a famous brand of coffee beans sold worldwide.")]}
        elif "library://" in user:
            out = {"page": page("educational"), "no_relevant_content_reason": None, "passages": [
                passage("Kilimanjaro stands in Tanzania.", answer="Tanzania", option="B")]}
        elif "quran/app" in user:
            out = {"page": page("primary_text"), "no_relevant_content_reason": None, "passages": [
                passage("And He taught Adam all the names", target="N1", stance="supports")]}
        else:
            out = {"page": page(), "passages": [], "no_relevant_content_reason": "nothing relevant"}
        return RawResponse(text=json.dumps(out), model=model, finish_reason="STOP")


class FakeSearch:
    name = "fakesearch"

    def search(self, query, *, max_results, ctx, objective=None):  # noqa: ANN001, ANN201
        return [SearchHit("https://www.sporcle.com/games/kili", "quiz", "", 1, self.name),
                SearchHit("https://enc.org/kili", "Kilimanjaro", "", 2, self.name),
                SearchHit("https://news.org/coffee", "Coffee", "", 3, self.name)]


def build(db: Database, llm: FakeLLM, now: datetime | None = None, **cfg: Any) -> ResearchDeps:
    ledger = QuotaLedger(db, reserve_fraction=0, clock=(lambda: now) if now else None)
    m = Metering(ledger, RateLimiter(sleep=lambda s: None), UsageRecorder(db))
    pools = {st: ModelPool.single(llm, ["m1"], {"m1": [Limit("day", 1000)]}, {"m1": 1000}, m) for st in ("s1a", "s1b", "s3")}
    fetcher = Fetcher(db, m.recorder, m.limiter, FetchConfig(), client=httpx.Client(follow_redirects=True))
    return ResearchDeps(db=db, runner=StageRunner(db, pools),
                        router=SearchRouter(db, [Pool(FakeSearch(), [Limit("day", 1000)], 1, 1000)], m),
                        fetcher=fetcher, quran=QuranSource(fetcher), registry=load_registry(),
                        cfg=ResearchConfig(**{"wikipedia_results": 0, "alislam_search_results": 0, **cfg}),
                        metering=m)


def mock_web() -> dict[str, respx.Route]:
    for host in ("enc.org", "news.org", "www.sporcle.com", "www.alislam.org"):
        respx.get(f"https://{host}/robots.txt").mock(return_value=httpx.Response(404))
    return {
        "kili": respx.get("https://enc.org/kili").mock(return_value=httpx.Response(
            200, headers={"content-type": "text/html"}, text=(FIX / "article.html").read_text())),
        "news": respx.get("https://news.org/coffee").mock(return_value=httpx.Response(
            200, headers={"content-type": "text/html"},
            text="<html><body><article><p>" + "Kilimanjaro is a famous brand of coffee beans sold worldwide. " * 6
                 + "</p></article></body></html>")),
        "quiz": respx.get("https://www.sporcle.com/games/kili").mock(return_value=httpx.Response(200, text="quiz")),
        "verse": respx.get("https://www.alislam.org/quran/app/2:32").mock(return_value=httpx.Response(
            200, text=(FIX / "alislam_quran_2_32.html").read_text())),
        "verse711": respx.get("https://www.alislam.org/quran/app/7:11").mock(return_value=httpx.Response(404)),
    }


@pytest.fixture
def dataset(db: Database) -> None:
    with db.session() as s:
        import_dataset(s, CSV, dataset_name="mini", source_filename="mini.csv", profile_name="prophets-stories")


@respx.mock
def test_pipeline_stores_only_grounded_evidence(db: Database, dataset: None) -> None:
    routes = mock_web()
    llm = FakeLLM()
    run_id = start_run(db, "mini", ["135"])
    report = execute_run(build(db, llm), run_id)
    assert (report.done, report.failed, report.pending) == (1, 0, 0)

    with db.session() as s:
        passages = list(s.scalars(select(Passage)))
        assert passages, "expected grounded passages"
        for p in passages:  # every stored quote is exactly the stored text at its offsets
            assert s.get(Document, p.document_id).text[p.char_start:p.char_end] == p.quote
        targets = sorted((p.target, p.asserted_answer or p.stance) for p in passages)
        assert targets == [("PR1", "supports"), ("need", "Tanzania")]
        kili = s.scalar(select(QuestionDocument).join(Document).where(Document.final_url == "https://enc.org/kili"))
        assert (kili.status, kili.grounded_count, kili.dropped_count) == ("extracted", 2, 2)
        news = s.scalar(select(QuestionDocument).join(Document).where(Document.final_url == "https://news.org/coffee"))
        assert news.status == "excluded" and news.grounded_count == 0  # about a different subject
        assert s.get(Run, run_id).status == "done"
    assert routes["quiz"].call_count == 0  # tier-X site never fetched


@respx.mock
def test_blind_stages_never_see_the_key_or_note(db: Database, dataset: None) -> None:
    mock_web()
    llm = FakeLLM()
    execute_run(build(db, llm), start_run(db, "mini", ["135"]))
    blind = [u for st, u in llm.prompts if st in ("s1a", "s3")]
    assert blind and all("Expected answer" not in u and "NOTE-MARKER" not in u for u in blind)
    s1b = [u for st, u in llm.prompts if st == "s1b"]
    assert "Expected answer: B. Tanzania" in s1b[0] and "NOTE-MARKER" in s1b[0]


@respx.mock
def test_note_reference_is_looked_up_and_read_in_mode_b(db: Database, dataset: None) -> None:
    routes = mock_web()
    execute_run(build(db, FakeLLM()), start_run(db, "mini", ["3"]))
    assert routes["verse"].call_count == 1
    assert routes["verse711"].call_count == 0  # 7:11 is not in the note → lookup dropped
    with db.session() as s:
        p = s.scalar(select(Passage).where(Passage.mode == "B"))
        assert (p.target, p.stance, p.quote) == ("N1", "supports", "And He taught Adam all the names")
        qd = s.get(QuestionDocument, p.question_document_id)
        assert qd.registry_tier == "P" and qd.frame_authority


@respx.mock
def test_run_stops_on_quota_and_resumes_without_repeating_work(db: Database, dataset: None) -> None:
    mock_web()
    run_id = start_run(db, "mini", ["135", "3"])
    today = datetime.now(UTC)
    llm = FakeLLM(budget=3)  # s1a + s1b + one s3 call, then the free quota is gone
    report = execute_run(build(db, llm, today), run_id)
    assert report.stopped_reason and report.done == 0 and report.pending == 2
    with db.session() as s:
        assert s.get(Run, run_id).status == "stopped"
        assert s.scalar(select(func.count()).select_from(StageOutput).where(StageOutput.stage == "s1a")) == 1

    same_day = execute_run(build(db, FakeLLM(), today), run_id)
    assert same_day.stopped_reason and same_day.done == 0  # quota marked used up for the rest of the day

    llm2 = FakeLLM()
    report = execute_run(build(db, llm2, today + timedelta(days=1)), run_id)
    assert (report.done, report.pending) == (2, 0)
    stages = [st for st, _ in llm2.prompts]
    assert stages.count("s1a") == 1  # question 135's S1a reused, only question 3 needed one
    with db.session() as s:
        quotes = [(p.question_id, p.document_id, p.char_start, p.target) for p in s.scalars(select(Passage))]
        assert len(quotes) == len(set(quotes))  # no duplicates after resume
        statuses = set(s.scalars(select(RunQuestion.status).where(RunQuestion.run_id == run_id)))
        assert statuses == {"done"}


@respx.mock
def test_second_run_reuses_stage_outputs_and_searches(db: Database, dataset: None) -> None:
    mock_web()
    execute_run(build(db, FakeLLM()), start_run(db, "mini", ["135"]))
    llm = FakeLLM()
    report = execute_run(build(db, llm), start_run(db, "mini", ["135"]))
    assert llm.prompts == []  # everything came from stored outputs
    assert report.questions[0]["searches_cached"] > 0 and "searches_run" not in report.questions[0]


def test_query_plan_order_and_budget() -> None:
    from qv.domain.stages import ClaimFormulation, Decomposition
    s1a = Decomposition.model_validate(s1a_json(""))
    s1b = ClaimFormulation.model_validate({**s1b_json(True), "note_queries": [{"q": "note q", "for_claim": "N1"}]})
    plan = _plan_web_queries(s1a, s1b, 4)
    assert [p[0] for p in plan] == ["Kilimanjaro location country", "highest mountain in Africa",
                                    "Kilimanjaro Kenya or Tanzania", "note q"]
    assert plan[0][3] == "Which country contains the mountain?"  # blind queries carry the blind need
    assert plan[2][3] is None and plan[3][2] == "B"
    assert len(_plan_web_queries(s1a, s1b, 2)) == 2


def test_start_run_rejects_unknown_ids(db: Database, dataset: None) -> None:
    with pytest.raises(ValueError, match="999"):
        start_run(db, "mini", ["999"])


@respx.mock
def test_views_and_cli_read_the_results(db: Database, dataset: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from qv.cli import app
    from qv.services import views
    mock_web()
    run_id = start_run(db, "mini", ["135"])
    execute_run(build(db, FakeLLM()), run_id)
    assert views.runs_overview(db)[0]["done"] == 1
    qrow = views.run_questions(db, run_id)[0]
    detail = views.question_detail(db, run_id, qrow["_qid"])
    assert detail["stages"]["s1a"]["output"]["information_need"]
    doc = next(d for d in detail["documents"] if d["url"] == "https://enc.org/kili")
    assert {p["quote"] for p in doc["passages"]} == {GOOD_QUOTE, PRESUP_QUOTE}
    assert any(u["provider"] == "fetch" and u["status"] == "ok" for u in views.usage_summary(db))
    assert views.datasets_overview(db)[0]["dataset"] == "mini"

    monkeypatch.setenv("QV_DB_URL", db.url)
    runner = CliRunner()
    res = runner.invoke(app, ["evidence", str(run_id), "135"])
    assert res.exit_code == 0, res.output
    assert GOOD_QUOTE in res.output and "need: Which country contains the mountain?" in res.output
    assert "gemini-3.5-flash-lite" in runner.invoke(app, ["quota"]).output
    assert f"run {run_id}" in runner.invoke(app, ["runs"]).output


@respx.mock
def test_library_pages_are_read_as_frame_authority_evidence(db: Database, dataset: None, tmp_path: Path) -> None:
    from qv.library import Book, Library, LibraryConfig
    mock_web()
    lib = Library(tmp_path, LibraryConfig(books=[Book(id="basics", file="b.pdf", title="Basics", publisher="alislam.org",
                                                      editions=["prophets-stories"])]))
    lib.index_pages("basics", ["12\nNothing here.", "13\nKilimanjaro stands in Tanzania."])
    deps = build(db, FakeLLM())
    deps.library = lib
    execute_run(deps, start_run(db, "mini", ["135"]))
    with db.session() as s:
        doc = s.scalar(select(Document).where(Document.source_kind == "library"))
        assert doc.final_url == "library://basics/p2" and doc.title == "Basics, p. 13 [PDF page 2]"
        qd = s.scalar(select(QuestionDocument).where(QuestionDocument.document_id == doc.id))
        assert qd.found_by_json[0]["via"] == "library"
        assert (qd.registry_tier, qd.effective_tier, qd.frame_authority) == ("S", "S", True)  # not capped to T
        assert s.scalar(select(Passage).where(Passage.question_document_id == qd.id)).quote == \
            "Kilimanjaro stands in Tanzania."


@respx.mock
def test_library_is_not_used_for_other_editions(db: Database, tmp_path: Path) -> None:
    from qv.library import Book, Library, LibraryConfig
    mock_web()
    with db.session() as s:
        import_dataset(s, CSV, dataset_name="wt", source_filename="wt.csv", profile_name="world-tour")
    lib = Library(tmp_path, LibraryConfig(books=[Book(id="basics", file="b.pdf", title="Basics",
                                                      editions=["prophets-stories"])]))
    lib.index_pages("basics", ["Kilimanjaro stands in Tanzania."])
    deps = build(db, FakeLLM())
    deps.library = lib
    execute_run(deps, start_run(db, "wt", ["135"]))
    with db.session() as s:
        assert s.scalar(select(Document).where(Document.source_kind == "library")) is None


class RetryLLM(FakeLLM):
    """S3 copies one quote wrongly the first time and correctly when told which quote was not verbatim."""

    def generate_json(self, *, model: str, system: str, messages: Sequence[Message], schema: dict[str, Any],
                      ctx: CallContext) -> RawResponse:
        user = messages[0].text
        if ctx.stage == "s3" and "enc.org/kili" in user:
            self.prompts.append((ctx.stage, user))
            fixed = "NOT word for word" in user
            border = ("The mountain lies near the border with Kenya" if fixed
                      else "The mountain lies close to the border of Kenya")  # paraphrased: not in the document
            out = {"page": page(), "no_relevant_content_reason": None, "passages": [
                passage(GOOD_QUOTE, answer="Tanzania", option="B"), passage(border, stance="qualifies")]
                + ([] if fixed else [passage(PRESUP_QUOTE, target="PR1", stance="supports")])}
            return RawResponse(text=json.dumps(out), model=model, finish_reason="STOP")
        return super().generate_json(model=model, system=system, messages=messages, schema=schema, ctx=ctx)


@respx.mock
def test_s3_is_asked_again_when_a_quote_is_dropped_and_both_answers_count(db: Database, dataset: None) -> None:
    mock_web()
    llm = RetryLLM()
    run_id = start_run(db, "mini", ["135"])
    execute_run(build(db, llm), run_id)
    kili = [u for st, u in llm.prompts if st == "s3" and "enc.org/kili" in u]
    assert len(kili) == 2 and "close to the border of Kenya" in kili[1]  # the retry names the wrong quote
    assert "Expected answer" not in kili[1] and "NOTE-MARKER" not in kili[1]  # still blind
    with db.session() as s:
        qd = s.scalar(select(QuestionDocument).join(Document).where(Document.final_url == "https://enc.org/kili"))
        quotes = sorted(p.quote[:30] for p in s.scalars(select(Passage).where(Passage.question_document_id == qd.id)))
        # PR1 came only in the first answer, the border quote only in the retry: both kept, nothing dropped
        assert (qd.grounded_count, qd.dropped_count) == (3, 0)
        assert any(q.startswith("The mountain lies near") for q in quotes)
        stats = s.scalar(select(RunQuestion.stats_json).where(RunQuestion.run_id == run_id))
        assert stats["s3_retries"] == 1 and stats["s3_quotes_recovered"] == 1
    n = len(llm.prompts)
    execute_run(build(db, llm), start_run(db, "mini", ["135"]))  # a new run: both S3 answers come from the cache
    assert not [u for st, u in llm.prompts[n:] if st == "s3" and "enc.org/kili" in u]


@respx.mock
def test_s3_retry_can_be_switched_off(db: Database, dataset: None) -> None:
    mock_web()
    llm = RetryLLM()
    execute_run(build(db, llm, s3_retry_dropped_quotes=False), start_run(db, "mini", ["135"]))
    assert len([u for st, u in llm.prompts if st == "s3" and "enc.org/kili" in u]) == 1


class VerseSearch(FakeSearch):
    """Search hits on alislam.org's Qur'an app: one verse page and one whole-surah page."""

    def search(self, query, *, max_results, ctx, objective=None):  # noqa: ANN001, ANN201
        return [SearchHit("https://www.alislam.org/quran/app/2:32", "Al-Baqarah 2:32", "", 1, self.name),
                SearchHit("https://www.alislam.org/quran/app/2", "Al-Baqarah", "", 2, self.name)]


@respx.mock
def test_quran_app_pages_found_by_search_are_read_with_the_verse_reader(db: Database, dataset: None) -> None:
    """The app is built in the browser: a plain fetch stored nothing (real runs: 'only 0 characters')."""
    routes = mock_web()
    surah = respx.get("https://www.alislam.org/quran/app/2").mock(return_value=httpx.Response(200, text="<html/>"))
    deps = build(db, FakeLLM())
    deps.router = SearchRouter(db, [Pool(VerseSearch(), [Limit("day", 1000)], 1, 1000)], deps.metering)
    run_id = start_run(db, "mini", ["3"])
    execute_run(deps, run_id)
    assert routes["verse"].call_count == 1 and surah.call_count == 0
    with db.session() as s:
        doc = s.scalar(select(Document).where(Document.final_url == "https://www.alislam.org/quran/app/2:32"))
        assert doc.source_kind == "quran" and "Sher Ali" in doc.text
        stats = s.scalar(select(RunQuestion.stats_json).where(RunQuestion.run_id == run_id))
        assert stats["quran_pages_from_search"] >= 1 and stats["quran_surah_pages_skipped"] >= 1
