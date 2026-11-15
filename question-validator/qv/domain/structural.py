"""Models for structural (no-AI) findings."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Severity(StrEnum):
    """How bad a structural finding is.

    ERROR   — the game would reject or mis-load the row (`npm run check:content` fails).
    WARNING — playable but probably unintended.
    INFO    — worth knowing; no action required.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCode(StrEnum):
    """Every structural finding has one stable code (used in reports and tests)."""

    # file level
    NOT_UTF8 = "not_utf8"
    BOM = "bom"
    MIXED_LINE_ENDINGS = "mixed_line_endings"
    EMPTY_FILE = "empty_file"
    MISSING_COLUMN = "missing_column"
    UNKNOWN_COLUMN = "unknown_column"
    DUPLICATE_COLUMN = "duplicate_column"
    # row shape
    COLUMN_COUNT = "column_count"
    UNBALANCED_QUOTES = "unbalanced_quotes"
    WHITESPACE = "whitespace"
    # row content (mirrors the game's checker)
    EMPTY_QUESTION = "empty_question"
    INVALID_ID = "invalid_id"
    DUPLICATE_ID = "duplicate_id"
    INVALID_TYPE = "invalid_type"
    INVALID_DIFFICULTY = "invalid_difficulty"
    MULTI_TOO_FEW_OPTIONS = "multi_too_few_options"
    MULTI_ANSWER_NOT_INDEX = "multi_answer_not_index"
    MULTI_ANSWER_EMPTY_OPTION = "multi_answer_empty_option"
    OPEN_NO_ANSWER = "open_no_answer"
    NO_TOPIC = "no_topic"
    # extra checks (not in the game's checker)
    FEWER_THAN_FOUR_OPTIONS = "fewer_than_four_options"
    OPTION_GAP = "option_gap"
    DUPLICATE_OPTIONS = "duplicate_options"
    OPEN_HAS_OPTIONS = "open_has_options"
    EMPTY_CATEGORY = "empty_category"
    EXACT_DUPLICATE_QUESTION = "exact_duplicate_question"
    NEAR_DUPLICATE_QUESTION = "near_duplicate_question"


class StructuralIssue(BaseModel):
    """One structural finding. `row_no`/`line_no` are None for file-level findings."""

    model_config = ConfigDict(frozen=True)

    code: IssueCode
    severity: Severity
    message: str
    row_no: int | None = None
    line_no: int | None = None
    ext_id: str | None = None
    related_ext_ids: tuple[str, ...] = ()
    column: str | None = None


class StructuralReport(BaseModel):
    """All findings for one file, with counts for the import summary."""

    model_config = ConfigDict(frozen=True)

    issues: tuple[StructuralIssue, ...]
    row_count: int
    multi_count: int
    open_count: int

    def count(self, severity: Severity) -> int:
        """Number of findings with the given severity."""
        return sum(1 for i in self.issues if i.severity == severity)

    @property
    def ok_for_game(self) -> bool:
        """True when nothing would make the game's checker fail."""
        return self.count(Severity.ERROR) == 0

    def by_code(self, code: IssueCode) -> list[StructuralIssue]:
        """Findings with the given code, in file order."""
        return [i for i in self.issues if i.code == code]
