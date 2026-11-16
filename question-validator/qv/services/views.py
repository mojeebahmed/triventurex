"""Read-only queries for the web view (plain dicts, no ORM objects leave a session)."""

from __future__ import annotations

from sqlalchemy import func, select

from qv.db.models import (
    ApiCall, Dataset, DatasetVersion, QuestionRow, Run, RunQuestion, StructuralIssueRow,
)
from qv.db.session import Database
from qv.services.research import question_evidence


def datasets_overview(db: Database) -> list[dict]:
    """One row per dataset version."""
    with db.session() as s:
        rows = s.execute(select(Dataset.name, Dataset.profile, DatasetVersion).join(DatasetVersion)
                         .order_by(Dataset.name, DatasetVersion.version_no))
        return [{"dataset": n, "profile": p, "version": v.version_no, "version_id": v.id, "rows": v.row_count,
                 "errors": v.error_count, "warnings": v.warning_count, "info": v.info_count,
                 "file": v.source_filename, "imported": v.imported_at.strftime("%Y-%m-%d %H:%M")}
                for n, p, v in rows]


def version_questions(db: Database, version_id: int) -> list[dict]:
    """Questions of a version with their structural issue codes."""
    with db.session() as s:
        issues: dict[int, list[str]] = {}
        for qid, code, sev in s.execute(select(StructuralIssueRow.question_id, StructuralIssueRow.code,
                                               StructuralIssueRow.severity)
                                        .where(StructuralIssueRow.dataset_version_id == version_id)):
            if qid:
                issues.setdefault(qid, []).append(f"{sev}:{code}")
        return [{"id": q.ext_id, "question": q.question, "type": q.type, "key": q.resolved_answer_text or "",
                 "difficulty": q.difficulty, "category": q.category, "note": q.note,
                 "issues": ", ".join(issues.get(q.id, [])), "_qid": q.id}
                for q in s.scalars(select(QuestionRow).where(QuestionRow.dataset_version_id == version_id)
                                   .order_by(QuestionRow.row_no))]


def version_issues(db: Database, version_id: int) -> list[dict]:
    """Structural issues of a version."""
    with db.session() as s:
        return [{"severity": i.severity, "code": i.code, "line": i.line_no, "id": i.ext_id, "message": i.message}
                for i in s.scalars(select(StructuralIssueRow).where(StructuralIssueRow.dataset_version_id == version_id)
                                   .order_by(StructuralIssueRow.line_no))]


def runs_overview(db: Database) -> list[dict]:
    """Research runs with question counts per status."""
    with db.session() as s:
        out = []
        for r in s.scalars(select(Run).order_by(Run.id.desc())):
            counts = dict(s.execute(select(RunQuestion.status, func.count()).where(RunQuestion.run_id == r.id)
                                    .group_by(RunQuestion.status)).all())
            out.append({"run": r.id, "created": r.created_at.strftime("%Y-%m-%d %H:%M"),
                        "dataset": r.config_json.get("dataset"), "version": r.config_json.get("version_no"),
                        "status": r.status, **{k: counts.get(k, 0) for k in ("done", "failed", "pending", "stopped")},
                        "stop_reason": r.stop_reason or ""})
        return out


def run_questions(db: Database, run_id: int) -> list[dict]:
    """Questions in a run with their research statistics and verdict (plain column names for the web view)."""
    from qv.db.models import Validation
    with db.session() as s:
        verdicts = {v.question_id: v for v in s.scalars(select(Validation).where(Validation.run_id == run_id))}
        rows = s.execute(select(RunQuestion, QuestionRow).join(QuestionRow, QuestionRow.id == RunQuestion.question_id)
                         .where(RunQuestion.run_id == run_id).order_by(QuestionRow.row_no))
        out = []
        for rq, q in rows:
            v = verdicts.get(q.id)
            st = rq.stats_json or {}
            out.append({"id": q.ext_id,
                        "verdict": v.verdict if v else "not judged", "evidence": v.evidence_strength if v else "",
                        "next step": v.review_status.replace("_", " ") if v else "", "question": q.question,
                        "quality": v.question_quality or "" if v else "",
                        "pages read": st.get("documents", 0), "passages found": st.get("passages_grounded", 0),
                        "quotes rejected": st.get("passages_dropped", 0), "research": rq.status,
                        "error": rq.error or "", "_qid": q.id})
        return out


