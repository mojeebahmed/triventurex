"""Command-line interface (`qv`). Thin: parses arguments and calls services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from qv.config import DEFAULT_PROFILE, Settings, available_profiles, load_profile
from qv.db.session import Database
from qv.domain.structural import Severity, StructuralReport
from qv.services import datasets as ds_service
from qv.services import exports as export_service

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Question Validator — check, import and export Triventurex question CSVs.")
eval_app = typer.Typer(no_args_is_help=True, help="Evaluation set tools.")
app.add_typer(eval_app, name="eval")

_state: dict[str, Settings] = {}


@app.callback()
def main(data_dir: Annotated[Path | None, typer.Option(help="Data directory (default: ./data or $QV_DATA_DIR)")]
         = None) -> None:
    """Global options."""
    _state["settings"] = Settings(data_dir=data_dir) if data_dir else Settings()


def _settings() -> Settings:
    """Settings chosen in the callback (or defaults when called programmatically)."""
    return _state.get("settings") or Settings()


def _db() -> Database:
    """Open (and migrate) the configured database."""
    return Database(_settings().database_url)


def _print_report(report: StructuralReport, *, show: str = "warning", limit: int = 50) -> None:
    """Print counts and the issues at or above `show` severity."""
    order = [Severity.ERROR, Severity.WARNING, Severity.INFO]
    typer.echo(f"{report.row_count} questions ({report.multi_count} multi, {report.open_count} open) — "
               f"{report.count(Severity.ERROR)} error(s), {report.count(Severity.WARNING)} warning(s), "
               f"{report.count(Severity.INFO)} info")
    cutoff = order.index(Severity(show))
    shown = [i for i in report.issues if order.index(i.severity) <= cutoff]
    for i in shown[:limit]:
        where = f"line {i.line_no}" if i.line_no else "file"
        ident = f" id {i.ext_id}" if i.ext_id else ""
        typer.echo(f"  {i.severity.value.upper():7} {where}{ident}  [{i.code.value}] {i.message}")
    if len(shown) > limit:
        typer.echo(f"  … {len(shown) - limit} more (use --limit)")
    typer.echo("OK for the game." if report.ok_for_game else "NOT OK: the game's checker would fail.")


@app.command()
def check(file: Path, profile: Annotated[str, typer.Option(help="Profile name")] = DEFAULT_PROFILE,
          show: Annotated[str, typer.Option(help="error | warning | info")] = "warning",
          limit: int = 50) -> None:
    """Check a CSV without storing it. Exit code 1 when there are errors."""
    result = ds_service.check_bytes(file.read_bytes(), load_profile(profile))
    _print_report(result.report, show=show, limit=limit)
    raise typer.Exit(0 if result.report.ok_for_game else 1)


@app.command("import")
def import_cmd(file: Path,
               dataset: Annotated[str, typer.Option(help="Dataset name (e.g. world-tour)")],
               profile: Annotated[str | None, typer.Option(help="Profile (default: dataset name if a "
                                                                "profile exists, else general)")] = None,
               show: str = "warning", limit: int = 50) -> None:
    """Import a CSV as a new immutable version of a dataset."""
    db = _db()
    with db.session() as s:
        res = ds_service.import_dataset(s, file.read_bytes(), dataset_name=dataset,
                                        source_filename=file.name, profile_name=profile)
    if not res.created:
        typer.echo(f"{dataset}: identical to version {res.version_no} — nothing imported.")
        return
    typer.echo(f"{dataset}: imported as version {res.version_no} (sha256 {res.file_sha256[:12]}…)")
    _print_report(res.report, show=show, limit=limit)
    if res.diff is not None:
        d = res.diff
        typer.echo(f"Changes since previous version: {len(d.added)} added, {len(d.removed)} removed, "
                   f"{len(d.changed)} changed, {d.unchanged_count} unchanged")


@app.command("datasets")
def list_datasets() -> None:
    """List datasets and their versions."""
    db = _db()
    with db.session() as s:
        for d in ds_service.list_datasets(s):
            typer.echo(f"{d.name}  (profile {d.profile})")
            for v in d.versions:
                typer.echo(f"  v{v.version_no}  {v.imported_at:%Y-%m-%d %H:%M}  {v.row_count} rows  "
                           f"{v.error_count}E {v.warning_count}W {v.info_count}I  {v.source_filename}")


@app.command()
def issues(dataset: str, version: Annotated[int | None, typer.Option(help="Version (default latest)")] = None,
           severity: str = "info") -> None:
    """List the stored structural issues of a dataset version."""
    order = ["error", "warning", "info"]
    db = _db()
    with db.session() as s:
        v = ds_service.get_version(s, dataset, version)
        for i in ds_service.version_issues(s, v):
            if order.index(i.severity) <= order.index(severity):
                where = f"line {i.line_no}" if i.line_no else "file"
                typer.echo(f"{i.severity.upper():7} {where} id {i.ext_id or '-'}  [{i.code}] {i.message}")


@app.command()
def diff(dataset: str, old: int, new: int) -> None:
    """Show what changed between two versions (by CSV id)."""
    db = _db()
    with db.session() as s:
        d = ds_service.diff_versions(s, ds_service.get_version(s, dataset, old),
                                     ds_service.get_version(s, dataset, new))
    typer.echo(f"added: {', '.join(d.added) or '-'}")
    typer.echo(f"removed: {', '.join(d.removed) or '-'}")
    for c in d.changed:
        typer.echo(f"changed: id {c.ext_id} ({', '.join(c.fields)})")
    typer.echo(f"unchanged: {d.unchanged_count}")
    if d.duplicate_ids:
        typer.echo(f"duplicate ids (compared by first occurrence): {', '.join(d.duplicate_ids)}")


@app.command()
def export(kind: Annotated[str, typer.Argument(help="corrected | verified | results | original | report")],
           dataset: str,
           version: Annotated[int | None, typer.Option(help="Version (default latest)")] = None,
           out: Annotated[Path | None, typer.Option(help="Output file (default: data/exports/…)")] = None,
           changes: Annotated[Path | None, typer.Option(
               help='corrected: JSON {"<id>": {"<column>": "<new value>"}} instead of your decisions')] = None
           ) -> None:
    """Export: corrected (your decisions applied), verified (only checked questions), results (one line per
    question), original (the imported file) or report (format problems)."""
    db = _db()
    with db.session() as s:
        v = ds_service.get_version(s, dataset, version)
        if kind == "original":
            data, suffix = export_service.export_original(v), "original.csv"
        elif kind == "report":
            data, suffix = export_service.structural_report_csv(s, v), "structural-report.csv"
        elif kind in ("verified", "results") or (kind == "corrected" and changes is None):
            if version is not None:
                raise typer.BadParameter(f"{kind} always uses the latest version")
            data, name, summary = export_service.workflow_export(db, dataset, kind)
            target = out or _settings().exports_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            typer.echo(f"Wrote {target}: " + ", ".join(f"{k} {v}" for k, v in summary.items()))
            return
        elif kind == "corrected":
            result = export_service.corrected_csv(v, json.loads(changes.read_text(encoding="utf-8")))
            data, suffix = result.data, "corrected.csv"
            typer.echo(f"Changed ids: {', '.join(result.changed_ids) or '-'}")
        else:
            raise typer.BadParameter("kind must be corrected, verified, results, original or report")
        target = out or _settings().exports_dir / f"{dataset}-v{v.version_no}-{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    typer.echo(f"Wrote {target} ({len(data)} bytes)")


@app.command()
def profiles() -> None:
    """List available profiles."""
    for name in available_profiles():
        p = load_profile(name)
        frame = f"frame: {p.frame.name}{'' if p.frame.confirmed else ' (draft)'}" if p.frame else "no frame"
        typer.echo(f"{name:18} {p.audience} — {frame}")


# --- research (phase 2) -------------------------------------------------------------

def _parse_ids(ids: str | None) -> list[str] | None:
    """'1,2,5-7' → ['1','2','5','6','7']."""
    if not ids:
        return None
    out: list[str] = []
    for part in ids.split(","):
        part = part.strip()
        if "-" in part and all(x.strip().isdigit() for x in part.split("-", 1)):
            a, b = (int(x) for x in part.split("-", 1))
            out += [str(i) for i in range(a, b + 1)]
        elif part:
            out.append(part)
    return out


def _quota_lines(db: Database) -> list[str]:
    """Remaining free quota per provider/model right now."""
    from qv.config import load_providers_config
    from qv.providers.usage import Limit, QuotaLedger
    pcfg = load_providers_config()
    ledger = QuotaLedger(db, reserve_fraction=pcfg.reserve_fraction)
    g = pcfg.llm.gemini
    lines = []
    for m, lim in g.models.items():
        limit = Limit("day", lim.rpd, g.daily_reset_timezone)
        lines.append(f"  gemini {m:24} {ledger.remaining('gemini', m, limit):7.0f} of {ledger.usable(limit):.0f} "
                     "requests left today")
    for m in pcfg.llm.ollama.models:
        lines.append(f"  ollama {m:24}       local model, no quota")
    sc = pcfg.search
    for name, limit, unit in (("parallel", Limit("day", sc.parallel.daily_soft_cap), "searches today (own cap)"),
                              ("tavily", Limit("month", sc.tavily.credits_per_month), "credits this month"),
                              ("exa", Limit("month", sc.exa.usd_credit_per_month), "USD credit this month")):
        lines.append(f"  {name:31} {ledger.remaining(name, '', limit):7.2f} of {ledger.usable(limit):.2f} {unit}")
    return lines


@app.command()
def quota() -> None:
    """Free quota left per provider (from our own ledger; the reserve is never used)."""
    for line in _quota_lines(_db()):
        typer.echo(line)


def _start_run(kind: str, dataset: str, ids: str | None, version: int | None, max_questions: int | None,
               yes: bool) -> None:
    """Shared body of `qv research` and `qv validate`."""
    from qv.config import load_research_config
    from qv.services.research import build_deps, execute_run, start_run
    settings = _settings()
    db = _db()
    id_list = _parse_ids(ids)
    n = len(id_list) if id_list else None
    with db.session() as s:
        v = ds_service.get_version(s, dataset, version)
        total = n or v.row_count
    if max_questions:
        total = min(total, max_questions)
    rc = load_research_config()
    llm_per_q = 2 + (rc.max_documents_per_question + rc.max_note_documents_per_question + 1) * rc.s3_max_windows
    verb = "research" if kind == "research" else "validate"
    typer.echo(f"About to {verb} up to {total} question(s) of {dataset}.")
    typer.echo(f"Rough upper bound per question: {llm_per_q} LLM requests for research (usually fewer), "
               f"{rc.max_web_queries_per_question} web searches (cached ones are free).")
    if kind == "validate":
        typer.echo("Judgement adds up to 3 requests per question (S4 + S5 on the 'judge' pool, S6 on 'cheap'); "
                   "stored outputs are reused.")
    typer.echo("Free quota now:")
    for line in _quota_lines(db):
        typer.echo(line)
    typer.echo("The run stops cleanly when a free quota runs out; `qv resume <run>` continues later.")
    if not yes and not typer.confirm("Start?"):
        raise typer.Exit(1)
    run_id = start_run(db, dataset, id_list, version_no=version, kind=kind)
    report = execute_run(build_deps(settings, db), run_id, max_questions=max_questions)
    _print_run_report(report)


@app.command()
def research(dataset: str,
             ids: Annotated[str | None, typer.Option(help="CSV ids, e.g. 1,5,10-12 (default: all)")] = None,
             version: Annotated[int | None, typer.Option(help="Dataset version (default latest)")] = None,
             max_questions: Annotated[int | None, typer.Option(help="Stop after this many questions")] = None,
             yes: Annotated[bool, typer.Option("--yes", help="Do not ask for confirmation")] = False) -> None:
    """Research questions: decomposition, searches, documents and grounded passages (uses free quotas)."""
    _start_run("research", dataset, ids, version, max_questions, yes)


@app.command()
def validate(dataset: str,
             ids: Annotated[str | None, typer.Option(help="CSV ids, e.g. 1,5,10-12 (default: all)")] = None,
             version: Annotated[int | None, typer.Option(help="Dataset version (default latest)")] = None,
             max_questions: Annotated[int | None, typer.Option(help="Stop after this many questions")] = None,
             yes: Annotated[bool, typer.Option("--yes", help="Do not ask for confirmation")] = False) -> None:
    """Research and judge questions: evidence, blind answer, verification, quality and a verdict."""
    _start_run("validate", dataset, ids, version, max_questions, yes)


@app.command("next")
def next_batch(dataset: str,
               size: Annotated[int | None, typer.Option(help="Questions in a new batch (default: what today's "
                                                              "free quota allows, at most research.yaml batch_size)")] = None,
               category: Annotated[list[str] | None, typer.Option(help="Only this category (repeatable)")] = None,
               subcategory: Annotated[list[str] | None, typer.Option(help="Only this subcategory (repeatable)")] = None,
               priority: Annotated[list[str] | None, typer.Option(help="Only these priority levels: high, medium, "
                                                                       "low (repeatable)")] = None,
               ids: Annotated[str | None, typer.Option(help="Only these CSV ids, e.g. 1,5,10-12")] = None,
               order: Annotated[str, typer.Option(help="priority (default) or file")] = "priority",
               yes: Annotated[bool, typer.Option("--yes", help="Do not ask for confirmation")] = False) -> None:
    """Validate the next batch: continues a stopped batch, else the next questions by priority. Run it again
    whenever it stops."""
    import os

    from qv.config import load_research_config
    from qv.services import worker, workflow
    from qv.services.research import build_deps, execute_run
    settings = _settings()
    db = _db()
    if order not in ("priority", "file"):
        raise typer.BadParameter("order must be priority or file")
    sel = workflow.Selection(categories=tuple(category or ()), subcategories=tuple(subcategory or ()),
                             levels=tuple(priority or ()), ids=tuple(_parse_ids(ids) or ()), order=order)
    default = load_research_config().batch_size
    n = size if size is not None else workflow.suggested_batch_size(db, default)
    plan = workflow.plan_next_batch(db, dataset, sel, n)
    typer.echo(f"{dataset}: {plan.message}")
    if plan.action == "start" and n == 0:
        typer.echo(f"Today's free judging requests are used up. Try again after "
                   f"{workflow.next_reset_local():%Y-%m-%d %H:%M}.")
        return
    if plan.action == "nothing":
        return
    for st in plan.questions[:10]:
        typer.echo(f"  #{st.ext_id:>5} [{st.priority_level}] {st.question[:80]}")
    if len(plan.questions) > 10:
        typer.echo(f"  … and {len(plan.questions) - 10} more")
    if not yes and not typer.confirm("Start?"):
        raise typer.Exit(1)
    log = os.environ.get("QV_BATCH_LOG")
    if not worker.acquire(settings.data_dir, dataset, Path(log) if log else None):
        st = worker.status(settings.data_dir)
        typer.echo(f"Another batch is running ({st.dataset}, started {st.started}); try again when it is done.")
        raise typer.Exit(1)
    try:
        run_id = workflow.start_batch(db, plan, sel)
        typer.echo(f"Batch = run {run_id}. It stops cleanly when a free limit is reached; run `qv next "
                   f"{dataset}` again later.", )
        report = execute_run(build_deps(settings, db), run_id)
        _print_run_report(report)
    finally:
        worker.release(settings.data_dir)
    _print_status(db, dataset)


def _print_status(db: Database, dataset: str) -> None:
    from qv.services import workflow
    states = workflow.question_states(db, dataset)
    c = workflow.counts(states)
    typer.echo(f"{dataset}: {len(states)} questions — " + ", ".join(
        f"{workflow.STATUS_LABEL[k].lower()} {v}" for k, v in c.items() if v))
    left = c["not_checked"] + c["failed"] + c["in_progress"]
    review = sum(c[k] for k in workflow.REVIEW_STATUSES)
    if left:
        typer.echo(f"Next: `qv next {dataset}` ({left} still to check)")
    if review:
        typer.echo(f"To look at: {review} question(s) on the Review page (`qv ui`)")


@app.command()
def status(dataset: Annotated[str | None, typer.Argument(help="Dataset (default: all)")] = None) -> None:
    """Where each file stands: checked, to review, still to check — and what to do next."""
    from qv.services import workflow
    db = _db()
    for name in [dataset] if dataset else workflow.dataset_names(db):
        _print_status(db, name)


@app.command()
def judge(run_id: int,
          ids: Annotated[str | None, typer.Option(help="Only these CSV ids")] = None) -> None:
    """Judge the researched questions of an existing run (S4–S6 + rules); verdicts are stored on that run."""
    from qv.services.judgement import judge_run
    from qv.services.research import build_deps
    db = _db()
    for line in judge_run(build_deps(_settings(), db), run_id, _parse_ids(ids)):
        typer.echo(line)
    typer.echo(f"Verdicts: qv verdicts {run_id}   ·   one question: qv verdict {run_id} <id>")


@app.command()
def verdicts(run_id: int) -> None:
    """Verdicts of a run, one line per question, and a count per verdict and route."""
    from qv.services.views import run_verdicts
    rows = run_verdicts(_db(), run_id)
    for r in rows:
        typer.echo(f"  #{r['id']:>5}  {r['verdict']:10} {r['strength']:8} {r['review']:16} "
                   f"quality {r['quality'] or '-':17} {r['question'][:60]}")
    from collections import Counter
    typer.echo("  " + ", ".join(f"{k} {v}" for k, v in Counter(r["verdict"] for r in rows).most_common()))
    typer.echo("  " + ", ".join(f"{k} {v}" for k, v in Counter(r["review"] for r in rows).most_common()))


@app.command()
def verdict(run_id: int, ext_id: str) -> None:
    """Why one question got its verdict: claim statuses, blind answer, quality and every rule that fired."""
    from qv.services.views import question_verdict
    v = question_verdict(_db(), run_id, ext_id)
    if v is None:
        raise typer.BadParameter(f"No verdict for id {ext_id} in run {run_id} (run `qv judge {run_id}` first)")
    for line in v["summary_lines"]:
        typer.echo(line)


@app.command()
def resume(run_id: int, max_questions: Annotated[int | None, typer.Option()] = None) -> None:
    """Continue an interrupted or stopped research or validate run."""
    from qv.services.research import build_deps, execute_run
    db = _db()
    _print_run_report(execute_run(build_deps(_settings(), db), run_id, max_questions=max_questions))


def _print_run_report(report) -> None:  # noqa: ANN001
    """Print a RunReport."""
    for q in report.questions:
        typer.echo(f"  id {q['id']}: {q.get('documents', 0)} documents, {q.get('passages_grounded', 0)} passages "
                   f"({q.get('passages_dropped', 0)} dropped), searches {q.get('searches_run', 0)} run / "
                   f"{q.get('searches_cached', 0)} cached")
        if q.get("verdict"):
            typer.echo(f"         verdict {q['verdict']} ({q['strength']}), {q['review']}")
    typer.echo(f"Run {report.run_id}: {report.done} done, {report.failed} failed, {report.pending} still pending")
    if report.stopped_reason:
        typer.echo(f"Stopped: {report.stopped_reason}")
    typer.echo(f"Details: qv evidence {report.run_id} <id>   ·   web view: qv ui")


@app.command()
def runs() -> None:
    """List research runs."""
    from sqlalchemy import func, select

    from qv.db.models import Run, RunQuestion
    db = _db()
    with db.session() as s:
        for r in s.scalars(select(Run).order_by(Run.id)):
            counts = dict(s.execute(select(RunQuestion.status, func.count()).where(RunQuestion.run_id == r.id)
                                    .group_by(RunQuestion.status)).all())
            typer.echo(f"run {r.id}  {r.created_at:%Y-%m-%d %H:%M}  {r.config_json.get('dataset')} "
                       f"v{r.config_json.get('version_no')}  {r.status}  {counts}"
                       + (f"  ({r.stop_reason[:80]})" if r.stop_reason else ""))


@app.command()
def evidence(run_id: int, ext_id: str) -> None:
    """Show what research found for one question: claims, queries, documents and passages."""
    from sqlalchemy import select

    from qv.db.models import QuestionRow, Run
    from qv.services.research import question_evidence
    db = _db()
    with db.session() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise typer.BadParameter(f"No run {run_id}")
        q = s.scalar(select(QuestionRow).where(QuestionRow.dataset_version_id == run.dataset_version_id,
                                               QuestionRow.ext_id == ext_id))
        if q is None:
            raise typer.BadParameter(f"No id {ext_id} in that dataset version")
        typer.echo(f"#{q.ext_id} {q.question}\n   key: {q.resolved_answer_text}   note: {q.note or '-'}")
        qid = q.id
    ev = question_evidence(db, run_id, qid)
    s1a = ev["stage_outputs"].get("s1a")
    if s1a:
        o = s1a.output_json
        typer.echo(f"\nS1a ({s1a.model}) need: {o['information_need']}")
        typer.echo(f"   claim type {o['claim_type']}, frame {o['frame_class']}")
        for p in o["presuppositions"]:
            typer.echo(f"   {p['id']}: {p['text']}{'' if p['material'] else ' (not material)'}")
        for x in o["queries"]:
            typer.echo(f"   query [{x['purpose']}] {x['q']}")
        for c in s1a.checks_json:
            typer.echo(f"   check: {c}")
    s1b = ev["stage_outputs"].get("s1b")
    if s1b:
        o = s1b.output_json
        typer.echo(f"\nS1b ({s1b.model}) key claim: {o['key_claim']}")
        for n in o["note_claims"]:
            typer.echo(f"   {n['id']} [{n['kind']}] {n['text']}")
        for c in o["challenge_queries"]:
            typer.echo(f"   challenge [{c['angle']}] {c['q']}")
    for d in ev["documents"]:
        qd, doc = d["qd"], d["doc"]
        tier = f"{qd.registry_tier}->{qd.effective_tier or '?'}" + (" frame-authority" if qd.frame_authority else "")
        typer.echo(f"\n[{qd.mode}] doc {doc.id} {doc.final_url}\n    {tier}, {qd.page_kind or '-'}, {qd.status}, "
                   f"{qd.grounded_count} grounded / {qd.dropped_count} dropped")
        for p in d["passages"]:
            ans = f" → {p.asserted_answer}" if p.asserted_answer else ""
            opt = f" [{p.matches_option}]" if p.matches_option else ""
            stance = f" ({p.stance})" if p.stance else ""
            typer.echo(f"    P{p.id} {p.target}{stance}{ans}{opt}\n      \"{p.quote[:300]}\"")


@app.command()
def metrics(run_id: int) -> None:
    """Evidence metrics for a run: grounding failure rate, coverage, documents by tier."""
    from qv.services.views import run_metrics
    for k, v in run_metrics(_db(), run_id).items():
        typer.echo(f"  {k:32} {v}")


@app.command()
def usage(run: Annotated[int | None, typer.Option(help="Only this run")] = None) -> None:
    """API usage: calls, tokens and credits per provider/model (cost is $0 on free tiers)."""
    from sqlalchemy import func, select

    from qv.db.models import ApiCall
    db = _db()
    with db.session() as s:
        q = select(ApiCall.provider, ApiCall.model, ApiCall.kind, ApiCall.status, func.count(),
                   func.sum(ApiCall.input_tokens), func.sum(ApiCall.output_tokens), func.sum(ApiCall.thinking_tokens),
                   func.sum(ApiCall.credits), func.sum(ApiCall.cost_usd)).group_by(
            ApiCall.provider, ApiCall.model, ApiCall.kind, ApiCall.status)
        if run is not None:
            q = q.where(ApiCall.run_id == run)
        for prov, model, kind, status, n, tin, tout, tthink, credits, cost in s.execute(q):
            typer.echo(f"  {prov:9} {model or '-':24} {kind:6} {status:8} {n:5} calls  in {tin or 0:>8}  "
                       f"out {tout or 0:>7}  think {tthink or 0:>7}  credits {credits or 0:8.3f}  ${cost or 0:.2f}")


@app.command()
def ui(port: int = 8501) -> None:
    """Open the read-only web view (Streamlit)."""
    import subprocess
    import sys
    from pathlib import Path as _P
    app_path = _P(__file__).parent / "ui" / "app.py"
    env_dir = str(_settings().data_dir)
    import os
    env = {**os.environ, "QV_DATA_DIR": env_dir}
    raise typer.Exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_path),
                                      "--server.port", str(port), "--server.headless", "true",
                                      "--browser.gatherUsageStats", "false", "--client.toolbarMode", "minimal"], env=env))


# --- evaluation set -----------------------------------------------------------

@eval_app.command("check")
def eval_check() -> None:
    """Check that every case in eval/cases.yaml points at the intended row."""
    from qv.evaluation import check_case_targets, load_cases
    cases = load_cases()
    problems = check_case_targets(cases)
    for p in problems:
        typer.echo(f"  {p}")
    typer.echo(f"{len(cases)} cases, {len(problems)} problem(s)")
    raise typer.Exit(1 if problems else 0)


@eval_app.command("score")
def eval_score(run_ids: Annotated[list[int], typer.Argument(help="One or more runs, scored together")]) -> None:
    """Compare runs' verdicts with the labels (eval/cases.yaml, seeded labels, controls) — Phase 3 exit metrics."""
    from qv.db.models import Run
    from qv.evaluation import expectations_for, score_many
    from qv.services.views import run_verdicts
    db = _db()
    groups = []
    for run_id in run_ids:
        with db.session() as s:
            run = s.get(Run, run_id)
            if run is None:
                raise typer.BadParameter(f"No run {run_id}")
            dataset = run.config_json.get("dataset")
            stale = run.dataset_version_id != ds_service.get_version(s, dataset, None).id
        if stale:
            typer.echo(f"  run {run_id} skipped: it used an older version of {dataset} (labels follow the latest)")
            continue
        groups.append(([{**r, "dataset": dataset} for r in run_verdicts(db, run_id)], expectations_for(dataset)))
    result = score_many(groups)
    if not result["labelled"]:
        typer.echo("No labelled questions in these runs (labels: eval/cases.yaml, eval/seeded_labels.yaml and "
                   "their originals as controls; `qv eval import` stores the eval datasets).")
        raise typer.Exit(1)
    for r in result["rows"]:
        typer.echo(f"  {'ok ' if r['agrees'] else 'XX '} {r['dataset']:28} #{r['id']:>5} got {r['verdict']:10} "
                   f"{r['review']:16} expected {r['expected']:20} ({r['label']})")
    for k, v in result.items():
        if k != "rows":
            typer.echo(f"  {k:24} {v}")


