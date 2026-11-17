"""Websites: which sites refused research, which unlisted sites gave useful quotes, and the person's marks.

The person's marks (`source_marks`, append-only, newest per domain wins) are applied on top of
config/sources.yaml by `registry_with_marks` whenever research runs:

- `use` + tier P/S/T: the site gets that tier (a site the person trusts or added),
- `dont_use`: tier X — never fetched, never evidence,
- `needs_access`: not fetched until the person clears the mark (no point asking a site that refuses us),
- `clear`: back to what sources.yaml says.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select

from qv.db.models import Document, Fetch, Passage, QuestionDocument, SourceMark
from qv.db.session import Database
from qv.providers.search.base import domain_of
from qv.sources import Registry, load_registry

ACTIONS = ("use", "dont_use", "needs_access", "clear")
ACTION_LABEL = {"use": "✅ Use", "dont_use": "⛔ Don't use", "needs_access": "🔑 Needs special access",
                "clear": "↩ No mark"}
TIER_TEXT = {"P": "P · primary source", "S": "S · expert source", "T": "T · encyclopaedia / summary",
             "X": "X · never evidence"}

_DOMAIN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def normalize_domain(text: str) -> str:
    """A bare domain from a domain or an address ('https://www.Example.org/a' → 'example.org').

    Raises ValueError when it does not look like a domain.
    """
    t = (text or "").strip()
    host = domain_of(t) if "://" in t else t.split("/", 1)[0].lower().removeprefix("www.")
    host = host.strip(".")
    if not _DOMAIN.match(host):
        raise ValueError(f"'{text}' is not a website address (example: alislam.org)")
    return host


@dataclass(frozen=True)
class Mark:
    """The newest mark for a domain."""

    domain: str
    action: str
    tier: str | None
    note: str
    when: str


def marks(db: Database) -> dict[str, Mark]:
    """Newest mark per domain, without cleared ones."""
    newest: dict[str, Mark] = {}
    with db.session() as s:
        for m in s.scalars(select(SourceMark).order_by(SourceMark.id)):
            newest[m.domain] = Mark(m.domain, m.action, m.tier, m.note, m.created_at.strftime("%Y-%m-%d %H:%M"))
    return {d: m for d, m in newest.items() if m.action != "clear"}


def mark(db: Database, domain: str, action: str, *, tier: str | None = None, note: str = "") -> Mark:
    """Store a mark for a website (a domain or an address). `use` needs a tier P, S or T."""
    d = normalize_domain(domain)
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    if action == "use" and tier not in ("P", "S", "T"):
        raise ValueError("choose how much to trust the site: P, S or T")
    if action != "use":
        tier = None
    with db.session() as s:
        m = SourceMark(domain=d, action=action, tier=tier, note=(note or "").strip())
        s.add(m)
        s.flush()
        return Mark(d, action, tier, m.note, m.created_at.strftime("%Y-%m-%d %H:%M"))


def mark_history(db: Database, domain: str) -> list[Mark]:
    """Every mark for one domain, oldest first."""
    with db.session() as s:
        return [Mark(m.domain, m.action, m.tier, m.note, m.created_at.strftime("%Y-%m-%d %H:%M"))
                for m in s.scalars(select(SourceMark).where(SourceMark.domain == domain).order_by(SourceMark.id))]


def registry_with_marks(db: Database, base: Registry | None = None) -> Registry:
    """config/sources.yaml with the person's marks applied (the registry research uses)."""
    reg = (base or load_registry()).model_copy(deep=True)
    for d, m in marks(db).items():
        if m.action == "use":
            reg.domains[d] = m.tier
        elif m.action == "dont_use":
            reg.domains[d] = "X"
        elif m.action == "needs_access":
            reg.skip_domains.append(d)
    return reg


def problem_text(status: str, http: int | None, error: str | None) -> str | None:
    """A failed fetch in plain words; None for what is not a site problem (web PDFs → Book library)."""
    err = (error or "").lower()
    if status in ("not_text", "needs_ocr") or (err.startswith("pdf:")):
        return None
    if status == "robots_disallowed":
        return "asks robots not to read it"
    if status == "empty":
        return "no readable text (page built in the browser?)"
    if status == "too_large":
        return "page too large"
    if http in (401, 403):
        return f"refused ({http})"
    if http == 429:
        return "too many requests (429)"
    if http == 404:
        return "page not found (404)"
    if http == 202:
        return "page not ready (202)"
    if http and http >= 500:
        return f"server error ({http})"
    if "timeout" in err or "timed out" in err:
        return "timed out"
    return "could not be read" + (f" ({http})" if http else "")


