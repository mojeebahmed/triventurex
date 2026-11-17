"""Prepare: wording flags (pure code), the quality check alone (S6, reused by validation), new wordings."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import respx
from sqlalchemy import select

from qv.db.models import StageOutput
from qv.db.session import Database
from qv.domain.question import Question
from qv.pipeline.wording import FLAG_BY_CODE, FLAGS, wording_flags
from qv.providers.llm.base import Message, RawResponse
from qv.providers.usage import CallContext
from qv.services import prepare, worker, workflow
from qv.services.datasets import import_dataset
from qv.services.research import execute_run, start_run
from tests.test_judgement import JudgingLLM, judging_deps
from tests.test_research import CSV, mock_web


def q(text: str, answer: str = "x", type_: str = "open") -> Question:
    return Question(row_no=1, line_no=2, ext_id="1", question=text, type=type_, answer=answer,
                    options=("", "", "", ""), difficulty="easy", category="c", subcategory="s", topic="t",
                    note="", raw={})


def flags(question: Question, **kw: Any) -> tuple[str, ...]:
    return wording_flags(question, long_question_words=kw.pop("lq", 25), long_answer_words=kw.pop("la", 8), **kw)


# --- wording flags ----------------------------------------------------------------------

def test_answer_with_several_facts_is_flagged() -> None:
    baitul = q("What is Baitul Futuh?", "An Ahmadiyya mosque in Morden, London — one of the largest mosques in "
                                        "Western Europe, opened in 2006.")
    assert flags(baitul) == ("answer_several_facts",)          # long too, but one flag is enough
    assert flags(q("Who?", " ".join(["word"] * 9))) == ("long_answer",)
    assert flags(q("What is the capital of France?", "Paris")) == ()
    assert "answer_several_facts" not in flags(q("Who?", "Adam and Eve"))       # short: not several facts


def test_statement_before_the_question() -> None:
    assert "statement_first" in flags(q("Kilimanjaro is the highest mountain in Africa. In which country is it?"))
    assert "statement_first" not in flags(q("Who built St. Peter's Basilica?"))
    assert "statement_first" not in flags(q("Which city is called the Big Apple?"))


def test_numbers_figures_negatives_and_length() -> None:
    assert flags(q("How high is Kilimanjaro?", "5,895 metres")) == ("exact_figure",)
    assert flags(q("In which year was the Community founded?", "1889")) == ()          # a year is not exact
    assert "several_numbers" in flags(q("Between 1914 and 1918, how many …?", "4"))
    assert flags(q("Which verse is 2:31 about?", "Adam")) == ()                       # a reference is no figure
    assert flags(q("Which of these is NOT a prophet?")) == ("negative",)
    assert flags(q("Who? And where?")) == ("two_questions",)
    assert "long_question" in flags(q(" ".join(["word"] * 26) + "?"))
    assert "long_question" not in flags(q(" ".join(["word"] * 26) + "?"), lq=30)
    assert flags(q("Who?"), near_duplicate=True) == ("near_duplicate",)


def test_flags_have_labels_and_the_help_lists_them_all() -> None:
    from qv.ui.help_text import help_for
    assert len(FLAG_BY_CODE) == len(FLAGS)
    text = "".join(t for _, t in help_for("prepare"))
    assert all(f.label in text for f in FLAGS) and "{flags}" not in text


# --- quality check alone, reused by validation -------------------------------------------

class RewritingLLM(JudgingLLM):
    """S6 says the wording could be better and suggests a rewrite; everything else as JudgingLLM."""

    def generate_json(self, *, model: str, system: str, messages: Sequence[Message], schema: dict[str, Any],
                      ctx: CallContext) -> RawResponse:
        if ctx.stage != "s6":
            return super().generate_json(model=model, system=system, messages=messages, schema=schema, ctx=ctx)
        self.prompts.append((ctx.stage, messages[0].text))
        from tests.test_rules import quality
        out = quality("NEEDS_IMPROVEMENT").model_dump()
        out["issues"] = [{"type": "compound_question", "severity": "major", "detail": "two facts",
                          "is_hypothesis": False, "option": None}]
        out["suggested_rewrite"] = {"question": "Which country is Mount Kilimanjaro in?", "options": None,
                                    "answer": "B", "note": None}
        out["rewrite_reason"] = "shorter"
        return RawResponse(text=json.dumps(out), model=model, finish_reason="STOP")


@pytest.fixture
def mini(db: Database) -> str:
    with db.session() as s:
        import_dataset(s, CSV, dataset_name="mini", source_filename="mini.csv", profile_name="prophets-stories")
    return "mini"


def s6_calls(llm: JudgingLLM) -> int:
    return sum(1 for st, _ in llm.prompts if st == "s6")


@respx.mock
def test_quality_check_is_stored_and_reused_by_validation(db: Database, mini: str) -> None:
    items = prepare.prepare_items(db, mini)
    assert [it.quality for it in items] == [None, None] and prepare.unchecked_ids(items) == ["135", "3"]
    llm = RewritingLLM()
    deps = judging_deps(db, llm)
    lines = prepare.quality_check(deps.runner, db, mini, limit=1)
    assert s6_calls(llm) == 1 and "#135: could be better — compound question" in lines[0]
    assert lines[-1] == "Quality check: 1 question(s) checked now, 1 still without one."
    with db.session() as s:
        out = s.scalar(select(StageOutput).where(StageOutput.stage == "s6"))
        assert out.run_id is None and out.valid          # no run: a Prepare check belongs to no batch
    item = {it.ext_id: it for it in prepare.prepare_items(db, mini)}["135"]
    assert item.quality.overall == "NEEDS_IMPROVEMENT" and item.quality_issues == ["compound_question"]
    assert item.needs_look and item.state.status == "not_checked"

    prepare.quality_check(deps.runner, db, mini)      # only the question without one
    assert s6_calls(llm) == 2 and prepare.unchecked_ids(prepare.prepare_items(db, mini)) == []
    prepare.quality_check(deps.runner, db, mini)      # nothing left: no call
    assert s6_calls(llm) == 2

    mock_web()                                        # the full check reuses the stored quality check
    execute_run(deps, start_run(db, mini, ["135"], kind="validate"))
    assert s6_calls(llm) == 2


# --- new wordings -------------------------------------------------------------------------

def test_new_wording_is_not_ready_and_becomes_a_new_version(db: Database, mini: str) -> None:
    workflow.record_decision(db, mini, "135", "reword", changes={"question": "Which country is Kilimanjaro in?"})
    workflow.record_decision(db, mini, "3", "wording_ok")
    st = {s.ext_id: s for s in workflow.question_states(db, mini)}
    assert st["135"].status == "not_checked" and st["135"].decision == ""   # never "edited" / ready
    assert st["135"].prepare == "reword" and st["3"].prepare == "wording_ok"
    assert workflow.pending_rewords(list(st.values())) == {"135": {"question": "Which country is Kilimanjaro in?"}}
    assert workflow.pending_edits(list(st.values())) == {}
    assert workflow.apply_edits_as_new_version(db, mini) is None             # review edits: none
    with pytest.raises(ValueError, match="Nothing was changed"):
        workflow.record_decision(db, mini, "3", "reword", changes={"answer": "The names of all things"})

    assert workflow.apply_edits_as_new_version(db, mini, prepared=True) == 2
    st = {s.ext_id: s for s in workflow.question_states(db, mini)}
    assert st["135"].question == "Which country is Kilimanjaro in?" and st["135"].prepare == ""
    assert st["3"].prepare == "wording_ok"                                   # unchanged question keeps its choice
    assert workflow.apply_edits_as_new_version(db, mini, prepared=True) is None


def test_wording_ok_takes_back_a_new_wording(db: Database, mini: str) -> None:
    workflow.record_decision(db, mini, "135", "reword", changes={"note": "New note"})
    workflow.record_decision(db, mini, "135", "wording_ok")
    assert workflow.pending_rewords(workflow.question_states(db, mini)) == {}


# --- background and command line -----------------------------------------------------------

def test_background_command_must_be_known(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        worker.start_background(tmp_path, "mini", [], command="rm")


def test_cli_prepare(db: Database, mini: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from qv.cli import app
    llm = RewritingLLM()
    monkeypatch.setattr("qv.cli._db", lambda: db)
    monkeypatch.setattr("qv.services.research.build_deps", lambda settings, db_: judging_deps(db_, llm))
    monkeypatch.setattr("qv.services.prepare.requests_left", lambda db_: 100.0)
    out = CliRunner().invoke(app, ["--data-dir", str(tmp_path), "prepare", "mini", "--ids", "3"], input="n\n").output
    assert "2 questions" in out and "Quality check: 1 question(s) to check" in out and s6_calls(llm) == 0
    out = CliRunner().invoke(app, ["--data-dir", str(tmp_path), "prepare", "mini", "--yes"]).output
    assert "#135: could be better" in out and s6_calls(llm) == 2
    assert not worker.status(tmp_path).running                               # the lock is released
