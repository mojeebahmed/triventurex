"""Research pipeline (phase 2): from a question to grounded, stored evidence. No verdicts.

Per question:  S1a (blind) → S1b (claims) → direct lookups (Qur'an) → stored pages (the
knowledge index, searched with S1a's blind queries only — KB phase 3) → searches (free
pools, cached) → choose and fetch documents → S3 per document (blind) → grounding
check → passages stored. Every step is idempotent: stage outputs are reused by input
hash, searches and fetches are cached, and a document's passages are written in the
same transaction that marks it extracted — so an interrupted run resumes cleanly.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

from qv.config import (
    Profile, ProvidersConfig, ResearchConfig, Settings, load_profile, load_providers_config,
    load_research_config,
)
from qv.db.models import (
    DatasetVersion, Document, Passage, QuestionDocument, QuestionRow, Run, RunQuestion, StageOutput,
)
from qv.db.session import Database
from qv.domain.question import Question
from qv.domain.stages import ClaimFormulation, ClaimType, Decomposition, Extraction
from qv.kb.search import search as kb_search
from qv.pipeline.grounding import DocumentIndex
from qv.pipeline.stages import (
    DocMeta, StageRunner, check_s1a, check_s1b, filter_s1b_lookups, render_s1a, render_s1b, render_s3,
    s3_target_ids, windows,
)
from qv.providers.fetch import Fetcher
from qv.config import split_entry
from qv.providers.llm.base import LLMError, LLMProvider, ModelPool, PoolEntry
from qv.providers.llm.gemini import GeminiProvider
from qv.providers.llm.ollama import OllamaProvider
from qv.providers.quran import QuranRefError, QuranSource
from qv.providers.search.base import SearchError, SearchHit, SearchProvider, domain_of
from qv.providers.search.free import AlislamSearch, SitemapSearch, WikipediaSearch
from qv.providers.search.router import Pool, SearchRouter
from qv.providers.search.web import ExaSearch, ParallelMCPSearch, TavilySearch
from qv.providers.usage import CallContext, Limit, Metering, QuotaExhausted
from qv.library import Library, PageHit, parse_page_url, query_words
from qv.services.websites import registry_with_marks
from qv.sources import Registry, effective_tier, is_frame_authority
from qv.services.datasets import get_version
from qv.services.judgement import judge_question

PURPOSE_PRIORITY = {"core": 0, "presupposition": 1, "competitor": 2, "definition": 3, "primary_source": 4}
#: Claim types whose answer can change over time: stored pages older than `stored_max_age_days` are skipped.
TIME_SENSITIVE_CLAIMS = {ClaimType.STATISTIC_CURRENT.value, ClaimType.SPORTS_RECORD.value}
RRF_K = 60   # reciprocal rank fusion constant (the phase-1 benchmark's bm25-queries-rrf)


# --- wiring ---------------------------------------------------------------------

@dataclass
class ResearchDeps:
    """Everything the pipeline talks to. Tests build this with fakes."""

    db: Database
    runner: StageRunner
    router: SearchRouter
    fetcher: Fetcher
    quran: QuranSource
    registry: Registry
    cfg: ResearchConfig
    metering: Metering
    wikipedia: SearchProvider | None = None
    alislam: SearchProvider | None = None
    site_searches: dict[str, SearchProvider] = field(default_factory=dict)  # frame domain → sitemap search
    library: Library | None = None                                           # local books (config/library.yaml)
    polite_rpm: dict[str, int] = field(default_factory=lambda: {"wikipedia": 60, "alislam": 10})
    audit_percent: float = 3.0
    named_pools: dict[str, ModelPool] = field(default_factory=dict)  # every llm.pools entry, for --judge-pool
    data_dir: Path | None = None                                     # for the knowledge index (stored pages)


def pool_entries(labels: list[str], providers: dict[str, LLMProvider], pcfg: ProvidersConfig) -> list[PoolEntry]:
    """`provider/model` labels → pool entries with their limits (local models have none).

    Entries whose provider is missing from `providers` (e.g. no Gemini key) are left out.
    """
    out: list[PoolEntry] = []
    for label in labels:
        name, model = split_entry(label)
        if name not in providers:
            continue
        if name == "gemini":
            g = pcfg.llm.gemini
            lim = g.models[model]
            out.append(PoolEntry(providers[name], model, [Limit("day", lim.rpd, g.daily_reset_timezone)], lim.rpm))
        else:
            out.append(PoolEntry(providers[name], model, [], pcfg.llm.ollama.models[model].rpm))
    return out


def build_llm_providers(settings: Settings, pcfg: ProvidersConfig, metering: Metering) -> dict[str, LLMProvider]:
    """The LLM providers that can be used: Gemini when a key is set, Ollama when models are configured."""
    providers: dict[str, LLMProvider] = {}
    if settings.gemini_api_key:
        providers["gemini"] = GeminiProvider(settings.gemini_api_key, metering.recorder)
    o = pcfg.llm.ollama
    if o.models:
        providers["ollama"] = OllamaProvider(metering.recorder, base_url=o.base_url, timeout_s=o.timeout_s,
                                             model_options={m: c.options() for m, c in o.models.items()})
    return providers


def build_pools(providers: dict[str, LLMProvider], pcfg: ProvidersConfig, metering: Metering,
                stages: tuple[str, ...] | None = None) -> dict[str, ModelPool]:
    """One ModelPool per stage from config/providers.yaml (default: every stage listed there)."""
    pools = {}
    for st in stages or tuple(pcfg.stage_pools):
        entries = pool_entries(pcfg.pool_for(st), providers, pcfg)
        if not entries:
            raise LLMError(f"No usable model for stage {st} (pool {pcfg.pool_for(st)}): "
                           "set GEMINI_API_KEY in .env or configure an Ollama model")
        pools[st] = ModelPool(entries, metering)
    return pools


def build_search_pools(settings: Settings, pcfg: ProvidersConfig, metering: Metering) -> list[Pool]:
    """Search pools in configured order; providers without a key are skipped."""
    sc = pcfg.search
    rec = metering.recorder
    pools: list[Pool] = []
    for name in sc.order:
        if name == "parallel":
            pools.append(Pool(ParallelMCPSearch(rec), [Limit("day", sc.parallel.daily_soft_cap)], 1,
                              sc.parallel.rpm))
        elif name == "tavily" and settings.tavily_api_key:
            pools.append(Pool(TavilySearch(settings.tavily_api_key, rec,
                                           credits_per_search=sc.tavily.credits_per_search),
                              [Limit("month", sc.tavily.credits_per_month)], sc.tavily.credits_per_search,
                              sc.tavily.rpm))
        elif name == "exa" and settings.exa_api_key:
            pools.append(Pool(ExaSearch(settings.exa_api_key, rec, est_usd_per_search=sc.exa.est_usd_per_search),
                              [Limit("month", sc.exa.usd_credit_per_month)], sc.exa.est_usd_per_search,
                              sc.exa.rpm))
    return pools


def build_deps(settings: Settings, db: Database) -> ResearchDeps:
    """Real providers from settings and config files."""
    pcfg = load_providers_config()
    metering = Metering.for_db(db, pcfg.reserve_fraction)
    fetcher = Fetcher(db, metering.recorder, metering.limiter, pcfg.fetch, contact=settings.contact)
    rcfg = load_research_config()
    providers = build_llm_providers(settings, pcfg, metering)
    named = {name: ModelPool(entries, metering) for name, labels in pcfg.llm.pools.items()
             if (entries := pool_entries(labels, providers, pcfg))}
    return ResearchDeps(
        db=db, runner=StageRunner(db, build_pools(providers, pcfg, metering)), named_pools=named,
        router=SearchRouter(db, build_search_pools(settings, pcfg, metering), metering,
                            cache_days=rcfg.search_cache_days),
        fetcher=fetcher, quran=QuranSource(fetcher), registry=registry_with_marks(db), cfg=rcfg, metering=metering,
        wikipedia=WikipediaSearch(metering.recorder, settings.contact) if settings.contact else None,
        alislam=AlislamSearch(metering.recorder),
        site_searches={
            site.domain: SitemapSearch(name, site.sitemap, settings.data_dir / "cache" / "sitemaps" / f"{name}.json",
                                       metering.recorder, include=site.include, refresh_days=site.refresh_days,
                                       wait=lambda name=name, rpm=site.rpm: metering.limiter.wait(f"search:{name}", rpm))
            for name, site in pcfg.search.sitemaps.items()},
        polite_rpm={"wikipedia": pcfg.search.wikipedia.rpm, "alislam": pcfg.search.alislam.rpm,
                    **{name: site.rpm for name, site in pcfg.search.sitemaps.items()}},
        audit_percent=rcfg.audit_sample_percent,
        library=Library(settings.data_dir),
        data_dir=settings.data_dir,
    )


# --- runs -------------------------------------------------------------------------

def start_run(db: Database, dataset: str, ext_ids: list[str] | None, *, version_no: int | None = None,
              config: dict[str, Any] | None = None, kind: str = "research") -> int:
    """Create a run for some (or all) questions of a dataset version.

    `kind` "research" gathers evidence; "validate" also judges each question (S4–S6, S8).
    """
    if kind not in ("research", "validate"):
        raise ValueError(f"Unknown run kind {kind!r}")
    with db.session() as s:
        v = get_version(s, dataset, version_no)
        q = select(QuestionRow).where(QuestionRow.dataset_version_id == v.id, QuestionRow.has_errors.is_(False))
        rows = list(s.scalars(q.order_by(QuestionRow.row_no)))
        if ext_ids:
            wanted = set(ext_ids)
            rows = [r for r in rows if r.ext_id in wanted]
            missing = wanted - {r.ext_id for r in rows}
            if missing:
                raise ValueError(f"ids not found (or have structural errors): {sorted(missing, key=_num)}")
        run = Run(dataset_version_id=v.id, kind=kind, status="running",
                  config_json={**(config or {}), "dataset": dataset, "version_no": v.version_no,
                               "profile": v.profile, "ids": [r.ext_id for r in rows]})
        s.add(run)
        s.flush()
        for r in rows:
            s.add(RunQuestion(run_id=run.id, question_id=r.id, status="pending"))
        return run.id


def _num(x: str) -> tuple[int, str]:
    return (int(x), "") if x.isdigit() else (10**9, x)


@dataclass
class RunReport:
    """Summary of a run invocation."""

    run_id: int
    done: int = 0
    failed: int = 0
    pending: int = 0
    stopped_reason: str | None = None
    questions: list[dict] = field(default_factory=list)


def execute_run(deps: ResearchDeps, run_id: int, *, max_questions: int | None = None) -> RunReport:
    """Research every pending question of a run (resumable). Stops cleanly when free quota runs out."""
    db = deps.db
    with db.session() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise ValueError(f"No run {run_id}")
        version = s.get(DatasetVersion, run.dataset_version_id)
        profile = load_profile(version.profile)
        judging = run.kind == "validate"
        judge_name = run.config_json.get("judge_pool")
        todo = list(s.execute(select(RunQuestion.id, QuestionRow).join(QuestionRow,
                    QuestionRow.id == RunQuestion.question_id)
                    .where(RunQuestion.run_id == run_id, RunQuestion.status.in_(("pending", "stopped")))
                    .order_by(QuestionRow.row_no)))
        run.status = "running"
        run.stop_reason = None
    report = RunReport(run_id)
    for count, (rq_id, qrow) in enumerate(todo):
        if max_questions is not None and count >= max_questions:
            break
        q = question_from_row(qrow)
        try:
            stats = research_question(deps, run_id, qrow.id, q, profile, rq_id)
            if judging:
                _set_rq(db, rq_id, "pending", None, None, "judgement")
                stats.update(judge_question(db, deps.runner, run_id, qrow.id, q, profile, stats["s1a_output_id"],
                                            stats["s1b_output_id"], audit_percent=deps.audit_percent,
                                            judge_pool=judge_pool_of(deps, judge_name)))
            _set_rq(db, rq_id, "done", None, stats)
            report.done += 1
            report.questions.append({"id": q.ext_id, **stats})
        except QuotaExhausted as exc:
            _set_rq(db, rq_id, "stopped", str(exc), None)
            report.stopped_reason = str(exc)
            break
        except (LLMError, SearchError, ValueError) as exc:
            _set_rq(db, rq_id, "failed", f"{type(exc).__name__}: {exc}", None)
            report.failed += 1
    with db.session() as s:
        statuses = [r for (r,) in s.execute(select(RunQuestion.status).where(RunQuestion.run_id == run_id))]
        report.pending = sum(1 for st in statuses if st in ("pending", "stopped"))
        run = s.get(Run, run_id)
        if report.stopped_reason:
            run.status, run.stop_reason = "stopped", report.stopped_reason
        elif report.pending:
            run.status = "stopped"
        else:
            run.status = "done" if not any(st == "failed" for st in statuses) else "done_with_failures"
    return report


def judge_pool_of(deps: ResearchDeps, name: str | None) -> tuple[str, ModelPool] | None:
    """The pool a run asked to judge with (S4/S5), or None for the configured one."""
    if not name:
        return None
    if name not in deps.named_pools:
        raise LLMError(f"Judge pool '{name}' is not configured or has no usable model")
    return name, deps.named_pools[name]


def _set_rq(db: Database, rq_id: int, status: str, error: str | None, stats: dict | None, step: str | None = None) -> None:
    with db.session() as s:
        rq = s.get(RunQuestion, rq_id)
        rq.status, rq.error = status, error
        if stats is not None:
            rq.stats_json = stats
        if step is not None:
            rq.step = step


def question_from_row(r: QuestionRow) -> Question:
    """Domain Question from a stored row."""
    return Question(row_no=r.row_no, line_no=r.line_no, ext_id=r.ext_id, question=r.question, type=r.type,
                    answer=r.answer, options=(r.opt_a, r.opt_b, r.opt_c, r.opt_d), difficulty=r.difficulty,
                    category=r.category, subcategory=r.subcategory, topic=r.topic, note=r.note, raw=r.raw_json)


# --- one question -------------------------------------------------------------------

@dataclass
class Candidate:
    """A document candidate for one question."""

    url: str
    mode: str
    found_by: list[dict]
    tier: str
    frame_authority: bool
    best_rank: int


def research_question(deps: ResearchDeps, run_id: int, question_id: int, q: Question, profile: Profile,
                      rq_id: int | None = None) -> dict:
    """Run the evidence pipeline for one question; returns statistics."""
    ctx = CallContext(run_id=run_id, question_id=question_id)
    step = (lambda name: _set_rq(deps.db, rq_id, "pending", None, None, name)) if rq_id else (lambda name: None)
    stats: dict[str, Any] = defaultdict(int)

    step("s1a")
    s1a_run = deps.runner.run(
        stage="s1a", user=render_s1a(q, profile), schema_cls=Decomposition,
        hash_inputs={"q": q.question, "type": q.type, "opts": q.options, "cat": [q.category, q.subcategory, q.topic],
                     "diff": q.difficulty, "profile": [profile.edition, _frame_name(profile), profile.conventions]},
        ctx=CallContext(run_id, question_id, "s1a"), checks=lambda o: check_s1a(o, q))
    s1a: Decomposition = s1a_run.output  # type: ignore[assignment]
    stats["s1a_check_problems"] = len(s1a_run.checks)
    stats["s1a_output_id"] = s1a_run.stage_output_id

    step("s1b")
    s1b_run = deps.runner.run(
        stage="s1b", user=render_s1b(q, profile, s1a), schema_cls=ClaimFormulation,
        hash_inputs={"q": q.question, "opts": q.options, "key": q.answer, "note": q.note,
                     "s1a": s1a_run.stage_output_id, "profile": [profile.edition, profile.conventions]},
        ctx=CallContext(run_id, question_id, "s1b"), checks=lambda o: check_s1b(o, q))
    s1b = filter_s1b_lookups(s1b_run.output, q)  # type: ignore[arg-type]
    stats["s1b_output_id"] = s1b_run.stage_output_id
    stats["s1b_check_problems"] = len(s1b_run.checks)

    step("retrieval")
    candidates: dict[tuple[str, str], Candidate] = {}
    direct_docs: list[tuple[int, str, dict]] = []  # (document_id, mode, found_by)
    for lk in s1a.direct_lookups:
        direct_docs += _direct_lookup(deps, lk.source, lk.ref, None, "A", ctx, stats)
    for lk in s1b.direct_lookups:
        direct_docs += _direct_lookup(deps, lk.source, lk.ref, lk.scheme or profile.conventions.get(
            "quran_numbering"), "B", ctx, stats, for_claim=lk.for_claim)

    # Stored pages first (KB phase 3): S1a's blind queries only; documents only, never another question's passages.
    stored = _stored_pages(deps, question_id, profile, s1a, stats)
    skip_web = deps.cfg.stored_first_skip_web and len(stored) >= deps.cfg.stored_skip_web_min
    if skip_web:
        stats["web_searches_skipped"] = 1
    web_plan = [] if skip_web else _plan_web_queries(s1a, s1b, deps.cfg.max_web_queries_per_question)
    for query, purpose, mode, objective in web_plan:
        try:
            routed = deps.router.search(query, max_results=deps.cfg.results_per_query,
                                        ctx=CallContext(run_id, question_id, "search"), objective=objective)
        except QuotaExhausted:
            raise
        except SearchError as exc:
            stats["search_errors"] += 1
            stats.setdefault("errors", []).append(str(exc)[:200])
            continue
        stats["searches_cached" if routed.cached else "searches_run"] += 1
        _add_hits(candidates, routed.hits, mode, {"via": routed.provider, "query": query, "purpose": purpose},
                  deps.registry, profile, stats)

    core = next((x.q for x in sorted(s1a.queries, key=lambda x: PURPOSE_PRIORITY[x.purpose])), s1a.information_need)
    if deps.wikipedia and deps.cfg.wikipedia_results:
        _free_search(deps, deps.wikipedia, core, deps.cfg.wikipedia_results, candidates, profile, ctx, stats)
    if deps.alislam and deps.cfg.alislam_search_results and _uses_alislam(profile):
        for x in sorted(s1a.queries, key=lambda x: PURPOSE_PRIORITY[x.purpose])[:2]:
            _free_search(deps, deps.alislam, x.q, deps.cfg.alislam_search_results, candidates, profile, ctx, stats)
    if deps.cfg.site_search_results:
        for domain, provider in deps.site_searches.items():
            if _frame_lists(profile, domain):
                _free_search(deps, provider, core, deps.cfg.site_search_results, candidates, profile, ctx, stats)

    chosen: list[tuple[int, str, list[dict]]] = list(stored)
    taken = {doc_id for doc_id, _, _ in stored}
    for mode, budget in (("A", deps.cfg.max_documents_per_question), ("B", deps.cfg.max_note_documents_per_question)):
        chosen += _choose_and_fetch(deps, [c for c in candidates.values() if c.mode == mode], budget, ctx, stats,
                                    taken=taken if mode == "A" else set())
    chosen += [(doc_id, mode, [fb]) for doc_id, mode, fb in direct_docs]
    chosen += _library_pages(deps, profile, [core] + [x.q for x in sorted(s1a.queries, key=lambda x: PURPOSE_PRIORITY[
        x.purpose])[:2]], stats)
    seen: set[tuple[int, str]] = set()
    chosen = [c for c in chosen if (c[0], c[1]) not in seen and not seen.add((c[0], c[1]))]  # each document once
    stats["searches_total"] = (stats.get("searches_run", 0) + stats.get("searches_cached", 0)
                               + sum(v for k, v in stats.items() if k.startswith("searches_")
                                     and k not in ("searches_run", "searches_cached", "searches_total")
                                     and isinstance(v, int)))

    step("extraction")
    note_claims = [(n.id, n.text) for n in s1b.note_claims if n.kind != "explanation"]
    for doc_id, mode, found_by in chosen:
        if mode == "B" and not note_claims:
            continue
        _extract_document(deps, run_id, question_id, q, profile, s1a, mode, doc_id, found_by, note_claims, stats)

    stats["models"] = sorted({s1a_run.model, s1b_run.model} - {""})
    return dict(stats)


def _library_pages(deps: ResearchDeps, profile: Profile, queries: list[str],
                   stats: dict) -> list[tuple[int, str, list[dict]]]:
    """The best book pages for the (answer-blind) queries, stored as documents (mode A)."""
    lib, n = deps.library, deps.cfg.library_pages_per_question
    books = lib.books_for(profile) if lib and n else []
    if not books:
        return []
    best: dict[tuple[str, int], tuple[float, object, str]] = {}
    for query in dict.fromkeys(queries):
        try:
            hits = lib.search(query, books=books, limit=n)
        except Exception as exc:  # noqa: BLE001 — a broken index must not stop research
            stats.setdefault("errors", []).append(f"library: {exc}"[:200])
            return []
        for h in hits:
            key = (h.book_id, h.page)
            if key not in best or h.score > best[key][0]:
                best[key] = (h.score, h, query)
    out = []
    for _, h, query in sorted(best.values(), key=lambda x: -x[0])[:n]:
        doc_id = _store_book_page(deps, h)
        stats["library_pages"] += 1
        out.append((doc_id, "A", [{"via": "library", "query": query, "book": h.book_id, "page": h.page,
                                   "printed_page": h.printed}]))
    return out


def _store_book_page(deps: ResearchDeps, h: PageHit) -> int:
    """A book page as a `library://` document (the same document whichever path found it)."""
    return deps.fetcher.store_text(url=h.url, final_url=h.url, title=deps.library.title_for(h), text=h.text,
                                   source_kind="library", extract_method="pypdf", http_status=None,
                                   ref=f"{h.book_id}:{h.page}")


# --- stored pages first (KB phase 3) ------------------------------------------------------

def stored_queries(s1a: Decomposition) -> list[str]:
    """What the knowledge index is searched with: S1a's answer-blind queries only — never S1b's challenge or
    note queries, the key, the note or the options (METHODOLOGY: retrieval for mode A stays blind)."""
    return list(dict.fromkeys(x.q for x in sorted(s1a.queries, key=lambda x: PURPOSE_PRIORITY[x.purpose])))


def is_time_sensitive(s1a: Decomposition) -> bool:
    """True when the answer can change over time (S1a says so, or a claim type that changes)."""
    return (s1a.time_sensitivity.is_time_sensitive or s1a.claim_type in TIME_SENSITIVE_CLAIMS
            or any(p.claim_type in TIME_SENSITIVE_CLAIMS for p in s1a.presuppositions))


def _stored_pages(deps: ResearchDeps, question_id: int, profile: Profile, s1a: Decomposition,
                  stats: dict) -> list[tuple[int, str, list[dict]]]:
    """Up to `stored_pages_per_question` stored documents for this question (mode A). A missing or broken
    knowledge index never fails research: it is noted in the stats and research goes on without it."""
    if not deps.cfg.stored_pages_per_question or deps.data_dir is None:
        return []
    from qv.kb.index import KnowledgeIndex, index_path
    try:
        idx = KnowledgeIndex.open_readonly(index_path(deps.data_dir))
    except Exception as exc:  # noqa: BLE001
        stats["stored_index_unavailable"] = 1
        stats.setdefault("errors", []).append(f"stored pages: {type(exc).__name__}: {exc}"[:200])
        return []
    try:
        return _pick_stored(deps, idx, question_id, profile, s1a, stats)
    except Exception as exc:  # noqa: BLE001 — a broken index must not stop research
        stats["stored_errors"] += 1
        stats.setdefault("errors", []).append(f"stored pages: {type(exc).__name__}: {exc}"[:200])
        return []
    finally:
        idx.close()


def _pick_stored(deps: ResearchDeps, idx: Any, question_id: int, profile: Profile, s1a: Decomposition,
                 stats: dict) -> list[tuple[int, str, list[dict]]]:
    """Per-query BM25 fused with RRF; skips what this question already read, tier X / skipped sites, books this
    edition does not use, too-old pages for time-sensitive questions, and a second page from the same site."""
    cfg = deps.cfg
    fused: dict[str, float] = defaultdict(float)
    first: dict[str, tuple[str, int, Any]] = {}          # doc key → (query, rank, hit) where it ranked best
    for query in stored_queries(s1a):
        stats["stored_searches"] += 1
        for rank, h in enumerate(kb_search(idx, query, limit=cfg.stored_results_per_query, chunks_per_doc=0), 1):
            fused[h.doc_key] += 1 / (RRF_K + rank)
            if h.doc_key not in first or rank < first[h.doc_key][1]:
                first[h.doc_key] = (query, rank, h)
    if not fused:
        return []
    canon_of = idx.canon_of_document()
    with deps.db.session() as s:
        read = set(s.scalars(select(QuestionDocument.document_id).where(QuestionDocument.question_id == question_id)))
    read_canon = {canon_of.get(d, f"doc:{d}") for d in read}
    books = set(deps.library.books_for(profile)) if deps.library else set()
    fresh_only = is_time_sensitive(s1a)
    oldest = datetime.now(UTC) - timedelta(days=cfg.stored_max_age_days)
    out: list[tuple[int, str, list[dict]]] = []
    sites: set[str] = set()
    for key in sorted(fused, key=lambda k: -fused[k]):
        if len(out) >= cfg.stored_pages_per_question:
            break
        query, rank, h = first[key]
        if h.canon_key in read_canon or key in read_canon or (h.document_id is not None and h.document_id in read):
            stats["stored_already_read"] += 1
            continue
        book = (h.book_id, h.page) if h.source_kind == "book" else (
            parse_page_url(h.url) if h.source_kind == "library" else None)
        if book is not None:
            if book[0] not in books:
                stats["stored_skipped_book"] += 1        # a book this edition does not use
                continue
            site = f"book:{book[0]}"
        else:
            if deps.registry.is_excluded(h.url):
                stats["stored_skipped_site"] += 1        # tier X or a site marked "needs special access"
                continue
            site = domain_of(h.url)
        if fresh_only and not _fresh_enough(h.fetched_at, oldest):
            stats["stored_too_old"] += 1
            continue
        if site in sites:                                # echo defence: one stored page per site / book
            continue
        doc_id = _stored_document_id(deps, h, book)
        if doc_id is None or doc_id in read:
            continue
        sites.add(site)
        out.append((doc_id, "A", [{"via": "stored", "query": query, "doc_key": h.doc_key, "rank": rank}]))
        stats["stored_pages"] += 1
    return out


def _fresh_enough(fetched_at: str, oldest: datetime) -> bool:
    """True when a stored page was fetched after `oldest` (no date — e.g. a book page — is never fresh)."""
    try:
        when = datetime.fromisoformat(fetched_at)
    except (TypeError, ValueError):
        return False
    return (when if when.tzinfo else when.replace(tzinfo=UTC)) >= oldest


def _stored_document_id(deps: ResearchDeps, h: Any, book: tuple[str, int] | None) -> int | None:
    """The `documents.id` to read: the existing one for a stored page; for a book page the same `library://`
    document the library path makes (None when the page is no longer in the library)."""
    if book is None:
        return h.document_id
    lib = deps.library
    row = lib.conn.execute("SELECT printed, text FROM pages WHERE book_id = ? AND page = ?", book).fetchone() \
        if lib and book[0] in lib.books else None
    if row is None:
        return h.document_id
    return _store_book_page(deps, PageHit(book[0], book[1], row[0], 0.0, row[1]))


def search_summary(db: Database, run_id: int) -> dict:
    """Searches and stored pages per question of a run (for "searches per question go down" in a later eval)."""
    with db.session() as s:
        stats = [r or {} for (r,) in s.execute(select(RunQuestion.stats_json).where(
            RunQuestion.run_id == run_id, RunQuestion.status == "done"))]
    n = len(stats)
    tot = {k: sum(int(st.get(k, 0) or 0) for st in stats) for k in
           ("searches_run", "searches_cached", "searches_total", "stored_pages", "stored_searches",
            "web_searches_skipped")}
    return {"questions": n, **tot,
            "searches_run_per_question": round(tot["searches_run"] / n, 2) if n else 0.0,
            "searches_per_question": round(tot["searches_total"] / n, 2) if n else 0.0,
            "stored_pages_per_question": round(tot["stored_pages"] / n, 2) if n else 0.0}


def _frame_name(profile: Profile) -> str | None:
    return profile.frame.name if profile.frame else None


def _uses_alislam(profile: Profile) -> bool:
    return _frame_lists(profile, "alislam.org")


def _frame_lists(profile: Profile, domain: str) -> bool:
    """True when the profile's frame names `domain` among its authorities."""
    return bool(profile.frame and any(domain in a for a in profile.frame.authorities))


