"""Wording flags for the Prepare page — pure code, no AI, free.

They point at questions worth a quick look **before** checking: several facts packed into one question or
answer, a statement before the question, exact figures, "not" questions, long wording, near-duplicates. A
flag is a hint for a person, never a verdict; nothing is changed automatically. The AI quality check (S6)
on the same page is the second, deeper look.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from qv.domain.question import Question
from qv.providers.quran import missing_verses

_REF = re.compile(r"\b\d{1,3}\s*:\s*\d{1,3}\b")              # verse references like 2:31 are not figures
_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_SENTENCE_END = re.compile(r"([.!])\s+[A-Z\"'(]")
_ABBREVIATIONS = {"st", "mt", "dr", "mr", "mrs", "ms", "no", "vs", "jr", "sr", "ft", "approx", "etc", "c", "ca"}
_NEGATIVE = re.compile(r"\b(not|never|except|isn't|wasn't|aren't|weren't|doesn't|didn't|cannot|can't)\b", re.I)
_JOINERS = re.compile(r",|;|\s—\s|\s–\s|\band\b", re.I)


@dataclass(frozen=True)
class Flag:
    """One wording flag: a short code, the label shown in the table, and what it means."""

    code: str
    label: str
    meaning: str


FLAGS: tuple[Flag, ...] = (
    Flag("answer_several_facts", "answer holds several facts",
         "The answer states more than one thing (a place, a size and a year …). One part can be wrong while the "
         "rest is right — shorter answers are easier to check and to remember."),
    Flag("statement_first", "statement before the question",
         "The question first states a fact, then asks. That fact must be right too. Fine for a story-style "
         "lead-in; shorten it when it adds a second fact the question does not need."),
    Flag("two_questions", "asks two things", "More than one question mark: players may answer only one part."),
    Flag("several_numbers", "several numbers or dates",
         "Two or more numbers or dates in the question and answer — each one has to be right."),
    Flag("exact_figure", "exact figure",
         "A precise figure (not a year): sources often give round or different numbers. Consider 'about …' "
         "or a range."),
    Flag("negative", "'not' question", "Asks which is NOT / never / except: easy to misread, especially for children."),
    Flag("long_question", "long question", "Many words: harder to read aloud and to understand quickly."),
    Flag("long_answer", "long answer", "A long answer is hard to give and to judge in play; an explanation "
                                       "can go in the note. (Not shown when the answer already holds several "
                                       "facts.)"),
    Flag("verse_not_found", "verse that does not exist",
         "The note, question or answer cites a Qur'an verse that this surah does not have in the edition's numbering "
         "(Bismillah = verse 1) — a typo, or a number from the other numbering. Shown only for editions that cite "
         "verses."),
    Flag("near_duplicate", "similar to another question", "The import found a question with the same or almost "
                                                           "the same wording in this file."),
)
FLAG_BY_CODE = {f.code: f for f in FLAGS}


def _words(text: str) -> int:
    return len(text.split())


def _numbers(text: str) -> list[str]:
    return _NUMBER.findall(_REF.sub(" ", text))


def _is_exact_figure(token: str) -> bool:
    digits = token.replace(",", "")
    if "." in digits.strip("."):
        return True
    try:
        n = int(digits.strip("."))
    except ValueError:
        return False
    is_year = len(digits.strip(".")) == 4 and 1000 <= n <= 2100
    return n >= 100 and not is_year


def _several_facts(answer: str) -> bool:
    """Two or more joins (commas, 'and', dashes …), a second sentence, or one join plus a number."""
    joins = len(_JOINERS.findall(answer))
    return joins >= 2 or _statement_first(answer.rstrip(". ")) or (joins == 1 and bool(_numbers(answer)))


def _statement_first(question: str) -> bool:
    for m in _SENTENCE_END.finditer(question):
        before = question[:m.start()].split()
        word = before[-1].lower().strip("(\"'") if before else ""
        if word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
            continue
        return True
    return False


def wording_flags(q: Question, *, long_question_words: int, long_answer_words: int,
                  near_duplicate: bool = False, quran_numbering: str | None = None) -> tuple[str, ...]:
    """Codes of the flags that apply to a question, in `FLAGS` order. `quran_numbering` (the edition profile's
    convention) turns on the verse check; editions without one never cite verses."""
    answer = q.resolved_answer_text or q.answer
    found: set[str] = set()
    if q.type == "open" and _words(answer) >= 6 and _several_facts(answer):
        found.add("answer_several_facts")
    if _statement_first(q.question):
        found.add("statement_first")
    if q.question.count("?") > 1:
        found.add("two_questions")
    numbers = _numbers(f"{q.question} {answer}")
    if len(numbers) >= 2:
        found.add("several_numbers")
    if any(_is_exact_figure(n) for n in numbers):
        found.add("exact_figure")
    if _NEGATIVE.search(q.question):
        found.add("negative")
    if _words(q.question) > long_question_words:
        found.add("long_question")
    if q.type == "open" and _words(answer) > long_answer_words and "answer_several_facts" not in found:
        found.add("long_answer")
    if near_duplicate:
        found.add("near_duplicate")
    if quran_numbering and missing_verses(f"{q.question} {answer} {q.note}", quran_numbering):
        found.add("verse_not_found")
    return tuple(f.code for f in FLAGS if f.code in found)
