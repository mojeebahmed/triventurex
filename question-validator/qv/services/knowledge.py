"""Knowledge search page (KB phase 2): search everything collected, saved searches ("topics"), relevance judgements.

- Search runs on the knowledge index (`qv.kb`, a rebuildable cache); the stored text shown for a result is read
  from where it is kept (`documents.text`, or the book library's page text), never from the index.
- Topics (`topics`) are a name + search words + filters; they can be renamed and changed. A topic also lists the
  existing questions of every edition that match its words, with their current result.
- Relevance judgements (`relevance_labels`, append-only, newest per question + page wins, `clear` takes one back)
  belong to a question's exact content and are passed to `qv kb benchmark` as extra labels.

The web page only calls the functions here. Text from the index is untrusted: `marked_html` escapes everything.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from qv.db.models import Dataset, DatasetVersion, Document, QuestionRow, RelevanceLabel, Topic
from qv.db.session import Database
from qv.kb.index import KnowledgeIndex, index_path
from qv.kb.search import DocHit, SearchFilters, search
from qv.library import Library, query_words
from qv.services.datasets import get_version

LABELS = ("relevant", "not_relevant", "clear")
LABEL_TEXT = {"relevant": "✅ relevant", "not_relevant": "❌ not relevant", "clear": "no judgement"}
SOURCE_KIND_TEXT = {"web": "Web page", "wikipedia": "Wikipedia", "quran": "Qur'an verse", "book": "Book page",
                    "library": "Book page"}
#: Filter keys stored in `topics.filters_json` (the same names as `SearchFilters`).
FILTER_KEYS = ("source_kinds", "languages", "tiers", "edition", "category", "include_older")


# --- filters ---------------------------------------------------------------------------------------

def filters_from_dict(d: dict | None) -> SearchFilters:
    """SearchFilters from stored / page values; unknown keys and empty values are ignored."""
    d = d or {}
    lists = {k: [str(x) for x in d.get(k) or [] if str(x)] for k in ("source_kinds", "languages", "tiers")}
    return SearchFilters(**lists, edition=d.get("edition") or None, category=d.get("category") or None,
                         include_older=bool(d.get("include_older")))


def filters_to_dict(f: SearchFilters) -> dict:
    """The filters as plain JSON (only what is set), for `topics.filters_json`."""
    d = {k: v for k, v in asdict(f).items() if k in FILTER_KEYS}
    return {k: v for k, v in d.items() if v not in (None, [], False)}


def filters_text(d: dict) -> str:
    """The filters in words, for a table cell ('' = everything)."""
    parts = [", ".join(SOURCE_KIND_TEXT.get(k, k) for k in d.get("source_kinds", [])),
             ", ".join(d.get("languages", [])), "trust " + "/".join(d["tiers"]) if d.get("tiers") else "",
             d.get("edition") or "", d.get("category") or "", "older versions too" if d.get("include_older") else ""]
    return " · ".join(p for p in parts if p)


@dataclass
class FilterOptions:
    """What the filters can be set to (from the index)."""

    source_kinds: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    tiers: list[str] = field(default_factory=list)
    editions: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


def filter_options(idx: KnowledgeIndex) -> FilterOptions:
    """Values present in the index, sorted."""
    import json
    c = idx.conn
    kinds = sorted({r[0] for r in c.execute("SELECT DISTINCT source_kind FROM kb_docs") if r[0]})
    langs = sorted({part for r in c.execute("SELECT DISTINCT lang FROM kb_docs") if r[0] for part in r[0].split("+")})
    tiers = sorted({r[0] for r in c.execute("SELECT DISTINCT tier FROM kb_docs") if r[0]}, key="PSTX".find)
    eds, cats = set(), set()
    for e, k in c.execute("SELECT DISTINCT editions, categories FROM kb_docs"):
        eds.update(json.loads(e or "[]"))
        cats.update(json.loads(k or "[]"))
    return FilterOptions(kinds, langs, tiers, sorted(eds), sorted(cats))


# --- search ----------------------------------------------------------------------------------------

def open_index(data_dir: Path) -> KnowledgeIndex | None:
    """The knowledge index, or None when it has not been built yet."""
    return KnowledgeIndex.for_data_dir(data_dir) if index_path(data_dir).exists() else None


def page_label(h: DocHit) -> str:
    """'p. 12 (PDF 14)' for a book page, '' otherwise."""
    if h.page is None:
        return ""
    return f"p. {h.printed} (PDF {h.page})" if h.printed else f"PDF page {h.page}"


def best_passage(h: DocHit, words: list[str] | None = None, width: int = 220) -> str:
    """The best matching piece of the result on one line: ≤ `width` characters around the first search word."""
    if not h.chunks:
        return ""
    text = " ".join(h.chunks[0].text.split())
    if len(text) <= width:
        return text
    low = text.lower()
    found = [i for w in words or [] if (i := low.find(w)) >= 0]
    lo = max(0, min(found) - width // 4) if found else 0
    while 0 < lo < len(text) and not text[lo - 1].isspace():      # start at a word
        lo += 1
    hi = min(len(text), lo + width)
    piece = text[lo:hi]
    if hi < len(text):
        piece = piece.rsplit(" ", 1)[0] + " …"
    return ("… " if lo else "") + piece


def result_rows(hits: list[DocHit], words: list[str] | None = None) -> list[dict]:
    """Table rows for the page (plain text; the table marks the search words itself)."""
    return [{"document": h.title, "best passage": ("(found through its translation) " if h.via_translation else "")
             + best_passage(h, words), "type": SOURCE_KIND_TEXT.get(h.source_kind, h.source_kind), "trust": h.tier,
             "language": h.lang, "page": page_label(h), "date": (h.fetched_at or "")[:10],
             "older version": "" if h.is_current else "older",
             "also at": ", ".join(h.also_at)} for h in hits]


def run_search(data_dir: Path, query: str, filters: SearchFilters | None = None, *, limit: int = 50
               ) -> list[DocHit]:
    """Search the knowledge index ([] when the index is missing or the query has no searchable word)."""
    idx = open_index(data_dir)
    if idx is None:
        return []
    try:
        return search(idx, query, filters=filters, limit=limit)
    finally:
        idx.close()


@dataclass
class StoredText:
    """The stored text of a result and where it comes from."""

    doc_key: str
    title: str
    text: str
    link: str | None            # web address to open (http/https only), or the book's PDF at its page
    where: str                  # in words: the address, or book + page


def safe_link(url: str | None) -> str | None:
    """The address when it is a plain web address, else None (stored addresses are untrusted)."""
    return url if url and re.match(r"^https?://[^\s<>\"']+$", url) else None


def stored_text(db: Database, data_dir: Path, doc_key: str, *, library: Library | None = None
                ) -> StoredText | None:
    """The full stored text of a result: `documents.text` or the book library's page text."""
    m = re.fullmatch(r"book:([a-z0-9-]+)/p(\d+)", doc_key)
    if m:
        lib = library or Library(data_dir)
        book_id, page = m.group(1), int(m.group(2))
        hit = lib.page(book_id, page) if book_id in lib.books else None
        if hit is None:
            return None
        src = safe_link(lib.books[book_id].source_url)
        return StoredText(doc_key, lib.title_for(hit), hit.text, f"{src}#page={page}" if src else None,
                          lib.title_for(hit))
    m = re.fullmatch(r"doc:(\d+)", doc_key)
    if not m:
        return None
    with db.session() as s:
        d = s.get(Document, int(m.group(1)))
        if d is None:
            return None
        return StoredText(doc_key, d.title or d.final_url, d.text, safe_link(d.final_url), d.final_url)


