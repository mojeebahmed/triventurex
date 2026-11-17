"""The simple workflow: where each question stands, what to check next, and the user's decisions.

Used by `qv next` / `qv status` and the web view's Validate, Review and Export pages. Works on the
**latest version** of a dataset (one dataset = one question file, e.g. one game edition).

A question's result is found by its content: a validation or decision made for the same text in an
earlier version still counts; a question whose text changed is "not checked" again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from qv.db.models import (
    Dataset, DatasetVersion, Decision, QuestionRow, Run, RunQuestion, StructuralIssueRow, Validation,
)
from qv.db.session import Database
from qv.pipeline.priority import CHANGED_SINCE_CHECK, priority
from qv.services.datasets import get_version

#: Where a question stands. Order = order of the groups on the page.
STATUS_LABEL: dict[str, str] = {
    "to_review": "To review",
    "specialist": "For a specialist",
    "no_evidence": "Not enough evidence",
    "spot_check": "Spot check",
    "verified": "Verified automatically",
    "approved": "Confirmed by you",
    "edited": "Edited by you",
    "removed": "Removed by you",
    "in_progress": "Being checked",
    "failed": "Check failed",
    "not_checked": "Not checked yet",
    "format_error": "Format error",
}
ROUTE_STATUS = {"auto_ok": "verified", "audit_sample": "spot_check", "needs_review": "to_review",
                "needs_specialist": "specialist", "needs_evidence": "no_evidence"}
DECISION_STATUS = {"keep": "approved", "edit": "edited", "remove": "removed", "specialist": "specialist"}
ACTIONS = ("keep", "edit", "specialist", "remove", "later")
#: Prepare-page decisions, made before checking: a new wording, or "the wording is fine". They never make a
#: question ready (only a check or a review decision does) and are kept apart from the review decision.
PREPARE_ACTIONS = ("reword", "wording_ok")
#: Statuses a person should look at, in review order.
REVIEW_STATUSES = ("to_review", "specialist", "no_evidence", "spot_check")
#: Ready for the game: verified automatically, confirmed by a person, or edited by a person.
READY_STATUSES = ("verified", "approved", "edited")
#: Statuses `qv next` picks up.
CHECKABLE = ("not_checked", "failed")
EDITABLE_COLUMNS = ("question", "answer", "opt_a", "opt_b", "opt_c", "opt_d", "note")


@dataclass
class QuestionState:
    """One question of the latest version and where it stands."""

    question_id: int
    ext_id: str
    row_no: int
    question: str
    type: str
    answer: str
    answer_text: str
    options: tuple[str, str, str, str]
    note: str
    difficulty: str
    category: str
    subcategory: str
    topic: str
    content_hash: str
    status: str
    priority_score: int
    priority_level: str
    priority_reasons: tuple[str, ...]
    verdict: str = ""
    review_status: str = ""
    validation_id: int | None = None
    run_id: int | None = None
    decision: str = ""
    decision_changes: dict = field(default_factory=dict)
    decision_comment: str = ""
    later: bool = False
    prepare: str = ""
    prepare_changes: dict = field(default_factory=dict)
    prepare_comment: str = ""

    @property
    def label(self) -> str:
        """The status in words."""
        return STATUS_LABEL[self.status]


def dataset_names(db: Database, *, include_eval: bool = False) -> list[str]:
    """Datasets in name order; evaluation sets (eval-…) only on request."""
    with db.session() as s:
        names = list(s.scalars(select(Dataset.name).order_by(Dataset.name)))
    return [n for n in names if include_eval or not n.startswith("eval-")]


#: Runs made to measure another judge (`qv validate --judge-pool`) are not part of the working results.
WORKING_RUN = func.json_extract(Run.config_json, "$.judge_pool").is_(None)


def _unfinished_run(s, version_id: int) -> tuple[int, set[int]] | None:  # noqa: ANN001
    """The newest validate run of this version with questions left, and those question ids."""
    for run in s.scalars(select(Run).where(Run.dataset_version_id == version_id, Run.kind == "validate",
                                           WORKING_RUN).order_by(Run.id.desc())):
        left = set(s.scalars(select(RunQuestion.question_id).where(
            RunQuestion.run_id == run.id, RunQuestion.status.in_(("pending", "stopped")))))
        return (run.id, left) if left else None
    return None


def question_states(db: Database, dataset: str) -> list[QuestionState]:
    """Every question of the dataset's latest version with its status, result, decision and priority."""
    from qv.services.research import question_from_row
    with db.session() as s:
        v = get_version(s, dataset)
        rows = list(s.scalars(select(QuestionRow).where(QuestionRow.dataset_version_id == v.id)
                              .order_by(QuestionRow.row_no)))
        warned = set(s.scalars(select(StructuralIssueRow.question_id).where(
            StructuralIssueRow.dataset_version_id == v.id, StructuralIssueRow.severity == "warning")))
        same_dataset = select(DatasetVersion.id).where(DatasetVersion.dataset_id == v.dataset_id)
        vals: dict[tuple[str, str], Validation] = {}
        checked_ids: set[str] = set()
        for val, ext, h in s.execute(select(Validation, QuestionRow.ext_id, QuestionRow.content_hash)
                                     .join(QuestionRow, QuestionRow.id == Validation.question_id)
                                     .join(Run, Run.id == Validation.run_id)
                                     .where(QuestionRow.dataset_version_id.in_(same_dataset), WORKING_RUN)
                                     .order_by(Validation.id)):
            vals[(ext, h)] = val
            checked_ids.add(ext)
        decisions: dict[tuple[str, str], Decision] = {}
        prepared: dict[tuple[str, str], Decision] = {}
        for d in s.scalars(select(Decision).where(Decision.dataset_id == v.dataset_id).order_by(Decision.id)):
            (prepared if d.action in PREPARE_ACTIONS else decisions)[(d.ext_id, d.content_hash)] = d
        unfinished = _unfinished_run(s, v.id)
        in_progress = unfinished[1] if unfinished else set()
        failed = {qid for qid, st in s.execute(
            select(RunQuestion.question_id, RunQuestion.status).join(Run, Run.id == RunQuestion.run_id)
            .where(Run.dataset_version_id == v.id, WORKING_RUN).order_by(RunQuestion.id)) if st == "failed"}
        out = []
        for r in rows:
            q = question_from_row(r)
            key = (r.ext_id, r.content_hash)
            val, dec, prep = vals.get(key), decisions.get(key), prepared.get(key)
            changed = r.ext_id in checked_ids and val is None
            p = priority(q, has_warnings=r.id in warned, changed=changed)
            if r.has_errors:
                status = "format_error"
            elif dec is not None and dec.action in DECISION_STATUS:
                status = DECISION_STATUS[dec.action]
            elif val is not None:
                status = ROUTE_STATUS.get(val.review_status, "to_review")
            elif r.id in in_progress:
                status = "in_progress"
            elif r.id in failed:
                status = "failed"
            else:
                status = "not_checked"
            out.append(QuestionState(
                question_id=r.id, ext_id=r.ext_id, row_no=r.row_no, question=r.question, type=r.type,
                answer=r.answer, answer_text=r.resolved_answer_text or r.answer,
                options=(r.opt_a, r.opt_b, r.opt_c, r.opt_d), note=r.note, difficulty=r.difficulty,
                category=r.category, subcategory=r.subcategory, topic=r.topic, content_hash=r.content_hash,
                status=status, priority_score=p.score, priority_level=p.level, priority_reasons=p.reasons,
                verdict=val.verdict if val else "", review_status=val.review_status if val else "",
                validation_id=val.id if val else None, run_id=val.run_id if val else None,
                decision=dec.action if dec else "", decision_changes=dict(dec.changes_json) if dec else {},
                decision_comment=dec.comment if dec else "", later=bool(dec and dec.action == "later"),
                prepare=prep.action if prep else "", prepare_changes=dict(prep.changes_json) if prep else {},
                prepare_comment=prep.comment if prep else ""))
        return out


