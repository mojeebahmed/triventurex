"""Prepare: look at the wording of a file's questions before checking them, and reword where it helps.

Two looks, both before any research:
1. **Wording flags** (`qv.pipeline.wording`) — pure code, free, for every question at once.
2. **The quality check** (S6) on its own — one Flash-Lite request per question, no searching. Its output is
   stored under the same input hash the full check uses (`s6_hash_inputs`), so a question checked here costs no
   second request when it is validated with the same wording.

New wordings are Prepare decisions (`workflow.PREPARE_ACTIONS`); "Save as a new version" turns them into a new
version of the file (`apply_edits_as_new_version(prepared=True)`) so the checks see the final wording. Nothing
here ever writes into the game's files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from qv.config import Profile, load_profile, load_research_config
from qv.db.models import QuestionRow, StructuralIssueRow
from qv.db.session import Database
from qv.domain.stages import Quality
from qv.pipeline.judgement import check_s6, render_s6, s6_hash_inputs, s6_system_values
from qv.pipeline.stages import StageRunner
from qv.pipeline.wording import wording_flags
from qv.providers.usage import CallContext
from qv.services import workflow
from qv.services.datasets import get_version

#: Structural warnings that count as "similar to another question".
DUPLICATE_CODES = ("exact_duplicate_question", "near_duplicate_question")
#: The quality check's overall rating in words.
QUALITY_TEXT = {"GOOD": "good", "NEEDS_IMPROVEMENT": "could be better", "POOR": "poor"}


@dataclass
class PrepareItem:
    """One question of the latest version, with its wording flags and stored quality check."""

    state: workflow.QuestionState
    flags: tuple[str, ...]
    quality: Quality | None

    @property
    def ext_id(self) -> str:
        return self.state.ext_id

    @property
    def quality_issues(self) -> list[str]:
        """Issue types of the quality check (empty when not checked or none)."""
        return [i.type for i in self.quality.issues] if self.quality else []

    @property
    def needs_look(self) -> bool:
        """A wording flag, or a quality check that is not GOOD."""
        return bool(self.flags) or bool(self.quality and self.quality.overall != "GOOD")


def _profile(db: Database, dataset: str) -> Profile:
    return load_profile(workflow.dataset_profile(db, dataset))


def _questions(db: Database, dataset: str) -> dict[int, Any]:
    """question_id → Question of the latest version (format errors included; they get no quality check)."""
    from qv.services.research import question_from_row
    with db.session() as s:
        v = get_version(s, dataset)
        return {r.id: question_from_row(r) for r in s.scalars(
            select(QuestionRow).where(QuestionRow.dataset_version_id == v.id))}


def _duplicates(db: Database, dataset: str) -> set[int]:
    with db.session() as s:
        v = get_version(s, dataset)
        return set(s.scalars(select(StructuralIssueRow.question_id).where(
            StructuralIssueRow.dataset_version_id == v.id, StructuralIssueRow.code.in_(DUPLICATE_CODES))))


def prepare_items(db: Database, dataset: str) -> list[PrepareItem]:
    """Every question of the latest version with its flags and (stored) quality check. Calls no model."""
    cfg = load_research_config()
    profile = _profile(db, dataset)
    system = s6_system_values(profile)
    runner = StageRunner(db, {})
    questions = _questions(db, dataset)
    dupes = _duplicates(db, dataset)
    out = []
    for st in workflow.question_states(db, dataset):
        q = questions[st.question_id]
        flags = wording_flags(q, long_question_words=cfg.prepare_long_question_words,
                              long_answer_words=cfg.prepare_long_answer_words,
                              near_duplicate=st.question_id in dupes)
        found = runner.stored("s6", StageRunner.hash_for("s6", s6_hash_inputs(q), system), Quality)
        out.append(PrepareItem(st, flags, found.output if found else None))  # type: ignore[arg-type]
    return out


def unchecked_ids(items: list[PrepareItem]) -> list[str]:
    """Questions without a quality check yet (format errors left out — they cannot be checked)."""
    return [it.ext_id for it in items if it.quality is None and it.state.status != "format_error"]


def quality_check(runner: StageRunner, db: Database, dataset: str, ext_ids: list[str] | None = None,
                  limit: int | None = None) -> list[str]:
    """Run the quality check (S6 only) for questions that have none yet. Returns report lines.

    Stops cleanly when the free quota runs out; running it again continues (finished ones are stored).
    """
    from qv.providers.llm.base import LLMError
    from qv.providers.usage import QuotaExhausted
    profile = _profile(db, dataset)
    system = s6_system_values(profile)
    items = prepare_items(db, dataset)
    todo = [it for it in items if it.ext_id in set(unchecked_ids(items))
            and (not ext_ids or it.ext_id in set(ext_ids))]
    if limit is not None:
        todo = todo[:max(limit, 0)]
    questions = _questions(db, dataset)
    lines: list[str] = []
    done = 0
    for it in todo:
        q = questions[it.state.question_id]
        try:
            r = runner.run(stage="s6", user=render_s6(q), schema_cls=Quality, hash_inputs=s6_hash_inputs(q),
                           system_values=system, ctx=CallContext(None, it.state.question_id, "s6"),
                           checks=lambda o, q=q: check_s6(o, q))
        except QuotaExhausted as exc:
            lines.append(f"Stopped: {exc}. Run it again later; finished questions are kept.")
            break
        except LLMError as exc:
            lines.append(f"  #{it.ext_id}: failed — {type(exc).__name__}: {str(exc)[:160]}")
            continue
        out: Quality = r.output  # type: ignore[assignment]
        done += 1
        issues = ", ".join(i.type.replace("_", " ") for i in out.issues)
        lines.append(f"  #{it.ext_id}: {QUALITY_TEXT[out.overall]}" + (f" — {issues}" if issues else ""))
    left = len(unchecked_ids(prepare_items(db, dataset)))
    lines.append(f"Quality check: {done} question(s) checked now, {left} still without one.")
    return lines


def requests_left(db: Database) -> float | None:
    """Free requests left today on the pool the quality check uses; None when a local model can take over."""
    return workflow.requests_left(db, "s6")
