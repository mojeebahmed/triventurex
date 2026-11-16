"""Book library on the web page: add a book (upload or download a PDF), remove a book, dismiss a web PDF.

Books added here go into the person's own list `<data_dir>/library/books.yaml` (git-ignored, like the PDFs);
config/library.yaml is never changed — a config book removed here is listed under `removed`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from qv.library import Book, IndexReport, Library, load_my_books, save_my_books
from qv.providers.search.web import USER_AGENT

MAX_PDF_BYTES = 80_000_000


@dataclass
class BookInfo:
    """What the person tells about a book."""

    title: str
    author: str = ""
    language: str = "en"
    publisher: str = ""
    tier: str = "S"
    editions: tuple[str, ...] = ()
    source_url: str = ""
    translate_for_search: str | None = None


def slug(text: str) -> str:
    """A book id from a title: 'Life of the Promised Messiah' → 'life-of-the-promised-messiah'."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")
    return s or "book"


def is_pdf(data: bytes) -> bool:
    """True when the bytes start like a PDF file."""
    return data[:1024].lstrip().startswith(b"%PDF")


def add_book(data_dir: Path, data: bytes, info: BookInfo) -> tuple[Book, IndexReport]:
    """Save the PDF, add the book to the person's list and read it. Raises ValueError for a non-PDF or bad info."""
    if not is_pdf(data):
        raise ValueError("This is not a PDF file.")
    if not info.title.strip():
        raise ValueError("Give the book a title.")
    lib = Library(data_dir)
    base = slug(info.title)
    book_id, n = base, 2
    while book_id in lib.books:
        book_id, n = f"{base}-{n}", n + 1
    book = Book(id=book_id, file=f"{book_id}.pdf", title=info.title.strip(), author=info.author.strip(),
                language=(info.language or "en").strip().lower(), publisher=info.publisher.strip().lower(),
                source_url=info.source_url.strip(), tier=info.tier, editions=list(info.editions),
                translate_for_search=info.translate_for_search or None)
    lib.dir.mkdir(parents=True, exist_ok=True)
    (lib.dir / book.file).write_bytes(data)
    mine = load_my_books(data_dir)
    mine["books"].append(book.model_dump(exclude_defaults=True) | {"id": book.id, "file": book.file,
                                                                  "title": book.title})
    if info.source_url:
        mine["dismissed"] = [u for u in mine["dismissed"] if u != info.source_url]
    save_my_books(data_dir, mine)
    return book, Library(data_dir).index_books()


def remove_book(data_dir: Path, book_id: str) -> None:
    """Remove a book: its PDF, its pages in the index, and its entry (own list) or a `removed` mark (config).

    Quotes already used as evidence stay in the validation database (they are history).
    """
    lib = Library(data_dir)
    book = lib.books.get(book_id)
    if book is None:
        raise ValueError(f"No book {book_id!r}.")
    lib.forget(book_id)
    pdf = lib.dir / book.file
    if pdf.exists():
        pdf.unlink()
    mine = load_my_books(data_dir)
    own = [b for b in mine["books"] if b.get("id") == book_id]
    if own:
        mine["books"] = [b for b in mine["books"] if b.get("id") != book_id]
    elif book_id not in mine["removed"]:
        mine["removed"].append(book_id)
    save_my_books(data_dir, mine)


def dismiss(data_dir: Path, url: str) -> None:
    """Hide a web PDF from the candidate list ("not a book for the library")."""
    mine = load_my_books(data_dir)
    if url not in mine["dismissed"]:
        mine["dismissed"].append(url)
        save_my_books(data_dir, mine)


def dismissed(data_dir: Path) -> set[str]:
    """Web PDFs the person hid."""
    return set(load_my_books(data_dir)["dismissed"])


def download_pdf(url: str, *, client: httpx.Client | None = None, max_bytes: int = MAX_PDF_BYTES) -> bytes:
    """Download one PDF the person asked for. Raises ValueError with a plain reason when it does not work."""
    own = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                raise ValueError(f"The site answered {resp.status_code} — try downloading it in your browser and "
                                 "upload the file.")
            chunks, size = [], 0
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"The file is larger than {max_bytes // 1_000_000} MB.")
                chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise ValueError(f"Could not download it ({exc.__class__.__name__}) — try it in your browser and upload "
                         "the file.") from exc
    finally:
        if own:
            client.close()
    data = b"".join(chunks)
    if not is_pdf(data):
        raise ValueError("The link did not give a PDF file (perhaps a login or a web page).")
    return data


def guess_title(url_or_name: str) -> str:
    """A readable title from a file name: 'Life-of-the-Promised-Messiah.pdf' → 'Life of the Promised Messiah'."""
    name = url_or_name.rsplit("/", 1)[-1]
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    name = re.sub(r"%20|[_\-+]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()
