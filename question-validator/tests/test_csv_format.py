"""CSV reading/writing: game-compatible parsing and byte-faithful patching."""

from __future__ import annotations

import json
import subprocess

import pytest

from qv.domain.question import LineEnding
from qv.io.csv_format import (
    PatchError, apply_patches, js_trim, normalise_header, parse_csv, quote_value, split_line,
)
from tests.conftest import EDITIONS, FIXTURES, REPO_ROOT, edition_bytes, make_csv


def values(line: str) -> list[str]:
    """Decoded values of one line."""
    return [t.value for t in split_line(line)[0]]


class TestSplitLine:
    """split_line mirrors the game's _csvSplit."""

    def test_plain_and_quoted_fields(self) -> None:
        assert values('1,"a, b",c') == ["1", "a, b", "c"]

    def test_escaped_quotes(self) -> None:
        assert values('"say ""hi""",x') == ['say "hi"', "x"]

    def test_empty_fields_and_trailing_comma(self) -> None:
        assert values("a,,b,") == ["a", "", "b", ""]

    def test_sources_rejoin_to_the_line(self) -> None:
        line = ' 1 ,"a, ""b""",,c '
        tokens, open_quote = split_line(line)
        assert ",".join(t.source for t in tokens) == line
        assert not open_quote

    def test_unbalanced_quote_is_reported(self) -> None:
        tokens, open_quote = split_line('1,"oops,2')
        assert open_quote
        assert [t.value for t in tokens] == ["1", "oops,2"]


def test_js_trim_removes_bom_and_nbsp() -> None:
    assert js_trim("﻿  id \t") == "id"


def test_normalise_header() -> None:
    assert normalise_header("  Sub  Category ") == "sub_category"


class TestParse:
    """parse_csv: rows, formats and the game's view of values."""

    def test_rows_and_values(self, good_csv: bytes) -> None:
        p = parse_csv(good_csv)
        assert len(p.rows) == 3
        assert p.rows[1].get("question") == "Which river flows through Cairo, Egypt?"
        assert p.rows[1].get("note") == "Longest, maybe"
        assert p.format.line_ending == LineEnding.LF and p.format.ends_with_newline

    def test_values_are_strings_never_numbers(self) -> None:
        p = parse_csv(make_csv("007,Q?,open,1997,,,,,easy,c,,,"))
        assert p.rows[0].get("id") == "007"
        assert p.rows[0].get("answer") == "1997"

    def test_blank_lines_skipped_but_line_numbers_kept(self, good_csv: bytes) -> None:
        data = good_csv.replace(b"\n2,", b"\n\n   \n2,")
        p = parse_csv(data)
        assert [r.row_no for r in p.rows] == [1, 2, 3]
        assert [r.line_no for r in p.rows] == [2, 5, 6]

    def test_bom_crlf_no_final_newline(self) -> None:
        data = b"\xef\xbb\xbf" + make_csv(
            "1,Q?,open,A,,,,,easy,c,,,", newline="\r\n", final_newline=False)
        p = parse_csv(data)
        assert p.header[0] == "id"
        assert p.format.has_bom and p.format.line_ending == LineEnding.CRLF
        assert not p.format.ends_with_newline

    def test_mixed_line_endings(self) -> None:
        p = parse_csv(make_csv("1,Q?,open,A,,,,,easy,c,,,") + b"2,R?,open,B,,,,,easy,c,,,\r\n")
        assert p.format.line_ending == LineEnding.MIXED

    def test_short_rows_padded_like_the_game(self) -> None:
        p = parse_csv(make_csv("1,Q?,open,A"))
        assert p.rows[0].get("note") == ""
        assert len(p.rows[0].cells) == 4

    def test_invalid_utf8_reported_not_raised(self) -> None:
        p = parse_csv(make_csv("1,Caf\xe9?,open,A,,,,,easy,c,,,").replace(b"\xc3\xa9", b"\xe9"))
        assert p.decode_error and "UTF-8" in p.decode_error


@pytest.mark.parametrize("edition", EDITIONS)
def test_parse_matches_the_games_parser(edition: str, node: str) -> None:
    """Every value we read equals what js/shared/csv.js reads, for every edition."""
    _assert_parity_with_game(edition_bytes(edition), node)


