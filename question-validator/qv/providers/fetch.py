"""Page fetching and text extraction. Stored text is what passages are grounded against.

- robots.txt is respected (our user agent and `*`).
- Size cap, timeout, per-domain rate limit; failures are cached so a dead page is not retried every run.
- HTML → main text with trafilatura; Wikipedia articles via the API's plain-text extract.
- PDFs (KB phase 3) → read page by page with the library's reader; one document per readable page
  (`<pdf url>#page=N`, source_kind `pdf`); pages whose text looks broken are not stored ("needs OCR").
- A document's text is stored once and never changed (database trigger).
"""

from __future__ import annotations

import hashlib
import time
import urllib.robotparser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlsplit

import httpx
import trafilatura
from sqlalchemy import select

from qv.config import FetchConfig
from qv.db.models import Document, Fetch
from qv.db.session import Database
from qv.kb.text import guess_language
from qv.library import clean_page, read_pdf_pages, text_quality
from qv.providers.search.base import domain_of
from qv.providers.search.free import WIKIPEDIA_API
from qv.providers.search.web import USER_AGENT, wikimedia_user_agent
from qv.providers.usage import CallContext, RateLimiter, UsageRecorder

ROBOTS_AGENT = "TriventurexQuestionValidator"
FAILURE_RETRY_AFTER = timedelta(days=7)
MIN_TEXT_CHARS = 200
MIN_PDF_PAGE_CHARS = 100          # shorter PDF pages (title pages, blank pages) are not stored


def is_pdf_response(content_type: str, url: str) -> bool:
    """True for a PDF answer (by content type, or a `.pdf` URL served as a generic binary)."""
    ctype = content_type.lower()
    return "pdf" in ctype or (urlsplit(url).path.lower().endswith(".pdf") and
                              ("octet-stream" in ctype or not ctype))


def pdf_page_url(pdf_url: str, page: int) -> str:
    """The stored URL of one page of a web PDF (opens that page in a browser)."""
    return f"{pdf_url.split('#', 1)[0]}#page={page}"


@dataclass(frozen=True)
class FetchResult:
    """Outcome of a fetch: a stored document or the reason there is none."""

    url: str
    status: str
    document_id: int | None = None
    error: str | None = None
    page_ids: tuple[int, ...] = ()   # a web PDF: one stored document per readable page (document_id = the first)

    @property
    def ok(self) -> bool:
        """True when a document is available."""
        return self.document_id is not None


def extract_main_text(page: str, url: str) -> tuple[str, str]:
    """Main text of an HTML page and the method used.

    Precision mode drops boilerplate best, but on some sites (alislam.org articles) it keeps
    only the header. When it keeps less than a quarter of what the default mode finds, the
    default mode's text is used instead.
    """
    kw = dict(url=url, include_comments=False, include_tables=True)
    precise = trafilatura.extract(page, favor_precision=True, **kw) or ""
    default = trafilatura.extract(page, **kw) or ""
    if len(default) >= MIN_TEXT_CHARS and len(precise) < 0.25 * len(default):
        return default, "trafilatura"
    return precise, "trafilatura_precision"