@eval_app.command("import")
def eval_import() -> None:
    """Store the eval set as datasets (seeded questions split by edition) and print the runs to start."""
    from qv.evaluation import eval_import_plan
    db = _db()
    commands = []
    for item in eval_import_plan():
        with db.session() as s:
            res = ds_service.import_dataset(s, item["data"], dataset_name=item["dataset"],
                                            source_filename=item["filename"], profile_name=item["profile"])
        state = f"version {res.version_no}" + ("" if res.created else " (unchanged)")
        typer.echo(f"  {item['dataset']:30} {state:22} {len(item['ids']):3} question(s) to validate")
        commands.append(f"qv validate {item['dataset']} --ids {','.join(item['ids'])}")
    typer.echo("Validate them (each asks before it starts; a stopped run continues with `qv resume <run>`):")
    for c in commands:
        typer.echo(f"  {c}")
    typer.echo("Then: qv eval score <run> [<run> …]")


@eval_app.command("seed")
def eval_seed(per_mutation: int = 10, seed: int = 20261115) -> None:
    """Regenerate eval/seeded.csv and eval/seeded_labels.yaml from the current editions."""
    from qv.evaluation import EVAL_DIR, generate_seeded_errors, labels_to_yaml
    data, labels = generate_seeded_errors(_edition_sources(), seed=seed, per_mutation=per_mutation)
    (EVAL_DIR / "seeded.csv").write_bytes(data)
    (EVAL_DIR / "seeded_labels.yaml").write_text(labels_to_yaml(labels), encoding="utf-8")
    typer.echo(f"Wrote {len(labels)} seeded questions to {EVAL_DIR}")


@eval_app.command("sample")
def eval_sample(out: Path, n: int = 150, seed: int = 20261115) -> None:
    """Write a stratified sample of questions as a labelling sheet (CSV)."""
    import csv

    from qv.evaluation import load_cases, stratified_sample
    always = {(c.dataset, c.id) for c in load_cases()}
    picked = stratified_sample(_edition_sources(), n=n, seed=seed, always=always)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["dataset", "id", "question", "key", "category", "expected_verdict", "defect", "comment"])
        for ds, q in picked:
            w.writerow([ds, q.ext_id, q.question, q.resolved_answer_text or "", q.category, "", "", ""])
    typer.echo(f"Wrote {len(picked)} questions to {out}")


def _edition_sources() -> dict:
    """Current questions of every edition (template excluded)."""
    from qv.evaluation import EDITIONS_DIR, load_questions
    return {p.parent.name: load_questions(p) for p in sorted(EDITIONS_DIR.glob("*/questions.csv"))
            if p.parent.name != "template"}


if __name__ == "__main__":
    app()
