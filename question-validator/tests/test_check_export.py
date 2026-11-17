"""Check columns of a game export: the column writer, the hash shared with the game, the values."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from qv.domain.question import CHECK_COLUMNS, check_hash
from qv.io.csv_format import PatchError, parse_csv, set_columns
from qv.pipeline.structural import run_structural_checks
from qv.config import load_profile
from qv.services.check_export import how_checked, one_line, short_quote, source_of

ROOT = Path(__file__).resolve().parents[2]
BASE = (b"id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note\r\n"
        b'1,"Where, exactly?",open,Here,,,,,easy,c,s,t,\r\n'
        b"\r\n"
        b"2,Two?,multi,1,yes,no,,,hard,c,s,t,a note\r\n")


def test_set_columns_adds_fills_and_keeps_other_bytes() -> None:
    out = set_columns(BASE, ("checked", "sources"), {2: {"checked": "verified", "sources": "a, b | c"}})
    lines = out.split(b"\r\n")
    assert lines[0].endswith(b",note,checked,sources")
    assert lines[1] == b'1,"Where, exactly?",open,Here,,,,,easy,c,s,t,,verified,"a, b | c"'
    assert lines[2] == b""                                   # blank line untouched
    assert lines[3] == b"2,Two?,multi,1,yes,no,,,hard,c,s,t,a note,,"
    # a second export overwrites the old values and clears rows that are no longer checked
    again = set_columns(out, ("checked", "sources"), {5: {"checked": "x"}})
    rows = parse_csv(again).rows
    assert [r.get("checked") for r in rows] == ["", ""] and parse_csv(again).header == parse_csv(out).header


def test_set_columns_refuses_a_short_row() -> None:
    with pytest.raises(PatchError, match="fields"):
        set_columns(BASE.replace(b",a note", b""), ("checked",), {})


def test_check_columns_are_not_unknown_columns() -> None:
    out = set_columns(BASE, CHECK_COLUMNS, {})
    report = run_structural_checks(parse_csv(out), load_profile("swab-quest").structural)
    assert not [i for i in report.issues if i.column in CHECK_COLUMNS]


def test_check_hash_matches_the_game() -> None:
    """scripts/content.js → checkHash must give the same value (it warns about questions changed after a check)."""
    values = {"question": "Wer? \u00e9", "type": "multi", "answer": "1", "opt_a": "a", "opt_b": "b", "note": "n"}
    script = ("const {checkHash}=require('./scripts/content.js');"
              "process.stdout.write(checkHash(JSON.parse(process.argv[1])))")
    got = subprocess.run(["node", "-e", script, json.dumps(values)], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout
    assert got == check_hash(values) and len(got) == 10


def test_quote_and_names() -> None:
    assert one_line("a\n b |c") == "a b /c"
    long = "word " * 80
    q = short_quote(long)
    assert len(q) <= 242 and q.endswith(" …")

    class Doc:
        def __init__(self, kind: str, title: str, url: str, domain: str = "www.example.org") -> None:
            self.source_kind, self.title, self.final_url, self.domain = kind, title, url, domain

    assert source_of(Doc("library", "Basics (Hadi), p. 3 [PDF p. 9]", "library://b/p9")).name == "Basics (Hadi), p. 3"
    assert source_of(Doc("library", "x", "library://b/p9")).link == ""
    assert source_of(Doc("quran", "The Holy Quran 11:25 – Hud", "https://q/11:25")).name == "The Holy Quran 11:25"
    assert source_of(Doc("wikipedia", "Mecca", "https://w/Mecca")).name == "Wikipedia: Mecca"
    assert source_of(Doc("web", "t", "https://www.example.org/a")).name == "example.org"


def test_how_checked_in_plain_words() -> None:
    assert how_checked("verified", 3, 2, True) == ("Checked against 2 independent sources; "
                                                   "the answer was also found without seeing it")
    assert how_checked("verified", 1, 1, False) == "Checked against 1 independent source"
    assert how_checked("confirmed", 0, 0, False) == "Confirmed by a reviewer"
    assert how_checked("edited", 2, 2, True).startswith("Corrected")
