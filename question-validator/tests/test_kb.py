"""Knowledge index (KNOWLEDGE_BASE_PLAN.md phase 1): chunker, URL normalisation, language guess, grouping,
incremental indexing, search, benchmark labels and metrics. No network, no PDFs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from qv.db.models import Document, Passage, QuestionDocument, QuestionRow, Run, RunQuestion, StageOutput
from qv.db.session import Database
from qv.kb import benchmark as bm
from qv.kb import text as kbtext
from qv.kb.index import KnowledgeIndex, collect_sources, compute_meta, update_index
from qv.kb.search import SearchFilters, build_match, search
from qv.library import Book, Library, LibraryConfig
from qv.services.datasets import import_dataset
from qv.sources import Registry
from tests.test_research import CSV

# --- text helpers -------------------------------------------------------------------------------

PARA = "Mount Kilimanjaro is a dormant volcano in Tanzania. It has three cones. "


def test_chunks_reproduce_the_text_and_stay_in_bounds() -> None:
    text = ("\n\n".join(PARA * 6 for _ in range(8))) + "\n" + "x" * 4000 + " tail"
    chunks = kbtext.chunk_text(text)
    assert len(chunks) > 3
    for ch in chunks:
        assert text[ch.start:ch.end] == ch.text
        assert len(ch.text) <= kbtext.CHUNK_MAX and ch.text == ch.text.strip()
    assert chunks[0].start == 0 and chunks[-1].end == len(text)
    # consecutive chunks overlap a little, never leave a gap
    for a, b in zip(chunks, chunks[1:]):
        assert b.start <= a.end and a.end - b.start <= kbtext.CHUNK_OVERLAP + 60


def test_chunks_prefer_paragraph_ends() -> None:
    text = (PARA * 13).strip() + "\n\n" + (PARA * 13).strip()           # two ≈ 950-char paragraphs
    chunks = kbtext.chunk_text(text)
    assert chunks[0].text.endswith("cones.") and text[chunks[0].end:].startswith("\n\n")


def test_short_text_is_one_chunk_and_empty_is_none() -> None:
    assert [c.text for c in kbtext.chunk_text("  short text  ")] == ["short text"]
    assert kbtext.chunk_text("   \n ") == []


@pytest.mark.parametrize("given, want", [
    ("http://WWW.Example.com/a/b/", "https://example.com/a/b"),
    ("https://example.com/a?utm_source=x&b=2&a=1#top", "https://example.com/a?a=1&b=2"),
    ("https://example.com/a?fbclid=1&gclid=2&ref=t&mc_cid=3", "https://example.com/a"),
    ("https://example.com:8080/x", "https://example.com:8080/x"),
    ("https://example.com/", "https://example.com"),
    ("library://basics/p12", "library://basics/p12"),
])
def test_normalize_url(given: str, want: str) -> None:
    assert kbtext.normalize_url(given) == want


def test_language_guess() -> None:
    assert kbtext.guess_language("The Holy Prophet was born in Mecca and he was the last of the prophets.") == "en"
    assert kbtext.guess_language("Der Verheißene Messias wurde in Qadian geboren und ist nicht ein Prophet.") == "de"
    assert kbtext.guess_language("روزہ رکھنا فرض ہے اور یہ بہت ضروری ہے") == "ur"
    assert kbtext.guess_language("بِسْمِ اللّٰهِ الرَّحْمٰنِ الرَّحِيمِ") == "ar"
    assert kbtext.guess_language("بِسْمِ اللّٰهِ الرَّحْمٰنِ In the name of Allah, the Gracious and the Merciful") \
        .endswith("+en")
    assert kbtext.guess_language("12 34 56") == "other"


# --- a small stored world -----------------------------------------------------------------------

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def add_doc(s, url: str, text: str, *, kind: str = "web", days: int = 0) -> int:  # noqa: ANN001
    import hashlib
    d = Document(url=url, final_url=url, domain=url.split("/")[2].removeprefix("www.") if "://" in url else "",
                 title=url.rsplit("/", 1)[-1], source_kind=kind, fetched_at=NOW + timedelta(days=days),
                 content_sha256=hashlib.sha256(text.encode()).hexdigest(), text=text, extract_method="t",
                 char_len=len(text))
    s.add(d)
    s.flush()
    return d.id


@pytest.fixture
def world(db: Database, tmp_path: Path) -> dict:
    """Two questions, five documents (two versions of one URL, a copy at another URL), research labels."""
    with db.session() as s:
        import_dataset(s, CSV, dataset_name="mini", source_filename="mini.csv", profile_name="world-tour")
        q135 = s.query(QuestionRow).filter_by(ext_id="135").one()
        q3 = s.query(QuestionRow).filter_by(ext_id="3").one()
        run = Run(dataset_version_id=q135.dataset_version_id, kind="research", config_json={})
        s.add(run)
        s.flush()
        docs = {
            "kili_old": add_doc(s, "https://www.example.com/kili/", "Kilimanjaro is in Tanzania. Old text.", days=0),
            "kili_new": add_doc(s, "http://example.com/kili?utm_source=x", "Kilimanjaro is in Tanzania. Updated.",
                                days=5),
            "copy": add_doc(s, "https://mirror.org/k", "Kilimanjaro is in Tanzania. Updated."),
            "adam": add_doc(s, "https://alislam.org/adam", "Allah taught Adam the names of all things."),
            "off": add_doc(s, "https://quiz.com/x", "Quiz: Kilimanjaro trivia with Kenya and Uganda answers."),
            "unread": add_doc(s, "https://other.org/everest", "Everest is in Nepal, the highest mountain."),
        }
        outs = {}
        for q, need, queries in ((q135, "country of Mount Kilimanjaro", ["Kilimanjaro country", "Kilimanjaro Tanzania"]),
                                 (q3, "what Allah taught Adam", ["Allah taught Adam names"])):
            so = StageOutput(run_id=run.id, question_id=q.id, stage="s1a", prompt_version="v1", schema_version="1",
                             input_hash=f"h{q.id}", provider="fake", model="m", valid=True,
                             output_json={"information_need": need, "queries": [{"q": x, "purpose": "core",
                                                                                   "target": "need"} for x in queries]})
            s.add(so)
            s.flush()
            outs[q.id] = so.id
            s.add(RunQuestion(run_id=run.id, question_id=q.id, status="done", stats_json={"s1a_output_id": so.id}))

        def read(q: QuestionRow, doc: str, on_subject: bool | None, passage_target: str | None) -> None:
            qd = QuestionDocument(run_id=run.id, question_id=q.id, document_id=docs[doc], mode="A",
                                  registry_tier="T", about_right_subject=on_subject,
                                  status="extracted", grounded_count=1 if passage_target else 0)
            s.add(qd)
            s.flush()
            if passage_target:
                s.add(Passage(run_id=run.id, question_id=q.id, question_document_id=qd.id, document_id=docs[doc],
                              stage_output_id=outs[q.id], mode="A", target=passage_target, quote="Kilimanjaro",
                              char_start=0, char_end=11))

        read(q135, "kili_old", True, "need")
        read(q135, "off", False, None)
        read(q3, "adam", True, "need")
        read(q3, "copy", True, "PR1")      # a passage, but not on the need → not relevant
    library = Library(tmp_path, LibraryConfig(books=[
        Book(id="basics", file="b.pdf", title="Basics", tier="P", editions=["swab-quest"], translate_for_search="en"),
        Book(id="de", file="d.pdf", title="Dieni", language="de", editions=["swab-quest"])]))
    library.index_pages("basics", ["1\nIntro page", "12\nThe first Jalsa Salana was held in Qadian in 1891."])
    library.index_pages("de", ["Die erste Jalsa Salana fand in Qadian statt. Das Fasten im Ramadan."])
    library.add_translation("de", 1, "en", "Die erste Jalsa Salana fand in Qadian statt. Das Fasten im Ramadan.",
                            "The first Jalsa Salana took place in Qadian. Fasting in Ramadan.")
    reg = Registry(version=1, domains={"alislam.org": "P", "quiz.com": "X"})
    return {"db": db, "dir": tmp_path, "docs": docs, "library": library, "registry": reg}


def build(world: dict, **kw) -> KnowledgeIndex:  # noqa: ANN003
    update_index(world["db"], world["dir"], registry=world["registry"], library=world["library"], **kw)
    return KnowledgeIndex.for_data_dir(world["dir"])


# --- index ----------------------------------------------------------------------------------------

def test_index_holds_documents_and_book_pages(world: dict) -> None:
    idx = build(world)
    st = idx.status()
    assert st["by_source"] == {"web": 6, "book": 3}
    assert st["translation_rows"] == 1
    d = idx.doc("book:basics/p2")
    assert d["tier"] == "P" and d["printed"] == "12" and d["title"].startswith("Basics, p. 12")
    assert idx.doc(f"doc:{world['docs']['adam']}")["tier"] == "P"
    assert idx.doc(f"doc:{world['docs']['off']}")["tier"] == "X"
    assert idx.doc("book:de/p1")["lang"] == "de"


def test_every_chunk_reproduces_its_stored_text(world: dict) -> None:
    idx = build(world)
    sources, _ = collect_sources(world["db"], world["library"])
    texts = {s.doc_key: s.text for s in sources}
    rows = idx.conn.execute('SELECT doc_key, start, "end", text FROM kb_chunks').fetchall()
    assert rows and all(texts[k][a:b] == t for k, a, b, t in rows)


def test_versions_and_copies_are_grouped(world: dict) -> None:
    idx = build(world)
    docs = world["docs"]
    old, new, copy = (idx.doc(f"doc:{docs[k]}") for k in ("kili_old", "kili_new", "copy"))
    assert old["norm_url"] == new["norm_url"] == "https://example.com/kili"
    assert (old["is_current"], new["is_current"], copy["is_current"]) == (0, 1, 1)
    assert old["canon_key"] == new["canon_key"] == copy["canon_key"]      # same URL, or same content
    hits = search(idx, "Kilimanjaro Tanzania")
    group = [h for h in hits if h.canon_key == new["canon_key"]]
    assert len(group) == 1 and group[0].also_at                             # one result, "also at …"
    assert all(h.is_current for h in hits)
    assert any(not h.is_current for h in search(idx, "Old text", filters=SearchFilters(include_older=True)))


def test_who_read_it(world: dict) -> None:
    idx = build(world)
    d = idx.doc(f"doc:{world['docs']['adam']}")
    assert d["editions"] == '["world-tour"]' and d["categories"] == '["Adam"]' and d["n_questions"] == 1
    assert idx.doc(f"doc:{world['docs']['unread']}")["n_questions"] == 0


def test_incremental_update(world: dict) -> None:
    db = world["db"]
    first = update_index(db, world["dir"], registry=world["registry"], library=world["library"])
    assert first.added == 9
    again = update_index(db, world["dir"], registry=world["registry"], library=world["library"])
    assert (again.added, again.rechunked, again.removed, again.meta_updated) == (0, 0, 0, 0)
    with db.session() as s:
        add_doc(s, "https://new.org/x", "A brand new page about Kilimanjaro.")
    world["library"].index_pages("basics", ["1\nIntro page changed", "12\nThe first Jalsa Salana was held in Qadian "
                                            "in 1891."])
    world["registry"].domains["other.org"] = "S"
    rep = update_index(db, world["dir"], registry=world["registry"], library=world["library"])
    assert (rep.added, rep.rechunked, rep.meta_updated) == (1, 1, 1)
    world["library"].forget("de")
    assert update_index(db, world["dir"], registry=world["registry"], library=world["library"]).removed == 1
    rebuilt = update_index(db, world["dir"], registry=world["registry"], library=world["library"], rebuild=True)
    assert rebuilt.added == 9


def test_chunker_version_change_rechunks(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    build(world)
    import qv.kb.index as kbindex
    monkeypatch.setattr(kbindex, "CHUNKER_VERSION", kbtext.CHUNKER_VERSION + 1)
    rep = update_index(world["db"], world["dir"], registry=world["registry"], library=world["library"])
    assert rep.rechunked == 9 and rep.added == 0


def test_library_documents_are_indexed_once_as_their_page(world: dict) -> None:
    with world["db"].session() as s:
        lib_doc = add_doc(s, "library://basics/p2", "12\nThe first Jalsa Salana was held in Qadian in 1891.",
                          kind="library")
        gone = add_doc(s, "library://removed-book/p1", "A page of a book no longer in the library.", kind="library")
    idx = build(world)
    assert idx.doc(f"doc:{lib_doc}") is None and idx.doc(f"doc:{gone}") is not None
    assert idx.canon_of_document()[lib_doc] == idx.doc("book:basics/p2")["canon_key"]


# --- search ---------------------------------------------------------------------------------------

def test_build_match() -> None:
    assert build_match("the first Jalsa") == '"first" OR "jalsa"'
    assert build_match('"Jalsa Salana" Qadian') == '"jalsa salana" AND ("qadian" OR "jalsa salana")'
    assert build_match("the of") is None


def test_search_finds_pages_and_filters(world: dict) -> None:
    idx = build(world)
    hits = search(idx, "first Jalsa Salana Qadian")
    assert hits[0].doc_key == "book:basics/p2"
    assert hits[0].chunks and "Jalsa Salana" in hits[0].chunks[0].text
    assert [h.doc_key for h in search(idx, "Kilimanjaro", filters=SearchFilters(tiers=["X"]))] == \
        [f"doc:{world['docs']['off']}"]
    assert all(h.source_kind == "book" for h in search(idx, "Qadian", filters=SearchFilters(source_kinds=["book"])))
    assert search(idx, "Adam", filters=SearchFilters(edition="world-tour"))[0].doc_key == \
        f"doc:{world['docs']['adam']}"
    assert search(idx, "Adam", filters=SearchFilters(edition="swab-quest")) == []
    assert search(idx, "Adam", filters=SearchFilters(category="Adam"))
    assert {h.lang for h in search(idx, "Qadian", filters=SearchFilters(languages=["de"]))} == {"de"}
    assert search(idx, '"Salana was held"')[0].doc_key == "book:basics/p2"
    assert search(idx, '"held was Salana"') == []


def test_translation_finds_the_page_but_shows_the_original(world: dict) -> None:
    idx = build(world)
    hits = search(idx, "Fasting", filters=SearchFilters(source_kinds=["book"]))
    assert [h.doc_key for h in hits] == ["book:de/p1"]
    assert hits[0].via_translation and "Fasten" in hits[0].chunks[0].text and "Fasting" not in hits[0].chunks[0].text


# --- benchmark ------------------------------------------------------------------------------------

def test_metrics_on_hand_made_rankings() -> None:
    rel = {"a", "b"}
    ranking = ["x", "a", "y", "b"]
    assert bm.recall_at(ranking, rel, 2) == 0.5 and bm.recall_at(ranking, rel, 10) == 1.0
    assert bm.mrr(ranking, rel) == 0.5 and bm.mrr(["x"], rel) == 0.0
    import math
    want = (1 / math.log2(3) + 1 / math.log2(5)) / (1 + 1 / math.log2(3))
    assert bm.ndcg_at(ranking, rel, 10) == pytest.approx(want)
    judged = {"a", "b", "y"}
    assert bm.condensed(ranking, judged) == ["a", "y", "b"]
    assert bm.judged_coverage_at(ranking, judged, 10) == 0.75
    assert bm.judged_coverage_at([], judged, 10) == 0.0
    assert bm.rrf([["a", "b"], ["b", "c"]])[0] == "b"
    lo, hi = bm.bootstrap_ci([0.0, 1.0] * 20)
    assert lo < 0.5 < hi


def test_labels_from_stored_research(world: dict) -> None:
    idx = build(world)
    qs = {q.key.split("@")[0]: q for q in bm.load_questions(world["db"], idx)}
    docs = world["docs"]
    canon = idx.canon_of_document()
    k135, k3 = qs["world-tour#135"], qs["world-tour#3"]
    assert k135.queries == ["Kilimanjaro country", "Kilimanjaro Tanzania"]
    assert k135.relevant == {canon[docs["kili_old"]]} and k135.not_relevant == {canon[docs["off"]]}
    assert k3.relevant == {canon[docs["adam"]]}
    assert k3.not_relevant == set()        # the copy is in the relevant Kilimanjaro group of q135, not q3's need …
    # … and a passage on a presupposition alone is not "relevant" for the need
    assert canon[docs["copy"]] not in k3.relevant
    extra = bm.load_questions(world["db"], idx, [(k3.key, f"doc:{docs['unread']}", "not_relevant")])
    assert canon[docs["unread"]] in {q.key: q for q in extra}[k3.key].not_relevant


def test_benchmark_report_and_decision_rule(world: dict) -> None:
    build(world).close()
    report, path = bm.run_benchmark(world["db"], world["dir"])
    assert path and path.exists() and report["questions"] == 2 and report["with_relevant"] == 2
    for sysr in report["systems"].values():
        assert set(bm.METRICS) <= set(sysr["metrics"]) and sysr["metrics"]["recall@10"]["mean"] == 1.0
    same = bm.compare(report, "bm25-need", "bm25-need")
    assert not same["better"] and same["recall@10"]["diff"] == 0.0
    assert bm.summary_lines(report)[0].startswith("2 questions")


def test_compute_meta_without_registry_or_library(world: dict) -> None:
    sources, alias = collect_sources(world["db"], None)
    meta = compute_meta(world["db"], sources, alias, None, None)
    assert {m["tier"] for m in meta.values()} == {"T"} and len(meta) == 6
