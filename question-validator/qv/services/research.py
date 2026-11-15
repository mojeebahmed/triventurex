"""Research pipeline (phase 2): from a question to grounded, stored evidence. No verdicts.

Per question:  S1a (blind) → S1b (claims) → direct lookups (Qur'an) → searches (free
pools, cached) → choose and fetch documents → S3 per document (blind) → grounding
check → passages stored. Every step is idempotent: stage outputs are reused by input
hash, searches and fetches are cached, and a document's passages are written in the
same transaction that marks it extracted — so an interrupted run resumes cleanly.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
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
from qv.domain.stages import ClaimFormulation, Decomposition, Extraction
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
from qv.providers.search.free import AlislamSearch, WikipediaSearch
from qv.providers.search.router import Pool, SearchRouter
from qv.providers.search.web import ExaSearch, ParallelMCPSearch, TavilySearch
from qv.providers.usage import CallContext, Limit, Metering, QuotaExhausted
from qv.sources import Registry, effective_tier, is_frame_authority, load_registry
from qv.services.datasets import get_version

PURPOSE_PRIORITY = {"core": 0, "presupposition": 1, "competitor": 2, "definition": 3, "primary_source": 4}


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
    polite_rpm: dict[str, int] = field(default_factory=lambda: {"wikipedia": 60, "alislam": 10})


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
                stages: tuple[str, ...] = ("s1a", "s1b", "s3")) -> dict[str, ModelPool]:
    """One ModelPool per stage from config/providers.yaml."""
    pools = {}
    for st in stages:
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
    return ResearchDeps(
        db=db, runner=StageRunner(db, build_pools(build_llm_providers(settings, pcfg, metering), pcfg, metering)),
        router=SearchRouter(db, build_search_pools(settings, pcfg, metering), metering,
                            cache_days=rcfg.search_cache_days),
        fetcher=fetcher, quran=QuranSource(fetcher), registry=load_registry(), cfg=rcfg, metering=metering,
        wikipedia=WikipediaSearch(metering.recorder, settings.contact) if settings.contact else None,
        alislam=AlislamSearch(metering.recorder),
        polite_rpm={"wikipedia": pcfg.search.wikipedia.rpm, "alislam": pcfg.search.alislam.rpm},
    )


# --- runs -------------------------------------------------------------------------

def start_run(db: Database, dataset: str, ext_ids: list[str] | None, *, version_no: int | None = None,
              config: dict[str, Any] | None = None) -> int:
    """Create a research run for some (or all) questions of a dataset version."""
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
        run = Run(dataset_version_id=v.id, kind="research", status="running",
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

    for query, purpose, mode, objective in _plan_web_queries(s1a, s1b, deps.cfg.max_web_queries_per_question):
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

    chosen: list[tuple[int, str, list[dict]]] = []
    for mode, budget in (("A", deps.cfg.max_documents_per_question), ("B", deps.cfg.max_note_documents_per_question)):
        chosen += _choose_and_fetch(deps, [c for c in candidates.values() if c.mode == mode], budget, ctx, stats)
    chosen += [(doc_id, mode, [fb]) for doc_id, mode, fb in direct_docs]

    step("extraction")
    note_claims = [(n.id, n.text) for n in s1b.note_claims if n.kind != "explanation"]
    for doc_id, mode, found_by in chosen:
        if mode == "B" and not note_claims:
            continue
        _extract_document(deps, run_id, question_id, q, profile, s1a, mode, doc_id, found_by, note_claims, stats)

    stats["models"] = sorted({s1a_run.model, s1b_run.model} - {""})
    return dict(stats)


def _frame_name(profile: Profile) -> str | None:
    return profile.frame.name if profile.frame else None


def _uses_alislam(profile: Profile) -> bool:
    return bool(profile.frame and any("alislam.org" in a for a in profile.frame.authorities))


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
                      stats: dict) -> list[tuple[int, str, list[dict]]]:
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
            if _fetch_into(deps, c, ctx, stats, chosen):
                domains.add(domain_of(c.url))
    for c in deferred:  # same-domain pages only if there was nothing else
        if len(chosen) >= budget:
            break
        if c.url not in seen_urls:
            seen_urls.add(c.url)
            _fetch_into(deps, c, ctx, stats, chosen)
    return chosen


def _fetch_into(deps: ResearchDeps, c: Candidate, ctx: CallContext, stats: dict,
                chosen: list[tuple[int, str, list[dict]]]) -> bool:
    res = deps.fetcher.fetch(c.url, CallContext(ctx.run_id, ctx.question_id, "fetch"))
    if not res.ok:
        stats[f"fetch_{res.status}"] += 1
        return False
    if any(doc_id == res.document_id and m == c.mode for doc_id, m, _ in chosen):
        return False
    stats["documents"] += 1
    chosen.append((res.document_id, c.mode, c.found_by))
    return True


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
        reg_tier = "P" if doc.source_kind == "quran" else deps.registry.tier(doc.final_url)
        if qd is None:
            qd = QuestionDocument(run_id=run_id, question_id=question_id, document_id=doc_id, mode=mode,
                                  found_by_json=found_by, registry_tier=reg_tier,
                                  frame_authority=is_frame_authority(doc.final_url, profile), status="pending")
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
            def check(out: Extraction) -> list[str]:
                bad = [p.quote[:120] for p in out.passages if index.find(p.quote) is None]
                return ([f"These quotes are not verbatim in the document; copy text exactly: {bad}"]
                        if len(bad) > 1 else [])

            run = deps.runner.run(
                stage="s3",
                user=render_s3(q, s1a, mode=mode, doc=meta, window=part,
                               note_claims=note_claims if mode == "B" else None),
                schema_cls=Extraction,
                hash_inputs={"doc": content_sha, "window": wi, "mode": mode, "need": s1a.information_need,
                             "answer_type": s1a.answer_type, "opts": q.options if q.is_multi else None,
                             "pre": [p.model_dump() for p in s1a.presuppositions] if mode == "A" else None,
                             "notes": note_claims if mode == "B" else None},
                ctx=CallContext(run_id, question_id, "s3"), checks=check)
            out: Extraction = run.output  # type: ignore[assignment]
            last_sid = run.stage_output_id
            page = page or out.page
            for p in out.passages:
                g = index.find(p.quote)
                if g is None or p.target not in targets:
                    dropped_total += 1
                    continue
                grounded.append((p, g, run.stage_output_id))
    except LLMError as exc:
        with db.session() as s:
            row = s.get(QuestionDocument, qd_id)
            row.status, row.error = "failed", str(exc)[:500]
        stats["s3_failed"] += 1
        return

    eff = effective_tier(reg_tier, page.page_kind if page else None)
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
