"""The simple workflow: priority, status per question, batches, decisions, exports, import hints, batch lock."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import respx
from sqlalchemy import text

from qv.db.session import Database
from qv.domain.question import Question
from qv.domain.structural import IssueCode, Severity, StructuralIssue
from qv.io.csv_format import parse_csv
from qv.pipeline.priority import CHANGED_SINCE_CHECK, priority
from qv.services import worker, workflow
from qv.services.datasets import import_dataset
from qv.services.exports import drop_rows, workflow_export
from qv.services.import_help import hint, suggest_column
from qv.services.research import execute_run
from tests.test_judgement import JudgingLLM, judging_deps
from tests.test_research import CSV, mock_web


def q(text_: str, answer: str = "x", note: str = "", difficulty: str = "easy") -> Question:
    return Question(row_no=1, line_no=2, ext_id="1", question=text_, type="open", answer=answer,
                    options=("", "", "", ""), difficulty=difficulty, category="c", subcategory="s", topic="t",
                    note=note, raw={})


# --- priority -----------------------------------------------------------------------------

def test_priority_reasons_and_levels() -> None:
    p = priority(q("Since 2010, which building has been the tallest in the world?", difficulty="hard"))
    assert p.level == "high" and "numbers or dates" in p.reasons and "can go out of date" in p.reasons
    assert "a 'most / first / only' claim" in p.reasons and "hard question" in p.reasons
    assert priority(q("What colour is a banana?", answer="yellow")).level == "low"
    assert priority(q("Who was Adam?", note="Surah Al-Baqarah 2:31")).reasons == ("the note makes its own claim",)
    edited = priority(q("What colour is a banana?"), changed=True)
    assert edited.level == "high" and edited.reasons[0] == CHANGED_SINCE_CHECK


# --- import help --------------------------------------------------------------------------

def test_column_suggestions() -> None:
    assert suggest_column("Question") == "question"
    assert suggest_column("Option 1") == "opt_a"
    assert suggest_column("correct answer") == "answer"
    assert suggest_column("questoin") == "question"
    assert suggest_column("Question", ["question"]) is None  # already there
    assert suggest_column("colour") is None


def test_every_issue_code_has_a_hint() -> None:
    from qv.services.import_help import FIX_HINTS
    assert set(FIX_HINTS) == set(IssueCode)
    issue = StructuralIssue(code=IssueCode.UNKNOWN_COLUMN, severity=Severity.WARNING, message="m", column="Option 2")
    assert hint(issue, ["id"]).startswith("Probably 'opt_b'")


# --- statuses, batches, decisions, exports ---------------------------------------------

@pytest.fixture
def mini(db: Database) -> str:
    with db.session() as s:
        import_dataset(s, CSV, dataset_name="mini", source_filename="mini.csv", profile_name="prophets-stories")
    return "mini"


def test_states_before_anything_is_checked(db: Database, mini: str) -> None:
    states = workflow.question_states(db, mini)
    assert [s.status for s in states] == ["not_checked", "not_checked"]
    plan = workflow.plan_next_batch(db, mini, workflow.Selection(), 5)
    assert plan.action == "start" and len(plan.questions) == 2
    by_file = workflow.plan_next_batch(db, mini, workflow.Selection(order="file"), 5)
    assert [s.ext_id for s in by_file.questions] == ["135", "3"]
    with pytest.raises(ValueError):
        workflow.Selection(order="random")
    assert workflow.Selection(order="priority").order == "risk"
    assert [s.ext_id for s in workflow.plan_next_batch(db, mini, workflow.Selection(topics=("Story",)), 5)
            .questions] == ["3"]
    only = workflow.plan_next_batch(db, mini, workflow.Selection(categories=("Adam",)), 5)
    assert [s.ext_id for s in only.questions] == ["3"]
    assert workflow.plan_next_batch(db, mini, workflow.Selection(categories=("None",)), 5).action == "nothing"


@respx.mock
def test_batch_review_decide_and_export(db: Database, mini: str) -> None:
    mock_web()
    plan = workflow.plan_next_batch(db, mini, workflow.Selection(ids=("135",)), 5)
    run_id = workflow.start_batch(db, plan, workflow.Selection(ids=("135",)))
    assert {s.ext_id: s.status for s in workflow.question_states(db, mini)}["135"] == "in_progress"
    # an interrupted batch is continued first
    assert workflow.plan_next_batch(db, mini, workflow.Selection(), 5).action == "resume"
    execute_run(judging_deps(db, JudgingLLM()), run_id)
    st = {s.ext_id: s for s in workflow.question_states(db, mini)}
    assert st["135"].verdict and st["135"].status in workflow.ROUTE_STATUS.values()
    assert workflow.plan_next_batch(db, mini, workflow.Selection(), 5).questions[0].ext_id == "3"

    # decisions: newest wins, history is kept, rows cannot be changed
    workflow.record_decision(db, mini, "135", "later")
    workflow.record_decision(db, mini, "135", "edit", changes={"note": "A new note"}, comment="clearer")
    st = {s.ext_id: s for s in workflow.question_states(db, mini)}["135"]
    assert st.status == "edited" and st.decision_changes == {"note": "A new note"}
    assert [h["action"] for h in workflow.decision_history(db, mini, "135")] == ["edit", "later"]
    with pytest.raises(Exception), db.session() as s:
        s.execute(text("UPDATE decisions SET action = 'keep'"))
    with pytest.raises(ValueError):
        workflow.record_decision(db, mini, "135", "edit", changes={"id": "9"})
    with pytest.raises(ValueError, match="Nothing was changed"):
        workflow.record_decision(db, mini, "135", "edit", changes={"note": "NOTE-MARKER the roof of Africa"})
    workflow.record_decision(db, mini, "3", "remove")

    data, name, summary = workflow_export(db, mini, "corrected")
    rows = {r.get("id"): r for r in parse_csv(data).rows}
    assert name == "mini-v1-corrected.csv" and set(rows) == {"135"} and rows["135"].get("note") == "A new note"
    assert summary == {"rows": 1, "edited": 1, "left_out": 1}
    verified, _, _ = workflow_export(db, mini, "verified")
    assert {r.get("id") for r in parse_csv(verified).rows} == {"135"}
    results, _, _ = workflow_export(db, mini, "results")
    assert b"Edited by you" in results and b"Removed by you" in results

    # checking edits again: a new version; the edited question is not checked and comes first
    assert workflow.apply_edits_as_new_version(db, mini) == 2
    st = {s.ext_id: s for s in workflow.question_states(db, mini)}
    assert st["135"].status == "not_checked" and CHANGED_SINCE_CHECK in st["135"].priority_reasons
    assert st["3"].status == "removed"  # unchanged question keeps its decision
    assert workflow.plan_next_batch(db, mini, workflow.Selection(), 5).questions[0].ext_id == "135"
    assert workflow.apply_edits_as_new_version(db, mini) is None


def test_drop_rows_keeps_other_bytes() -> None:
    data = b"h\r\n1,a\r\n2,b\r\n3,c"
    assert drop_rows(data, {3}) == b"h\r\n1,a\r\n3,c"
    assert drop_rows(data, set()) == data


# --- one batch at a time ------------------------------------------------------------------

def test_batch_lock(tmp_path: Path) -> None:
    assert not worker.status(tmp_path).running
    assert worker.acquire(tmp_path, "mini")
    st = worker.status(tmp_path)
    assert st.running and st.pid == os.getpid() and st.dataset == "mini"
    worker.release(tmp_path)
    assert not worker.status(tmp_path).running
    (tmp_path / worker.LOCK_NAME).write_text('{"pid": 999999, "dataset": "x"}')  # stale lock
    assert not worker.status(tmp_path).running and worker.acquire(tmp_path, "mini")
    worker.release(tmp_path)


def test_batch_lock_refuses_a_second_live_batch(tmp_path: Path) -> None:
    import subprocess
    import sys
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (tmp_path / worker.LOCK_NAME).write_text(f'{{"pid": {child.pid}, "dataset": "other"}}')
        assert worker.status(tmp_path).running and not worker.acquire(tmp_path, "mini")
    finally:
        child.kill()
        child.wait()
    assert not worker.status(tmp_path).running


def test_cli_next_and_status(db: Database, mini: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from qv.cli import app
    monkeypatch.setattr("qv.cli._db", lambda: db)
    out = CliRunner().invoke(app, ["status", "mini"]).output
    assert "not checked yet 2" in out and "qv next mini" in out
    out = CliRunner().invoke(app, ["next", "mini", "--size", "1", "--category", "Adam", "--difficulty", "hard"],
                             input="n\n").output
    assert "#    3" in out and "#  135" not in out


def test_missing_column_hint_names_the_users_column() -> None:
    issue = StructuralIssue(code=IssueCode.MISSING_COLUMN, severity=Severity.ERROR, message="m", column="answer")
    assert "'correct answer' is probably 'answer'" in hint(issue, ["id", "question", "type", "correct answer"])


def test_signal_table_matches_the_scoring() -> None:
    from qv.pipeline.priority import SIGNALS
    every = q("Since 2010 the most famous record, said in 2:3", note="2:3", difficulty="hard")
    p = priority(every, has_warnings=True, changed=True)
    points = {r: pts for r, pts, _ in SIGNALS}
    assert set(p.reasons) == set(points) and sum(points[r] for r in p.reasons) == p.score


def test_difficulty_orders_keep_edited_questions_first() -> None:
    def st(i: str, diff: str, changed: bool = False) -> workflow.QuestionState:
        return workflow.QuestionState(
            question_id=int(i), ext_id=i, row_no=int(i), question="q", type="open", answer="a", answer_text="a",
            options=("", "", "", ""), note="", difficulty=diff, category="c", subcategory="s", topic="t",
            content_hash=i, status="not_checked", priority_score=0, priority_level="low",
            priority_reasons=(CHANGED_SINCE_CHECK,) if changed else ())
    states = [st("1", "easy"), st("2", "hard"), st("3", "easy", changed=True), st("4", "hard")]
    ids = lambda order: [s.ext_id for s in workflow.candidates(states, workflow.Selection(order=order))]  # noqa: E731
    assert ids("file") == ["3", "1", "2", "4"]
    assert ids("hard") == ["3", "2", "4", "1"]
    assert ids("easy") == ["3", "1", "2", "4"]
    assert [s.ext_id for s in workflow.candidates(states, workflow.Selection(difficulties=("hard",)))] == ["2", "4"]


@respx.mock
def test_measurement_runs_are_not_working_results(db: Database, mini: str) -> None:
    from qv.services.research import start_run
    mock_web()
    deps = judging_deps(db, JudgingLLM())
    deps.named_pools["cheap"] = deps.runner.pools["s4"]
    run_id = start_run(db, mini, ["135"], kind="validate", config={"judge_pool": "cheap"})
    assert workflow.plan_next_batch(db, mini, workflow.Selection(), 5).action == "start"  # not "resume"
    execute_run(deps, run_id)
    assert {s.ext_id: s.status for s in workflow.question_states(db, mini)}["135"] == "not_checked"