def _plan_web_queries(s1a: Decomposition, s1b: ClaimFormulation, budget: int) -> list[tuple[str, str, str, str | None]]:
    """Choose which queries spend web-search quota: (query, purpose, mode, objective).

    Order: best blind query, one per material presupposition, one challenge query, one note
    query, then the remaining blind / challenge / note queries. Blind queries carry the
    (answer-blind) information need as the search objective; others carry only themselves.
    """
    blind = sorted(s1a.queries, key=lambda x: PURPOSE_PRIORITY[x.purpose])
    material = [p.id for p in s1a.presuppositions if p.material]
    ordered: list[tuple[str, str, str, str | None]] = []

    def add(item: tuple[str, str, str, str | None]) -> None:
        if all(item[0].strip().lower() != o[0].strip().lower() for o in ordered):
            ordered.append(item)

    need = s1a.information_need
    if blind:
        add((blind[0].q, f"blind:{blind[0].purpose}", "A", need))
    for pid in material:
        for x in blind:
            if x.target == pid:
                add((x.q, f"blind:{x.purpose}", "A", need))
                break
    if s1b.challenge_queries:
        add((s1b.challenge_queries[0].q, f"challenge:{s1b.challenge_queries[0].angle}", "A", None))
    if s1b.note_queries:
        add((s1b.note_queries[0].q, f"note:{s1b.note_queries[0].for_claim}", "B", None))
    for x in blind:
        add((x.q, f"blind:{x.purpose}", "A", need))
    for c in s1b.challenge_queries:
        add((c.q, f"challenge:{c.angle}", "A", None))
    for n in s1b.note_queries:
        add((n.q, f"note:{n.for_claim}", "B", None))
    return ordered[:budget]


