"""Book library: page cleaning, garbled-text detection, index and search (no PDFs needed)."""

from __future__ import annotations

from pathlib import Path

from qv.config import load_profile
from qv.library import (Book, Library, LibraryConfig, clean_page, load_library_config, parse_page_url, printed_page,
                        text_quality)


def lib(tmp_path: Path) -> Library:
    return Library(tmp_path, LibraryConfig(books=[
        Book(id="basics", file="basics.pdf", title="Basics", author="A. Hadi", publisher="alislam.org",
             editions=["swab-quest"]),
        Book(id="other", file="other.pdf", title="Other", editions=["world-tour"])]))


def test_clean_page_collapses_repeats_and_joins_hyphens() -> None:
    raw = "118118118118118\nBASICS\nsuch evils are an abomi-\nnation of Satan.\nIn 1888 and 2000."
    text = clean_page(raw)
    assert text.startswith("118\nBASICS") and "abomination" in text and "1888" in text and "2000" in text
    assert printed_page(text) == "118"


def test_text_quality_spots_broken_urdu() -> None:
    assert text_quality("Fasting is a source of many blessings.", "en") == 1.0
    assert text_quality("روزہ رکھنا فرض ہے", "ur") > 0.95
    assert text_quality("ت%$ \"د \x91\x92 : s t \x94 x a \x96 v \x9e", "ur") < 0.85


def test_index_search_and_book_scope(tmp_path: Path) -> None:
    library = lib(tmp_path)
    library.index_pages("basics", ["1\nIntro", "12\nThe first Jalsa Salana was held in Qadian in 1891.",
                                   "13\nFasting in Ramadan."])
    library.index_pages("other", ["Jalsa Salana Qadian 1891 Jalsa Salana"])
    hits = library.search("When was the first Jalsa Salana held in Qadian?", books=["basics"])
    assert [(h.book_id, h.page, h.printed) for h in hits] == [("basics", 2, "12")]
    assert library.title_for(hits[0]) == "Basics (A. Hadi), p. 12 [PDF page 2]"
    assert hits[0].url == "library://basics/p2" and parse_page_url(hits[0].url) == ("basics", 2)
    assert library.search("the of and", books=["basics"]) == []
    assert library.books_for(load_profile("swab-quest")) == ["basics"]


def test_tier_and_frame_authority(tmp_path: Path) -> None:
    library = lib(tmp_path)
    swab, world = load_profile("swab-quest"), load_profile("world-tour")
    assert library.tier("library://basics/p3") == "S" and library.tier("https://x.org") is None
    assert library.is_frame_authority("library://basics/p3", swab)
    assert not library.is_frame_authority("library://other/p3", swab)
    assert not library.is_frame_authority("library://basics/p3", world)       # no frame


def test_garbled_book_is_marked_and_not_searchable(tmp_path: Path) -> None:
    library = Library(tmp_path, LibraryConfig(books=[Book(id="ur", file="ur.pdf", title="Urdu", language="ur",
                                                          editions=["swab-quest"])]))
    (tmp_path / "library").mkdir()
    (tmp_path / "library" / "ur.pdf").write_bytes(b"%PDF fake")
    rep = library.index_books(reader=lambda p: ["ت%$ \"د \x91\x92 : s t \x94 x a"])
    assert "ur" in rep.needs_ocr and library.search("s t x", books=["ur"]) == []
    assert library.status()[0]["state"].startswith("needs OCR")
    assert library.index_books(reader=lambda p: []).unchanged == ["ur"]          # same file: not read again


def test_config_lists_the_downloaded_books() -> None:
    ids = [b.id for b in load_library_config().books]
    assert {"basics-religious-education", "dieni-malumat-de", "deeni-maloomat-ur"} <= set(ids)


def test_pdfs_found_on_web_are_listed_as_candidates(db) -> None:  # noqa: ANN001
    from qv.db.models import Fetch
    from qv.services.views import pdfs_found_on_web
    with db.session() as s:
        s.add(Fetch(url="https://files.alislam.cloud/pdf/Fazl-e-Umar.pdf", status="not_text",
                    error="content-type application/pdf"))
        s.add(Fetch(url="https://x.org/page", status="not_text", error="content-type image/png"))
        s.add(Fetch(url="https://x.org/ok", status="ok"))
    rows = pdfs_found_on_web(db)
    assert [(r["file"], r["site"]) for r in rows] == [("Fazl-e-Umar.pdf", "files.alislam.cloud")]