def question_detail(db: Database, run_id: int, question_id: int) -> dict:
    """Question, stage outputs, documents and passages as plain data."""
    ev = question_evidence(db, run_id, question_id)
    with db.session() as s:
        q = s.get(QuestionRow, question_id)
        question = {"id": q.ext_id, "question": q.question, "type": q.type, "key": q.resolved_answer_text,
                    "options": [o for o in (q.opt_a, q.opt_b, q.opt_c, q.opt_d)], "note": q.note,
                    "category": " > ".join(x for x in (q.category, q.subcategory, q.topic) if x)}
    stages = {k: {"model": v.model, "output": v.output_json, "checks": v.checks_json}
              for k, v in ev["stage_outputs"].items()}
    docs = []
    for d in ev["documents"]:
        qd, doc = d["qd"], d["doc"]
        docs.append({
            "doc_id": doc.id, "url": doc.final_url, "title": doc.title, "source_kind": doc.source_kind,
            "mode": qd.mode, "registry_tier": qd.registry_tier, "effective_tier": qd.effective_tier,
            "frame_authority": qd.frame_authority, "page_kind": qd.page_kind, "status": qd.status,
            "about_right_subject": qd.about_right_subject, "concerns": qd.concerns_json, "found_by": qd.found_by_json,
            "grounded": qd.grounded_count, "dropped": qd.dropped_count, "fetched": doc.fetched_at.strftime("%Y-%m-%d"),
            "text": doc.text,
            "passages": [{"pid": p.id, "target": p.target, "quote": p.quote, "start": p.char_start, "end": p.char_end,
                          "asserted_answer": p.asserted_answer, "matches_option": p.matches_option,
                          "stance": p.stance, "qualifiers": p.qualifiers, "as_of": p.as_of,
                          "origin": p.attributed_origin, "primary": p.is_primary_for_claim} for p in d["passages"]],
        })
    rq = ev["run_question"]
    from qv.services.judgement import load_evidence
    numbering = {p.passage_id: (p.pid, p.cluster) for p in load_evidence(db, run_id, question_id)}
    for d in docs:
        for p in d["passages"]:
            p["short_id"], p["cluster"] = numbering.get(p["pid"], (f"#{p['pid']}", ""))
    return {"question": question, "stages": stages, "documents": docs,
            "stats": (rq.stats_json if rq else {}) or {}, "status": rq.status if rq else None}


def usage_summary(db: Database) -> list[dict]:
    """API calls grouped by provider, model, kind and status."""
    with db.session() as s:
        q = select(ApiCall.provider, ApiCall.model, ApiCall.kind, ApiCall.status, func.count(),
                   func.sum(ApiCall.input_tokens), func.sum(ApiCall.output_tokens), func.sum(ApiCall.credits)
                   ).group_by(ApiCall.provider, ApiCall.model, ApiCall.kind, ApiCall.status)
        return [{"provider": p, "model": m or "-", "kind": k, "status": st, "calls": n, "input_tokens": ti or 0,
                 "output_tokens": to or 0, "credits": round(c or 0, 3)} for p, m, k, st, n, ti, to, c in s.execute(q)]