def _add_hits(candidates: dict[tuple[str, str], Candidate], hits: list[SearchHit], mode: str, found: dict,
              registry: Registry, profile: Profile, stats: dict) -> None:
    for h in hits:
        if registry.is_excluded(h.url):
            stats["excluded_hits"] += 1
            continue
        key = (h.url, mode)
        c = candidates.get(key)
        if c is None:
            candidates[key] = Candidate(h.url, mode, [{**found, "rank": h.rank}], registry.tier(h.url),
                                        is_frame_authority(h.url, profile), h.rank)
        else:
            c.found_by.append({**found, "rank": h.rank})
            c.best_rank = min(c.best_rank, h.rank)


def _free_search(deps: ResearchDeps, provider: SearchProvider, query: str, n: int,
                 candidates: dict[tuple[str, str], Candidate], profile: Profile, ctx: CallContext,
                 stats: dict) -> None:
    deps.metering.limiter.wait(f"search:{provider.name}", deps.polite_rpm.get(provider.name, 10))
    try:
        hits = provider.search(query, max_results=n, ctx=CallContext(ctx.run_id, ctx.question_id, "search"))
    except SearchError as exc:
        stats["search_errors"] += 1
        stats.setdefault("errors", []).append(str(exc)[:200])
        return
    stats[f"searches_{provider.name}"] += 1
    _add_hits(candidates, hits, "A", {"via": provider.name, "query": query, "purpose": "free"},
              deps.registry, profile, stats)