def counts(states: list[QuestionState]) -> dict[str, int]:
    """Questions per status (every status present, in page order)."""
    out = {k: 0 for k in STATUS_LABEL}
    for st in states:
        out[st.status] += 1
    return out


# --- what to check next ---------------------------------------------------------------

#: Batch orders. Edited questions ("changed since it was last checked") always come first.
ORDERS: dict[str, str] = {
    "file": "As in the file",
    "hard": "Hard questions first",
    "easy": "Easy questions first",
    "risk": "Fact-heavy wording first",
}
_DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}


def parse_ids(ids: str | None) -> list[str] | None:
    """'1,2,5-7' → ['1','2','5','6','7'] (None for nothing)."""
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
    return out or None


@dataclass(frozen=True)
class Selection:
    """Which questions a batch may take, and in which order."""

    categories: tuple[str, ...] = ()
    subcategories: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    difficulties: tuple[str, ...] = ()
    levels: tuple[str, ...] = ()          # wording-risk levels: high / medium / low
    ids: tuple[str, ...] = ()
    order: str = "file"                   # see ORDERS

    def __post_init__(self) -> None:
        """'priority' is the old name of 'risk'."""
        if self.order == "priority":
            object.__setattr__(self, "order", "risk")
        if self.order not in ORDERS:
            raise ValueError(f"order must be one of {sorted(ORDERS)}")

    def matches(self, st: QuestionState) -> bool:
        """True when a question falls inside this selection."""
        return ((not self.categories or st.category in self.categories)
                and (not self.subcategories or st.subcategory in self.subcategories)
                and (not self.topics or st.topic in self.topics)
                and (not self.difficulties or st.difficulty in self.difficulties)
                and (not self.levels or st.priority_level in self.levels)
                and (not self.ids or st.ext_id in self.ids))


