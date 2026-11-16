"""Which questions to check first — a quick guess from the wording (pure code, no AI, free).

Errors in quiz questions cluster in a few kinds of claim (METHODOLOGY.md §2): numbers and dates,
"most / first / only" records, facts that change over time, references and quotes, and notes that
make claims of their own. Each signal adds points; the total gives a level (high / medium / low)
and the reasons are shown to the user. It only orders the work — every question still gets the
full check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from qv.domain.question import Question

_NUMBER = re.compile(r"\d")
_SUPERLATIVE = re.compile(
    r"\b(most|least|largest|biggest|smallest|highest|lowest|longest|shortest|tallest|oldest|youngest|"
    r"fastest|slowest|deepest|first|last|only|record|best|worst|greatest|more than any)\b", re.I)
_TIME = re.compile(r"\b(since|currently|current|now|today|still|latest|recent|recently|this year|nowadays|"
                   r"as of|world record|reigning|holds?)\b", re.I)
_REFERENCE = re.compile(r"\b\d{1,3}\s*:\s*\d{1,3}\b|\b(said|says|wrote|quote|narrat\w*|hadith|verse|surah|"
                        r"ayah|book of)\b", re.I)

HIGH, MEDIUM = 4, 2
CHANGED_SINCE_CHECK = "changed since it was last checked"


@dataclass(frozen=True)
class Priority:
    """Points, level and the reasons behind them."""

    score: int
    level: str
    reasons: tuple[str, ...]


def priority(q: Question, *, has_warnings: bool = False, changed: bool = False) -> Priority:
    """Score a question from its wording. `changed`: edited since an earlier check (always first)."""
    text = f"{q.question} {q.resolved_answer_text or q.answer}"
    reasons: list[tuple[int, str]] = []
    if changed:
        reasons.append((5, CHANGED_SINCE_CHECK))
    if _NUMBER.search(text):
        reasons.append((2, "numbers or dates"))
    if _SUPERLATIVE.search(text):
        reasons.append((2, "a 'most / first / only' claim"))
    if _TIME.search(text):
        reasons.append((2, "can go out of date"))
    if _REFERENCE.search(text):
        reasons.append((1, "a reference or quote"))
    if q.note and (_NUMBER.search(q.note) or _REFERENCE.search(q.note)):
        reasons.append((1, "the note makes its own claim"))
    if has_warnings:
        reasons.append((2, "format warning"))
    if q.difficulty == "hard":
        reasons.append((1, "hard question"))
    score = sum(p for p, _ in reasons)
    level = "high" if score >= HIGH else "medium" if score >= MEDIUM else "low"
    return Priority(score, level, tuple(r for _, r in reasons))


#: What each signal means and its points — shown on the web page so the list is not mistaken for a
#: prediction. (Points must match `priority` above.)
SIGNALS: tuple[tuple[str, int, str], ...] = (
    (CHANGED_SINCE_CHECK, 5, "You edited it after it was checked; always checked first."),
    ("numbers or dates", 2, "A digit in the question or answer: years, counts, amounts. Easy to get slightly wrong."),
    ("a 'most / first / only' claim", 2, "Words like most, largest, first, only, record. One counter-example "
                                         "makes them wrong."),
    ("can go out of date", 2, "Words like since, currently, now, latest, holds. True once, may have changed."),
    ("a reference or quote", 1, "A verse number like 2:31, or said / wrote / hadith / surah: the reference itself "
                                "must be right."),
    ("the note makes its own claim", 1, "The note has numbers or a reference, so it needs checking too."),
    ("format warning", 2, "The import check found a warning on this question."),
    ("hard question", 1, "Marked hard in the file."),
)
