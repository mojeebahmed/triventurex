"""CSV reading and writing that matches the game's own parser (js/shared/csv.js).

The game's parser is line-based: it normalises line endings, skips blank lines,
trims each line, splits on commas outside double quotes ("" is an escaped quote)
and trims every value. It does not support line breaks inside quoted fields.
Reading the file any other way (e.g. Python's `csv` module) could accept files
the game mis-reads, so this module re-implements the same algorithm and keeps
every raw token, which lets the writer change one field and leave every other
byte untouched.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from qv.domain.question import CsvRow, FileFormat, LineEnding, ParsedCsv

#: Characters JavaScript's String.prototype.trim() removes (WhiteSpace + LineTerminator).
JS_WHITESPACE = (
    " \t\n\v\f\r            "
    "     　﻿"
)
_LINE_SPLIT = re.compile(r"(\r\n|\r|\n)")
_BOM = b"\xef\xbb\xbf"


def js_trim(text: str) -> str:
    """Trim exactly like JavaScript's `String.prototype.trim()`."""
    return text.strip(JS_WHITESPACE)


def normalise_header(name: str) -> str:
    """Header normalisation used by the game: trim, lower-case, whitespace runs → `_`."""
    return re.sub(r"\s+", "_", js_trim(name).lower())


@dataclass(frozen=True)
class Token:
    """One field of a line: its decoded value and its exact source text (quotes included)."""

    value: str
    source: str


def split_line(line: str) -> tuple[list[Token], bool]:
    """Split one CSV line like the game's `_csvSplit`.

    Returns the tokens and whether a quote was left open at the end of the line.
    Joining the tokens' `source` with commas reproduces `line` exactly.
    """
    tokens: list[Token] = []
    cur: list[str] = []
    start = 0
    in_quotes = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == '"':
            if in_quotes and i + 1 < len(line) and line[i + 1] == '"':
                cur.append('"')
                i += 1
            else:
                in_quotes = not in_quotes
        elif c == "," and not in_quotes:
            tokens.append(Token("".join(cur), line[start:i]))
            cur = []
            start = i + 1
        else:
            cur.append(c)
        i += 1
    tokens.append(Token("".join(cur), line[start:]))
    return tokens, in_quotes


def quote_value(value: str) -> str:
    """Serialise a value so that the game's parser reads it back unchanged.

    Quotes only when needed (comma, quote, or whitespace the game would trim),
    which matches how the edition CSVs are written by hand.
    """
    if any(ch in value for ch in "\r\n"):
        raise ValueError("The game's CSV format cannot hold line breaks inside a field")
    needs_quotes = "," in value or '"' in value or (value != js_trim(value))
    if not needs_quotes:
        return value
    return '"' + value.replace('"', '""') + '"'


def _split_physical_lines(text: str) -> list[tuple[str, str]]:
    """Split text into (line, terminator) pairs; the last pair may have an empty terminator."""
    parts = _LINE_SPLIT.split(text)
    lines = parts[0::2]
    terms = parts[1::2] + [""]
    return list(zip(lines, terms))


def _detect_line_ending(terms: list[str]) -> LineEnding:
    """Dominant line ending, or MIXED when more than one kind is used."""
    kinds = {t for t in terms if t}
    if not kinds:
        return LineEnding.NONE
    if len(kinds) > 1:
        return LineEnding.MIXED
    return {"\n": LineEnding.LF, "\r\n": LineEnding.CRLF, "\r": LineEnding.CR}[kinds.pop()]


def decode(data: bytes) -> tuple[str, FileFormat, str | None]:
    """Decode bytes as UTF-8 (BOM removed). Undecodable bytes are replaced and reported."""
    has_bom = data.startswith(_BOM)
    body = data[len(_BOM):] if has_bom else data
    error: str | None = None
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        error = f"not valid UTF-8 at byte {exc.start + (3 if has_bom else 0)}: {exc.reason}"
        text = body.decode("utf-8", errors="replace")
    pairs = _split_physical_lines(text)
    terms = [t for _, t in pairs]
    fmt = FileFormat(
        encoding="utf-8",
        has_bom=has_bom,
        line_ending=_detect_line_ending(terms),
        ends_with_newline=bool(terms[-2]) if len(pairs) > 1 and pairs[-1][0] == "" else False,
    )
    return text, fmt, error