def test_parse_matches_the_games_parser_on_tricky_input(node: str) -> None:
    _assert_parity_with_game((FIXTURES / "tricky.csv").read_bytes(), node)


def _assert_parity_with_game(data: bytes, node: str) -> None:
    """Compare parse_csv with the game's _parseCSV through node."""
    script = (
        "const {_parseCSV}=require(process.argv[1]);"
        "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>process.stdout.write(JSON.stringify(_parseCSV(s))));"
    )
    out = subprocess.run([node, "-e", script, str(REPO_ROOT / "js/shared/csv.js")], input=data,
                         capture_output=True, check=True)
    game_rows = json.loads(out.stdout)
    ours = [dict(r.values) for r in parse_csv(data).rows]
    assert ours == game_rows


class TestQuoteValue:
    """quote_value produces text the game reads back unchanged."""

    @pytest.mark.parametrize("value", ["plain", "a, b", 'say "hi"', " padded ", "", "x,\"y\",z"])
    def test_round_trip(self, value: str) -> None:
        line = "1," + quote_value(value) + ",2"
        assert values(line)[1] == value

    def test_plain_values_are_not_quoted(self) -> None:
        assert quote_value("Paris") == "Paris"

    def test_line_breaks_refused(self) -> None:
        with pytest.raises(ValueError):
            quote_value("two\nlines")


class TestApplyPatches:
    """apply_patches changes only the requested fields."""

    @pytest.mark.parametrize("edition", EDITIONS)
    def test_no_patches_is_byte_identical(self, edition: str) -> None:
        data = edition_bytes(edition)
        assert apply_patches(parse_csv(data), {}) == data

    def test_no_patches_keeps_bom_crlf_blank_lines(self) -> None:
        data = (FIXTURES / "tricky.csv").read_bytes()
        assert apply_patches(parse_csv(data), {}) == data

    def test_single_field_change(self, good_csv: bytes) -> None:
        p = parse_csv(good_csv)
        out = apply_patches(p, {3: {"answer": "Cairo, of course", "note": 'a "note"'}})
        old_lines, new_lines = good_csv.split(b"\n"), out.split(b"\n")
        assert [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b] == [2]
        assert new_lines[2] == ('2,"Which river flows through Cairo, Egypt?",open,"Cairo, of course"'
                                ',,,,,hard,Geo,Rivers,Africa,"a ""note"""').encode()

    def test_keeps_crlf_and_bom(self) -> None:
        data = b"\xef\xbb\xbf" + make_csv("1,Q?,open,A,,,,,easy,c,,,", "2,R?,open,B,,,,,easy,c,,,",
                                          newline="\r\n")
        out = apply_patches(parse_csv(data), {3: {"answer": "C"}})
        assert out == data.replace(b"2,R?,open,B", b"2,R?,open,C")

    def test_pads_short_row(self) -> None:
        p = parse_csv(make_csv("1,Q?,open,A"))
        out = apply_patches(p, {2: {"note": "n"}})
        assert parse_csv(out).rows[0].get("note") == "n"

    def test_id_is_immutable(self, good_csv: bytes) -> None:
        with pytest.raises(PatchError, match="ids are permanent"):
            apply_patches(parse_csv(good_csv), {2: {"id": "99"}})

    def test_unknown_column_and_line(self, good_csv: bytes) -> None:
        p = parse_csv(good_csv)
        with pytest.raises(PatchError, match="Unknown column"):
            apply_patches(p, {2: {"colour": "x"}})
        with pytest.raises(PatchError, match="not a data row"):
            apply_patches(p, {1: {"answer": "x"}})

    def test_refuses_line_with_unbalanced_quote(self) -> None:
        p = parse_csv(make_csv('1,"Q?,open,A,,,,,easy,c,,,'))
        with pytest.raises(PatchError, match="unbalanced"):
            apply_patches(p, {2: {"note": "x"}})

    def test_refuses_invalid_utf8(self) -> None:
        p = parse_csv(make_csv("1,Q\xe9?,open,A,,,,,easy,c,,,").replace(b"\xc3\xa9", b"\xe9"))
        with pytest.raises(PatchError, match="UTF-8"):
            apply_patches(p, {})
