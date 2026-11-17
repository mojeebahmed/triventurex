"""The check columns of a game export: how each ready question was checked.

`corrected` and `ready` exports carry `CHECK_COLUMNS` (qv.domain.question) so the game's Questions tab
and the Academy can show it. Only questions ready for the game (verified automatically, confirmed or
edited by a person) get values; every other row gets empty ones. Everything is built from stored data
in code — no model is asked — and source text is cleaned to one line (the game's CSV has no line breaks).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select

from qv.db.models import Document, Passage, QuestionDocument, Validation
from qv.domain.question import CHECK_COLUMNS, check_hash
from qv.io.csv_format import parse_csv, set_columns

#: `checked` values, from the workflow status.
CHECKED_VALUE = {"verified": "verified", "approved": "confirmed", "edited": "edited"}
MAX_SOURCES = 3
MAX_QUOTE = 240
SEP = " | "


@dataclass(frozen=True)
class Source:
    """One source as the game shows it: a short name and a link (empty for a book page)."""

    name: str
    link: str


def one_line(text: str) -> str:
    """Whitespace runs (line breaks included) → one space; `|` is the list separator, so it becomes `/`."""
    return re.sub(r"\s+", " ", text or "").replace("|", "/").strip()


def short_quote(text: str, limit: int = MAX_QUOTE) -> str:
    """The quote on one line, cut at a word boundary with … when longer than `limit`."""
    text = one_line(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.")
    return cut + " …"


def source_of(doc: Document) -> Source:
    """Short name + link for a stored document."""
    link = doc.final_url if doc.final_url.startswith(("http://", "https://")) else ""
    title = one_line(doc.title)
    if doc.source_kind == "library":
        return Source(title.split(" [")[0] or doc.domain, "")
    if doc.source_kind == "quran":
        return Source(title.split(" – ")[0] or "The Holy Quran", link)
    if doc.source_kind == "wikipedia":
        return Source(f"Wikipedia: {title}" if title else "Wikipedia", link)
    return Source(doc.domain.removeprefix("www."), link)


def how_checked(checked: str, n_sources: int, independent: int, blind_matched: bool) -> str:
    """One line in plain words for the game."""
    if checked == "edited":
        return "Corrected by a reviewer after the automatic check"
    if checked == "confirmed":
        found = f"; {n_sources} source{'s' if n_sources != 1 else ''} found" if n_sources else ""
        return f"Confirmed by a reviewer{found}"
    words = (f"Checked against {independent} independent source{'s' if independent != 1 else ''}"
             if independent else "Checked against sources")
    return words + ("; the answer was also found without seeing it" if blind_matched else "")


def check_values(session, validation: Validation | None, checked: str) -> dict[str, str]:  # noqa: ANN001
    """The check columns (without `check_hash`) for one ready question."""
    out = {"checked": checked}
    if validation is None:
        return out
    out["checked_on"] = validation.created_at.date().isoformat()
    pmap = validation.passage_map_json or {}
    support = (validation.support_json or {}).get("key") or {}
    labels = [p for p in support.get("passages_for", []) if p in pmap]
    ids = [pmap[p]["passage_id"] for p in labels]
    clusters = {pmap[p].get("cluster") for p in labels if pmap[p].get("cluster")}
    rows = []
    if ids and checked != "edited":          # an edited answer is no longer the one these passages support
        rows = list(session.execute(
            select(Passage, Document, QuestionDocument.effective_tier)
            .join(Document, Document.id == Passage.document_id)
            .join(QuestionDocument, QuestionDocument.id == Passage.question_document_id)
            .where(Passage.id.in_(ids))
            .order_by(func.coalesce(QuestionDocument.effective_tier, QuestionDocument.registry_tier),
                      Passage.is_primary_for_claim.desc(), Passage.id)))
    sources: list[Source] = []
    for _, doc, _ in rows:
        src = source_of(doc)
        if src.name and all(s.name != src.name for s in sources):
            sources.append(src)
    sources = sources[:MAX_SOURCES]
    if sources:
        out["sources"] = SEP.join(s.name for s in sources)
        out["source_links"] = SEP.join(s.link for s in sources) if any(s.link for s in sources) else ""
    if rows:
        out["source_quote"] = short_quote(rows[0][0].quote)
        out["as_of"] = next((one_line(p.as_of) for p, _, _ in rows if p.as_of), "")
    out["check_how"] = how_checked(checked, len(sources), len(clusters) if checked != "edited" else 0,
                                   bool(validation.blind_matches_key))
    return out


def add_check_columns(db, data: bytes, states: list) -> bytes:  # noqa: ANN001
    """Fill the check columns of an exported file (`data`) from the questions' states."""
    parsed = parse_csv(data)
    by_id = {st.ext_id: st for st in states}
    values: dict[int, dict[str, str]] = {}
    with db.session() as s:
        for row in parsed.rows:
            st = by_id.get(row.get("id"))
            checked = CHECKED_VALUE.get(st.status, "") if st else ""
            if not checked:
                continue
            val = s.get(Validation, st.validation_id) if st.validation_id else None
            cols = check_values(s, val, checked)
            cols["check_hash"] = check_hash({c: row.get(c) for c in parsed.header})
            values[row.line_no] = cols
    return set_columns(data, CHECK_COLUMNS, values)