def parse_csv(data: bytes) -> ParsedCsv:
    """Parse a questions CSV from its original bytes into a ParsedCsv.

    Never raises on malformed content: problems are visible in the result
    (`decode_error`, `unbalanced_quotes`, cell counts) and reported by the
    structural checks.
    """
    text, fmt, error = decode(data)
    pairs = _split_physical_lines(text)
    header_line = pairs[0][0] if pairs else ""
    header_tokens, _ = split_line(header_line)
    header = tuple(normalise_header(t.value) for t in header_tokens) if js_trim(header_line) else ()

    rows: list[CsvRow] = []
    row_no = 0
    for idx, (line, _term) in enumerate(pairs[1:], start=2):
        trimmed = js_trim(line)
        if not trimmed:
            continue
        row_no += 1
        raw_tokens, open_quote = split_line(line)
        game_tokens, _ = split_line(trimmed)
        # Like the game: missing trailing cells read as "", and for a duplicated
        # header the last column wins (duplicates are reported as an error).
        values = {h: js_trim(game_tokens[i].value) if i < len(game_tokens) else ""
                  for i, h in enumerate(header)}
        rows.append(CsvRow(
            row_no=row_no, line_no=idx, raw_line=line,
            cells=tuple(t.value for t in raw_tokens),
            values=values, unbalanced_quotes=open_quote,
        ))
    return ParsedCsv(
        original_bytes=data, sha256=hashlib.sha256(data).hexdigest(), format=fmt,
        header=header, header_line_no=1, rows=tuple(rows), decode_error=error,
    )


class PatchError(ValueError):
    """A requested change cannot be written safely."""


#: Columns a correction may never change.
IMMUTABLE_COLUMNS = frozenset({"id"})


def apply_patches(parsed: ParsedCsv, patches: dict[int, dict[str, str]]) -> bytes:
    """Return the original file with only the given fields changed.

    `patches` maps a physical line number to {column: new value}. Every other
    line, every unchanged field on a changed line, the quoting style, the line
    endings and the BOM are kept byte-for-byte. The result is re-parsed and
    checked; any unexpected difference raises PatchError.
    """
    if parsed.decode_error:
        raise PatchError(f"Refusing to rewrite a file that is not valid UTF-8 ({parsed.decode_error})")
    text, _, _ = decode(parsed.original_bytes)
    pairs = _split_physical_lines(text)
    by_line = {r.line_no: r for r in parsed.rows}
    col_index = {h: i for i, h in enumerate(parsed.header)}

    out_pairs = list(pairs)
    for line_no, changes in patches.items():
        if line_no not in by_line:
            raise PatchError(f"Line {line_no} is not a data row")
        bad = IMMUTABLE_COLUMNS.intersection(changes)
        if bad:
            raise PatchError(f"Column(s) {sorted(bad)} may never be changed (ids are permanent)")
        unknown = [c for c in changes if c not in col_index]
        if unknown:
            raise PatchError(f"Unknown column(s) {unknown} on line {line_no}")
        line, term = pairs[line_no - 1]
        tokens, open_quote = split_line(line)
        if open_quote:
            raise PatchError(f"Line {line_no} has an unbalanced quote; fix it by hand first")
        sources = [t.source for t in tokens]
        while len(sources) < len(parsed.header):
            sources.append("")
        for col, value in changes.items():
            sources[col_index[col]] = quote_value(value)
        out_pairs[line_no - 1] = (",".join(sources), term)

    new_text = "".join(line + term for line, term in out_pairs)
    new_bytes = (_BOM if parsed.format.has_bom else b"") + new_text.encode("utf-8")
    _verify_patch(parsed, parse_csv(new_bytes), patches)
    return new_bytes


def _verify_patch(before: ParsedCsv, after: ParsedCsv, patches: dict[int, dict[str, str]]) -> None:
    """Check that only the requested fields changed, and to the requested values."""
    if before.header != after.header or len(before.rows) != len(after.rows):
        raise PatchError("Patch changed the file's structure")
    for old, new in zip(before.rows, after.rows):
        wanted = patches.get(old.line_no, {})
        for col in before.header:
            expected = js_trim(wanted[col]) if col in wanted else old.get(col)
            if new.get(col) != expected:
                raise PatchError(
                    f"Line {old.line_no}, column {col}: read back {new.get(col)!r}, expected {expected!r}"
                )
