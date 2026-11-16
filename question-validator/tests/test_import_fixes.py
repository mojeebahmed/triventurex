"""One-click import fixes: only certain fixes, ids never change, the result passes the checks."""

from __future__ import annotations

from qv.config import load_profile
from qv.io.csv_format import parse_csv
from qv.services.datasets import check_bytes
from qv.services.import_fixes import suggest_fixes

PROFILE = load_profile("general")
HEAD = "id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category\n"


def errors(data: bytes) -> list[str]:
    return [i.code for i in check_bytes(data, PROFILE).report.issues if i.severity == "error"]


def test_nothing_to_fix_returns_the_same_bytes() -> None:
    data = (HEAD + "1,Capital of France?,multi,2,Lyon,Paris,Nice,Lille,easy,geo\n").encode()
    res = suggest_fixes(data, PROFILE)
    assert res.data == data and res.fixes == []


def test_answer_text_letter_case_and_spaces() -> None:
    data = (HEAD + '1,Capital of France?,Multi,Paris,Lyon,Paris,Nice,Lille,Easy,geo\n'
                   '2,Largest ocean?,multi,C,Atlantic,Indian,Pacific,Arctic,hard,geo\n'
                   '3,  Red planet? ,open,Mars,,,,,easy,space\n').encode()
    assert errors(data)
    res = suggest_fixes(data, PROFILE)
    rows = parse_csv(res.data).rows
    assert [r.get("answer") for r in rows] == ["2", "3", "Mars"]
    assert rows[0].get("type") == "multi" and rows[0].get("difficulty") == "easy"
    assert rows[2].cells[1] == "Red planet?"
    assert [r.get("id") for r in rows] == ["1", "2", "3"]
    assert errors(res.data) == []
    assert any("written as option 2" in f.what for f in res.fixes)


def test_ambiguous_answer_text_is_left_for_a_person() -> None:
    data = (HEAD + "1,Pick one,multi,Paris,Paris,Paris,Nice,Lille,easy,geo\n").encode()
    assert "answer" not in str([f.what for f in suggest_fixes(data, PROFILE).fixes])


def test_option_gap_moves_the_answer_with_its_text() -> None:
    data = (HEAD + "1,Capital of France?,multi,3,Lyon,,Paris,Nice,easy,geo\n").encode()
    rows = parse_csv(suggest_fixes(data, PROFILE).data).rows
    assert [rows[0].get(c) for c in ("opt_a", "opt_b", "opt_c", "opt_d", "answer")] == ["Lyon", "Paris", "Nice", "", "2"]


def test_header_rename_encoding_and_bom() -> None:
    data = b"\xef\xbb\xbf" + ("ID,Question,type,Correct Answer,opt_a,opt_b\r\n"
                              "1,Caf\xe9 means?,multi,2,Tea,Coffee\r\n").encode("cp1252")
    res = suggest_fixes(data, PROFILE)
    parsed = parse_csv(res.data)
    assert parsed.header[:4] == ("id", "question", "type", "answer")
    assert parsed.rows[0].get("question") == "Café means?" and not parsed.decode_error
    whats = " ".join(f.what for f in res.fixes)
    assert "BOM" in whats and "UTF-8" in whats and "'Correct Answer' to 'answer'" in whats


def test_comma_problems_are_not_touched() -> None:
    data = (HEAD + "1,Capital of France, really?,multi,Paris,Lyon,Paris,Nice,Lille,easy,geo\n").encode()
    assert suggest_fixes(data, PROFILE).data == data
