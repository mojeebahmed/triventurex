"""Pure text helpers for the knowledge index: URL normalisation, chunking, language guess."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

#: Bump when the chunking rules change: every document is chunked again on the next index run.
CHUNKER_VERSION = 1

CHUNK_TARGET = 1200     # a chunk ends at the best break after this many characters …
CHUNK_MIN = 800         # … but not before this many (unless the text ends)
CHUNK_MAX = 1500        # … and never after this many
CHUNK_OVERLAP = 150     # the next chunk starts about this many characters before the previous end

_TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|ref|mc_.*)$", re.I)


def normalize_url(url: str) -> str:
    """One spelling per page: lower-case host, no `www.`, https, no fragment, no tracking parameters, the
    remaining parameters sorted, no trailing slash. Non-web URLs (library://) come back unchanged.

    The one fragment kept is `#page=N`: each page of a web PDF is its own stored document (KB phase 3), not a
    version of the PDF's other pages."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        return url.strip()
    host = (parts.hostname or "").lower().removeprefix("www.")
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    params = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING.match(k))
    path = parts.path.rstrip("/")
    frag = parts.fragment if re.fullmatch(r"page=\d+", parts.fragment) else ""
    return urlunsplit(("https", host, path, urlencode(params), frag))


@dataclass(frozen=True)
class Chunk:
    """A window of a document's text: `text == document_text[start:end]`."""

    start: int
    end: int
    text: str


def _break_at(text: str, lo: int, hi: int, target: int) -> int | None:
    """The best place to end a chunk inside text[lo:hi]: a paragraph end, else a line end, a sentence end, a
    word end — of the best kind found, the one closest to `target`."""
    window = text[lo:hi]
    for pattern in (r"\n\s*\n", r"\n", r"[.!?؟۔][\"'”’)\]]?\s", r"\s"):
        ends = [lo + m.end() for m in re.finditer(pattern, window)]
        if ends:
            return min(ends, key=lambda e: abs(e - target))
    return None


def chunk_text(text: str, *, target: int = CHUNK_TARGET, minimum: int = CHUNK_MIN, maximum: int = CHUNK_MAX,
               overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    """Paragraph-based windows of about `target` characters with a small overlap. Offsets point into `text`
    (no character is changed), leading/trailing whitespace is left out of each chunk."""
    chunks: list[Chunk] = []
    n, start = len(text), 0
    while start < n:
        while start < n and text[start].isspace():
            start += 1
        if start >= n:
            break
        if n - start <= maximum:
            end = n
        else:
            end = _break_at(text, start + minimum, start + maximum, start + target) or start + maximum
        stop = end
        while stop > start and text[stop - 1].isspace():
            stop -= 1
        if stop > start:
            chunks.append(Chunk(start, stop, text[start:stop]))
        if end >= n:
            break
        nxt = max(end - overlap, start + 1)
        while nxt < end and not text[nxt - 1].isspace():   # start the overlap at a word start
            nxt += 1
        start = nxt
    return chunks


_EN = frozenset("the and of to in is was that for with as by on are from his he it this which be at".split())
_DE = frozenset("der die und das ist nicht ein eine zu den von mit sich des auf für im dem er wurde auch".split())
_URDU_LETTERS = set("ٹڈڑںھےیپچژگک")


def guess_language(text: str) -> str:
    """A rough language guess without extra libraries: 'en', 'de', 'ar', 'ur', a mix such as 'ar+en'
    (Qur'an pages carry Arabic and English), or 'other'."""
    sample = text[:20000]
    letters = [c for c in sample if c.isalpha()]
    if not letters:
        return "other"
    arabic = [c for c in letters if "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ" or "ﭐ" <= c <= "﻿"]
    share = len(arabic) / len(letters)
    arabic_lang = ("ur" if sum(c in _URDU_LETTERS for c in arabic) > 0.02 * len(arabic) else "ar") if arabic else ""
    words = re.findall(r"[a-zäöüß]+", sample.lower())
    en = sum(w in _EN for w in words)
    de = sum(w in _DE for w in words)
    latin = ("de" if de > en else "en") if max(en, de) >= 3 else ""
    if share >= 0.8 or (share >= 0.2 and not latin):
        return arabic_lang
    if share >= 0.2:
        return f"{arabic_lang}+{latin}"
    return latin or "other"
