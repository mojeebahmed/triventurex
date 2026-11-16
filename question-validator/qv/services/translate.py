"""Translate library book pages for search (`qv library translate`).

A machine translation only helps questions in another language FIND a page; the evidence stays the
original page (S3 reads and quotes the original). Runs page by page, resumable: pages already translated
from the same text are skipped, and a used-up free quota stops cleanly (run it again the next day).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from qv.library import Library
from qv.providers.llm.base import LLMError, ModelPool
from qv.providers.usage import CallContext, QuotaExhausted

PROMPT_VERSION = "translate.v1"
LANG_NAMES = {"en": "English", "de": "German", "ur": "Urdu", "ar": "Arabic", "sv": "Swedish"}

SYSTEM = """You translate one page of a book into {target}, faithfully and completely.
- Translate every sentence; do not summarise, explain, add or leave out anything.
- Keep names, titles of honour, places, numbers, dates and Qur'an / hadith references exactly as written.
- Keep text in Arabic script (verses, prayers, honorific formulas) unchanged.
- Keep the page's own structure: one line per line or question/answer ("F:" → "Q:", "A:" stays "A:").
Reply with JSON: {{"translation": "<the whole page in {target}>"}}"""


class Translation(BaseModel):
    """Model output."""

    model_config = ConfigDict(extra="forbid")

    translation: str


@dataclass
class TranslateReport:
    """What one `translate_book` call did."""

    book_id: str
    lang: str
    translated: int = 0
    already: int = 0
    left: int = 0
    stopped: str | None = None
    failed: list[int] = field(default_factory=list)


def translate_book(lib: Library, pool: ModelPool, book_id: str, *, limit: int | None = None,
                   echo=lambda _msg: None) -> TranslateReport:  # noqa: ANN001
    """Translate the book's untranslated pages into its `translate_for_search` language."""
    book = lib.books[book_id]
    lang = book.translate_for_search
    if not lang:
        raise ValueError(f"{book_id}: set translate_for_search (e.g. en) in config/library.yaml first")
    todo = lib.pages_to_translate(book_id, lang)
    rep = TranslateReport(book_id, lang, already=lib.translated_count(book_id, lang))
    system = SYSTEM.format(target=LANG_NAMES.get(lang, lang))
    for n, (page, text) in enumerate(todo):
        if limit is not None and rep.translated >= limit:
            rep.left = len(todo) - n
            break
        try:
            res = pool.complete(system=system, user=f"Page {page}:\n\n{text}", schema_cls=Translation,
                                ctx=CallContext(None, None, "translate"))
        except QuotaExhausted as exc:
            rep.stopped, rep.left = str(exc), len(todo) - n
            break
        except LLMError as exc:
            rep.failed.append(page)
            echo(f"  page {page}: failed ({exc})")
            continue
        out: Translation = res.output  # type: ignore[assignment]
        lib.add_translation(book_id, page, lang, text, out.translation.strip(), model=res.model,
                            prompt_version=PROMPT_VERSION)
        rep.translated += 1
        echo(f"  page {page} translated ({res.model})")
    return rep
