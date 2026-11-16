"""Stage models vs design schemas, prompt blindness, code checks, cached stage execution."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from qv.config import load_profile
from qv.db.session import Database
from qv.domain.question import Question
from qv.domain.stages import BlindAnswer, ClaimFormulation, Decomposition, Extraction, Quality, Verification
from qv.pipeline.stages import (
    DocMeta, StageRunner, check_s1a, check_s1b, filter_s1b_lookups, render_s1a, render_s1b, render_s3,
    system_prompt, windows,
)
from qv.providers.llm.base import json_schema_for
from qv.providers.usage import CallContext
from tests.test_llm import make_pool

PROMPTS = Path(__file__).parents[1] / "prompts"
DESIGN = {"s1a": ("s1a-question-decomposition.md", Decomposition),
          "s1b": ("s1b-claim-formulation.md", ClaimFormulation),
          "s3": ("s3-evidence-extraction.md", Extraction),
          "s4": ("s4-blind-answer.md", BlindAnswer),
          "s5": ("s5-verification.md", Verification),
          "s6": ("s6-quality.md", Quality)}


def design_schema(file: str) -> dict:
    text = (PROMPTS / file).read_text()
    block = re.search(r"## Output schema\s*\n```json\n(.*?)\n```", text, re.S).group(1)
    return json.loads(block)


def shape(schema: Any) -> Any:
    """Required fields, enums and nesting — the parts both schemas must agree on."""
    if isinstance(schema, dict):
        if "anyOf" in schema:
            enums = sorted({e for s in schema["anyOf"] for e in s.get("enum", []) if e is not None})
            inner = [shape(s) for s in schema["anyOf"] if s.get("type") != "null"]
            return {"enum": enums} if enums else (inner[0] if len(inner) == 1 else inner)
        out: dict[str, Any] = {}
        if "properties" in schema:
            out["required"] = sorted(schema.get("required", []))
            out["props"] = {k: shape(v) for k, v in schema["properties"].items()}
        if "items" in schema:
            out["items"] = shape(schema["items"])
        if "enum" in schema:
            out["enum"] = sorted(e for e in schema["enum"] if e is not None)
        return out
    return schema


@pytest.mark.parametrize("stage", list(DESIGN))
def test_models_match_the_design_schemas(stage: str) -> None:
    file, model = DESIGN[stage]
    assert shape(json_schema_for(model)) == shape(design_schema(file))


@pytest.mark.parametrize("stage", list(DESIGN))
def test_versioned_prompts_equal_the_design_docs(stage: str) -> None:
    text = (PROMPTS / DESIGN[stage][0]).read_text()
    block = re.search(r"## System prompt\s*\n```\n(.*?)\n```", text, re.S).group(1)
    assert system_prompt(f"{stage}.v1") == block.strip()


@pytest.fixture
def q_multi() -> Question:
    return Question(row_no=1, line_no=2, ext_id="135", question="In which country is Mount Kilimanjaro?",
                    type="multi", answer="2", options=("Ethiopia", "Tanzania", "Uganda", "Kenya"),
                    difficulty="hard", category="Wonders", subcategory="Natural", topic="Africa",
                    note="SECRET-NOTE: Tanzania is right", raw={})


def s1a_out(**over: Any) -> Decomposition:
    base = {
        "information_need": "Which country contains Mount Kilimanjaro?", "answer_type": "place",
        "subject_entities": ["Mount Kilimanjaro"], "claim_type": "geography_fact", "frame_class": "universal",
        "presuppositions": [], "time_sensitivity": {"is_time_sensitive": False, "as_of_in_question": None,
                                                    "reason": "x"},
        "conventions": [], "interpretations": [],
        "superlative": {"is_superlative": False, "dimension": None, "competitor_check_needed": False},
        "queries": [{"q": "Mount Kilimanjaro location", "purpose": "core", "target": "need"},
                    {"q": "Kilimanjaro national park country", "purpose": "core", "target": "need"},
                    {"q": "highest mountain in Africa country", "purpose": "core", "target": "need"}],
        "direct_lookups": [], "researchable": True, "researchable_note": None}
    base.update(over)
    return Decomposition.model_validate(base)


def test_s1a_prompt_is_blind(q_multi: Question) -> None:
    text = render_s1a(q_multi, load_profile("world-tour"))
    assert "SECRET-NOTE" not in text and "Expected" not in text
    assert "A. Ethiopia" in text and "D. Kenya" in text
    assert "correct one is not indicated" in text


def test_s1b_prompt_sees_key_and_note(q_multi: Question) -> None:
    text = render_s1b(q_multi, load_profile("world-tour"), s1a_out())
    assert "Expected answer: B. Tanzania" in text and "SECRET-NOTE" in text


def test_s3_prompt_is_blind_and_mode_a_has_no_note_claims(q_multi: Question) -> None:
    meta = DocMeta(1, "https://x.org", "T", "x.org", "2026-11-15")
    a = render_s3(q_multi, s1a_out(), mode="A", doc=meta, window="DOC TEXT", note_claims=[("N1", "secret claim")])
    assert "Expected" not in a and "SECRET-NOTE" not in a and "secret claim" not in a
    assert "<document>\nDOC TEXT\n</document>" in a
    b = render_s3(q_multi, s1a_out(), mode="B", doc=meta, window="DOC", note_claims=[("N1", "claim one")])
    assert "N1: claim one" in b and "Expected" not in b


def test_check_s1a_symmetry(q_multi: Question) -> None:
    biased = s1a_out(queries=[{"q": "is Kilimanjaro in Tanzania", "purpose": "core", "target": "need"},
                              {"q": "Kilimanjaro location", "purpose": "core", "target": "need"},
                              {"q": "Kilimanjaro facts", "purpose": "core", "target": "need"}])
    assert any("biased" in p for p in check_s1a(biased, q_multi))
    assert check_s1a(s1a_out(), q_multi) == []


def test_check_s1a_presuppositions_and_competitor(q_multi: Question) -> None:
    out = s1a_out(presuppositions=[{"id": "PR1", "text": "x", "claim_type": "other", "frame_class": "universal",
                                    "material": True}],
                  superlative={"is_superlative": True, "dimension": "height", "competitor_check_needed": True})
    problems = check_s1a(out, q_multi)
    assert any("PR1" in p for p in problems) and any("competitor" in p for p in problems)


def test_s1b_lookups_must_come_from_the_note() -> None:
    q = Question(row_no=1, line_no=2, ext_id="3", question="What did Allah teach Adam?", type="open",
                 answer="The names", options=("", "", "", ""), difficulty="hard", category="c", subcategory="",
                 topic="", note="Surah Al-Baqarah 2:32", raw={})
    out = ClaimFormulation.model_validate({
        "key_claim": "k", "key_components": [], "answer_equivalents": [], "note_claims": [],
        "direct_lookups": [{"for_claim": "N1", "source": "quran", "ref": "2:32", "scheme": None},
                           {"for_claim": "N1", "source": "quran", "ref": "2:31", "scheme": "common"}],
        "challenge_queries": [], "note_queries": []})
    assert check_s1b(out, q) == ["lookup '2:31' is not a reference written in the note"]
    assert [lk.ref for lk in filter_s1b_lookups(out, q).direct_lookups] == ["2:32"]


def test_windows() -> None:
    assert windows("abc", 10, 2, 3) == ["abc"]
    w = windows("x" * 25, 10, 2, 3)
    assert [len(p) for p in w] == [10, 10, 9]
    assert len(windows("x" * 100, 10, 2, 2)) == 2


def test_stage_runner_reuses_outputs_by_input_hash(db: Database, q_multi: Question) -> None:
    good = s1a_out().model_dump_json()
    pool, prov = make_pool(db, {"a": [good]})
    runner = StageRunner(db, {"s1a": pool})
    kw = dict(stage="s1a", user="u", schema_cls=Decomposition, hash_inputs={"q": 1}, ctx=CallContext())
    first = runner.run(**kw)
    second = runner.run(**kw)
    assert not first.reused and second.reused and second.stage_output_id == first.stage_output_id
    assert len(prov.calls) == 1


def test_stage_runner_retries_once_on_check_failure(db: Database, q_multi: Question) -> None:
    biased = s1a_out(queries=[{"q": "Tanzania Kilimanjaro", "purpose": "core", "target": "need"},
                              {"q": "Kilimanjaro location", "purpose": "core", "target": "need"},
                              {"q": "Kilimanjaro facts", "purpose": "core", "target": "need"}]).model_dump_json()
    pool, prov = make_pool(db, {"a": [biased, s1a_out().model_dump_json()]})
    run = StageRunner(db, {"s1a": pool}).run(stage="s1a", user="u", schema_cls=Decomposition, hash_inputs={},
                                            ctx=CallContext(), checks=lambda o: check_s1a(o, q_multi))
    assert run.checks == [] and len(prov.calls) == 2
    assert "avoid them" in prov.calls[1][1][0].text
