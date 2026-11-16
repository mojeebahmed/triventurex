"""One-click fixes for format problems on import (only fixes whose result is certain).

Each fix is listed in plain words before it is applied; nothing is guessed. The result is a new file
(bytes) that is checked again like any upload. Ids are never changed. Fixes that need a person
(a missing answer, a duplicate id, a comma problem) stay as hints in `import_help`.

What is fixed:
- file saved in the Windows/Excel encoding (cp1252) → UTF-8; byte-order mark removed; mixed line endings
  made the same
- a column under another name ("Question", "option 1") renamed to the standard name
- spaces at the start or end of a field
- type / difficulty in other letter case ("Multi" → "multi")
- a multi answer written as the option's text or letter ("Paris", "B") → its number
- empty options between filled ones moved up, the answer number moved with them
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from qv.config import Profile
from qv.domain.question import OPTION_COLUMNS, Question
from qv.io.csv_format import apply_patches, js_trim, parse_csv, quote_value, split_line
from qv.pipeline.structural import normalise_text
from qv.services.import_help import suggest_column

_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True)
class Fix:
    """One change, in plain words."""

    what: str
    line_no: int | None = None
    ext_id: str | None = None


@dataclass
class FixResult:
    """The fixed file and the list of changes (empty when there was nothing to fix)."""

    data: bytes
    fixes: list[Fix] = field(default_factory=list)


def suggest_fixes(data: bytes, profile: Profile) -> FixResult:
    """Apply every certain fix to a file; returns the new bytes and what changed."""
    fixes: list[Fix] = []
    data = _fix_encoding(data, fixes)
    data = _fix_header(data, fixes)
    data = _fix_rows(data, profile, fixes)
    return FixResult(data, fixes)


# --- file level ----------------------------------------------------------------------------

def _fix_encoding(data: bytes, fixes: list[Fix]) -> bytes:
    if data.startswith(_BOM):
        data = data[len(_BOM):]
        fixes.append(Fix("Removed the byte-order mark (BOM) at the start of the file"))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError:
            return data            # neither: leave it to the person (hint: save as CSV UTF-8)
        fixes.append(Fix("Converted the file from the Windows/Excel encoding to UTF-8 (letters like é, ā, ’ "
                         "now read correctly)"))
    endings = re.findall(r"\r\n|\r|\n", text)
    kinds = set(endings)
    if len(kinds) > 1:
        common = max(kinds, key=endings.count)
        text = re.sub(r"\r\n|\r|\n", lambda _: common, text)
        fixes.append(Fix("Made all line endings the same"))
    return text.encode("utf-8")


def _fix_header(data: bytes, fixes: list[Fix]) -> bytes:
    text = data.decode("utf-8", errors="strict") if _is_utf8(data) else None
    if text is None:
        return data
    first, sep, rest = text.partition("\n")
    line = first.removesuffix("\r")
    ending = first[len(line):]
    tokens, open_quote = split_line(line)
    if open_quote or not js_trim(line):
        return data
    names = [js_trim(t.value) for t in tokens]
    header = [n.lower() for n in names]
    renamed = list(names)
    for i, name in enumerate(names):
        guess = suggest_column(name, header)
        if guess and guess not in [r.lower() for r in renamed]:
            renamed[i] = guess
            fixes.append(Fix(f"Renamed column '{name}' to '{guess}'", line_no=1))
    if renamed == names:
        return data
    new_first = ",".join(quote_value(n) for n in renamed) + ending
    return (new_first + sep + rest).encode("utf-8")


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


# --- row level -----------------------------------------------------------------------------

def _fix_rows(data: bytes, profile: Profile, fixes: list[Fix]) -> bytes:
    parsed = parse_csv(data)
    if parsed.decode_error or not parsed.header:
        return data
    header = parsed.header
    rules = profile.structural
    patches: dict[int, dict[str, str]] = {}
    for row in parsed.rows:
        if row.unbalanced_quotes or len(row.cells) != len(header):
            continue               # comma/quote problems need a person; patching could move fields
        q = Question.from_row(row, header)
        changes: dict[str, str] = {}

        spaced = [h for i, h in enumerate(header) if h != "id" and row.cells[i] != js_trim(row.cells[i])]
        for col in spaced:
            changes[col] = row.get(col)
        if spaced:
            fixes.append(Fix(f"Removed extra spaces in {', '.join(spaced)}", row.line_no, q.ext_id))

        qtype = _case_fix("type", q.type, rules.allowed_types, changes, fixes, row.line_no, q.ext_id, header)
        _case_fix("difficulty", q.difficulty, rules.allowed_difficulties, changes, fixes, row.line_no, q.ext_id,
                  header)

        if qtype == "multi" and "answer" in header:
            options = list(q.options)
            answer = _answer_number(q.answer, options)
            if answer is not None and answer != q.answer:
                changes["answer"] = answer
                fixes.append(Fix(f"Answer '{q.answer}' written as option {answer} ({options[int(answer) - 1]})",
                                 row.line_no, q.ext_id))
            moved = _close_option_gaps(options, changes.get("answer", q.answer))
            if moved is not None and all(c in header for c in OPTION_COLUMNS):
                new_options, new_answer = moved
                for col, old, new in zip(OPTION_COLUMNS, options, new_options):
                    if old != new:
                        changes[col] = new
                if new_answer is not None:
                    changes["answer"] = new_answer
                fixes.append(Fix("Moved options up to close an empty option"
                                 + (f"; answer is now {new_answer}" if new_answer else ""), row.line_no, q.ext_id))
        if changes:
            patches[row.line_no] = changes
    return apply_patches(parsed, patches) if patches else data


def _case_fix(col: str, value: str, allowed: list[str], changes: dict[str, str], fixes: list[Fix],
              line_no: int, ext_id: str, header: tuple[str, ...]) -> str:
    """Lower-case a value when only the case is wrong; returns the (fixed) value."""
    if col in header and value and value not in allowed and value.lower() in allowed:
        changes[col] = value.lower()
        fixes.append(Fix(f"{col.capitalize()} '{value}' → '{value.lower()}'", line_no, ext_id))
        return value.lower()
    return value


def _answer_number(answer: str, options: list[str]) -> str | None:
    """The option number for an answer written as an option's text or letter (None when not certain)."""
    if re.fullmatch(r"[1-4]", answer):
        return answer
    letter = re.fullmatch(r"(?i)(?:opt_)?([a-d])\)?", answer)
    if letter:
        i = "abcd".index(letter.group(1).lower())
        return str(i + 1) if options[i] else None
    want = normalise_text(answer)
    if not want:
        return None
    hits = [i for i, o in enumerate(options) if o and normalise_text(o) == want]
    return str(hits[0] + 1) if len(hits) == 1 else None


def _close_option_gaps(options: list[str], answer: str) -> tuple[list[str], str | None] | None:
    """Options moved up over empty ones, and the answer number that keeps pointing at the same text.

    None when there is no gap, or when the answer does not point at a filled option (then the right
    number is unknown and a person must decide).
    """
    filled = [i for i, o in enumerate(options) if o]
    if not filled or filled == list(range(len(filled))):
        return None
    if not re.fullmatch(r"[1-4]", answer) or not options[int(answer) - 1]:
        return None
    new = [options[i] for i in filled] + [""] * (len(options) - len(filled))
    new_answer = str(filled.index(int(answer) - 1) + 1)
    return new, (new_answer if new_answer != answer else None)
