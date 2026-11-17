"""Models for imported questions and the CSV file they came from."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

#: Columns of the game's questions.csv, in the game's order.
STANDARD_COLUMNS: tuple[str, ...] = (
    "id", "question", "type", "answer", "opt_a", "opt_b", "opt_c", "opt_d",
    "difficulty", "category", "subcategory", "topic", "note",
)
#: Columns the validator's game exports add: how a question was checked (the game's Questions tab and the
#: Academy show them). Not part of `content_hash` — re-importing an exported file keeps every result.
CHECK_COLUMNS: tuple[str, ...] = (
    "checked", "checked_on", "check_how", "sources", "source_links", "source_quote", "as_of", "check_hash",
)
#: Columns without which a row cannot be understood at all.
REQUIRED_COLUMNS: tuple[str, ...] = ("id", "question", "type", "answer")
OPTION_COLUMNS: tuple[str, ...] = ("opt_a", "opt_b", "opt_c", "opt_d")
OPTION_LETTERS: tuple[str, ...] = ("A", "B", "C", "D")


class QuestionType(StrEnum):
    """Question type as written in the CSV `type` column."""

    MULTI = "multi"
    OPEN = "open"


class LineEnding(StrEnum):
    """Dominant line ending of a CSV file."""

    LF = "lf"
    CRLF = "crlf"
    CR = "cr"
    MIXED = "mixed"
    NONE = "none"


class FileFormat(BaseModel):
    """Byte-level facts about an imported file, needed to write it back faithfully."""

    model_config = ConfigDict(frozen=True)

    encoding: str = "utf-8"
    has_bom: bool = False
    line_ending: LineEnding = LineEnding.LF
    ends_with_newline: bool = True


class CsvRow(BaseModel):
    """One data row exactly as read: physical line, raw cells and header mapping.

    `cells` are **untrimmed** and keep their original spelling; `values` is the
    game's view (header → trimmed value), so checks see what the game sees.
    """

    model_config = ConfigDict(frozen=True)

    row_no: int = Field(description="1-based data row number (header excluded, blank lines skipped)")
    line_no: int = Field(description="1-based physical line number in the file")
    raw_line: str = Field(description="The line exactly as in the file, without its line ending")
    cells: tuple[str, ...]
    values: dict[str, str]
    unbalanced_quotes: bool = False

    def get(self, column: str) -> str:
        """Return the trimmed value of `column`, or '' when the column is absent."""
        return self.values.get(column, "")


class ParsedCsv(BaseModel):
    """A whole parsed CSV file. `original_bytes` is never modified."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    original_bytes: bytes
    sha256: str
    format: FileFormat
    header: tuple[str, ...]
    header_line_no: int
    rows: tuple[CsvRow, ...]
    decode_error: str | None = None

    @property
    def extra_columns(self) -> tuple[str, ...]:
        """Header columns the game does not know (kept, never dropped)."""
        return tuple(h for h in self.header if h not in STANDARD_COLUMNS and h not in CHECK_COLUMNS)

    @property
    def missing_columns(self) -> tuple[str, ...]:
        """Standard columns absent from the header."""
        return tuple(c for c in STANDARD_COLUMNS if c not in self.header)


class Question(BaseModel):
    """A question in the game's terms, built from one CSV row.

    Built for every row, including malformed ones: invalid values are kept as
    text so nothing is lost; structural issues say what is wrong.
    """

    model_config = ConfigDict(frozen=True)

    row_no: int
    line_no: int
    ext_id: str = Field(description="The CSV `id`, as text (never renumbered)")
    question: str
    type: str
    answer: str
    options: tuple[str, str, str, str]
    difficulty: str
    category: str
    subcategory: str
    topic: str
    note: str
    raw: dict[str, str] = Field(description="Every column of the row, untrimmed, including unknown ones")

    @property
    def is_multi(self) -> bool:
        """True for a multiple-choice question."""
        return self.type == QuestionType.MULTI

    @property
    def answer_index(self) -> int | None:
        """0-based index of the keyed option for a multi question, or None if invalid."""
        if not self.is_multi or not self.answer.isdigit():
            return None
        idx = int(self.answer) - 1
        return idx if 0 <= idx < 4 else None

    @property
    def resolved_answer_text(self) -> str | None:
        """The key as text: the option text for multi, the answer for open; None if unresolvable."""
        if self.is_multi:
            idx = self.answer_index
            return self.options[idx] or None if idx is not None else None
        return self.answer or None

    @property
    def filled_options(self) -> list[tuple[str, str]]:
        """(letter, text) for every non-empty option."""
        return [(OPTION_LETTERS[i], o) for i, o in enumerate(self.options) if o]

    def content_hash(self) -> str:
        """Hash of the fields a validation depends on (used for diffs and cache keys)."""
        payload = json.dumps(
            [self.question, self.type, self.answer, list(self.options), self.difficulty,
             self.category, self.subcategory, self.topic, self.note],
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def from_row(cls, row: CsvRow, header: tuple[str, ...]) -> "Question":
        """Build a Question from a parsed row (values are the game's trimmed view)."""
        raw = {h: (row.cells[i] if i < len(row.cells) else "") for i, h in enumerate(header)}
        g = row.get
        return cls(
            row_no=row.row_no, line_no=row.line_no, ext_id=g("id"), question=g("question"),
            type=g("type"), answer=g("answer"),
            options=(g("opt_a"), g("opt_b"), g("opt_c"), g("opt_d")),
            difficulty=g("difficulty"), category=g("category"), subcategory=g("subcategory"),
            topic=g("topic"), note=g("note"), raw=raw,
        )


#: Fields `check_hash` covers: what a check of a question's facts depends on (not its difficulty or place).
CHECK_HASH_FIELDS: tuple[str, ...] = ("question", "type", "answer", "opt_a", "opt_b", "opt_c", "opt_d", "note")


def check_hash(values: dict[str, str]) -> str:
    """Short fingerprint of a row's checked wording (10 hex characters).

    Written to the `check_hash` column of a game export; the game's content checker
    (scripts/content.js → `checkHash`) computes the same value and warns when a checked
    question was changed afterwards. Values are the game's trimmed view; keep both in step.
    """
    payload = "\n".join(values.get(f, "") for f in CHECK_HASH_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
