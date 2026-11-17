"""Qur'an verses from alislam.org (Arabic + Maulawi Sher Ali English), a primary (P) source.

alislam.org numbers verses with the Bismillah as verse 1 — the convention of the
Ahmadiyya editions. References in the common (Hafs/Cairo) numbering are converted:
for every surah except 1 (where the Bismillah is 1:1 in both) and 9 (no Bismillah),
verse n (common) = verse n+1 (Bismillah numbering).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

import httpx

from qv.providers.fetch import Fetcher, FetchResult
from qv.providers.usage import CallContext

ALISLAM_VERSE_URL = "https://www.alislam.org/quran/app/{surah}:{verse}"
BISMILLAH_SCHEME = "bismillah_is_verse_1"
COMMON_SCHEME = "common"
_SCHEME_ALIASES = {
    None: BISMILLAH_SCHEME, "": BISMILLAH_SCHEME, "bismillah_is_verse_1": BISMILLAH_SCHEME,
    "bismillah1": BISMILLAH_SCHEME, "bismillah": BISMILLAH_SCHEME,
    "common": COMMON_SCHEME, "hafs": COMMON_SCHEME, "cairo": COMMON_SCHEME, "standard": COMMON_SCHEME,
}
MAX_VERSES_PER_LOOKUP = 6
#: Verses per surah in the common (Hafs / Cairo) numbering — 6,236 in all. In the Bismillah-as-verse-1 numbering
#: every surah except 1 (Bismillah already 1:1) and 9 (no Bismillah) has one verse more.
VERSES_COMMON = (
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64,
    77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49,
    62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
    29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4,
    5, 6,
)
_VERSE_URL = re.compile(r"^https?://(?:www\.)?alislam\.org/quran/app/(\d{1,3})(?::(\d{1,3})(?:-(\d{1,3}))?)?/?$")


def scheme_of(scheme: str | None) -> str:
    """The canonical numbering scheme name (unknown names raise QuranRefError)."""
    key = (scheme or "").strip().lower()
    if key not in _SCHEME_ALIASES:
        raise QuranRefError(f"Unknown numbering scheme {scheme!r}")
    return _SCHEME_ALIASES[key]


def verse_count(surah: int, scheme: str | None = None) -> int:
    """How many verses a surah has in a numbering scheme (default: Bismillah as verse 1)."""
    n = VERSES_COMMON[surah - 1]
    return n + 1 if scheme_of(scheme) == BISMILLAH_SCHEME and surah not in (1, 9) else n


def missing_verses(text: str, scheme: str | None = None) -> list[str]:
    """References 's:v' (or 's:v-w') in a text that name a surah or verse that does not exist in the scheme —
    e.g. '66:20' (Surah 66 has 12 verses, 13 counting the Bismillah)."""
    out = []
    for m in re.finditer(r"(?<![\d:])(\d{1,3})\s*:\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?(?![\d:])", text):
        surah, first, last = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(2))
        if not 1 <= surah <= 114 or first < 1 or max(first, last) > verse_count(surah, scheme):
            out.append(m.group(0).replace(" ", ""))
    return out


def verse_url_ref(url: str) -> str | None:
    """'s:v' / 's:v-w' when a URL is an alislam.org Qur'an app verse page (read with the verse reader, not as a web
    page — the app is built in the browser), '' for a whole-surah page (not readable), else None."""
    m = _VERSE_URL.match(url.strip())
    if not m:
        return None
    if m.group(2) is None:
        return ""
    return f"{m.group(1)}:{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")


class QuranRefError(ValueError):
    """A reference that cannot be parsed or is out of range."""


@dataclass(frozen=True)
class VerseRef:
    """A verse in the Bismillah-as-verse-1 numbering."""

    surah: int
    verse: int

    @property
    def label(self) -> str:
        """e.g. '2:32'."""
        return f"{self.surah}:{self.verse}"


def parse_refs(ref: str, scheme: str | None = None) -> list[VerseRef]:
    """Verses named by a reference like '2:32', 'Al-Baqarah 2:31-33' or 'quran:2:32@bismillah1'.

    The result is always in Bismillah-as-verse-1 numbering (what alislam.org uses).
    """
    m = re.search(r"(\d{1,3})\s*:\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?", ref)
    if not m:
        raise QuranRefError(f"No surah:verse in {ref!r}")
    if "@" in ref:
        scheme = scheme or ref.rsplit("@", 1)[1]
    norm = scheme_of(scheme)
    surah, first = int(m.group(1)), int(m.group(2))
    last = int(m.group(3)) if m.group(3) else first
    if not 1 <= surah <= 114 or first < 1 or last < first:
        raise QuranRefError(f"Out of range: {ref!r}")
    n = verse_count(surah, norm)
    if first > n:  # never fetched: the verse does not exist (a typo, or the other numbering)
        raise QuranRefError(f"Surah {surah} has {n} verses in this numbering ({norm}); {ref!r} does not exist")
    last = min(last, n, first + MAX_VERSES_PER_LOOKUP - 1)
    shift = 1 if norm == COMMON_SCHEME and surah not in (1, 9) else 0
    return [VerseRef(surah, v + shift) for v in range(first, last + 1)]


def parse_verse_page(page: str) -> tuple[str, str, str]:
    """(heading, arabic, english) from an alislam.org verse page; raises ValueError if missing."""
    def clean(fragment: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()

    h1 = re.search(r"<h1>(.*?)</h1>", page, re.S)
    ar = re.search(r'<p class="rq-arabic"[^>]*>(.*?)</p>', page, re.S)
    en = re.search(r"<h2>\s*English translation by Maulawi Sher Ali\s*</h2>\s*<p[^>]*>(.*?)</p>", page, re.S)
    if not (h1 and ar and en):
        raise ValueError("Verse page does not have the expected heading, Arabic and Sher Ali text")
    return clean(h1.group(1)), clean(ar.group(1)), clean(en.group(1))


class QuranSource:
    """Looks verses up on alislam.org and stores each as a document (source_kind 'quran')."""

    def __init__(self, fetcher: Fetcher) -> None:
        """Uses the fetcher's client, robots check, rate limit and document store."""
        self.fetcher = fetcher

    def lookup(self, ref: str, scheme: str | None, ctx: CallContext | None = None) -> list[FetchResult]:
        """Fetch every verse named by `ref`; one FetchResult per verse."""
        return [self._verse(v, ctx or CallContext()) for v in parse_refs(ref, scheme)]

    def _verse(self, v: VerseRef, ctx: CallContext) -> FetchResult:
        url = ALISLAM_VERSE_URL.format(surah=v.surah, verse=v.verse)
        cached = self.fetcher.cached(url)
        if cached is not None:
            return cached
        if not self.fetcher.allowed_by_robots(url, ctx):
            return self.fetcher.remember(url, "robots_disallowed", None, None, "disallowed by robots.txt")
        self.fetcher.limiter.wait("fetch:alislam.org", self.fetcher.cfg.rpm_per_domain)
        try:
            resp = self.fetcher.client.get(url)
        except httpx.HTTPError as exc:
            return self.fetcher.remember(url, "error", None, None, str(exc)[:300])
        if resp.status_code != 200:
            return self.fetcher.remember(url, "error", resp.status_code, None, f"HTTP {resp.status_code}")
        try:
            heading, arabic, english = parse_verse_page(resp.text)
        except ValueError as exc:
            return self.fetcher.remember(url, "empty", 200, None, str(exc))
        text = (f"{heading}\nNumbering: the Bismillah is counted as verse 1.\n\n"
                f"Arabic: {arabic}\n\nEnglish translation by Maulawi Sher Ali: {english}\n")
        doc_id = self.fetcher.store_text(url=url, final_url=url, title=heading, text=text, source_kind="quran",
                                         extract_method="alislam_quran_v1", ref=f"{v.label}@{BISMILLAH_SCHEME}")
        self.fetcher.recorder.record(provider="alislam", kind="fetch", status="ok", ctx=ctx, http_status=200)
        return self.fetcher.remember(url, "ok", 200, doc_id, None)