def run_metrics(db: Database, run_id: int) -> dict:
    """Phase 2 exit metrics for a run (ARCHITECTURE.md §6).

    - grounding_failure_rate: quotes dropped / quotes reported (dropped also counts quotes with an
      unknown target, so this is an upper bound on pure grounding failures)
    - need_coverage: share of finished questions with ≥1 stored passage on the information need
      from a non-excluded document
    """
    from qv.db.models import Passage, QuestionDocument
    with db.session() as s:
        qds = list(s.scalars(select(QuestionDocument).where(QuestionDocument.run_id == run_id)))
        grounded = sum(q.grounded_count for q in qds)
        dropped = sum(q.dropped_count for q in qds)
        done = list(s.scalars(select(RunQuestion.question_id).where(RunQuestion.run_id == run_id,
                                                                     RunQuestion.status == "done")))
        covered = set(s.scalars(select(Passage.question_id).where(Passage.run_id == run_id, Passage.target == "need")))
        tiers: dict[str, int] = {}
        for q in qds:
            tiers[q.effective_tier or "?"] = tiers.get(q.effective_tier or "?", 0) + 1
        return {
            "questions_done": len(done),
            "documents": len(qds),
            "documents_by_tier": dict(sorted(tiers.items())),
            "documents_excluded": sum(1 for q in qds if q.status == "excluded"),
            "documents_failed": sum(1 for q in qds if q.status == "failed"),
            "passages_grounded": grounded,
            "quotes_dropped": dropped,
            "grounding_failure_rate": round(dropped / (grounded + dropped), 3) if grounded + dropped else 0.0,
            "need_coverage": round(len(covered & set(done)) / len(done), 3) if done else 0.0,
            "questions_without_need_passage": len(set(done) - covered),
        }


# --- Phase 3: verdicts -------------------------------------------------------------

def evidence_summary(passages: list, key_text: str, key_letter: str | None, options: tuple[str, ...]) -> str:
    """One plain line: what the evidence says the answer is, counted by independent origin.

    e.g. "Evidence says: 540 (2 origins) · 558 (1 origin) — expected answer: 540".
    `passages` are EvidencePassage (mode A only are counted: they were read without the key).
    """
    from qv.domain.question import OPTION_LETTERS
    groups: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    for p in passages:
        if p.mode != "A":
            continue
        if p.matches_option and p.matches_option in OPTION_LETTERS[:len(options)]:
            label = f"{p.matches_option}. {options[OPTION_LETTERS.index(p.matches_option)]}"
        elif p.asserted_answer:
            label = p.asserted_answer.strip()
        else:
            continue
        k = label.casefold()
        labels.setdefault(k, label if len(label) <= 60 else label[:59].rstrip() + "…")
        groups.setdefault(k, set()).add(p.cluster)
    key = f"{key_letter}. {key_text}" if key_letter else key_text
    if not groups:
        return f"Evidence says: nothing about the answer — expected answer: {key}"
    parts = [f"{labels[k]} ({len(c)} origin{'s' if len(c) != 1 else ''})"
             for k, c in sorted(groups.items(), key=lambda kv: -len(kv[1]))]
    more = f" · {len(parts) - 4} more" if len(parts) > 4 else ""
    return "Evidence says: " + " · ".join(parts[:4]) + more + f" — expected answer: {key}"


def run_verdicts(db: Database, run_id: int) -> list[dict]:
    """One row per judged question of a run."""
    from qv.db.models import Validation
    with db.session() as s:
        rows = s.execute(select(Validation, QuestionRow).join(QuestionRow, QuestionRow.id == Validation.question_id)
                         .where(Validation.run_id == run_id).order_by(QuestionRow.row_no))
        return [{"id": q.ext_id, "question_id": q.id, "question": q.question, "verdict": v.verdict,
                 "strength": v.evidence_strength, "review": v.review_status, "quality": v.question_quality,
                 "blind_matches_key": v.blind_matches_key, "note": v.note_status, "defect": v.defect_location}
                for v, q in rows]