def _sort_key(order: str):  # noqa: ANN202
    def key(st: QuestionState) -> tuple:
        changed = CHANGED_SINCE_CHECK not in st.priority_reasons
        rank = _DIFFICULTY_RANK.get(st.difficulty, 1)
        if order == "hard":
            return (changed, -rank, st.row_no)
        if order == "easy":
            return (changed, rank, st.row_no)
        if order == "risk":
            return (changed, -st.priority_score, st.row_no)
        return (changed, st.row_no)
    return key


def candidates(states: list[QuestionState], sel: Selection) -> list[QuestionState]:
    """Questions still to check that match the selection, in batch order (edited ones first)."""
    return sorted((st for st in states if st.status in CHECKABLE and sel.matches(st)), key=_sort_key(sel.order))


@dataclass
class BatchPlan:
    """What `qv next` would do now."""

    dataset: str
    action: str                  # resume | start | nothing
    run_id: int | None = None
    questions: list[QuestionState] = field(default_factory=list)
    message: str = ""


def plan_next_batch(db: Database, dataset: str, sel: Selection, size: int) -> BatchPlan:
    """Continue an unfinished batch first; otherwise the next `size` questions of the selection."""
    states = question_states(db, dataset)
    with db.session() as s:
        unfinished = _unfinished_run(s, get_version(s, dataset).id)
    if unfinished:
        run_id, left = unfinished
        qs = [st for st in states if st.question_id in left]
        return BatchPlan(dataset, "resume", run_id, qs,
                         f"Continue the batch that stopped: {len(qs)} question(s) left.")
    todo = candidates(states, sel)[:max(size, 0)]
    if not todo:
        left = sum(1 for st in states if st.status in CHECKABLE)
        msg = ("Every question has been checked." if not left
               else f"No question to check in this selection ({left} left outside it).")
        return BatchPlan(dataset, "nothing", message=msg)
    return BatchPlan(dataset, "start", questions=todo,
                     message=f"Check {len(todo)} question(s) — {ORDERS[sel.order].lower()}.")


def start_batch(db: Database, plan: BatchPlan, sel: Selection) -> int | None:
    """Create the run for a plan (a resumed batch keeps its run). Returns the run id."""
    from qv.services.research import start_run
    if plan.action == "resume":
        return plan.run_id
    if plan.action != "start":
        return None
    return start_run(db, plan.dataset, [st.ext_id for st in plan.questions], kind="validate",
                     config={"batch": True, "selection": {
                         "categories": list(sel.categories), "subcategories": list(sel.subcategories),
                         "topics": list(sel.topics), "difficulties": list(sel.difficulties),
                         "levels": list(sel.levels), "order": sel.order}})


def judge_requests_left(db: Database) -> float | None:
    """Free requests left today on the pool that judges (S4/S5); None when a local model can take over."""
    return requests_left(db, "s5")


def requests_left(db: Database, stage: str) -> float | None:
    """Free requests left today on a stage's pool; None when a local model can take over."""
    from qv.config import load_providers_config, split_entry
    from qv.providers.usage import Limit, QuotaLedger
    pcfg = load_providers_config()
    ledger = QuotaLedger(db, reserve_fraction=pcfg.reserve_fraction)
    g = pcfg.llm.gemini
    total = 0.0
    for entry in pcfg.pool_for(stage):
        provider, model = split_entry(entry)
        if provider != "gemini":
            return None
        if model in g.models:
            total += max(0.0, ledger.remaining("gemini", model,
                                               Limit("day", g.models[model].rpd, g.daily_reset_timezone)))
    return total


def suggested_batch_size(db: Database, default: int) -> int:
    """Today's batch: what the free judging requests allow (≈ 2.2 per question), at most `default`."""
    left = judge_requests_left(db)
    if left is None:
        return default
    return max(0, min(default, int(left / 2.2)))


def next_reset_local() -> datetime:
    """When the free daily limits reset, in local time."""
    from qv.config import load_providers_config
    tz = ZoneInfo(load_providers_config().llm.gemini.daily_reset_timezone)
    now = datetime.now(tz)
    reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return reset.astimezone()


# --- decisions ------------------------------------------------------------------------