def _choose_and_fetch(deps: ResearchDeps, cands: list[Candidate], budget: int, ctx: CallContext,
                      stats: dict, *, taken: set[int] | None = None) -> list[tuple[int, str, list[dict]]]:
    """Fetch the best candidates until `budget` documents are stored.

    Round-robin over the queries that found them (so each query — blind, presupposition,
    challenge — contributes), preferring frame authorities, better tiers, better ranks,
    and new domains.
    """
    if budget <= 0 or not cands:
        return []
    by_query: dict[str, list[Candidate]] = defaultdict(list)
    for c in cands:
        by_query[c.found_by[0]["query"]].append(c)
    order = {"P": 0, "S": 1, "T": 2, "X": 3}
    for lst in by_query.values():
        lst.sort(key=lambda c: (not c.frame_authority, order[c.tier], c.best_rank))
    queues = list(by_query.values())
    chosen: list[tuple[int, str, list[dict]]] = []
    seen_urls: set[str] = set()
    domains: set[str] = set()
    deferred: list[Candidate] = []
    while len(chosen) < budget and any(queues):
        for qlist in queues:
            if len(chosen) >= budget or not qlist:
                continue
            c = qlist.pop(0)
            if c.url in seen_urls:
                continue
            if domain_of(c.url) in domains:
                deferred.append(c)
                continue
            seen_urls.add(c.url)
            if _fetch_into(deps, c, ctx, stats, chosen, taken or set()):
                domains.add(domain_of(c.url))
    for c in deferred:  # same-domain pages only if there was nothing else
        if len(chosen) >= budget:
            break
        if c.url not in seen_urls:
            seen_urls.add(c.url)
            _fetch_into(deps, c, ctx, stats, chosen, taken or set())
    return chosen


