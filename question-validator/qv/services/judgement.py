"""Phase 3: judge one researched question — S4 blind answer, S5 verification, S6 quality, S8 rules.

Runs after `research_question` in a run of kind "validate". Stage outputs are cached by
input hash like every other stage, so re-judging after a rules change costs no quota.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from qv.config import Profile
from qv.db.models import Document, Passage, QuestionDocument, StageOutput, Validation
from qv.db.session import Database
from qv.domain.question import Question
from qv.domain.stages import BlindAnswer, ClaimFormulation, Decomposition, Quality, Verification
from qv.pipeline.evidence import EvidencePassage, number_passages
from qv.pipeline.judgement import (
    blind_passages, check_s4, check_s5, check_s6, key_letter, render_s4, render_s5, render_s6, s5_system_values,
    s6_system_values,
)
from qv.pipeline.rules import Judgement, PremiseInfo, RulesInput, judge, load_requirements
from qv.pipeline.stages import StageRunner, filter_s1b_lookups
from qv.providers.usage import CallContext


def load_evidence(db: Database, run_id: int, question_id: int) -> list[EvidencePassage]:
    """Grounded passages of a question in a run, from non-excluded documents, numbered and clustered."""
    with db.session() as s:
        rows = s.execute(
            select(Passage, QuestionDocument, Document)
            .join(QuestionDocument, QuestionDocument.id == Passage.question_document_id)
            .join(Document, Document.id == Passage.document_id)
            .where(Passage.run_id == run_id, Passage.question_id == question_id,
                   QuestionDocument.status == "extracted", QuestionDocument.effective_tier.in_(("P", "S", "T"))))
        out = [EvidencePassage(
            pid="", passage_id=p.id, mode=p.mode, target=p.target, quote=p.quote, tier=qd.effective_tier,
            frame_authority=qd.frame_authority, publisher=qd.publisher or d.domain, domain=d.domain,
            page_kind=qd.page_kind or "other", asserted_answer=p.asserted_answer, matches_option=p.matches_option,
            stance=p.stance, qualifiers=p.qualifiers, as_of=p.as_of, attributed_origin=p.attributed_origin)
            for p, qd, d in rows]
    return number_passages(out)


def _output(db: Database, output_id: int, cls: type) -> Any:
    with db.session() as s:
        return cls.model_validate(s.get(StageOutput, output_id).output_json)


def _evidence_hash(passages: list[EvidencePassage]) -> list[list[Any]]:
    return [[p.pid, p.quote, p.tier, p.cluster, p.target, p.frame_authority, p.publisher, p.page_kind,
             p.qualifiers, p.as_of] for p in passages]


def judge_question(db: Database, runner: StageRunner, run_id: int, question_id: int, q: Question,
                   profile: Profile, s1a_output_id: int, s1b_output_id: int,
                   requirements: dict[str, list[dict]] | None = None, audit_percent: float = 3.0) -> dict:
    """Run S4/S5/S6 (cached), apply S8 and store the validation. Returns statistics for the run report."""
    requirements = requirements or load_requirements()
    s1a: Decomposition = _output(db, s1a_output_id, Decomposition)
    s1b = filter_s1b_lookups(_output(db, s1b_output_id, ClaimFormulation), q)
    passages = load_evidence(db, run_id, question_id)
    question_hash = {"q": q.question, "type": q.type, "opts": q.options, "s1a": s1a_output_id}
    stats: dict[str, Any] = {}

    s4 = s5 = None
    s4_id = s5_id = None
    if blind_passages(passages):
        r4 = runner.run(stage="s4", user=render_s4(q, s1a, passages), schema_cls=BlindAnswer,
                        hash_inputs={**question_hash, "ev": _evidence_hash(blind_passages(passages))},
                        ctx=CallContext(run_id, question_id, "s4"), checks=lambda o: check_s4(o, q, passages))
        s4, s4_id = r4.output, r4.stage_output_id
        stats["s4_check_problems"] = len(r4.checks)
    if passages:
        r5 = runner.run(stage="s5", user=render_s5(q, s1a, s1b, profile, passages), schema_cls=Verification,
                        hash_inputs={**question_hash, "key": q.answer, "note": q.note, "s1b": s1b_output_id,
                                     "ev": _evidence_hash(passages), "s4": s4_id},
                        system_values=s5_system_values(q, s1a, profile, s4, requirements),
                        ctx=CallContext(run_id, question_id, "s5"), checks=lambda o: check_s5(o, q, passages))
        s5, s5_id = r5.output, r5.stage_output_id
        stats["s5_check_problems"] = len(r5.checks)
    r6 = runner.run(stage="s6", user=render_s6(q), schema_cls=Quality,
                    hash_inputs={"q": q.question, "type": q.type, "opts": q.options, "key": q.answer,
                                 "note": q.note, "diff": q.difficulty, "cat": [q.category, q.subcategory, q.topic]},
                    system_values=s6_system_values(profile),
                    ctx=CallContext(run_id, question_id, "s6"), checks=lambda o: check_s6(o, q))
    s6: Quality = r6.output  # type: ignore[assignment]

    j = judge(RulesInput(
        run_id=run_id, question_id=question_id, is_multi=q.is_multi, key_letter=key_letter(q),
        key_text=q.resolved_answer_text or q.answer, claim_type=str(s1a.claim_type), frame_class=str(s1a.frame_class),
        as_of_in_question=s1a.time_sensitivity.as_of_in_question,
        premises=[PremiseInfo(p.id, p.text, p.claim_type, p.frame_class, p.material) for p in s1a.presuppositions],
        note_claim_ids=[n.id for n in s1b.note_claims if n.kind != "explanation"],
        passages=passages, blind=s4, verification=s5, quality=s6,
        specialist_for=profile.specialist_for, audit_percent=audit_percent), requirements)
    store_validation(db, run_id, question_id, j, s1a, passages, s6, s4_id, s5_id, r6.stage_output_id)
    stats.update(verdict=j.verdict, review=j.review_status, strength=j.evidence_strength)
    return stats


def store_validation(db: Database, run_id: int, question_id: int, j: Judgement, s1a: Decomposition,
                     passages: list[EvidencePassage], s6: Quality, s4_id: int | None, s5_id: int | None,
                     s6_id: int) -> None:
    """Replace the validation of this question in this run."""
    with db.session() as s:
        s.execute(delete(Validation).where(Validation.run_id == run_id, Validation.question_id == question_id))
        s.add(Validation(
            run_id=run_id, question_id=question_id, verdict=j.verdict, defect_location=j.defect_location,
            evidence_strength=j.evidence_strength, factual_accuracy=j.factual_accuracy,
            claim_type=str(s1a.claim_type), frame_class=str(s1a.frame_class),
            claim_statuses_json=j.claim_statuses, note_status=j.note_status, note_statuses_json=j.note_statuses,
            blind_status=j.blind_status, blind_answer=j.blind_answer, blind_matches_key=j.blind_matches_key,
            within_frame=j.within_frame, contested_outside_frame=j.contested_outside_frame,
            question_quality=j.quality, quality_json=s6.model_dump(mode="json"), review_status=j.review_status,
            routes_json=j.routes, reasons_json=j.reasons, support_json=j.support,
            suggested_answer=j.suggested_answer, suggested_question=j.suggested_question,
            acceptable_alternatives_json=j.acceptable_alternatives,
            passage_map_json={p.pid: {"passage_id": p.passage_id, "cluster": p.cluster} for p in passages},
            s4_output_id=s4_id, s5_output_id=s5_id, s6_output_id=s6_id, rules_version=j.rules_version))


def judge_run(deps: Any, run_id: int, ext_ids: list[str] | None = None) -> list[str]:
    """Judge every researched question of a run (cached stage outputs are reused). Returns report lines.

    Stops cleanly when a free quota runs out; running it again continues (finished stages are cached).
    """
    from qv.config import load_profile
    from qv.db.models import DatasetVersion, QuestionRow, Run, RunQuestion
    from qv.providers.llm.base import LLMError
    from qv.providers.usage import QuotaExhausted
    from qv.services.research import question_from_row

    db = deps.db
    with db.session() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise ValueError(f"No run {run_id}")
        profile = load_profile(s.get(DatasetVersion, run.dataset_version_id).profile)
        rows = list(s.execute(select(RunQuestion.stats_json, QuestionRow).join(
            QuestionRow, QuestionRow.id == RunQuestion.question_id).where(
            RunQuestion.run_id == run_id, RunQuestion.status == "done").order_by(QuestionRow.row_no)))
    if ext_ids:
        rows = [r for r in rows if r[1].ext_id in set(ext_ids)]
    lines = []
    requirements = load_requirements()
    for stats, qrow in rows:
        q = question_from_row(qrow)
        if not stats.get("s1a_output_id") or not stats.get("s1b_output_id"):
            lines.append(f"  #{q.ext_id}: no research outputs recorded — skipped")
            continue
        try:
            st = judge_question(db, deps.runner, run_id, qrow.id, q, profile, stats["s1a_output_id"],
                                stats["s1b_output_id"], requirements, deps.audit_percent)
            lines.append(f"  #{q.ext_id}: {st['verdict']} ({st['strength']}), {st['review']}")
        except QuotaExhausted as exc:
            lines.append(f"Stopped: {exc}. Run `qv judge {run_id}` again later; finished stages are reused.")
            break
        except LLMError as exc:
            lines.append(f"  #{q.ext_id}: failed — {type(exc).__name__}: {str(exc)[:200]}")
    return lines