def refused_sites(db: Database, registry: Registry | None = None) -> list[dict]:
    """Websites research could not read, one row per domain, most failures first."""
    registry = registry or registry_with_marks(db)
    current = marks(db)
    fails: dict[str, Counter] = defaultdict(Counter)
    last: dict[str, tuple] = {}
    ok: Counter = Counter()
    with db.session() as s:
        for f in s.scalars(select(Fetch).order_by(Fetch.fetched_at)):
            d = domain_of(f.url)
            if f.status == "ok":
                ok[d] += 1
                continue
            text = problem_text(f.status, f.http_status, f.error)
            if text is None:
                continue
            fails[d][text] += 1
            last[d] = (f.fetched_at.strftime("%Y-%m-%d"), f.url)
    rows = []
    for d, c in fails.items():
        m = current.get(d)
        rows.append({"site": d, "problem": ", ".join(f"{t} ×{n}" if n > 1 else t for t, n in c.most_common()),
                     "failed": sum(c.values()), "read ok": ok[d], "trust": registry.tier(d),
                     "your mark": ACTION_LABEL[m.action] if m else "", "last tried": last[d][0],
                     "example": last[d][1], "note": m.note if m else ""})
    rows.sort(key=lambda r: (bool(r["your mark"]), -r["failed"], r["site"]))
    return rows


def candidate_sites(db: Database, registry: Registry | None = None, *, base: Registry | None = None) -> list[dict]:
    """Websites research read that are not listed in sources.yaml and not marked yet — possibly good sources.

    Most quotes first. `pages judged weak` = pages S3 rated quiz / content farm / forum / machine-made, or
    about a different subject.
    """
    base = base or load_registry()
    registry = registry or registry_with_marks(db, base)
    current = marks(db)
    weak_kinds = ("quiz_or_trivia", "listicle_or_content_farm", "forum_or_social", "machine_generated_suspected")
    with db.session() as s:
        qd = list(s.execute(
            select(Document.domain, Document.final_url, Document.title, QuestionDocument.id,
                   QuestionDocument.question_id, QuestionDocument.page_kind, QuestionDocument.about_right_subject,
                   QuestionDocument.grounded_count, QuestionDocument.frame_authority)
            .join(QuestionDocument, QuestionDocument.document_id == Document.id)
            .where(Document.source_kind.in_(("web", "pdf")))))
    agg: dict[str, dict] = {}
    for dom, url, title, _qd_id, qid, kind, right, grounded, frame in qd:
        a = agg.setdefault(dom, {"pages": set(), "questions": set(), "quotes": 0, "weak": set(), "frame": False,
                                 "example": (grounded or 0, url, title)})
        a["pages"].add(url)
        a["questions"].add(qid)
        a["quotes"] += grounded or 0
        a["frame"] |= bool(frame)
        if kind in weak_kinds or right is False:
            a["weak"].add(url)
        if (grounded or 0) > a["example"][0]:
            a["example"] = (grounded or 0, url, title)
    rows = []
    for dom, a in agg.items():
        if _listed(base, dom) or dom in current or a["quotes"] == 0:
            continue
        rows.append({"site": dom, "quotes": a["quotes"], "pages read": len(a["pages"]),
                     "questions": len(a["questions"]), "pages judged weak": len(a["weak"]),
                     "trust now": registry.tier(dom), "frame authority": "yes" if a["frame"] else "",
                     "example": a["example"][1]})
    rows.sort(key=lambda r: (-r["quotes"], r["pages judged weak"], r["site"]))
    return rows


def _listed(reg: Registry, domain: str) -> bool:
    """True when sources.yaml names the domain or one of its parents."""
    parts = domain.split(".")
    return any(".".join(parts[i:]) in reg.domains for i in range(len(parts) - 1))


def marked_sites(db: Database) -> list[dict]:
    """The person's current marks (also sites they added), newest first."""
    rows = [{"site": m.domain, "your mark": ACTION_LABEL[m.action],
             "trust": TIER_TEXT.get(m.tier or ("X" if m.action == "dont_use" else ""), "not read for now"
                                    if m.action == "needs_access" else ""),
             "note": m.note, "when": m.when} for m in marks(db).values()]
    rows.sort(key=lambda r: r["when"], reverse=True)
    return rows


def passages_count(db: Database, domain: str) -> int:
    """How many grounded quotes came from a domain (for the page's detail line)."""
    with db.session() as s:
        return s.scalar(select(func.count(Passage.id)).join(Document, Document.id == Passage.document_id)
                        .where(Document.domain == domain)) or 0
