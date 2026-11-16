"""Book library: Ahmadiyya books (PDFs) as a local, citable source (book + page).

- `config/library.yaml` lists the books (title, author, language, publisher, which editions use them).
- The PDF files live in `<data_dir>/library/` (git-ignored; books never leave the Mac).
- `qv library index` reads every page's text (pypdf) into a local full-text index
  (`<data_dir>/library/index.sqlite`, SQLite FTS5). The index is a cache: delete it and index again.
- A book in another language can get a machine translation per page (`qv library translate`), stored in the
  index and searched together with the original. The translation only FINDS the page; S3 reads and quotes the
  original page, so evidence is never a translation.
- During research, the best-matching pages for a question become documents
  (`library://<book>/p<pdf page>`), read by S3 and grounded like any web page.

Books whose PDF has no usable text layer (scanned pages, or Urdu fonts that extract as garbage) are marked
`needs_ocr` and skipped until OCR is added.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from qv.config import CONFIG_DIR, Profile

SCHEME = "library://"
_STOPWORDS = frozenset(
    "a an and are as at be by did do does for from had has he her his how in is it its of on or she that the "
    "their them they this to was were what when where which who whom whose why with".split())


class Book(BaseModel):
    """One book in config/library.yaml."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", description="short name, used in citations")
    file: str = Field(description="PDF file name inside <data_dir>/library/")
    title: str
    author: str = ""
    language: str = Field("en", description="ISO code: en, de, ur …")
    edition_of_book: str = ""
    publisher: str = Field("", description="domain of the publisher, e.g. alislam.org (decides frame authority)")
    source_url: str = ""
    tier: str = Field("S", pattern="^[PST]$")
    editions: list[str] = Field(default_factory=list, description="game editions whose questions use this book")
    translate_for_search: str | None = Field(
        None, description="language code (e.g. en): a machine translation of every page is indexed too, so "
                          "questions in that language find the page. Search only — evidence is the original text")


class LibraryConfig(BaseModel):
    """config/library.yaml"""

    model_config = ConfigDict(extra="forbid")

    books: list[Book] = Field(default_factory=list)


def load_library_config(path: Path = CONFIG_DIR / "library.yaml") -> LibraryConfig:
    """Books listed in the config (empty when the file does not exist)."""
    if not path.exists():
        return LibraryConfig()
    cfg = LibraryConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    ids = [b.id for b in cfg.books]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate book id in library.yaml")
    return cfg


# --- page text ---------------------------------------------------------------------------

_REPEAT = re.compile(r"(.{2,60}?)\1{2,}")   # "118118118118118", headings drawn five times (bold); not "1888"
_HYPHEN = re.compile(r"(\w)-\n(\w)")                # "abomi-\nnation" → "abomination"


