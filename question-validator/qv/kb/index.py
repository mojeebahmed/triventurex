"""The knowledge index: `<data_dir>/kb/index.sqlite` — every stored document and book page, chunked and searchable
with one SQLite FTS5 index.

It is a **cache**: derived only from the Alembic database (`documents`, `question_documents`, `questions`) and the
book library's index (`data/library/index.sqlite`, pages + search-only translations). Delete it and `qv kb index`
builds it again. Nothing here is evidence; search only decides what is read.

Document keys
- `doc:<documents.id>` — a stored page (web, Wikipedia, Qur'an verse; a library document whose book is no longer
  in the library index falls back to this too)
- `book:<book id>/p<pdf page>` — a book page (the library's own text; a `library://` document with the same page
  is the same text and is not indexed twice)

Grouping (KNOWLEDGE_BASE_PLAN.md → Document identity)
- versions: documents with the same normalised URL; the newest fetch is *current*, older ones are kept, hidden by
  default in search, never invalidated
- same content at different URLs: documents with the same content hash
- `canon_key`: both kinds of grouping joined (union–find); search shows one result per canon_key ("also at …") and
  the benchmark judges on canon keys
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text as sql

from qv.db.session import Database
from qv.kb.text import CHUNKER_VERSION, chunk_text, guess_language, normalize_url
from qv.library import Library, PageHit, parse_page_url, printed_page
from qv.sources import Registry

INDEX_FILE = "index.sqlite"
SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS kb_docs (
    doc_key TEXT PRIMARY KEY,
    source_kind TEXT,            -- web | wikipedia | quran | library | book
    document_id INTEGER,         -- documents.id (NULL for a book page)
    book_id TEXT, page INTEGER, printed TEXT,
    url TEXT, norm_url TEXT, domain TEXT, title TEXT,
    content_hash TEXT,           -- sha256 of the text
    fetched_at TEXT,
    char_len INTEGER,
    chunker_version INTEGER,
    -- metadata, refreshed on every run (cheap; never re-chunks)
    lang TEXT, tier TEXT, is_current INTEGER, canon_key TEXT,
    editions TEXT, categories TEXT, n_questions INTEGER
);
CREATE INDEX IF NOT EXISTS kb_docs_canon ON kb_docs (canon_key);
CREATE INDEX IF NOT EXISTS kb_docs_document ON kb_docs (document_id);
CREATE TABLE IF NOT EXISTS kb_chunks (
    chunk_id INTEGER PRIMARY KEY,
    doc_key TEXT, ord INTEGER, start INTEGER, "end" INTEGER, page INTEGER, text TEXT
);
CREATE INDEX IF NOT EXISTS kb_chunks_doc ON kb_chunks (doc_key);
CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
    text, chunk_id UNINDEXED, doc_key UNINDEXED, kind UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2');
"""
# kb_fts.kind: 'original' (a chunk of the stored text) or a language code (a search-only machine translation of a
# book page; chunk_id is NULL — it only finds the page, its text is never shown as the page's text)

_META_COLS = ("lang", "tier", "is_current", "canon_key", "editions", "categories", "n_questions")


def index_path(data_dir: Path) -> Path:
    """Where the knowledge index lives."""
    return data_dir / "kb" / INDEX_FILE