def marked_html(text: str, words: list[str], spans: list[tuple[int, int]] | None = None) -> str:
    """HTML of a stored text: every search word in <mark>, the given passages (character offsets) in a
    <span class="qv-hit">. Everything is escaped — the text is untrusted."""
    pattern = (re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")",
                          re.IGNORECASE) if words else None)

    def esc(part: str) -> str:
        out = html.escape(part)
        return pattern.sub(r"<mark>\1</mark>", out) if pattern else out

    cuts = sorted({(max(0, a), min(len(text), b)) for a, b in spans or [] if a < b})
    out, at = [], 0
    for a, b in cuts:
        if a < at:                       # overlapping passages: continue after the previous one
            a = at
        if a >= b:
            continue
        out.append(esc(text[at:a]))
        out.append(f"<span class='qv-hit'>{esc(text[a:b])}</span>")
        at = b
    out.append(esc(text[at:]))
    return "".join(out)


# --- topics (saved searches) -----------------------------------------------------------------------

@dataclass(frozen=True)
class TopicView:
    """A saved search."""

    id: int
    name: str
    query: str
    filters: dict
    created: str
    updated: str


def _view(t: Topic) -> TopicView:
    return TopicView(t.id, t.name, t.query, dict(t.filters_json or {}), str(t.created_at)[:16],
                     str(t.updated_at)[:16])


