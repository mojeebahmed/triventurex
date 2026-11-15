"""Grounding check (METHODOLOGY.md §1 principle 5): a quote is evidence only if it is in the stored text.

Both texts are normalised the same way — Unicode NFKC, curly → straight quotes, all
dashes → '-', zero-width characters removed, whitespace runs → one space — and the
quote must then be an exact substring. Footnote markers like "[24]" are ignored on
both sides. Offsets are computed here, mapped back to the original stored text; the
model never supplies them. No fuzzy matching.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_QUOTES = {"‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "´": "'",
           "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "«": '"', "»": '"'}
_DASHES = {"‐", "‑", "‒", "–", "—", "―", "−", "﹘", "﹣", "－"}
_ZERO_WIDTH = {"​", "‌", "‍", "⁠", "﻿", "­"}
MIN_QUOTE_CHARS = 12
#: Footnote / citation markers ("[24]", "[ 3 ]") are not content; they are ignored on both sides.
_FOOTNOTE = re.compile(r"\[\s*\d{1,3}\s*\]")


@dataclass(frozen=True)
class Grounded:
    """Where a quote was found in the original text."""

    start: int
    end: int
    text: str


def normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Normalised text and, for each of its characters, the index of the original character."""
    out: list[str] = []
    idx: list[int] = []
    skip = {i for m in _FOOTNOTE.finditer(text) for i in range(m.start(), m.end())}
    prev_space = True  # also trims leading whitespace
    for i, ch in enumerate(text):
        if ch in _ZERO_WIDTH or i in skip:
            continue
        for c in unicodedata.normalize("NFKC", ch):
            c = _QUOTES.get(c, c)
            if c in _DASHES:
                c = "-"
            if c.isspace():
                if prev_space:
                    continue
                c, prev_space = " ", True
            else:
                prev_space = False
            out.append(c)
            idx.append(i)
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def normalise(text: str) -> str:
    """Normalised form only."""
    return normalise_with_map(text)[0]


class DocumentIndex:
    """A stored document prepared for repeated grounding lookups."""

    def __init__(self, text: str) -> None:
        """Normalise once."""
        self.text = text
        self.norm, self.map = normalise_with_map(text)

    def find(self, quote: str) -> Grounded | None:
        """Locate `quote`; None if it is not a verbatim (normalised) substring or is too short."""
        q = normalise(quote)
        if len(q) < MIN_QUOTE_CHARS:
            return None
        pos = self.norm.find(q)
        if pos < 0:
            return None
        start = self.map[pos]
        end = self.map[pos + len(q) - 1] + 1
        return Grounded(start, end, self.text[start:end])