def record_decision(db: Database, dataset: str, ext_id: str, action: str, *,
                    changes: dict[str, str] | None = None, comment: str = "") -> int:
    """Store a decision for the latest version's question `ext_id`. Edits are checked for format."""
    if action not in ACTIONS + PREPARE_ACTIONS:
        raise ValueError(f"Unknown action {action!r}")
    changing = action in ("edit", "reword")
    changes = {k: v for k, v in (changes or {}).items()}
    bad = set(changes) - set(EDITABLE_COLUMNS)
    if bad:
        raise ValueError(f"These columns cannot be edited here: {sorted(bad)}")
    if changing and not changes:
        raise ValueError("An edit needs at least one changed field")
    with db.session() as s:
        v = get_version(s, dataset)
        q = s.scalar(select(QuestionRow).where(QuestionRow.dataset_version_id == v.id, QuestionRow.ext_id == ext_id))
        if q is None:
            raise ValueError(f"No question {ext_id} in {dataset}")
        changes = {k: val for k, val in changes.items() if val != getattr(q, k)}
        if changing and not changes:
            raise ValueError("Nothing was changed")
        same = select(DatasetVersion.id).where(DatasetVersion.dataset_id == v.dataset_id)
        val = s.scalar(select(Validation).join(QuestionRow, QuestionRow.id == Validation.question_id)
                       .where(QuestionRow.dataset_version_id.in_(same), QuestionRow.ext_id == ext_id,
                              QuestionRow.content_hash == q.content_hash).order_by(Validation.id.desc()))
        d = Decision(dataset_id=v.dataset_id, ext_id=ext_id, content_hash=q.content_hash, question_id=q.id,
                     validation_id=val.id if val else None, action=action,
                     changes_json=changes if changing else {}, comment=comment.strip(),
                     created_at=datetime.now(UTC))
        s.add(d)
        s.flush()
        return d.id


def decision_history(db: Database, dataset: str, ext_id: str) -> list[dict]:
    """Every decision ever made for a question id (newest first)."""
    with db.session() as s:
        ds = s.scalar(select(Dataset).where(Dataset.name == dataset))
        if ds is None:
            return []
        return [{"when": d.created_at.strftime("%Y-%m-%d %H:%M"), "action": d.action, "changes": d.changes_json,
                 "comment": d.comment}
                for d in s.scalars(select(Decision).where(Decision.dataset_id == ds.id, Decision.ext_id == ext_id)
                                   .order_by(Decision.id.desc()))]


def pending_edits(states: list[QuestionState]) -> dict[str, dict[str, str]]:
    """Edits decided on the latest version: {id: {column: value}}."""
    return {st.ext_id: st.decision_changes for st in states if st.decision == "edit" and st.decision_changes}


def pending_rewords(states: list[QuestionState]) -> dict[str, dict[str, str]]:
    """New wordings chosen on the Prepare page for the latest version: {id: {column: value}}."""
    return {st.ext_id: st.prepare_changes for st in states if st.prepare == "reword" and st.prepare_changes}


def apply_edits_as_new_version(db: Database, dataset: str, *, prepared: bool = False) -> int | None:
    """Store the latest version with the decided edits as a new version, so edited questions get checked.

    `prepared`: apply the Prepare page's new wordings instead of the review edits (each kind is saved by its
    own button; the other kind's decisions stay with their unchanged questions).
    Returns the new version number (None when there is nothing to apply). Removed questions stay in the
    file (they are left out only at export); unchanged questions keep their results and decisions.
    """
    from qv.services.datasets import import_dataset
    from qv.services.exports import corrected_csv
    states = question_states(db, dataset)
    edits = pending_rewords(states) if prepared else pending_edits(states)
    if not edits:
        return None
    with db.session() as s:
        v = get_version(s, dataset)
        result = corrected_csv(v, edits)
        name = v.source_filename.split(" + ")[0]
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        what = "new wording(s)" if prepared else "edit(s)"
        res = import_dataset(s, result.data, dataset_name=dataset,
                             source_filename=f"{name} + {len(edits)} {what} {stamp}")
        return res.version_no


def dataset_profile(db: Database, dataset: str) -> str | None:
    """The profile a dataset was imported with."""
    with db.session() as s:
        return s.scalar(select(Dataset.profile).where(Dataset.name == dataset))


#: Groups on the Review page: every checked question, the ones to look at, and the verified ones.
CHECKED_STATUSES = ("to_review", "specialist", "no_evidence", "spot_check", "verified", "approved", "edited",
                    "removed")
REVIEW_GROUPS: dict[str, tuple[str, ...]] = {
    "all": CHECKED_STATUSES,
    "to_review": ("to_review",),
    "specialist": ("specialist",),
    "no_evidence": ("no_evidence",),
    "spot_check": ("spot_check",),
    "verified": ("verified",),
    "decided": ("approved", "edited", "removed"),
}
