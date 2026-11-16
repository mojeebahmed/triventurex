"""Book library on the web page: add / remove books (own list in data/library/books.yaml), dismiss, download."""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest
from pypdf import PdfWriter

from qv.library import Library, load_books, load_library_config
from qv.services import books


def blank_pdf() -> bytes:
    """A one-page PDF without text."""
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_names() -> None:
    assert books.slug("Life of the Promised Messiah (a.s.)") == "life-of-the-promised-messiah-a-s"
    assert books.slug("???") == "book"
    assert books.guess_title("https://x.org/files/Life-of_the%20Promised+Messiah.PDF") == \
        "Life of the Promised Messiah"
    assert books.is_pdf(b"%PDF-1.7\n...") and not books.is_pdf(b"<html>")


def test_add_and_remove_own_book(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a PDF"):
        books.add_book(tmp_path, b"<html>login</html>", books.BookInfo(title="X"))
    info = books.BookInfo(title="Life of Muhammad", author="Mirza Bashiruddin", editions=("prophets-stories",),
                          source_url="https://example.org/life.pdf")
    book, rep = books.add_book(tmp_path, blank_pdf(), info)
    assert book.id == "life-of-muhammad" and (tmp_path / "library" / "life-of-muhammad.pdf").exists()
    assert book.id in rep.needs_ocr                    # a page without text is kept but not searched
    again, _ = books.add_book(tmp_path, blank_pdf(), info)
    assert again.id == "life-of-muhammad-2"
    ids = [b.id for b in load_books(tmp_path).books]
    assert {"life-of-muhammad", "life-of-muhammad-2"} <= set(ids)
    assert load_books(tmp_path).books[ids.index("life-of-muhammad")].editions == ["prophets-stories"]
    books.remove_book(tmp_path, "life-of-muhammad")
    assert "life-of-muhammad" not in [b.id for b in load_books(tmp_path).books]
    assert not (tmp_path / "library" / "life-of-muhammad.pdf").exists()
    assert Library(tmp_path).conn.execute("SELECT COUNT(*) FROM books WHERE id = 'life-of-muhammad'").fetchone()[0] == 0


def test_remove_config_book_marks_it_removed(tmp_path: Path) -> None:
    config_id = load_library_config().books[0].id
    books.remove_book(tmp_path, config_id)
    assert config_id not in [b.id for b in load_books(tmp_path).books]
    assert config_id in [b.id for b in load_library_config().books]       # config/library.yaml is never changed
    with pytest.raises(ValueError):
        books.remove_book(tmp_path, "no-such-book")


def test_dismiss(tmp_path: Path) -> None:
    books.dismiss(tmp_path, "https://x.org/a.pdf")
    books.dismiss(tmp_path, "https://x.org/a.pdf")
    assert books.dismissed(tmp_path) == {"https://x.org/a.pdf"}


def client(status: int, body: bytes) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status, content=body)))


def test_download_pdf() -> None:
    pdf = blank_pdf()
    assert books.download_pdf("https://x.org/a.pdf", client=client(200, pdf)) == pdf
    with pytest.raises(ValueError, match="403"):
        books.download_pdf("https://x.org/a.pdf", client=client(403, b""))
    with pytest.raises(ValueError, match="did not give a PDF"):
        books.download_pdf("https://x.org/a.pdf", client=client(200, b"<html>login</html>"))
    with pytest.raises(ValueError, match="larger"):
        books.download_pdf("https://x.org/a.pdf", client=client(200, pdf), max_bytes=10)