def sha(text: str) -> str:
    """sha256 of a text (hex)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Source:
    """One document or book page as it should be in the index."""

    doc_key: str
    source_kind: str
    text: str
    content_hash: str
    document_id: int | None = None
    book_id: str | None = None
    page: int | None = None
    printed: str | None = None
    url: str = ""
    title: str = ""
    domain: str = ""
    fetched_at: str = ""
    translations: dict[str, str] = field(default_factory=dict)   # lang → search-only text (book pages)


@dataclass
class IndexReport:
    """What one `update` did."""

    added: int = 0
    rechunked: int = 0
    removed: int = 0
    meta_updated: int = 0
    unchanged: int = 0
    chunks: int = 0
    seconds: float = 0.0

    def line(self) -> str:
        """One line for the CLI and the logs."""
        return (f"{self.added} added, {self.rechunked} re-chunked, {self.removed} removed, {self.meta_updated} "
                f"with new details, {self.unchanged} unchanged — {self.chunks} chunks in all ({self.seconds:.1f} s)")


class KnowledgeIndex:
    """`<data_dir>/kb/index.sqlite` — build, update and read it."""

    def __init__(self, path: Path) -> None:
        """Open (and create) the index file."""
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        version = self._meta_raw("schema_version")
        if version is not None and int(version) != SCHEMA_VERSION:
            self._drop_all()                       # a cache: an old layout is simply rebuilt
        self.conn.executescript(_SCHEMA)
        self._set_meta("schema_version", str(SCHEMA_VERSION))

    @classmethod
    def for_data_dir(cls, data_dir: Path) -> KnowledgeIndex:
        """The index of a data directory."""
        return cls(index_path(data_dir))

    def close(self) -> None:
        """Close the connection."""
        self.conn.close()

    # -- meta -------------------------------------------------------------------------------
    def _meta_raw(self, key: str) -> str | None:
        try:
            row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        except sqlite3.OperationalError:
            return None
        return row[0] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
        self.conn.commit()

    def _drop_all(self) -> None:
        self.conn.executescript("DROP TABLE IF EXISTS kb_fts; DROP TABLE IF EXISTS kb_chunks; "
                                "DROP TABLE IF EXISTS kb_docs; DROP TABLE IF EXISTS meta;")

    def clear(self) -> None:
        """Empty the index (`qv kb rebuild`)."""
        self._drop_all()
        self.conn.executescript(_SCHEMA)
        self._set_meta("schema_version", str(SCHEMA_VERSION))

    # -- update -----------------------------------------------------------------------------
    def update(self, sources: list[Source], meta: dict[str, dict]) -> IndexReport:
        """Bring the index in line with `sources` (+ their metadata from `compute_meta`): new or changed texts
        are chunked, gone ones removed, metadata refreshed where it changed. Incremental and idempotent."""
        t0 = time.monotonic()
        rep = IndexReport()
        c = self.conn
        trans_sig: dict[str, list[str]] = defaultdict(list)
        for key, kind, length in c.execute("SELECT doc_key, kind, length(text) FROM kb_fts WHERE kind != 'original'"):
            trans_sig[key].append(f"{kind}:{length}")
        have = {r["doc_key"]: (r["content_hash"], r["chunker_version"], tuple(r[k] for k in _META_COLS),
                               ",".join(trans_sig.get(r["doc_key"], [])) or None)
                for r in c.execute("SELECT doc_key, content_hash, chunker_version, " + ", ".join(_META_COLS)
                                   + " FROM kb_docs")}
        want = {s.doc_key: s for s in sources}
        for key in set(have) - set(want):
            self._delete(key)
            rep.removed += 1
        for key, src in want.items():
            m = meta[key]
            m_tuple = tuple(m[k] for k in _META_COLS)
            tr_sig = ",".join(f"{lang}:{len(t)}" for lang, t in sorted(src.translations.items())) or None
            old = have.get(key)
            if old is None or old[0] != src.content_hash or old[1] != CHUNKER_VERSION:
                if old is None:
                    rep.added += 1
                else:
                    rep.rechunked += 1
                    self._delete(key)
                self._insert(src, m)
            else:
                if old[2] != m_tuple:
                    c.execute(f"UPDATE kb_docs SET {', '.join(f'{k} = ?' for k in _META_COLS)} WHERE doc_key = ?",
                              (*m_tuple, key))
                    rep.meta_updated += 1
                else:
                    rep.unchanged += 1
                if self._translation_sig(old[3]) != self._translation_sig(tr_sig):
                    self._write_translations(src)
        c.commit()
        rep.chunks = c.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0]
        rep.seconds = time.monotonic() - t0
        self._set_meta("updated_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        return rep

    @staticmethod
    def _translation_sig(sig: str | None) -> str:
        return ",".join(sorted((sig or "").split(","))) if sig else ""

    def _delete(self, key: str) -> None:
        c = self.conn
        c.execute("DELETE FROM kb_fts WHERE doc_key = ?", (key,))
        c.execute("DELETE FROM kb_chunks WHERE doc_key = ?", (key,))
        c.execute("DELETE FROM kb_docs WHERE doc_key = ?", (key,))

    def _insert(self, src: Source, m: dict) -> None:
        c = self.conn
        c.execute("INSERT INTO kb_docs (doc_key, source_kind, document_id, book_id, page, printed, url, norm_url, "
                  "domain, title, content_hash, fetched_at, char_len, chunker_version, "
                  + ", ".join(_META_COLS) + ") VALUES (" + ", ".join("?" * (14 + len(_META_COLS))) + ")",
                  (src.doc_key, src.source_kind, src.document_id, src.book_id, src.page, src.printed, src.url,
                   normalize_url(src.url), src.domain, src.title, src.content_hash, src.fetched_at, len(src.text),
                   CHUNKER_VERSION, *(m[k] for k in _META_COLS)))
        for i, ch in enumerate(chunk_text(src.text)):
            cur = c.execute('INSERT INTO kb_chunks (doc_key, ord, start, "end", page, text) VALUES (?, ?, ?, ?, ?, ?)',
                            (src.doc_key, i, ch.start, ch.end, src.page, ch.text))
            c.execute("INSERT INTO kb_fts (text, chunk_id, doc_key, kind) VALUES (?, ?, ?, 'original')",
                      (ch.text, cur.lastrowid, src.doc_key))
        self._write_translations(src)

    def _write_translations(self, src: Source) -> None:
        c = self.conn
        c.execute("DELETE FROM kb_fts WHERE doc_key = ? AND kind != 'original'", (src.doc_key,))
        for lang, tr in src.translations.items():
            c.execute("INSERT INTO kb_fts (text, chunk_id, doc_key, kind) VALUES (?, NULL, ?, ?)",
                      (tr, src.doc_key, lang))

    # -- read -------------------------------------------------------------------------------
    def status(self) -> dict:
        """Counts for `qv kb status`."""
        c = self.conn
        by_kind = {r[0]: r[1] for r in c.execute("SELECT source_kind, COUNT(*) FROM kb_docs GROUP BY 1")}
        by_lang = {r[0]: r[1] for r in c.execute("SELECT lang, COUNT(*) FROM kb_docs GROUP BY 1")}
        return {
            "file": str(self.path),
            "documents": sum(by_kind.values()),
            "by_source": by_kind,
            "by_language": by_lang,
            "older_versions": c.execute("SELECT COUNT(*) FROM kb_docs WHERE is_current = 0").fetchone()[0],
            "search_results": c.execute("SELECT COUNT(DISTINCT canon_key) FROM kb_docs").fetchone()[0],
            "chunks": c.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0],
            "translation_rows": c.execute("SELECT COUNT(*) FROM kb_fts WHERE kind != 'original'").fetchone()[0],
            "characters": c.execute("SELECT COALESCE(SUM(char_len), 0) FROM kb_docs").fetchone()[0],
            "chunker_version": CHUNKER_VERSION,
            "updated_at": self._meta_raw("updated_at"),
        }

    def doc(self, doc_key: str) -> sqlite3.Row | None:
        """One document's row."""
        return self.conn.execute("SELECT * FROM kb_docs WHERE doc_key = ?", (doc_key,)).fetchone()

    def canon_of_document(self) -> dict[int, str]:
        """documents.id → the canon key search shows for it (library documents → their book page's group)."""
        out = {r[0]: r[1] for r in self.conn.execute(
            "SELECT document_id, canon_key FROM kb_docs WHERE document_id IS NOT NULL")}
        canon = {r[0]: r[1] for r in self.conn.execute("SELECT doc_key, canon_key FROM kb_docs")}
        for doc_id, key in json.loads(self._meta_raw("aliases") or "{}").items():
            if key in canon:
                out[int(doc_id)] = canon[key]
        return out


