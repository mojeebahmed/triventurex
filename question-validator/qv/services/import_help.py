"""Plain-words help for the import step: a suggested fix for every format problem.

The check itself is `qv.pipeline.structural` (same rules as the game). This module only explains what
to do about each finding and recognises columns that are probably a standard column under another
name (e.g. "Question" or "option 1").
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from qv.domain.question import STANDARD_COLUMNS
from qv.domain.structural import IssueCode, StructuralIssue

FIX_HINTS: dict[str, str] = {
    IssueCode.NOT_UTF8: "Save the file as 'CSV UTF-8' (Excel: File → Save As → CSV UTF-8; Numbers: Export → CSV, "
                        "Unicode UTF-8).",
    IssueCode.BOM: "Harmless. To remove it, save as plain UTF-8 without BOM.",
    IssueCode.MIXED_LINE_ENDINGS: "Harmless. Saving the file again from one program usually makes them consistent.",
    IssueCode.EMPTY_FILE: "The file has no questions. Check that you picked the right file.",
    IssueCode.MISSING_COLUMN: "Add the column to the first line (the header). Required: id, question, type, answer.",
    IssueCode.UNKNOWN_COLUMN: "Rename it to a standard column (see the suggestion), or leave it: extra columns are "
                              "kept but not checked.",
    IssueCode.DUPLICATE_COLUMN: "Remove or rename one of the two columns with the same name.",
    IssueCode.COLUMN_COUNT: "This line has more or fewer fields than the header. A comma inside a text needs the "
                            "whole text in double quotes: \"Paris, France\".",
    IssueCode.UNBALANCED_QUOTES: "A double quote is opened but not closed. Inside a quoted text, write a quote as two "
                                 "quotes: \"\"like this\"\".",
    IssueCode.WHITESPACE: "Remove the extra spaces at the start or end of the field (harmless for the game).",
    IssueCode.EMPTY_QUESTION: "Write the question text, or delete the line.",
    IssueCode.INVALID_ID: "Use a whole number as id. Never reuse or renumber ids of existing questions.",
    IssueCode.DUPLICATE_ID: "Give one of the questions a new id that is not used anywhere in the file.",
    IssueCode.INVALID_TYPE: "Write multi (four options) or open (free answer).",
    IssueCode.INVALID_DIFFICULTY: "Use one of the allowed difficulties (easy or hard in the game).",
    IssueCode.MULTI_TOO_FEW_OPTIONS: "A multi question needs at least two options in opt_a … opt_d.",
    IssueCode.MULTI_ANSWER_NOT_INDEX: "For multi, the answer is the number of the right option: 1 = opt_a, 2 = opt_b, "
                                      "3 = opt_c, 4 = opt_d — not the option's text.",
    IssueCode.MULTI_ANSWER_EMPTY_OPTION: "The answer points at an empty option. Fill that option or change the answer "
                                         "number.",
    IssueCode.OPEN_NO_ANSWER: "Write the answer text in the answer column.",
    IssueCode.NO_TOPIC: "Fill category (and ideally subcategory and topic) so the game can group the question.",
    IssueCode.FEWER_THAN_FOUR_OPTIONS: "Add options until there are four (the game shows four buttons).",
    IssueCode.OPTION_GAP: "Move the options up so there is no empty option between filled ones.",
    IssueCode.DUPLICATE_OPTIONS: "Two options are the same. Change one of them.",
    IssueCode.OPEN_HAS_OPTIONS: "Open questions show no options: empty opt_a … opt_d, or change the type to multi.",
    IssueCode.EMPTY_CATEGORY: "Fill the category.",
    IssueCode.EXACT_DUPLICATE_QUESTION: "The same question appears twice. Keep one, or reword one.",
    IssueCode.NEAR_DUPLICATE_QUESTION: "Very similar questions. Fine if they are different on purpose; otherwise keep "
                                       "one.",
}

#: Common other names for the standard columns (lower case, spaces/dashes as underscores).
ALIASES: dict[str, str] = {
    "q": "question", "question_text": "question", "vraag": "question", "fraga": "question",
    "correct": "answer", "correct_answer": "answer", "right_answer": "answer", "answer_index": "answer",
    "solution": "answer", "key": "answer",
    "option_1": "opt_a", "option1": "opt_a", "a": "opt_a", "option_a": "opt_a", "choice_a": "opt_a",
    "option_2": "opt_b", "option2": "opt_b", "b": "opt_b", "option_b": "opt_b", "choice_b": "opt_b",
    "option_3": "opt_c", "option3": "opt_c", "c": "opt_c", "option_c": "opt_c", "choice_c": "opt_c",
    "option_4": "opt_d", "option4": "opt_d", "d": "opt_d", "option_d": "opt_d", "choice_d": "opt_d",
    "level": "difficulty", "explanation": "note", "notes": "note", "fact": "note", "qtype": "type",
    "question_type": "type", "sub_category": "subcategory", "subject": "category", "number": "id", "nr": "id",
}


def _norm(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", name.strip().lower())


def suggest_column(name: str, header: tuple[str, ...] | list[str] = ()) -> str | None:
    """The standard column an unknown column probably is (None when no good guess or it is already there)."""
    n = _norm(name)
    guess = n if n in STANDARD_COLUMNS else ALIASES.get(n)
    if guess is None:
        match = process.extractOne(n, STANDARD_COLUMNS, scorer=fuzz.ratio, score_cutoff=80)
        guess = match[0] if match else None
    return guess if guess and guess not in header else None


def hint(issue: StructuralIssue, header: tuple[str, ...] | list[str] = ()) -> str:
    """What to do about one finding, in plain words."""
    text = FIX_HINTS.get(issue.code, "")
    if issue.code == IssueCode.MISSING_COLUMN and issue.column:
        yours = [h for h in header if h not in STANDARD_COLUMNS and suggest_column(h, header) == issue.column]
        if yours:
            return f"Your column '{yours[0]}' is probably '{issue.column}': rename it in the header line."
    if issue.code == IssueCode.UNKNOWN_COLUMN and issue.column:
        guess = suggest_column(issue.column, header)
        if guess:
            text = f"Probably '{guess}': rename '{issue.column}' to '{guess}'. " + text
    return text