def _clean_name(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("A topic needs a name")
    if len(name) > 200:
        raise ValueError("A topic name can have at most 200 characters")
    return name


def save_topic(db: Database, name: str, query: str, filters: SearchFilters | dict | None = None) -> TopicView:
    """A new topic. Raises ValueError for an empty or already used name, or a search without words."""
    name = _clean_name(name)
    if not query_words(query):
        raise ValueError("Type the search words first")
    fd = filters_to_dict(filters if isinstance(filters, SearchFilters) else filters_from_dict(filters))
    with db.session() as s:
        if s.scalar(select(Topic.id).where(Topic.name == name)) is not None:
            raise ValueError(f"There is already a topic called '{name}'")
        t = Topic(name=name, query=query.strip(), filters_json=fd)
        s.add(t)
        s.flush()
        return _view(t)


def update_topic(db: Database, topic_id: int, *, name: str | None = None, query: str | None = None,
                 filters: SearchFilters | dict | None = None) -> TopicView:
    """Rename a topic and/or change its search. Raises ValueError (unknown topic, name taken, empty search)."""
    with db.session() as s:
        t = s.get(Topic, topic_id)
        if t is None:
            raise ValueError("This topic no longer exists")
        if name is not None:
            name = _clean_name(name)
            if s.scalar(select(Topic.id).where(Topic.name == name, Topic.id != topic_id)) is not None:
                raise ValueError(f"There is already a topic called '{name}'")
            t.name = name
        if query is not None:
            if not query_words(query):
                raise ValueError("Type the search words first")
            t.query = query.strip()
        if filters is not None:
            t.filters_json = filters_to_dict(filters if isinstance(filters, SearchFilters)
                                             else filters_from_dict(filters))
        t.updated_at = datetime.now(UTC)
        s.flush()
        return _view(t)


def delete_topic(db: Database, topic_id: int) -> None:
    """Remove a topic (only the saved search; nothing it found is touched)."""
    with db.session() as s:
        t = s.get(Topic, topic_id)
        if t is not None:
            s.delete(t)


def list_topics(db: Database) -> list[TopicView]:
    """All topics by name."""
    with db.session() as s:
        return [_view(t) for t in s.scalars(select(Topic).order_by(Topic.name))]


def get_topic(db: Database, topic_id: int) -> TopicView | None:
    """One topic."""
    with db.session() as s:
        t = s.get(Topic, topic_id)
        return _view(t) if t else None


# --- questions that match a search -----------------------------------------------------------------

def _question_text(q: QuestionRow) -> str:
    return " ".join([q.question, q.resolved_answer_text or q.answer, q.opt_a, q.opt_b, q.opt_c, q.opt_d, q.note,
                     q.category, q.subcategory, q.topic])


def question_score(text: str, query: str) -> int:
    """How many of the search words are in the text (0 = no match); a "quoted phrase" must be in it as written."""
    low = " ".join(re.findall(r"\w+", text.lower()))
    for phrase in re.findall(r'"([^"]+)"', query):
        toks = re.findall(r"\w+", phrase.lower())
        if toks and not re.search(r"\b" + r"\s+".join(map(re.escape, toks)) + r"\b", low):
            return 0
    words = query_words(re.sub(r'"[^"]*"', " ", query)) or query_words(query)
    have = set(low.split())
    return sum(1 for w in words if w in have or any(h.startswith(w) for h in have if len(w) >= 4))


def matching_questions(db: Database, query: str, *, include_eval: bool = False, limit: int = 100) -> list[dict]:
    """Questions of every file's latest version that contain the search words, best first, with their result."""
    from qv.services import workflow
    if not query_words(query):
        return []
    out = []
    for name in workflow.dataset_names(db, include_eval=include_eval):
        try:
            states = workflow.question_states(db, name)
        except Exception:  # noqa: BLE001 — a file without a version simply has no questions
            continue
        for st in states:
            text = " ".join([st.question, st.answer_text, *st.options, st.note, st.category, st.subcategory,
                             st.topic])
            score = question_score(text, query)
            if score:
                out.append({"id": st.ext_id, "question": st.question, "answer": st.answer_text,
                            "status": workflow.STATUS_LABEL[st.status], "result": st.verdict,
                            "category": " > ".join(p for p in (st.category, st.subcategory, st.topic) if p),
                            "file": name, "_score": score})
    out.sort(key=lambda r: -r["_score"])
    return [{k: v for k, v in r.items() if k != "_score"} for r in out[:limit]]


# --- relevance judgements --------------------------------------------------------------------------

@dataclass(frozen=True)
class QuestionRef:
    """A question of a file's latest version, for judging."""

    dataset: str
    ext_id: str
    content_hash: str
    question: str


def find_question(db: Database, dataset: str, ext_id: str) -> QuestionRef | None:
    """A question of the file's latest version by its id, or None."""
    with db.session() as s:
        try:
            v = get_version(s, dataset)
        except Exception:  # noqa: BLE001 — unknown file
            return None
        q = s.scalar(select(QuestionRow).where(QuestionRow.dataset_version_id == v.id,
                                               QuestionRow.ext_id == str(ext_id).strip()))
        return QuestionRef(dataset, q.ext_id, q.content_hash, q.question) if q else None


def add_label(db: Database, q: QuestionRef, doc_key: str, label: str, *, who: str = "you") -> None:
    """Store a judgement (append-only). Raises ValueError for an unknown label or doc key."""
    if label not in LABELS:
        raise ValueError(f"Unknown judgement '{label}'")
    if not re.fullmatch(r"doc:\d+|book:[a-z0-9-]+/p\d+", doc_key):
        raise ValueError(f"Unknown page '{doc_key}'")
    with db.session() as s:
        ds = s.scalar(select(Dataset.id).where(Dataset.name == q.dataset))
        if ds is None:
            raise ValueError(f"No file '{q.dataset}'")
        s.add(RelevanceLabel(dataset_id=ds, ext_id=q.ext_id, content_hash=q.content_hash, doc_key=doc_key,
                             label=label, who=who))


def _newest_labels(db: Database) -> dict[tuple[int, str, str, str], RelevanceLabel]:
    with db.session() as s:
        newest = {}
        for r in s.scalars(select(RelevanceLabel).order_by(RelevanceLabel.id)):
            newest[(r.dataset_id, r.ext_id, r.content_hash, r.doc_key)] = r
        for r in newest.values():
            s.expunge(r)
    return {k: v for k, v in newest.items() if v.label != "clear"}


def label_for(db: Database, q: QuestionRef, doc_key: str) -> str | None:
    """The current judgement of a page for a question (None = not judged)."""
    with db.session() as s:
        ds = s.scalar(select(Dataset.id).where(Dataset.name == q.dataset))
        r = s.scalar(select(RelevanceLabel).where(
            RelevanceLabel.dataset_id == ds, RelevanceLabel.ext_id == q.ext_id,
            RelevanceLabel.content_hash == q.content_hash, RelevanceLabel.doc_key == doc_key)
            .order_by(RelevanceLabel.id.desc()).limit(1))
        return r.label if r is not None and r.label != "clear" else None


def labels_for_doc(db: Database, doc_key: str) -> list[dict]:
    """Current judgements of one page: [{file, id, judgement, who, when}]."""
    names = _dataset_names(db)
    return [{"file": names.get(k[0], "?"), "id": k[1], "judgement": LABEL_TEXT[r.label], "who": r.who,
             "when": str(r.created_at)[:16]} for k, r in _newest_labels(db).items() if k[3] == doc_key]


def _dataset_names(db: Database) -> dict[int, str]:
    with db.session() as s:
        return dict(s.execute(select(Dataset.id, Dataset.name)).all())


def benchmark_labels(db: Database) -> list[tuple[str, str, str]]:
    """The current judgements as `qv kb benchmark` extra labels: (question key "<edition>#<id>@<hash8>", doc key,
    'relevant' | 'not_relevant'). The edition is the profile of the version that holds that exact question."""
    newest = _newest_labels(db)
    if not newest:
        return []
    with db.session() as s:
        profiles: dict[tuple[int, str, str], str] = {}
        for ds, ext, h, prof in s.execute(select(DatasetVersion.dataset_id, QuestionRow.ext_id,
                                                 QuestionRow.content_hash, DatasetVersion.profile)
                                          .join(DatasetVersion, DatasetVersion.id == QuestionRow.dataset_version_id)
                                          .order_by(DatasetVersion.id)):
            profiles.setdefault((ds, ext, h), prof)
    out = []
    for (ds, ext, h, doc_key), r in newest.items():
        prof = profiles.get((ds, ext, h))
        if prof:
            out.append((f"{prof}#{ext}@{h[:8]}", doc_key, r.label))
    return out
