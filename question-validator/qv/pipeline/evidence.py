"""The evidence S4/S5 see and S8 counts: grounded passages with short ids, tiers and origin clusters.

Origin clusters (METHODOLOGY.md §5.2) decide independence: passages that credit the
same origin are one cluster; otherwise passages from the same publisher are one
cluster; near-identical wording across sites (copying) joins clusters. Counting rules
use clusters, never pages.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

from rapidfuzz import fuzz

#: Attributed origins that say nothing about where a fact comes from.
GENERIC_ORIGINS = {"", "none", "null", "unknown", "not specified", "not stated", "n/a", "na", "unspecified",
                   "the author", "author", "the page", "the website", "website", "page"}
#: Wording similarity (0–100) above which two passages from different sites count as copies.
COPY_SIMILARITY = 85.0
COPY_MIN_CHARS = 40
TIER_ORDER = {"P": 0, "S": 1, "T": 2}


@dataclass(frozen=True)
class EvidencePassage:
    """One grounded passage as shown to S4/S5 (`pid` like "P3") and counted by S8."""

    pid: str
    passage_id: int
    mode: str  # A (question) | B (note claims)
    target: str
    quote: str
    tier: str  # P | S | T (excluded documents never get here)
    frame_authority: bool
    publisher: str
    domain: str
    page_kind: str
    asserted_answer: str | None = None
    matches_option: str | None = None
    stance: str | None = None
    qualifiers: str | None = None
    as_of: str | None = None
    attributed_origin: str | None = None
    cluster: str = ""


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def origin_key(p: EvidencePassage) -> str:
    """The first-guess cluster key: attributed origin when it names one, else the publisher (or domain)."""
    origin = _norm(p.attributed_origin or "")
    if origin not in GENERIC_ORIGINS and _norm(p.publisher) != origin and _norm(p.domain) != origin:
        return "origin:" + origin
    return "publisher:" + (_norm(p.publisher) or _norm(p.domain))


def assign_clusters(passages: list[EvidencePassage]) -> list[EvidencePassage]:
    """Return the passages with `cluster` set to C1, C2, … in order of first appearance."""
    parent = list(range(len(passages)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    first_by_key: dict[str, int] = {}
    for i, p in enumerate(passages):
        key = origin_key(p)
        if key in first_by_key:
            union(i, first_by_key[key])
        else:
            first_by_key[key] = i
    for i, a in enumerate(passages):
        if len(a.quote) < COPY_MIN_CHARS:
            continue
        for j in range(i + 1, len(passages)):
            b = passages[j]
            if a.domain != b.domain and len(b.quote) >= COPY_MIN_CHARS and find(i) != find(j) \
                    and fuzz.ratio(_norm(a.quote), _norm(b.quote)) >= COPY_SIMILARITY:
                union(i, j)
    names: dict[int, str] = {}
    out = []
    for i, p in enumerate(passages):
        root = find(i)
        names.setdefault(root, f"C{len(names) + 1}")
        out.append(replace(p, cluster=names[root]))
    return out


def number_passages(rows: list[EvidencePassage]) -> list[EvidencePassage]:
    """Give passages stable short ids (mode A first, then by stored id) and assign clusters."""
    ordered = sorted(rows, key=lambda p: (p.mode, p.passage_id))
    return assign_clusters([replace(p, pid=f"P{i + 1}") for i, p in enumerate(ordered)])


def passage_line(p: EvidencePassage, *, with_target: bool = False) -> str:
    """`[P3] (publisher · page_kind · tier S · origin C2 …) "quote"` as in prompts/README.md."""
    meta = [p.publisher or p.domain, p.page_kind, f"tier {p.tier}", f"origin {p.cluster}"]
    if p.frame_authority:
        meta.append("frame authority")
    if p.as_of:
        meta.append(f"as of {p.as_of}")
    target = f" target {p.target}:" if with_target else ""
    line = f"[{p.pid}] ({' · '.join(meta)}){target} \"{p.quote}\""
    if p.qualifiers:
        line += f" — qualifiers: {p.qualifiers}"
    return line
