"""S0 structural checks: every code, game parity, and the real editions."""

from __future__ import annotations

import json
import subprocess

import pytest

from qv.config import StructuralRules, load_profile
from qv.domain.structural import IssueCode, Severity
from qv.io.csv_format import parse_csv
from qv.pipeline.structural import normalise_text, run_structural_checks
from tests.conftest import EDITIONS, FIXTURES, GOOD_ROWS, REPO_ROOT, edition_bytes, make_csv


def codes(data: bytes, rules: StructuralRules | None = None) -> dict[IssueCode, list]:
    """Issues grouped by code."""
    out: dict[IssueCode, list] = {}
    for i in run_structural_checks(parse_csv(data), rules).issues:
        out.setdefault(i.code, []).append(i)
    return out


def test_clean_file_has_no_errors_or_warnings(good_csv: bytes) -> None:
    report = run_structural_checks(parse_csv(good_csv))
    assert report.ok_for_game
    assert report.count(Severity.WARNING) == 0
    assert (report.row_count, report.multi_count, report.open_count) == (3, 2, 1)
    # Only the 3-option question is reported, as info
    assert [i.code for i in report.issues] == [IssueCode.FEWER_THAN_FOUR_OPTIONS]


@pytest.mark.parametrize("row,code,severity", [
    (",Q?,open,A,,,,,easy,c,,,", IssueCode.INVALID_ID, Severity.ERROR),
    ("x7,Q?,open,A,,,,,easy,c,,,", IssueCode.INVALID_ID, Severity.ERROR),
    ("9,,open,A,,,,,easy,c,,,", IssueCode.EMPTY_QUESTION, Severity.ERROR),
    ("9,Q?,quiz,A,,,,,easy,c,,,", IssueCode.INVALID_TYPE, Severity.ERROR),
    ("9,Q?,open,A,,,,,medium,c,,,", IssueCode.INVALID_DIFFICULTY, Severity.ERROR),
    ("9,Q?,open,,,,,,easy,c,,,", IssueCode.OPEN_NO_ANSWER, Severity.ERROR),
    ("9,Q?,open,A,x,,,,easy,c,,,", IssueCode.OPEN_HAS_OPTIONS, Severity.WARNING),
    ("9,Q?,multi,1,Only,,,,easy,c,,,", IssueCode.MULTI_TOO_FEW_OPTIONS, Severity.ERROR),
    ("9,Q?,multi,5,A,B,C,D,easy,c,,,", IssueCode.MULTI_ANSWER_NOT_INDEX, Severity.ERROR),
    ("9,Q?,multi,B,A,B,C,D,easy,c,,,", IssueCode.MULTI_ANSWER_NOT_INDEX, Severity.ERROR),
    ("9,Q?,multi,4,A,B,C,,easy,c,,,", IssueCode.MULTI_ANSWER_EMPTY_OPTION, Severity.ERROR),
    ("9,Q?,multi,1,A,a ,C,D,easy,c,,,", IssueCode.DUPLICATE_OPTIONS, Severity.WARNING),
    ("9,Q?,multi,1,A,,C,D,easy,c,,,", IssueCode.OPTION_GAP, Severity.WARNING),
    ("9,Q?,multi,3,A,,C,D,easy,c,,,", IssueCode.OPTION_GAP, Severity.ERROR),
    ("9,Q?,open,A,,,,,easy,,,,", IssueCode.EMPTY_CATEGORY, Severity.INFO),
    ("9,Q?,open,A,,,,,easy,c,,,,extra", IssueCode.COLUMN_COUNT, Severity.ERROR),
    ('9,"Q?,open,A,,,,,easy,c,,,', IssueCode.UNBALANCED_QUOTES, Severity.ERROR),
    ("9, Q? ,open,A,,,,,easy,c,,,", IssueCode.WHITESPACE, Severity.INFO),
])
def test_each_row_code(row: str, code: IssueCode, severity: Severity) -> None:
    found = codes(make_csv(row))
    assert code in found, found
    assert found[code][0].severity == severity
    assert found[code][0].line_no == 2


def test_option_gap_names_the_option_the_game_would_mark() -> None:
    issue = codes(make_csv("9,Q?,multi,3,Right?,,Correct,Other,easy,c,,,"))[IssueCode.OPTION_GAP][0]
    assert '"Other" as correct instead of "Correct"' in issue.message


def test_duplicate_id() -> None:
    found = codes(make_csv(GOOD_ROWS[0], GOOD_ROWS[0].replace("France", "Spain")))
    assert found[IssueCode.DUPLICATE_ID][0].line_no == 3
    assert "also on line 2" in found[IssueCode.DUPLICATE_ID][0].message


def test_no_topic_only_when_topics_are_used() -> None:
    assert IssueCode.NO_TOPIC not in codes(make_csv("1,Q?,open,A,,,,,easy,c,,,"))
    found = codes(make_csv("1,Q?,open,A,,,,,easy,c,,t,", "2,R?,open,B,,,,,easy,c,,,"))
    assert [i.line_no for i in found[IssueCode.NO_TOPIC]] == [3]


def test_file_level_checks() -> None:
    data = b"\xef\xbb\xbf" + make_csv("1,Q?,open,A,,,,,easy,c,,,,", header="id,question,type,answer,"
                                      "opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note,source")
    found = codes(data)
    assert found[IssueCode.BOM][0].severity == Severity.INFO
    assert found[IssueCode.UNKNOWN_COLUMN][0].column == "source"


def test_missing_required_column_is_error_and_skips_row_checks() -> None:
    found = codes(make_csv("1,Q?", header="id,question"))
    missing = {i.column: i.severity for i in found[IssueCode.MISSING_COLUMN]}
    assert missing["type"] == Severity.ERROR and missing["note"] == Severity.WARNING
    assert IssueCode.INVALID_TYPE not in found