class Fetcher:
    """Fetches URLs into stored documents (cached by URL)."""

    def __init__(self, db: Database, recorder: UsageRecorder, limiter: RateLimiter, cfg: FetchConfig, *,
                 client: httpx.Client | None = None, contact: str = "",
                 pdf_reader: Callable[[bytes], list[str]] = read_pdf_pages) -> None:
        """`client` and `pdf_reader` are injectable for tests; `contact` enables Wikipedia (Wikimedia requires it)."""
        self.pdf_reader = pdf_reader
        self.db = db
        self.wikimedia_ua = wikimedia_user_agent(contact)
        self.recorder = recorder
        self.limiter = limiter
        self.cfg = cfg
        self.client = client or httpx.Client(timeout=cfg.timeout_s, follow_redirects=True,
                                             headers={"User-Agent": USER_AGENT})
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    # -- public -------------------------------------------------------------
    def fetch(self, url: str, ctx: CallContext | None = None) -> FetchResult:
        """Return the stored document for `url`, fetching it if needed."""
        ctx = ctx or CallContext()
        cached = self.cached(url)
        if cached is not None:
            return cached
        if domain_of(url).endswith("wikipedia.org"):
            # Articles are read through the MediaWiki API (its own etiquette rules), never scraped.
            if self.wikimedia_ua is None or domain_of(url) != "en.wikipedia.org" or "/wiki/" not in url:
                return FetchResult(url, "skipped", None, "Wikipedia needs QV_CONTACT (Wikimedia user-agent policy)")
            self.limiter.wait("fetch:wikipedia.org", self.cfg.rpm_per_domain)
            return self._fetch_wikipedia(url, ctx)
        if not self.allowed_by_robots(url, ctx):
            return self.remember(url, "robots_disallowed", None, None, "disallowed by robots.txt")
        self.limiter.wait(f"fetch:{domain_of(url)}", self.cfg.rpm_per_domain)
        return self._fetch_http(url, ctx)

    def store_text(self, *, url: str, final_url: str, title: str, text: str, source_kind: str,
                   extract_method: str, http_status: int | None = 200, ref: str | None = None) -> int:
        """Store a text as a document (deduplicated by final URL + content hash); returns its id."""
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self.db.session() as s:
            doc = s.scalar(select(Document).where(Document.final_url == final_url, Document.content_sha256 == sha))
            if doc is None:
                doc = Document(url=url, final_url=final_url, domain=domain_of(final_url), title=title[:500],
                               source_kind=source_kind, ref=ref, http_status=http_status, content_sha256=sha,
                               text=text, extract_method=extract_method, char_len=len(text))
                s.add(doc)
                s.flush()
            return doc.id

    # -- internals ----------------------------------------------------------
    def cached(self, url: str) -> FetchResult | None:
        """The stored result for `url`: a document, or a recent failure (None when unknown or stale)."""
        with self.db.session() as s:
            row = s.scalar(select(Fetch).where(Fetch.url == url))
            if row is None:
                return None
            if row.status == "ok":
                pages = tuple(s.scalars(select(Document.id).where(Document.url == url, Document.source_kind == "pdf")
                                        .order_by(Document.id)))
                return FetchResult(url, "ok", row.document_id, row.error, pages)
            fetched = row.fetched_at if row.fetched_at.tzinfo else row.fetched_at.replace(tzinfo=UTC)
            if datetime.now(UTC) - fetched < FAILURE_RETRY_AFTER:
                return FetchResult(url, row.status, None, row.error)
            s.delete(row)
        return None

    def remember(self, url: str, status: str, http_status: int | None, document_id: int | None,
                  error: str | None) -> FetchResult:
        """Write the fetch log entry for `url` and return it as a FetchResult."""
        with self.db.session() as s:
            row = s.scalar(select(Fetch).where(Fetch.url == url))
            if row is None:
                row = Fetch(url=url)
                s.add(row)
            row.status, row.http_status, row.document_id, row.error = status, http_status, document_id, error
            row.fetched_at = datetime.now(UTC)
        return FetchResult(url, status, document_id, error)

    def allowed_by_robots(self, url: str, ctx: CallContext) -> bool:
        """robots.txt check for our agent and `*` (cached per origin; unreachable robots.txt → not allowed)."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
            try:
                resp = self.client.get(origin + "/robots.txt")
                if resp.status_code >= 500:
                    parser = None  # unknown → treat as disallowed for now
                elif resp.status_code >= 400:
                    parser.parse([])  # no robots.txt → everything allowed
                else:
                    parser.parse(resp.text.splitlines())
            except httpx.HTTPError:
                parser = None
            self._robots[origin] = parser
        parser = self._robots[origin]
        if parser is None:
            return False
        return parser.can_fetch(ROBOTS_AGENT, url) and parser.can_fetch("*", url)

    def _fetch_http(self, url: str, ctx: CallContext) -> FetchResult:
        start = time.monotonic()
        try:
            with self.client.stream("GET", url) as resp:
                status = resp.status_code
                ctype = resp.headers.get("content-type", "").lower()
                final_url = str(resp.url)
                if status != 200:
                    self._log(ctx, "error", start, status, f"HTTP {status}")
                    return self.remember(url, "error", status, None, f"HTTP {status}")
                pdf = is_pdf_response(ctype, final_url)
                cap = self.cfg.max_pdf_bytes if pdf else self.cfg.max_bytes
                if not pdf and not any(t in ctype for t in ("text/html", "text/plain", "application/xhtml")):
                    self._log(ctx, "error", start, status, f"content-type {ctype}")
                    return self.remember(url, "not_text", status, None, f"content-type {ctype or 'unknown'}")
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body += chunk
                    if len(body) > cap:
                        self._log(ctx, "error", start, status, "too large")
                        return self.remember(url, "too_large", status, None,
                                             f"{'pdf: ' if pdf else ''}> {cap} bytes")
                encoding = resp.encoding or "utf-8"
        except httpx.HTTPError as exc:
            self._log(ctx, "error", start, None, str(exc))
            return self.remember(url, "error", None, None, str(exc)[:300])

        if pdf:
            return self._store_pdf(url, final_url, bytes(body), ctx, start)
        raw = bytes(body).decode(encoding, errors="replace")
        if "text/plain" in ctype:
            text, title, method = raw, "", "plain"
        else:
            text, method = extract_main_text(raw, final_url)
            meta = trafilatura.extract_metadata(raw, default_url=final_url)
            title = meta.title if meta and meta.title else ""
        text = text.strip()
        if len(text) < MIN_TEXT_CHARS:
            self._log(ctx, "error", start, 200, "no main text")
            return self.remember(url, "empty", 200, None, f"only {len(text)} characters of main text")
        doc_id = self.store_text(url=url, final_url=final_url, title=title, text=text, source_kind="web",
                                 extract_method=method)
        self._log(ctx, "ok", start, 200, None)
        return self.remember(url, "ok", 200, doc_id, None)

    def _store_pdf(self, url: str, final_url: str, body: bytes, ctx: CallContext, start: float) -> FetchResult:
        """A web PDF, page by page: readable pages become documents with the site's URL (`#page=N`); a PDF
        without any readable page is remembered as `needs_ocr` (its text is never stored)."""
        if not body.startswith(b"%PDF"):
            self._log(ctx, "error", start, 200, "not a PDF file")
            return self.remember(url, "not_text", 200, None, "pdf: not a PDF file")
        try:
            pages = self.pdf_reader(body)
        except Exception as exc:  # noqa: BLE001 — a broken PDF is a fetch failure, never a crash
            self._log(ctx, "error", start, 200, f"unreadable PDF: {exc}"[:300])
            return self.remember(url, "not_text", 200, None, f"pdf: could not be read ({type(exc).__name__})")
        name = unquote(urlsplit(final_url).path.rsplit("/", 1)[-1]) or domain_of(final_url)
        ids: list[int] = []
        needs_ocr = 0
        for n, raw in enumerate(pages[: self.cfg.max_pdf_pages], 1):
            text = clean_page(raw)
            if len(text) < MIN_PDF_PAGE_CHARS:
                continue
            lang = guess_language(text)
            if text_quality(text, lang if lang in ("ar", "ur") else "en") < self.cfg.pdf_min_quality:
                needs_ocr += 1
                continue
            ids.append(self.store_text(url=url, final_url=pdf_page_url(final_url, n), title=f"{name}, page {n}",
                                       text=text, source_kind="pdf", extract_method="pypdf", ref=f"pdf page {n}"))
        if not ids:
            self._log(ctx, "error", start, 200, "PDF needs OCR")
            return self.remember(url, "needs_ocr", 200, None,
                                 f"pdf: no readable text on {len(pages)} pages (needs OCR)")
        note = (f"pdf: {len(ids)} of {len(pages)} pages stored"
                + (f", {needs_ocr} need OCR" if needs_ocr else "")
                + (f", only the first {self.cfg.max_pdf_pages} read" if len(pages) > self.cfg.max_pdf_pages else ""))
        self._log(ctx, "ok", start, 200, None)
        res = self.remember(url, "ok", 200, ids[0], note)
        return FetchResult(url, "ok", res.document_id, note, tuple(ids))

    def _fetch_wikipedia(self, url: str, ctx: CallContext) -> FetchResult:
        title = unquote(urlsplit(url).path.split("/wiki/", 1)[1]).replace("_", " ")
        start = time.monotonic()
        try:
            resp = self.client.get(WIKIPEDIA_API, headers={"User-Agent": self.wikimedia_ua}, params={
                "action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title,
                "format": "json", "formatversion": 2})
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", [])
        except (httpx.HTTPError, ValueError) as exc:
            self._log(ctx, "error", start, None, str(exc))
            return self.remember(url, "error", None, None, str(exc)[:300])
        page = pages[0] if pages else {}
        text = (page.get("extract") or "").strip()
        if page.get("missing") or len(text) < MIN_TEXT_CHARS:
            self._log(ctx, "error", start, 200, "missing or empty article")
            return self.remember(url, "empty", 200, None, "missing or empty article")
        final_url = "https://en.wikipedia.org/wiki/" + page.get("title", title).replace(" ", "_")
        doc_id = self.store_text(url=url, final_url=final_url, title=page.get("title", title), text=text,
                                 source_kind="wikipedia", extract_method="wikipedia_api_plaintext")
        self._log(ctx, "ok", start, 200, None)
        return self.remember(url, "ok", 200, doc_id, None)

    def _log(self, ctx: CallContext, status: str, start: float, http_status: int | None, error: str | None) -> None:
        self.recorder.record(provider="fetch", kind="fetch", status=status, ctx=ctx, http_status=http_status,
                             error=error, latency_ms=int((time.monotonic() - start) * 1000))
