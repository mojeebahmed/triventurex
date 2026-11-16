"""S4/S5/S6 prompts (what each stage may see), code checks, and an end-to-end validate run (no network)."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import respx
from sqlalchemy import select
from typer.testing import CliRunner

from qv.config import load_profile
from qv.db.models import Run, StageOutput, Validation
from qv.db.session import Database
from qv.domain.stages import BlindAnswer, Decomposition, Quality, Verification
from qv.pipeline.evidence import EvidencePassage, assign_clusters
from qv.pipeline.judgement import check_s4, check_s5, check_s6, render_s4, render_s5, render_s6, s5_system_values
from qv.pipeline.rules import load_requirements
from qv.pipeline.stages import fill_template, system_prompt
from qv.providers.llm.base import Message, ModelPool, RawResponse
from qv.providers.usage import CallContext, Limit
from qv.services.judgement import judge_run
from qv.services.research import execute_run, start_run
from qv.services.views import evidence_summary, question_verdict, run_verdicts
from tests.test_research import FakeLLM, build, mock_web, s1a_json, s1b_json

PROMPTS = Path(__file__).parents[1] / "prompts"


def design_example(file: str) -> dict:
    blocks = re.findall(r"```json\n(.*?)\n```", (PROMPTS / file).read_text(), re.S)
    return json.loads(blocks[-1])


@pytest.mark.parametrize("file,model", [("s4-blind-answer.md", BlindAnswer), ("s5-verification.md", Verification),
                                        ("s6-quality.md", Quality)])
def test_design_examples_are_valid_outputs(file: str, model: type) -> None:
    model.model_validate(design_example(file))


def test_fill_template() -> None:
    t = "a {{x}}{{#if on}} b {{y}}{{/if}}{{#if off}} c{{/if}}"
    assert fill_template(t, {"x": 1, "y": 2, "on": True, "off": False}) == "a 1 b 2"
    with pytest.raises(KeyError):
        fill_template("{{missing}}", {})


def test_every_placeholder_in_s5_and_s6_is_filled(q_kili: Any) -> None:
    from qv.pipeline.judgement import s6_system_values
    profile = load_profile("prophets-stories")
    s1a = Decomposition.model_validate(s1a_json(""))
    for version, values in (("s5.v1", s5_system_values(q_kili, s1a, profile, None, load_requirements())),
                            ("s6.v1", s6_system_values(profile))):
        assert "{{" not in fill_template(system_prompt(version), values)


@pytest.fixture
def q_kili() -> Any:
    from qv.domain.question import Question
    return Question(row_no=1, line_no=2, ext_id="135", question="In which country is Mount Kilimanjaro?",
                    type="multi", answer="2", options=("Ethiopia", "Tanzania", "Uganda", "Kenya"), difficulty="hard",
                    category="c", subcategory="s", topic="t", note="NOTE-MARKER roof of Africa", raw={})


def passages() -> list[EvidencePassage]:
    def p(pid: str, mode: str, quote: str) -> EvidencePassage:
        return EvidencePassage(pid=pid, passage_id=int(pid[1:]), mode=mode, target="need" if mode == "A" else "N1",
                               quote=quote, tier="S", frame_authority=False, publisher=f"pub{pid}",
                               domain=f"d{pid}.org", page_kind="news", matches_option="B" if mode == "A" else None)
    return assign_clusters([p("P1", "A", "Kilimanjaro is in Tanzania."), p("P2", "B", "NOTE-PASSAGE roof text")])


def test_s4_never_sees_key_note_or_note_passages(q_kili: Any) -> None:
    s1a = Decomposition.model_validate(s1a_json(""))
    text = render_s4(q_kili, s1a, passages())
    assert "Tanzania." in text and "NOTE-MARKER" not in text and "NOTE-PASSAGE" not in text
    assert "Expected" not in text and "answer: B" not in text.lower()


def test_s5_sees_key_note_and_all_passages(q_kili: Any) -> None:
    s1a = Decomposition.model_validate(s1a_json(""))
    s1b = __import__("qv.domain.stages", fromlist=["ClaimFormulation"]).ClaimFormulation.model_validate(
        s1b_json(False))
    text = render_s5(q_kili, s1a, s1b, load_profile("world-tour"), passages())
    assert "Expected answer: B. Tanzania" in text and "NOTE-MARKER" in text and "NOTE-PASSAGE" in text


def test_s6_sees_no_evidence(q_kili: Any) -> None:
    text = render_s6(q_kili)
    assert "Expected answer: B. Tanzania" in text and "Kilimanjaro is in Tanzania." not in text


def test_s4_checks(q_kili: Any) -> None:
    ok = BlindAnswer(status="answered", answer="Tanzania", option="B", supporting_passages=["P1"],
                     conflicting_passages=[], alternative_answers=[], presupposition_findings=[],
                     missing_evidence=None, reasoning="r")
    assert check_s4(ok, q_kili, passages()) == []
    bad = ok.model_copy(update={"supporting_passages": ["P2"], "option": None})
    problems = check_s4(bad, q_kili, passages())
    assert any("not provided" in p for p in problems)  # P2 is a note passage S4 never saw
    assert any("option letter" in p for p in problems)


def test_s5_and_s6_checks(q_kili: Any) -> None:
    from tests.test_rules import quality, verification
    v = verification(supporting=[], option_assessments=[
        {"option": "B", "status": "correct", "passages": ["P1"], "reason": "r"}])
    problems = check_s5(v, q_kili, passages())
    assert any("CORRECT needs" in p for p in problems) and any("missing" in p for p in problems)
    q = Quality.model_validate({**quality().model_dump(), "suggested_rewrite": {
        "question": "q", "options": None, "answer": "a", "note": None}})
    assert check_s6(q, q_kili)


def test_evidence_summary_counts_origins() -> None:
    ps = passages()
    assert evidence_summary(ps, "Tanzania", "B", ("Ethiopia", "Tanzania", "Uganda", "Kenya")) == \
        "Evidence says: B. Tanzania (1 origin) — expected answer: B. Tanzania"


# --- end to end ---------------------------------------------------------------------

class JudgingLLM(FakeLLM):
    """FakeLLM plus S4/S5/S6 answers that cite whatever passage ids the prompt shows."""

    def generate_json(self, *, model: str, system: str, messages: Sequence[Message], schema: dict[str, Any],
                      ctx: CallContext) -> RawResponse:
        if ctx.stage not in ("s4", "s5", "s6"):
            return super().generate_json(model=model, system=system, messages=messages, schema=schema, ctx=ctx)
        user = messages[0].text
        self.prompts.append((ctx.stage, user))
        ids = re.findall(r"^\[(P\d+)\]", user, re.M)
        from tests.test_rules import blind, quality, verification
        if ctx.stage == "s4":
            out = blind(supporting=ids[:1]).model_dump()
        elif ctx.stage == "s5":
            out = verification(supporting=ids[:1], option_assessments=[
                {"option": o, "status": "correct" if o == "B" else "incorrect", "passages": ids[:1], "reason": "r"}
                for o in "ABCD"]).model_dump()
        else:
            out = quality().model_dump()
        return RawResponse(text=json.dumps(out), model=model, finish_reason="STOP")


def judging_deps(db: Database, llm: FakeLLM) -> Any:
    deps = build(db, llm)
    for st in ("s4", "s5", "s6"):
        deps.runner.pools[st] = ModelPool.single(llm, ["m1"], {"m1": [Limit("day", 1000)]}, {"m1": 1000},
                                                 deps.metering)
    return deps


@pytest.fixture
def dataset(db: Database) -> None:
    from tests.test_research import CSV
    from qv.services.datasets import import_dataset
    with db.session() as s:
        import_dataset(s, CSV, dataset_name="mini", source_filename="mini.csv", profile_name="prophets-stories")


@respx.mock
def test_validate_run_stores_a_verdict_and_keeps_the_key_out_of_s4(db: Database, dataset: None) -> None:
    mock_web()
    llm = JudgingLLM()
    run_id = start_run(db, "mini", ["135"], kind="validate")
    report = execute_run(judging_deps(db, llm), run_id)
    assert report.done == 1 and report.questions[0]["verdict"]
    s4_prompts = [u for st, u in llm.prompts if st == "s4"]
    assert s4_prompts and all("NOTE-MARKER" not in u and "Expected" not in u for u in s4_prompts)
    with db.session() as s:
        v = s.scalar(select(Validation))
        assert v.run_id == run_id and v.passage_map_json and v.s4_output_id and v.s5_output_id
        assert s.get(Run, run_id).kind == "validate"
    rows = run_verdicts(db, run_id)
    assert rows[0]["id"] == "135"
    detail = question_verdict(db, run_id, "135")
    assert detail and any(line.startswith("VERDICT") for line in detail["summary_lines"])


@respx.mock
def test_judging_an_existing_research_run_reuses_stage_outputs(db: Database, dataset: None) -> None:
    mock_web()
    llm = JudgingLLM()
    run_id = start_run(db, "mini", ["135"])
    execute_run(judging_deps(db, llm), run_id)  # research only
    assert not any(st in ("s4", "s5", "s6") for st, _ in llm.prompts)
    lines = judge_run(judging_deps(db, llm), run_id)
    assert lines and "#135" in lines[0]
    n = len(llm.prompts)
    judge_run(judging_deps(db, llm), run_id)  # again: everything cached
    assert len(llm.prompts) == n
    with db.session() as s:
        assert len(list(s.scalars(select(Validation)))) == 1
        assert {o.stage for o in s.scalars(select(StageOutput))} >= {"s4", "s5", "s6"}


@respx.mock
def test_cli_verdicts(db: Database, dataset: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from qv.cli import app
    mock_web()
    run_id = start_run(db, "mini", ["135"], kind="validate")
    execute_run(judging_deps(db, JudgingLLM()), run_id)
    monkeypatch.setattr("qv.cli._db", lambda: db)
    out = CliRunner().invoke(app, ["verdicts", str(run_id)]).output
    assert "#  135" in out
    out = CliRunner().invoke(app, ["verdict", str(run_id), "135"]).output
    assert "VERDICT" in out and "Why:" in out
