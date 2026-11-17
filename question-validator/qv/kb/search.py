"""Search the knowledge index: BM25 over chunks (+ search-only translations), one result per document group.

Query language: plain words (any shared content word counts, rarer and more words rank higher — the same rule as
the book library search); a part in double quotes must appear as that exact phrase.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from qv.kb.index import KnowledgeIndex
from qv.library import query_words

#: How many FTS rows are looked at before filtering and grouping (plenty for ≤ 100 k chunks).
_CANDIDATES = 3000


@dataclass
class SearchFilters:
    """What a search is limited to (empty = no limit)."""

    source_kinds: list[str] = field(default_factory=list)   # web | wikipedia | quran | book | library
    languages: list[str] = field(default_factory=list)      # 'en' also matches a mixed page 'ar+en'
    tiers: list[str] = field(default_factory=list)          # P | S | T | X
    edition: str | None = None                               # read for a question of this edition
    category: str | None = None                              # read for a question of this category
    include_older: bool = False                              # older versions of a page
    exclude_doc_keys: set[str] = field(default_factory=set)

    def allows(self, row) -> bool:  # noqa: ANN001 — sqlite3.Row of kb_docs
        """True when a kb_docs row passes the filters."""
        if row["doc_key"] in self.exclude_doc_keys:
            return False
        if not self.include_older and not row["is_current"]:
            return False
        if self.source_kinds and row["source_kind"] not in self.source_kinds:
            return False
        if self.languages and not set((row["lang"] or "").split("+")) & set(self.languages):
            return False
        if self.tiers and row["tier"] not in self.tiers:
            return False
        if self.edition and self.edition not in json.loads(row["editions"] or "[]"):
            return False
        return not (self.category and self.category not in json.loads(row["categories"] or "[]"))


@dataclass
class ChunkHit:
    """A matching chunk: `text == stored_text[start:end]`."""

    chunk_id: int
    start: int
    end: int
    text: str


@dataclass
class DocHit:
    """One search result (a document group)."""

    doc_key: str
    canon_key: str
    score: float
    title: str
    url: str
    source_kind: str
    tier: str
    lang: str
    is_current: bool
    document_id: int | None
    book_id: str | None
    page: int | None
    printed: str | None
    fetched_at: str
    via_translation: bool                 # found only through a search-only translation
    chunks: list[ChunkHit] = field(default_factory=list)
    also_at: list[str] = field(default_factory=list)


def build_match(query: str) -> str | None:
    """The FTS5 MATCH expression: quoted phrases are required, other content words are OR-ed."""
    phrases = [p.strip() for p in re.findall(r'"([^"]+)"', query) if p.strip()]
    rest = re.sub(r'"[^"]*"', " ", query)
    words = query_words(rest)
    parts = []
    for p in phrases:
        toks = re.findall(r"\w+", p.lower())
        if toks:
            parts.append('"' + " ".join(toks) + '"')
    if not parts and not words:
        return None
    ored = " OR ".join(f'"{w}"' for w in words)
    if parts and words:
        return " AND ".join(parts) + f" AND ({ored} OR " + parts[0] + ")"
    return " AND ".join(parts) if parts else ored


def search(idx: KnowledgeIndex, query: str, *, filters: SearchFilters | None = None, limit: int = 20,
           chunks_per_doc: int = 2, original_only: bool = False) -> list[DocHit]:
    """The best documents for a query, one per document group, best first. `original_only` leaves the search-only
    translations out (KB phase 4: original text vs translation)."""
    match = build_match(query)
    if match is None:
        return []
    filters = filters or SearchFilters()
    c = idx.conn
    rows = c.execute("SELECT chunk_id, doc_key, kind, bm25(kb_fts) AS s FROM kb_fts WHERE kb_fts MATCH ? "
                     "ORDER BY s LIMIT ?", (match, _CANDIDATES)).fetchall()
    docs: dict[str, object] = {}
    best: dict[str, tuple[float, list[int], bool]] = {}     # canon → (score, chunk ids, only via translation)
    winner: dict[str, str] = {}
    for chunk_id, doc_key, kind, score in rows:
        if original_only and kind != "original":
            continue
        if doc_key not in docs:
            docs[doc_key] = c.execute("SELECT * FROM kb_docs WHERE doc_key = ?", (doc_key,)).fetchone()
        d = docs[doc_key]
        if d is None or not filters.allows(d):
            continue
        canon = d["canon_key"]
        if canon not in best:
            best[canon] = (-float(score), [], True)
            winner[canon] = doc_key
        sc, ids, via_tr = best[canon]
        if winner[canon] == doc_key:
            if kind == "original" and chunk_id is not None and len(ids) < chunks_per_doc:
                ids.append(int(chunk_id))
            best[canon] = (sc, ids, via_tr and kind != "original")
    out: list[DocHit] = []
    for canon, (score, ids, via_tr) in sorted(best.items(), key=lambda kv: -kv[1][0])[:limit]:
        d = docs[winner[canon]]
        if not ids and chunks_per_doc:                    # matched through a translation only: show the start
            ids = [r[0] for r in c.execute("SELECT chunk_id FROM kb_chunks WHERE doc_key = ? ORDER BY ord LIMIT 1",
                                           (d["doc_key"],))]
        chunks = [ChunkHit(r[0], r[1], r[2], r[3]) for cid in ids
                  for r in c.execute('SELECT chunk_id, start, "end", text FROM kb_chunks WHERE chunk_id = ?', (cid,))]
        also = [r[0] for r in c.execute("SELECT url FROM kb_docs WHERE canon_key = ? AND doc_key != ? AND is_current = 1 "
                                        "AND norm_url != ?", (canon, d["doc_key"], d["norm_url"]))]
        out.append(DocHit(doc_key=d["doc_key"], canon_key=canon, score=score, title=d["title"] or d["url"],
                          url=d["url"], source_kind=d["source_kind"], tier=d["tier"], lang=d["lang"],
                          is_current=bool(d["is_current"]), document_id=d["document_id"], book_id=d["book_id"],
                          page=d["page"], printed=d["printed"], fetched_at=d["fetched_at"] or "",
                          via_translation=via_tr, chunks=chunks, also_at=sorted(set(also))))
    return out


def ranked_keys(idx: KnowledgeIndex, query: str, *, filters: SearchFilters | None = None,
                limit: int = 100, original_only: bool = False) -> list[str]:
    """Canon keys only, best first (for the benchmark)."""
    return [h.canon_key for h in search(idx, query, filters=filters, limit=limit, chunks_per_doc=0,
                                        original_only=original_only)]