def test_duplicate_column_and_empty_header() -> None:
    assert IssueCode.DUPLICATE_COLUMN in codes(make_csv("1,Q?,open,A,,,,,easy,c,,,,x", header=
        "id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note,note"))
    assert IssueCode.EMPTY_FILE in codes(b"\n1,Q?,open,A\n")
    assert IssueCode.EMPTY_FILE in codes(b"")


def test_not_utf8() -> None:
    data = make_csv("1,Caf\xe9?,open,A,,,,,easy,c,,,").replace(b"\xc3\xa9", b"\xe9")
    assert codes(data)[IssueCode.NOT_UTF8][0].severity == Severity.ERROR


def test_difficulties_come_from_the_profile() -> None:
    row = "9,Q?,open,A,,,,,medium,c,,,"
    rules = StructuralRules(allowed_difficulties=["easy", "medium", "hard"])
    assert IssueCode.INVALID_DIFFICULTY not in codes(make_csv(row), rules)


class TestDuplicates:
    """Exact and near-duplicate questions."""

    def test_exact_duplicate_ignores_case_and_punctuation(self) -> None:
        found = codes(make_csv("1,What is X?,open,A,,,,,easy,c,,,", "2,what is x,open,B,,,,,easy,c,,,"))
        issue = found[IssueCode.EXACT_DUPLICATE_QUESTION][0]
        assert issue.ext_id == "2" and issue.related_ext_ids == ("1",)

    def test_near_duplicate_with_same_answer(self) -> None:
        found = codes(make_csv(
            "1,Who was the mother of Hadhrat Isa (Jesus)?,open,Hadhrat Maryam,,,,,easy,c,,,",
            "2,Who was the mother of Hadhrat Isa (Jesus)(as)?,open,Hadhrat Maryam,,,,,easy,c,,,"))
        issue = found[IssueCode.NEAR_DUPLICATE_QUESTION][0]
        assert issue.severity == Severity.WARNING and issue.related_ext_ids == ("1",)

    def test_template_questions_with_different_answers_are_not_duplicates(self) -> None:
        found = codes(make_csv("1,What is the capital of Germany?,open,Berlin,,,,,easy,c,,,",
                               "2,What is the capital of Romania?,open,Bucharest,,,,,easy,c,,,"))
        assert IssueCode.NEAR_DUPLICATE_QUESTION not in found

    def test_different_numbers_are_different_answers(self) -> None:
        found = codes(make_csv(
            "1,How old was the Holy Prophet when his mother died?,open,6 years old,,,,,easy,c,,,",
            "2,How old was the Holy Prophet when he died?,open,63 years old,,,,,easy,c,,,"))
        assert IssueCode.NEAR_DUPLICATE_QUESTION not in found

    def test_normalise_text(self) -> None:
        assert normalise_text("  Café, “Quoted”!  ") == "cafe quoted"


@pytest.mark.parametrize("edition", EDITIONS)
def test_editions_pass_structural_checks(edition: str) -> None:
    """The current edition files are clean for the game (phase 1 exit criterion)."""
    report = run_structural_checks(parse_csv(edition_bytes(edition)), load_profile(edition).structural)
    assert report.ok_for_game, [i.message for i in report.issues if i.severity == Severity.ERROR]


def test_known_duplicate_in_swab_quest() -> None:
    report = run_structural_checks(parse_csv(edition_bytes("swab-quest")))
    dupes = report.by_code(IssueCode.NEAR_DUPLICATE_QUESTION)
    assert [(i.ext_id, i.related_ext_ids) for i in dupes] == [("285", ("127",))]


@pytest.mark.parametrize("data", [
    pytest.param((FIXTURES / "tricky.csv").read_bytes(), id="tricky"),
    pytest.param(make_csv(
        ",No id,open,A,,,,,easy,c,,,", "2,,open,A,,,,,easy,c,,,", "2,Dup,open,A,,,,,easy,c,,,",
        "4,Bad type,quiz,A,,,,,easy,c,,,", "5,Bad diff,open,A,,,,,medium,c,,,",
        "6,One opt,multi,1,A,,,,easy,c,,,", "7,Bad key,multi,7,A,B,,,easy,c,,,",
        "8,Empty key,multi,4,A,B,C,,easy,c,,,", "9,No answer,open,,,,,,easy,c,,,",
        "10,Comma, unquoted,open,A,,,,,easy,c,,,", "11,No topic,open,A,,,,,easy,c,,t,"), id="many-errors"),
])
def test_errors_cover_every_error_of_the_games_checker(data: bytes, node: str) -> None:
    """Every line the game's checkEdition reports as an error, we report as an error too."""
    script = (
        "const {makeEdition,checkEdition}=require(process.argv[1]);"
        "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{"
        "const r=checkEdition(makeEdition({questionsCsv:s}));"
        "process.stdout.write(JSON.stringify({errors:r.errors.map(e=>e.line),warnings:r.warnings.map(w=>w.line)}))})"
    )
    out = subprocess.run([node, "-e", script, str(REPO_ROOT / "scripts/content.js")], input=data,
                         capture_output=True, check=True)
    game = json.loads(out.stdout)
    ours = run_structural_checks(parse_csv(data)).issues
    our_errors = {i.line_no for i in ours if i.severity == Severity.ERROR}
    our_flagged = {i.line_no for i in ours if i.severity in (Severity.ERROR, Severity.WARNING)}
    assert set(game["errors"]) <= our_errors
    assert set(game["warnings"]) <= our_flagged
    assert game["errors"], "fixture should make the game's checker fail"