def _fetch_into(deps: ResearchDeps, c: Candidate, ctx: CallContext, stats: dict,
                chosen: list[tuple[int, str, list[dict]]], taken: set[int]) -> bool:
    """Fetch one candidate into `chosen` (a web PDF: its best pages). `taken` = documents already chosen by
    another path (stored pages), so the web budget is not spent on them again."""
    res = deps.fetcher.fetch(c.url, CallContext(ctx.run_id, ctx.question_id, "fetch"))
    if not res.ok:
        stats[f"fetch_{res.status}"] += 1
        return False
    have = {doc_id for doc_id, m, _ in chosen if m == c.mode} | taken
    if res.page_ids:
        pages = [(pid, n) for pid, n in _best_pdf_pages(deps, res.page_ids, c, deps.cfg.pdf_pages_per_document)
                 if pid not in have]
        for pid, n in pages:
            chosen.append((pid, c.mode, [{**fb, "pdf_page": n} for fb in c.found_by]))
        stats["documents"] += len(pages)
        stats["pdf_pages"] += len(pages)
        return bool(pages)
    if res.document_id in have:
        return False
    stats["documents"] += 1
    chosen.append((res.document_id, c.mode, c.found_by))
    return True


def _best_pdf_pages(deps: ResearchDeps, page_ids: tuple[int, ...], c: Candidate, n: int) -> list[tuple[int, int]]:
    """The `n` pages of a web PDF that best match the queries that found it: (document id, page number).
    Shared query words weighted by rarity across the PDF's pages; earlier pages win ties."""
    words = list(dict.fromkeys(w for fb in c.found_by for w in query_words(fb.get("query") or "")))
    with deps.db.session() as s:
        pages = [(d.id, d.final_url, d.text.lower()) for d in s.scalars(select(Document).where(Document.id.in_(page_ids)))]
    pages.sort(key=lambda p: p[0])
    df = {w: sum(w in t for _, _, t in pages) for w in words}
    idf = {w: math.log(1 + len(pages) / df[w]) for w in words if df[w]}

    def page_no(url: str) -> int:
        return int(url.rsplit("#page=", 1)[1]) if "#page=" in url else 0

    ranked = sorted(pages, key=lambda p: -sum(v for w, v in idf.items() if w in p[2]))
    return [(pid, page_no(url)) for pid, url, _ in ranked[:n]]


