"""Websites: the person's marks on sites, applied on top of sources.yaml; refused and candidate site lists."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from qv.db.models import Fetch
from qv.db.session import Database
from qv.services import websites as ws
from qv.sources import Registry


def reg() -> Registry:
    """A small registry like sources.yaml."""
    return Registry(version=1, default_tier="T", domains={"alislam.org": "S", "quizlet.com": "X"})


@pytest.mark.parametrize("given, want", [
    ("Example.org", "example.org"), ("https://www.example.org/a/b?c=1", "example.org"),
    ("www.kids.example.org/page", "kids.example.org"), (" example.org ", "example.org")])
def test_normalize_domain(given: str, want: str) -> None:
    assert ws.normalize_domain(given) == want


@pytest.mark.parametrize("bad", ["", "not a site", "localhost", "http://", "exa mple.org"])
def test_normalize_domain_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        ws.normalize_domain(bad)


def test_marks_apply_on_top_of_the_registry(db: Database) -> None:
    ws.mark(db, "https://www.ahmadipedia.org/x", "use", tier="S", note="community wiki")
    ws.mark(db, "britannica.com", "needs_access")
    ws.mark(db, "alislam.org", "dont_use")
    ws.mark(db, "alislam.org", "clear")          # newest wins: back to sources.yaml
    ws.mark(db, "spam.example", "dont_use")
    r = ws.registry_with_marks(db, reg())
    assert r.tier("ahmadipedia.org") == "S"
    assert r.tier("https://alislam.org/q") == "S"
    assert r.tier("spam.example") == "X" and r.is_excluded("https://spam.example/p")
    assert r.is_skipped("https://kids.britannica.com/x") and r.is_excluded("https://britannica.com/a")
    assert r.tier("britannica.com") == "T"       # skipped, but its trust is unchanged
    assert set(ws.marks(db)) == {"ahmadipedia.org", "britannica.com", "spam.example"}
    assert [m.action for m in ws.mark_history(db, "alislam.org")] == ["dont_use", "clear"]


def test_mark_needs_a_tier_for_use(db: Database) -> None:
    with pytest.raises(ValueError):
        ws.mark(db, "example.org", "use")
    with pytest.raises(ValueError):
        ws.mark(db, "example.org", "use", tier="X")
    with pytest.raises(ValueError):
        ws.mark(db, "example.org", "maybe")


def test_marks_are_append_only(db: Database) -> None:
    ws.mark(db, "example.org", "dont_use")
    with db.session() as s, pytest.raises(Exception, match="append-only"):
        s.execute(text("UPDATE source_marks SET action = 'use'"))
    with db.session() as s, pytest.raises(Exception, match="append-only"):
        s.execute(text("DELETE FROM source_marks"))


def test_refused_sites_group_by_domain_and_skip_pdfs(db: Database) -> None:
    with db.session() as s:
        s.add_all([Fetch(url="https://www.britannica.com/a", status="error", http_status=403),
                   Fetch(url="https://britannica.com/b", status="error", http_status=403),
                   Fetch(url="https://alislam.org/x", status="error", http_status=500),
                   Fetch(url="https://alislam.org/y", status="ok", http_status=200),
                   Fetch(url="https://files.example.org/book.pdf", status="not_text", http_status=200,
                         error="content-type application/pdf"),
                   Fetch(url="https://slow.example.org/", status="error", error="timeout")])
    ws.mark(db, "alislam.org", "needs_access", note="ask the webmaster")
    rows = {r["site"]: r for r in ws.refused_sites(db, reg())}
    assert set(rows) == {"britannica.com", "alislam.org", "slow.example.org"}
    assert rows["britannica.com"]["problem"] == "refused (403) ×2"
    assert rows["alislam.org"]["read ok"] == 1 and rows["alislam.org"]["note"] == "ask the webmaster"
    assert rows["slow.example.org"]["problem"] == "timed out"
    assert list(rows)[-1] == "alislam.org"        # marked sites go last


def test_problem_text() -> None:
    assert ws.problem_text("robots_disallowed", None, None) == "asks robots not to read it"
    assert ws.problem_text("error", 429, None) == "too many requests (429)"
    assert ws.problem_text("not_text", 200, "content-type application/pdf") is None