def clean_page(text: str) -> str:
    """Page text made readable: repeated runs collapsed, line-end hyphens joined, spaces tidied."""
    text = unicodedata.normalize("NFC", text.replace("\r", "\n"))
    text = "\n".join(_REPEAT.sub(r"\1", line) for line in text.split("\n"))
    text = _HYPHEN.sub(r"\1\2", text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def printed_page(text: str) -> str | None:
    """The page number printed on the page (its first number on the first lines), if any."""
    for line in text.split("\n")[:3]:
        m = re.fullmatch(r"\s*(\d{1,4}|[ivxlc]{1,6})\s*", line, re.I)
        if m:
            return m.group(1)
    return None


def text_quality(text: str, language: str) -> float:
    """Share of characters that look like real text (0–1). Broken font encodings give odd symbols."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    bad = 0
    for c in chars:
        cat = unicodedata.category(c)
        if cat in ("Cc", "Co", "Cn") or "\x80" <= c <= "\xbf" or c == "�":
            bad += 1
        elif language in ("ur", "ar", "fa") and c.isalpha() and not ("؀" <= c <= "ۿ" or
                                                                      "ݐ" <= c <= "ݿ" or
                                                                      "ﭐ" <= c <= "﻿"):
            bad += 1        # Latin letters inside an Urdu text are a sign of a broken encoding
    return 1 - bad / len(chars)


def read_pdf_pages(path: Path) -> list[str]:
    """Text of every page (pypdf). Pages without a text layer come back empty."""
    import logging

    import pypdf
    logging.getLogger("pypdf").setLevel(logging.ERROR)   # font warnings are noise here
    reader = pypdf.PdfReader(str(path))
    out = []
    for page in reader.pages:
        try:
            out.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 — one bad page must not stop a whole book
            out.append("")
    return out


# --- index -------------------------------------------------------------------------------

@dataclass(frozen=True)
class PageHit:
    """A page that matches a query."""

    book_id: str
    page: int                    # 1-based PDF page
    printed: str | None          # page number printed on it
    score: float
    text: str

    @property
    def url(self) -> str:
        """Stable citation URL of the page."""
        return page_url(self.book_id, self.page)


@dataclass
class IndexReport:
    """What `index_books` did per book."""

    indexed: dict[str, int] = field(default_factory=dict)      # book → pages
    unchanged: list[str] = field(default_factory=list)
    needs_ocr: dict[str, float] = field(default_factory=dict)  # book → text quality
    missing: list[str] = field(default_factory=list)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page_url(book_id: str, page: int) -> str:
    """library://<book>/p<page>"""
    return f"{SCHEME}{book_id}/p{page}"


def parse_page_url(url: str) -> tuple[str, int] | None:
    """(book, page) of a library URL, else None."""
    m = re.fullmatch(r"library://([a-z0-9-]+)/p(\d+)", url)
    return (m.group(1), int(m.group(2))) if m else None


class Library:
    """The books and their full-text index."""

    def __init__(self, data_dir: Path, cfg: LibraryConfig | None = None) -> None:
        """Books from config/library.yaml (or `cfg`); files and index under <data_dir>/library/."""
        self.dir = data_dir / "library"
        self.cfg = cfg if cfg is not None else load_library_config()
        self.books = {b.id: b for b in self.cfg.books}
        self._conn: sqlite3.Connection | None = None

    # -- index --------------------------------------------------------------------------
    @property
    def conn(self) -> sqlite3.Connection:
        """The index database (created on first use)."""
        if self._conn is None:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.dir / "index.sqlite", check_same_thread=False)
            cols = [r[1] for r in self._conn.execute("PRAGMA table_info(pages_fts)")]
            if cols and "kind" not in cols:          # index from before translations: rebuild (it is a cache)
                self._conn.executescript("DROP TABLE pages_fts; DROP TABLE IF EXISTS pages; "
                                         "DROP TABLE IF EXISTS books;")
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS translations (book_id TEXT, page INTEGER, lang TEXT, source_sha TEXT,
                                                         text TEXT, model TEXT, prompt_version TEXT,
                                                         PRIMARY KEY (book_id, page, lang));
                CREATE TABLE IF NOT EXISTS books (id TEXT PRIMARY KEY, sha256 TEXT, pages INTEGER,
                                                  status TEXT, quality REAL);
                CREATE TABLE IF NOT EXISTS pages (book_id TEXT, page INTEGER, printed TEXT, text TEXT,
                                                  PRIMARY KEY (book_id, page));
                CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
                    text, book_id UNINDEXED, page UNINDEXED, kind UNINDEXED,
                    tokenize = 'unicode61 remove_diacritics 2');
            """)
        return self._conn

    def index_books(self, *, reader=read_pdf_pages, min_quality: float = 0.85) -> IndexReport:  # noqa: ANN001
        """(Re)index every listed book whose file changed; `reader(path)` returns page texts."""
        rep = IndexReport()
        for book in self.cfg.books:
            path = self.dir / book.file
            if not path.exists():
                rep.missing.append(book.id)
                continue
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            row = self.conn.execute("SELECT sha256, status FROM books WHERE id = ?", (book.id,)).fetchone()
            if row and row[0] == sha:
                rep.unchanged.append(book.id)
                if row[1] == "needs_ocr":
                    rep.needs_ocr[book.id] = self.conn.execute(
                        "SELECT quality FROM books WHERE id = ?", (book.id,)).fetchone()[0]
                continue
            pages = [clean_page(t) for t in reader(path)]
            quality = text_quality("\n".join(pages), book.language)
            self.index_pages(book.id, pages, sha=sha, quality=quality, min_quality=min_quality)
            if quality < min_quality:
                rep.needs_ocr[book.id] = quality
            else:
                rep.indexed[book.id] = len(pages)
        return rep

    def index_pages(self, book_id: str, pages: list[str], *, sha: str = "", quality: float = 1.0,
                    min_quality: float = 0.85) -> None:
        """Replace a book's pages in the index (a book below `min_quality` is stored as needs_ocr, unsearchable)."""
        c = self.conn
        c.execute("DELETE FROM pages WHERE book_id = ?", (book_id,))
        c.execute("DELETE FROM pages_fts WHERE book_id = ?", (book_id,))
        status = "ok" if quality >= min_quality else "needs_ocr"
        if status == "ok":
            for i, text in enumerate(pages, start=1):
                if not text:
                    continue
                c.execute("INSERT INTO pages VALUES (?, ?, ?, ?)", (book_id, i, printed_page(text), text))
                c.execute("INSERT INTO pages_fts (text, book_id, page, kind) VALUES (?, ?, ?, 'original')",
                          (text, book_id, i))
                for lang, tr in c.execute("SELECT lang, text FROM translations WHERE book_id = ? AND page = ? "
                                          "AND source_sha = ?", (book_id, i, _sha(text))).fetchall():
                    c.execute("INSERT INTO pages_fts (text, book_id, page, kind) VALUES (?, ?, ?, ?)",
                              (tr, book_id, i, lang))
        c.execute("INSERT OR REPLACE INTO books VALUES (?, ?, ?, ?, ?)", (book_id, sha, len(pages), status, quality))
        c.commit()

    def status(self) -> list[dict]:
        """Every listed book with its file and index state."""
        out = []
        for b in self.cfg.books:
            row = self.conn.execute("SELECT pages, status, quality FROM books WHERE id = ?", (b.id,)).fetchone()
            out.append({"book": b.id, "title": b.title, "language": b.language, "editions": ", ".join(b.editions),
                        "file": "found" if (self.dir / b.file).exists() else "missing",
                        "pages": row[0] if row else None,
                        "state": ("searchable" if row and row[1] == "ok" else
                                  "needs OCR (no usable text in the PDF)" if row else "not indexed yet"),
                        "text quality": round(row[2], 2) if row else None,
                        "translated for search": (f"{self.translated_count(b.id, b.translate_for_search)} pages "
                                                  f"→ {b.translate_for_search}" if b.translate_for_search else "")})
        return out

    # -- search -------------------------------------------------------------------------
    def books_for(self, profile: Profile) -> list[str]:
        """Books this edition uses."""
        return [b.id for b in self.cfg.books if profile.edition in b.editions]

    def search(self, query: str, *, books: list[str], limit: int = 3) -> list[PageHit]:
        """Best pages for a query (BM25), within `books`. Any shared content word counts; more and rarer
        words rank higher."""
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 1 and w not in _STOPWORDS]
        if not words or not books:
            return []
        match = " OR ".join(f'"{w}"' for w in dict.fromkeys(words))
        marks = ",".join("?" * len(books))
        ranked = self.conn.execute(
            f"SELECT book_id, page, bm25(pages_fts) AS s FROM pages_fts "
            f"WHERE pages_fts MATCH ? AND book_id IN ({marks}) ORDER BY s LIMIT ?",
            (match, *books, limit * 4)).fetchall()
        best: dict[tuple[str, int], float] = {}
        for book_id, page, score in ranked:          # a page can match through its original and its translation
            best.setdefault((book_id, int(page)), float(score))
        rows = []
        for (book_id, page), score in list(best.items())[:limit]:
            printed, text = self.conn.execute("SELECT printed, text FROM pages WHERE book_id = ? AND page = ?",
                                              (book_id, page)).fetchone()
            rows.append((book_id, page, score, printed, text))
        return [PageHit(r[0], int(r[1]), r[3], -float(r[2]), r[4]) for r in rows]

    # -- translations (search only) ----------------------------------------------------
    def pages_to_translate(self, book_id: str, lang: str) -> list[tuple[int, str]]:
        """(page, original text) of pages without a current translation into `lang`."""
        rows = self.conn.execute("SELECT page, text FROM pages WHERE book_id = ? ORDER BY page", (book_id,)).fetchall()
        done = {(p, sha) for p, sha in self.conn.execute(
            "SELECT page, source_sha FROM translations WHERE book_id = ? AND lang = ?", (book_id, lang))}
        return [(p, t) for p, t in rows if (p, _sha(t)) not in done]

    def add_translation(self, book_id: str, page: int, lang: str, source_text: str, text: str, *, model: str = "",
                        prompt_version: str = "") -> None:
        """Store a page's translation and make it searchable (replaces an older one)."""
        c = self.conn
        c.execute("INSERT OR REPLACE INTO translations VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (book_id, page, lang, _sha(source_text), text, model, prompt_version))
        c.execute("DELETE FROM pages_fts WHERE book_id = ? AND page = ? AND kind = ?", (book_id, page, lang))
        c.execute("INSERT INTO pages_fts (text, book_id, page, kind) VALUES (?, ?, ?, ?)", (text, book_id, page, lang))
        c.commit()

    def translation(self, book_id: str, page: int, lang: str) -> str | None:
        """The stored translation of a page, if any."""
        r = self.conn.execute("SELECT text FROM translations WHERE book_id = ? AND page = ? AND lang = ?",
                              (book_id, page, lang)).fetchone()
        return r[0] if r else None

    def translated_count(self, book_id: str, lang: str) -> int:
        """How many pages have a translation into `lang`."""
        return self.conn.execute("SELECT COUNT(*) FROM translations WHERE book_id = ? AND lang = ?",
                                 (book_id, lang)).fetchone()[0]

    def page(self, book_id: str, page: int) -> PageHit | None:
        """One page's stored text."""
        r = self.conn.execute("SELECT printed, text FROM pages WHERE book_id = ? AND page = ?",
                              (book_id, page)).fetchone()
        return PageHit(book_id, page, r[0], 0.0, r[1]) if r else None

    # -- citation, tier, frame ----------------------------------------------------------
    def title_for(self, hit: PageHit) -> str:
        """"Title (author), p. 118 [PDF page 127]"."""
        b = self.books[hit.book_id]
        who = f" ({b.author})" if b.author else ""
        printed = f"p. {hit.printed} " if hit.printed else ""
        return f"{b.title}{who}, {printed}[PDF page {hit.page}]"

    def tier(self, url: str) -> str | None:
        """The book's tier for a library URL (None for other URLs)."""
        ref = parse_page_url(url)
        return self.books[ref[0]].tier if ref and ref[0] in self.books else None

    def is_frame_authority(self, url: str, profile: Profile) -> bool:
        """True when the book's publisher is one of the edition frame's authorities."""
        ref = parse_page_url(url)
        if not ref or ref[0] not in self.books or profile.frame is None:
            return False
        pub = self.books[ref[0]].publisher.lower().removeprefix("www.")
        return bool(pub) and any(pub == a.lower().removeprefix("www.") for a in profile.frame.authorities)