def _direct_lookup(deps: ResearchDeps, source: str, ref: str, scheme: str | None, mode: str, ctx: CallContext,
                   stats: dict, for_claim: str | None = None) -> list[tuple[int, str, dict]]:
    if source != "quran":
        stats[f"lookup_unsupported_{source}"] += 1  # hadith/wikidata: no direct source yet (searched instead)
        return []
    try:
        results = deps.quran.lookup(ref, scheme, CallContext(ctx.run_id, ctx.question_id, "lookup"))
    except QuranRefError as exc:
        stats["lookup_bad_ref"] += 1
        stats.setdefault("errors", []).append(str(exc)[:200])
        return []
    out = []
    for r in results:
        if r.ok:
            stats["lookups_ok"] += 1
            out.append((r.document_id, mode, {"via": "quran", "ref": ref, "scheme": scheme, "for_claim": for_claim}))
        else:
            stats["lookups_failed"] += 1
    return out


def ungrounded_quotes(out: Extraction, index: DocumentIndex) -> list[str]:
    """Quotes (first 200 characters) that are not word for word in the document."""
    return [p.quote[:200] for p in out.passages if index.find(p.quote) is None]


def s3_quote_problems(out: Extraction, index: DocumentIndex) -> list[str]:
    """Code check stored with an S3 output: one problem per quote that is not verbatim."""
    return [f"not verbatim in the document: {b[:120]!r}" for b in ungrounded_quotes(out, index)]


