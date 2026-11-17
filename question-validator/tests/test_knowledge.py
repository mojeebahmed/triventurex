"""Knowledge search page (KB phase 2): filters, search results, stored text, topics, relevance labels."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from qv.kb import benchmark as bm
from qv.kb.search import SearchFilters
from qv.services import knowledge as kn
from tests.test_kb import build, world  # noqa: F401 — the shared fixture


# --- filters and search ---------------------------------------------------------------------------

def test_filters_round_trip_and_ignore_empty_values() -> None:
    f = kn.filters_from_dict({"source_kinds": ["book", ""], "tiers": ["P"], "edition": "", "include_older": 1,
                              "unknown": "x"})
    assert f == SearchFilters(source_kinds=["book"], tiers=["P"], include_older=True)
    assert kn.filters_to_dict(f) == {"source_kinds": ["book"], "tiers": ["P"], "include_older": True}
    assert kn.filters_to_dict(kn.filters_from_dict(None)) == {}
    assert kn.filters_text({"source_kinds": ["book"], "tiers": ["P", "S"], "edition": "swab-quest"}) == \
        "Book page · trust P/S · swab-quest"


def test_filter_options_come_from_the_index(world: dict) -> None:  # noqa: F811
    idx = build(world)
    o = kn.filter_options(idx)
    assert o.source_kinds == ["book", "web"]
    assert {"en", "de"} <= set(o.languages)
    assert o.tiers[0] == "P" and "X" in o.tiers
    assert o.editions == ["world-tour"]
    idx.close()


def test_search_rows_and_combined_filters(world: dict) -> None:  # noqa: F811
    build(world).close()
    hits = kn.run_search(world["dir"], "first Jalsa Salana Qadian")
    assert hits[0].doc_key == "book:basics/p2"
    row = kn.result_rows(hits, ["jalsa"])[0]
    assert row["type"] == "Book page" and row["page"] == "p. 12 (PDF 2)" and "Jalsa Salana" in row["best passage"]
    # filters combine: a book page in German only
    de = kn.run_search(world["dir"], "Qadian", kn.filters_from_dict({"source_kinds": ["book"], "languages": ["de"]}))
    assert [h.doc_key for h in de] == ["book:de/p1"]
    assert kn.run_search(world["dir"], "Qadian", kn.filters_from_dict({"source_kinds": ["web"]})) == []
    # older versions only when asked; the copy at another address is "also at"
    k = kn.run_search(world["dir"], "Kilimanjaro Tanzania")
    assert all(h.is_current for h in k)
    assert any(h.also_at for h in k)
    assert kn.run_search(world["dir"], '"Old text"') == []          # only the older version has these words
    older = kn.run_search(world["dir"], '"Old text"', SearchFilters(include_older=True))
    assert [h.is_current for h in older] == [False]
    assert kn.result_rows(older)[0]["older version"] == "older"
    assert kn.run_search(world["dir"], "the of") == []


def test_search_without_an_index_is_empty(tmp_path) -> None:  # noqa: ANN001
    assert kn.open_index(tmp_path) is None
    assert kn.run_search(tmp_path, "anything") == []


def test_any_stored_page_is_findable_by_a_distinctive_phrase(world: dict) -> None:  # noqa: F811
    idx = build(world)
    for doc_key in [f"doc:{i}" for i in world["docs"].values()] + ["book:basics/p2", "book:de/p1"]:
        st = kn.stored_text(world["db"], world["dir"], doc_key, library=world["library"])
        phrase = " ".join(st.text.split()[-4:])
        hits = kn.run_search(world["dir"], f'"{phrase}"', SearchFilters(include_older=True), limit=50)
        assert idx.doc(doc_key)["canon_key"] in {h.canon_key for h in hits}, doc_key
    idx.close()


def test_stored_text_and_offsets_open_the_right_page(world: dict) -> None:  # noqa: F811
    build(world).close()
    hit = kn.run_search(world["dir"], "Jalsa Salana held")[0]
    st = kn.stored_text(world["db"], world["dir"], hit.doc_key, library=world["library"])
    assert st is not None and st.title.startswith("Basics")
    for ch in hit.chunks:
        assert st.text[ch.start:ch.end] == ch.text
    adam = kn.stored_text(world["db"], world["dir"], f"doc:{world['docs']['adam']}")
    assert adam.link == "https://alislam.org/adam" and "Adam" in adam.text
    assert kn.stored_text(world["db"], world["dir"], "doc:99999") is None
    assert kn.stored_text(world["db"], world["dir"], "book:nope/p1") is None


def test_links_are_plain_web_addresses_only() -> None:
    assert kn.safe_link("https://a.org/x?y=1") == "https://a.org/x?y=1"
    for bad in ("javascript:alert(1)", "library://basics/p2", "https://a.org/\"onmouseover", None, ""):
        assert kn.safe_link(bad) is None


def test_marked_html_escapes_and_marks() -> None:
    out = kn.marked_html("<b>Adam</b> & Eve; adamant", ["adam"], [(0, 12)])
    assert "<b>" not in out and "&lt;b&gt;" in out and "&amp;" in out
    assert out.count("<mark>") == 2                     # "Adam" and the word start of "adamant"
    assert out.startswith("<span class='qv-hit'>")
    assert kn.marked_html("abc", [], [(2, 1), (5, 9)]) == "abc"
    # overlapping passages do not repeat text
    assert kn.marked_html("abcdef", [], [(0, 4), (2, 6)]).replace("<span class='qv-hit'>", "").replace(
        "</span>", "") == "abcdef"


def test_best_passage_is_short_and_near_the_words() -> None:
    from qv.kb.search import ChunkHit, DocHit
    long = "word " * 100 + "Kilimanjaro is high. " + "more " * 100
    h = DocHit("doc:1", "c", 1.0, "t", "u", "web", "T", "en", True, 1, None, None, None, "", False,
               [ChunkHit(1, 0, len(long), long)])
    p = kn.best_passage(h, ["kilimanjaro"])
    assert "Kilimanjaro" in p and len(p) <= 230 and p.startswith("… ")


# --- topics -----------------------------------------------------------------------------------------

def test_topic_save_reopen_rename_change_delete(world: dict) -> None:  # noqa: F811
    db = world["db"]
    t = kn.save_topic(db, "  First   Jalsa ", '"Jalsa Salana" Qadian', {"source_kinds": ["book"]})
    assert t.name == "First Jalsa" and t.filters == {"source_kinds": ["book"]}
    with pytest.raises(ValueError, match="already"):
        kn.save_topic(db, "First Jalsa", "Qadian")
    with pytest.raises(ValueError, match="name"):
        kn.save_topic(db, "  ", "Qadian")
    with pytest.raises(ValueError, match="words"):
        kn.save_topic(db, "Empty", "the of")
    other = kn.save_topic(db, "Mountains", "Kilimanjaro", SearchFilters(tiers=["T"]))
    assert [x.name for x in kn.list_topics(db)] == ["First Jalsa", "Mountains"]
    again = kn.get_topic(db, t.id)
    assert again.query == '"Jalsa Salana" Qadian' and kn.filters_from_dict(again.filters).source_kinds == ["book"]
    renamed = kn.update_topic(db, t.id, name="Jalsa 1891")
    assert renamed.name == "Jalsa 1891" and renamed.query == t.query
    with pytest.raises(ValueError, match="already"):
        kn.update_topic(db, t.id, name="Mountains")
    changed = kn.update_topic(db, other.id, query="Everest", filters={})
    assert changed.query == "Everest" and changed.filters == {}
    kn.delete_topic(db, other.id)
    assert kn.get_topic(db, other.id) is None
    with pytest.raises(ValueError, match="no longer"):
        kn.update_topic(db, other.id, name="x")


def test_questions_matching_a_topic(world: dict) -> None:  # noqa: F811
    rows = kn.matching_questions(world["db"], "Kilimanjaro")
    assert rows and rows[0]["id"] == "135" and rows[0]["file"] == "mini" and rows[0]["status"]
    assert kn.matching_questions(world["db"], "the of") == []
    assert kn.question_score("Mount Kilimanjaro is in Tanzania", '"Kilimanjaro is" Tanzania') == 1
    assert kn.question_score("Mount Kilimanjaro is in Tanzania", '"is Kilimanjaro"') == 0


# --- relevance labels ---------------------------------------------------------------------------------

def test_labels_newest_wins_clear_and_append_only(world: dict) -> None:  # noqa: F811
    db = world["db"]
    q = kn.find_question(db, "mini", "3")
    assert q is not None and kn.find_question(db, "mini", "nope") is None and kn.find_question(db, "x", "3") is None
    doc = f"doc:{world['docs']['unread']}"
    assert kn.label_for(db, q, doc) is None
    kn.add_label(db, q, doc, "relevant")
    kn.add_label(db, q, doc, "not_relevant")
    assert kn.label_for(db, q, doc) == "not_relevant"
    assert kn.labels_for_doc(db, doc)[0]["judgement"] == kn.LABEL_TEXT["not_relevant"]
    kn.add_label(db, q, doc, "clear")
    assert kn.label_for(db, q, doc) is None and kn.labels_for_doc(db, doc) == []
    for bad in (("relevant", "http://x"), ("maybe", doc)):
        with pytest.raises(ValueError):
            kn.add_label(db, q, bad[1], bad[0])
    with pytest.raises((IntegrityError, OperationalError), match="append-only"):
        with db.session() as s:
            s.execute(text("UPDATE relevance_labels SET label = 'relevant'"))
    with pytest.raises((IntegrityError, OperationalError), match="append-only"):
        with db.session() as s:
            s.execute(text("DELETE FROM relevance_labels"))


def test_labels_reach_the_benchmark(world: dict) -> None:  # noqa: F811
    db = world["db"]
    idx = build(world)
    q = kn.find_question(db, "mini", "3")
    unread = f"doc:{world['docs']['unread']}"
    kn.add_label(db, q, unread, "relevant")
    kn.add_label(db, q, "book:basics/p2", "not_relevant")
    labels = kn.benchmark_labels(db)
    key = f"world-tour#3@{q.content_hash[:8]}"
    assert sorted(labels) == sorted([(key, unread, "relevant"), (key, "book:basics/p2", "not_relevant")])
    qs = {b.key: b for b in bm.load_questions(db, idx, labels)}
    assert idx.doc(unread)["canon_key"] in qs[key].relevant
    assert idx.doc("book:basics/p2")["canon_key"] in qs[key].not_relevant
    idx.close()
    report, _ = bm.run_benchmark(db, world["dir"], save=False, extra_labels=labels)
    assert report["person_labels"] == 2