# --- collecting sources -----------------------------------------------------------------------

def collect_sources(db: Database, library: Library | None) -> tuple[list[Source], dict[int, str]]:
    """Everything that belongs in the index, plus documents.id → doc key for `library://` documents that map
    onto a book page (they are the same text and are indexed once, as the page)."""
    sources: list[Source] = []
    book_pages: dict[tuple[str, int], Source] = {}
    if library is not None and library.dir.joinpath("index.sqlite").exists():
        lc = library.conn
        ok = {r[0] for r in lc.execute("SELECT id FROM books WHERE status = 'ok'")}
        trans: dict[tuple[str, int], dict[str, str]] = defaultdict(dict)
        current = {(b, p): s for b, p, s in lc.execute("SELECT book_id, page, text FROM pages")}
        for b, p, lang, src_sha, t in lc.execute("SELECT book_id, page, lang, source_sha, text FROM translations"):
            if (b, p) in current and sha(current[(b, p)]) == src_sha:
                trans[(b, p)][lang] = t
        for book_id, page, printed, text in lc.execute("SELECT book_id, page, printed, text FROM pages "
                                                       "ORDER BY book_id, page"):
            if book_id not in ok or book_id not in library.books or not text:
                continue
            title = library.title_for(PageHit(book_id, int(page), printed, 0.0, ""))
            src = Source(doc_key=f"book:{book_id}/p{page}", source_kind="book", text=text, content_hash=sha(text),
                         book_id=book_id, page=int(page), printed=printed or printed_page(text),
                         url=f"library://{book_id}/p{page}", title=title, domain="library",
                         translations=dict(trans.get((book_id, int(page)), {})))
            sources.append(src)
            book_pages[(book_id, int(page))] = src
    alias: dict[int, str] = {}
    with db.session() as s:
        rows = s.execute(sql("SELECT id, url, final_url, domain, title, source_kind, fetched_at, content_sha256, text, "
                             "ref FROM documents ORDER BY id")).all()
    for r in rows:
        if r.source_kind == "library":
            ref = parse_page_url(r.final_url)
            if ref and ref in book_pages:
                alias[r.id] = book_pages[ref].doc_key
                continue
        sources.append(Source(doc_key=f"doc:{r.id}", source_kind=r.source_kind, text=r.text,
                              content_hash=r.content_sha256, document_id=r.id, url=r.final_url, title=r.title or "",
                              domain=r.domain or "", fetched_at=str(r.fetched_at or "")))
    return sources, alias


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def compute_meta(db: Database, sources: list[Source], alias: dict[int, str], registry: Registry | None,
                 library: Library | None) -> dict[str, dict]:
    """Per doc key: language guess, trust tier, current/older version, canon key, and the editions / categories /
    number of questions that read it. Pure bookkeeping — no text is changed."""
    # versions: newest fetch per normalised URL is current
    newest: dict[str, tuple[str, int]] = {}
    for s in sources:
        if s.document_id is None:
            continue
        key = normalize_url(s.url)
        cand = (s.fetched_at, s.document_id)
        if key not in newest or cand > newest[key]:
            newest[key] = cand
    uf = _UnionFind()
    by_url: dict[str, list[str]] = defaultdict(list)
    by_hash: dict[str, list[str]] = defaultdict(list)
    for s in sources:
        uf.find(s.doc_key)
        if s.document_id is not None:
            by_url[normalize_url(s.url)].append(s.doc_key)
        by_hash[s.content_hash].append(s.doc_key)
    for group in (*by_url.values(), *by_hash.values()):
        for other in group[1:]:
            uf.union(group[0], other)
    order = {s.doc_key: (s.document_id is None, s.fetched_at, s.document_id or 0) for s in sources}
    members: dict[str, list[str]] = defaultdict(list)
    for s in sources:
        members[uf.find(s.doc_key)].append(s.doc_key)
    canon: dict[str, str] = {}
    for group in members.values():
        best = max(group, key=lambda k: order[k])           # a book page, else the newest fetch
        for k in group:
            canon[k] = best

    # who read it
    readers: dict[str, dict[str, set]] = defaultdict(lambda: {"editions": set(), "categories": set(), "q": set()})
    with db.session() as s:
        rows = s.execute(sql("SELECT qd.document_id, dv.profile, q.category, q.ext_id, q.content_hash "
                             "FROM question_documents qd JOIN questions q ON q.id = qd.question_id "
                             "JOIN dataset_versions dv ON dv.id = q.dataset_version_id")).all()
    for doc_id, profile, category, ext_id, chash in rows:
        key = alias.get(doc_id, f"doc:{doc_id}")
        r = readers[key]
        r["editions"].add(profile)
        if category:
            r["categories"].add(category)
        r["q"].add((profile, ext_id, chash))

    out: dict[str, dict] = {}
    for s in sources:
        if s.source_kind == "book":
            book = library.books.get(s.book_id) if library else None
            tier = book.tier if book else "S"
            lang = (book.language if book else None) or guess_language(s.text)
        elif s.source_kind == "quran":
            tier, lang = "P", guess_language(s.text).replace("ur", "ar")   # Qur'an script, not Urdu
        else:
            tier = registry.tier(s.url) if registry else "T"
            lang = guess_language(s.text)
        r = readers.get(s.doc_key)
        is_current = 1 if s.document_id is None or newest.get(normalize_url(s.url), (None, s.document_id))[1] \
            == s.document_id else 0
        out[s.doc_key] = {
            "lang": lang, "tier": tier, "is_current": is_current, "canon_key": canon[s.doc_key],
            "editions": json.dumps(sorted(r["editions"])) if r else "[]",
            "categories": json.dumps(sorted(r["categories"])) if r else "[]",
            "n_questions": len(r["q"]) if r else 0,
        }
    return out


def update_index(db: Database, data_dir: Path, *, rebuild: bool = False, registry: Registry | None = None,
                 library: Library | None = None) -> IndexReport:
    """Collect, compute metadata and update `<data_dir>/kb/index.sqlite` (the whole job of `qv kb index`)."""
    if registry is None:
        from qv.services.websites import registry_with_marks
        registry = registry_with_marks(db)
    if library is None:
        library = Library(data_dir)
    sources, alias = collect_sources(db, library)
    meta = compute_meta(db, sources, alias, registry, library)
    idx = KnowledgeIndex.for_data_dir(data_dir)
    try:
        if rebuild:
            idx.clear()
        rep = idx.update(sources, meta)
        idx._set_meta("aliases", json.dumps({str(k): v for k, v in alias.items()}))
        return rep
    finally:
        idx.close()


def update_quietly(db: Database, data_dir: Path) -> str:
    """Update the index after a batch; never raises (a broken index must not fail a batch). Returns a log line."""
    try:
        return "Knowledge index: " + update_index(db, data_dir).line()
    except Exception as exc:  # noqa: BLE001
        return f"Knowledge index not updated: {type(exc).__name__}: {exc}"