def s3_retry_feedback(bad: list[str]) -> str:
    """What the S3 retry is told: which quotes were not found word for word."""
    lines = "\n".join(f"- {b!r}" for b in bad)
    return ("\n\nA previous answer to this request quoted text that is NOT word for word in the document:\n"
            f"{lines}\nCopy every quote exactly as it is written in the document (same words, same order, no "
            "changes, no joining of separate sentences), or leave it out. Return all passages again.")


def _extract_document(deps: ResearchDeps, run_id: int, question_id: int, q: Question, profile: Profile,
                      s1a: Decomposition, mode: str, doc_id: int, found_by: list[dict],
                      note_claims: list[tuple[str, str]], stats: dict) -> None:
    """S3 on one document (windowed), grounding check, then store passages atomically."""
    db = deps.db
    with db.session() as s:
        qd = s.scalar(select(QuestionDocument).where(
            QuestionDocument.run_id == run_id, QuestionDocument.question_id == question_id,
            QuestionDocument.document_id == doc_id, QuestionDocument.mode == mode))
        doc = s.get(Document, doc_id)
        if qd is not None and qd.status in ("extracted", "excluded"):
            stats["documents_already_extracted"] += 1
            return
        book_tier = deps.library.tier(doc.final_url) if deps.library and doc.source_kind == "library" else None
        reg_tier = "P" if doc.source_kind == "quran" else book_tier or deps.registry.tier(doc.final_url)
        frame = (deps.library.is_frame_authority(doc.final_url, profile) if book_tier
                 else is_frame_authority(doc.final_url, profile))
        if qd is None:
            qd = QuestionDocument(run_id=run_id, question_id=question_id, document_id=doc_id, mode=mode,
                                  found_by_json=found_by, registry_tier=reg_tier,
                                  frame_authority=frame, status="pending")
            s.add(qd)
            s.flush()
        qd_id = qd.id
        text, meta = doc.text, DocMeta(doc.id, doc.final_url, doc.title or "", doc.domain,
                                       doc.fetched_at.date().isoformat())
        content_sha = doc.content_sha256

    index = DocumentIndex(text)
    targets = s3_target_ids(s1a, mode, [cid for cid, _ in note_claims])
    parts = windows(text, deps.cfg.s3_window_chars, deps.cfg.s3_window_overlap_chars, deps.cfg.s3_max_windows)
    grounded: list[tuple[Any, Any, int]] = []  # (passage, Grounded, stage_output_id)
    page = None
    dropped_total = 0
    last_sid: int | None = None
    try:
        for wi, part in enumerate(parts):
            user = render_s3(q, s1a, mode=mode, doc=meta, window=part,
                             note_claims=note_claims if mode == "B" else None)
            hash_inputs = {"doc": content_sha, "window": wi, "mode": mode, "need": s1a.information_need,
                           "answer_type": s1a.answer_type, "opts": q.options if q.is_multi else None,
                           "pre": [p.model_dump() for p in s1a.presuppositions] if mode == "A" else None,
                           "notes": note_claims if mode == "B" else None}
            run = deps.runner.run(stage="s3", user=user, schema_cls=Extraction, hash_inputs=hash_inputs,
                                  ctx=CallContext(run_id, question_id, "s3"),
                                  checks=lambda o: s3_quote_problems(o, index), retry_on_check_failure=False)
            out: Extraction = run.output  # type: ignore[assignment]
            last_sid = run.stage_output_id
            page = page or out.page
            attempts = [(out, run.stage_output_id)]
            bad = ungrounded_quotes(out, index)
            if bad and deps.cfg.s3_retry_dropped_quotes:
                # One more request, only when a quote is not word for word in the document (target < 2 % dropped).
                # Its own cache entry; the grounded passages of both attempts are kept (grounding proves each one).
                stats["s3_retries"] += 1
                try:
                    retry = deps.runner.run(
                        stage="s3", user=user + s3_retry_feedback(bad), schema_cls=Extraction,
                        hash_inputs={**hash_inputs, "retry_for": bad}, ctx=CallContext(run_id, question_id, "s3"),
                        checks=lambda o: s3_quote_problems(o, index), retry_on_check_failure=False)
                    attempts.append((retry.output, retry.stage_output_id))  # type: ignore[arg-type]
                    last_sid = retry.stage_output_id
                except LLMError as exc:  # the first attempt still counts; QuotaExhausted is not an LLMError
                    stats["s3_retry_failed"] += 1
                    stats.setdefault("errors", []).append(f"S3 retry: {type(exc).__name__}")
            spans = set()
            for n, (attempt, sid) in enumerate(attempts):
                last = n == len(attempts) - 1
                for p in attempt.passages:
                    g = index.find(p.quote)
                    if g is None or p.target not in targets:
                        if last:  # a quote counts as dropped only when the last attempt still has it wrong
                            dropped_total += 1
                        continue
                    if n and (g.start, g.end, p.target) not in spans:
                        stats["s3_quotes_recovered"] += 1
                    spans.add((g.start, g.end, p.target))
                    grounded.append((p, g, sid))
    except LLMError as exc:
        with db.session() as s:
            row = s.get(QuestionDocument, qd_id)
            row.status, row.error = "failed", str(exc)[:500]
        stats["s3_failed"] += 1
        return

    # A library book was chosen by the person (config/library.yaml): its tier is not lowered by page kind.
    eff = reg_tier if book_tier else effective_tier(reg_tier, page.page_kind if page else None)
    excluded = eff == "X" or (page is not None and not page.about_right_subject)
    # Deduplicate identical spans found in overlapping windows.
    unique: dict[tuple[int, int, str], tuple[Any, Any, int]] = {}
    for p, g, sid in grounded:
        unique.setdefault((g.start, g.end, p.target), (p, g, sid))
    with db.session() as s:
        row = s.get(QuestionDocument, qd_id)
        row.page_kind = page.page_kind if page else None
        row.about_right_subject = page.about_right_subject if page else None
        row.publisher = page.publisher if page else None
        row.concerns_json = page.concerns if page else []
        row.effective_tier = eff
        row.stage_output_id = last_sid
        row.dropped_count = dropped_total
        row.grounded_count = 0 if excluded else len(unique)
        row.status = "excluded" if excluded else "extracted"
        if not excluded:
            for p, g, sid in unique.values():
                s.add(Passage(run_id=run_id, question_id=question_id, question_document_id=qd_id, document_id=doc_id,
                              stage_output_id=sid, mode=mode, target=p.target, quote=g.text, char_start=g.start,
                              char_end=g.end, asserted_answer=p.asserted_answer,
                              matches_option=p.matches_option if q.is_multi else None, stance=p.stance,
                              qualifiers=p.qualifiers, as_of=p.as_of, attributed_origin=p.attributed_origin,
                              is_primary_for_claim=p.is_primary_for_claim))
    stats["s3_documents"] += 1
    stats["passages_grounded"] += 0 if excluded else len(unique)
    stats["passages_dropped"] += dropped_total
    if excluded:
        stats["documents_excluded"] += 1


# --- reading results (CLI / UI) ----------------------------------------------------

def question_evidence(db: Database, run_id: int, question_id: int) -> dict:
    """Everything stored for one question in a run, for display."""
    with db.session() as s:
        rq = s.scalar(select(RunQuestion).where(RunQuestion.run_id == run_id, RunQuestion.question_id == question_id))
        stats = (rq.stats_json or {}) if rq else {}
        # Stage outputs may be reused from an earlier run; the run question records which ones were used.
        outs = {st: s.get(StageOutput, stats[f"{st}_output_id"]) for st in ("s1a", "s1b")
                if stats.get(f"{st}_output_id")}
        docs = []
        for qd, d in s.execute(select(QuestionDocument, Document).join(Document, Document.id == QuestionDocument.document_id)
                               .where(QuestionDocument.run_id == run_id, QuestionDocument.question_id == question_id)
                               .order_by(QuestionDocument.id)):
            passages = list(s.scalars(select(Passage).where(Passage.question_document_id == qd.id).order_by(Passage.char_start)))
            docs.append({"qd": qd, "doc": d, "passages": passages})
        return {"stage_outputs": outs, "documents": docs, "run_question": rq}