def question_verdict(db: Database, run_id: int, ext_id: str) -> dict | None:
    """Everything about one verdict, plus plain-words summary lines for the CLI and web view."""
    from qv.db.models import Run, Validation
    from qv.pipeline.judgement import key_letter
    from qv.services.judgement import load_evidence
    from qv.services.research import question_from_row
    with db.session() as s:
        run = s.get(Run, run_id)
        if run is None:
            return None
        qrow = s.scalar(select(QuestionRow).where(QuestionRow.dataset_version_id == run.dataset_version_id,
                                                  QuestionRow.ext_id == ext_id))
        if qrow is None:
            return None
        v = s.scalar(select(Validation).where(Validation.run_id == run_id, Validation.question_id == qrow.id))
        if v is None:
            return None
        q = question_from_row(qrow)
        data = {c.name: getattr(v, c.name) for c in Validation.__table__.columns}
    passages = load_evidence(db, run_id, qrow.id)
    summary = evidence_summary(passages, q.resolved_answer_text or q.answer, key_letter(q), q.options)
    lines = [f"#{q.ext_id} {q.question}", f"   expected answer: {q.resolved_answer_text}   note: {q.note or '-'}",
             "", f"VERDICT {data['verdict']}" + (f" (defect: {data['defect_location']})" if data["defect_location"]
                                                 else "")
             + f" · evidence {data['evidence_strength']} · route {data['review_status']}"
             + (" · within frame" if data["within_frame"] else "")
             + (" · contested outside frame" if data["contested_outside_frame"] else ""),
             f"   {summary}"]
    if data["blind_status"]:
        match = {True: "same as the key", False: "DIFFERENT from the key", None: "-"}[data["blind_matches_key"]]
        lines.append(f"   Answer from the evidence without the key: {data['blind_answer'] or data['blind_status']}"
                     f" ({match})")
    lines.append("   Claims: " + ", ".join(f"{k} {st}" for k, st in data["claim_statuses_json"].items()))
    if data["note_status"]:
        lines.append(f"   Note: {data['note_status']} ("
                     + ", ".join(f"{k} {st}" for k, st in data["note_statuses_json"].items()) + ")")
    if data["question_quality"]:
        issues = (data["quality_json"] or {}).get("issues", [])
        lines.append(f"   Quality: {data['question_quality']}"
                     + (" — " + "; ".join(f"{i['type']} ({i['severity']})" for i in issues) if issues else ""))
    if data["suggested_answer"]:
        lines.append(f"   Suggested answer: {data['suggested_answer']}")
    if data["suggested_question"]:
        lines.append(f"   Suggested question: {data['suggested_question']}")
    lines += ["", "Why:"] + [f"   - {r}" for r in data["reasons_json"]]
    return {**data, "question": q, "passages": passages, "evidence_summary": summary, "summary_lines": lines}


def quota_rows(db: Database) -> list[dict]:
    """Free quota left now, per provider/model (same numbers as `qv quota`)."""
    from qv.config import load_providers_config
    from qv.providers.usage import Limit, QuotaLedger
    pcfg = load_providers_config()
    ledger = QuotaLedger(db, reserve_fraction=pcfg.reserve_fraction)
    g = pcfg.llm.gemini
    rows = [{"service": f"Gemini {m}", "left": round(ledger.remaining("gemini", m, lim := Limit(
        "day", c.rpd, g.daily_reset_timezone))), "of": round(ledger.usable(lim)), "per": "day"}
        for m, c in g.models.items()]
    sc = pcfg.search
    for name, limit in (("Parallel search", Limit("day", sc.parallel.daily_soft_cap)),
                        ("Tavily search", Limit("month", sc.tavily.credits_per_month)),
                        ("Exa search (USD credit)", Limit("month", sc.exa.usd_credit_per_month))):
        key = name.split()[0].lower()
        rows.append({"service": name, "left": round(ledger.remaining(key, "", limit), 2),
                     "of": round(ledger.usable(limit), 2), "per": limit.period})
    rows += [{"service": f"Local model {m}", "left": "no limit", "of": "", "per": ""} for m in pcfg.llm.ollama.models]
    return rows


def dataset_cards(db: Database, *, include_eval: bool = False) -> list[dict]:
    """One row per dataset (latest version) with its progress, for the overview."""
    from qv.services import workflow
    overview = datasets_overview(db)
    latest = {}
    for o in overview:
        latest[o["dataset"]] = o
    out = []
    for o in latest.values():
        if o["dataset"].startswith("eval-") and not include_eval:
            continue
        c = workflow.counts(workflow.question_states(db, o["dataset"]))
        out.append({"file": o["dataset"], "source file": o["file"], "version": o["version"],
                    "imported": o["imported"], "profile": o["profile"], "questions": o["rows"],
                    "verified": c["verified"] + c["approved"] + c["edited"],
                    "to look at": sum(c[k] for k in workflow.REVIEW_STATUSES),
                    "still to check": c["not_checked"] + c["failed"] + c["in_progress"],
                    "format errors": c["format_error"]})
    return out
