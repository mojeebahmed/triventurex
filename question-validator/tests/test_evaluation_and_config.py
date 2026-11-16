"""Evaluation set integrity and profile loading."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from qv.config import available_profiles, load_profile
from qv.evaluation import (
    EVAL_DIR, Expectation, Mutation, check_case_targets, generate_seeded_errors, labels_to_yaml, load_cases,
    load_questions, load_seeded_labels, stratified_sample,
)
from qv.io.csv_format import js_trim, parse_csv
from qv.pipeline.structural import run_structural_checks
from tests.conftest import EDITIONS, EDITIONS_DIR


@pytest.fixture(scope="module")
def sources() -> dict:
    """Current questions of every edition."""
    return {e: load_questions(EDITIONS_DIR / e / "questions.csv") for e in EDITIONS}


def test_cases_point_at_the_intended_rows() -> None:
    cases = load_cases()
    assert len(cases) >= 20
    assert check_case_targets(cases) == []


def test_known_errors_file_is_valid_csv() -> None:
    report = run_structural_checks(parse_csv((EVAL_DIR / "known_errors.csv").read_bytes()))
    assert report.ok_for_game and report.row_count == 4


def test_expectation_validation() -> None:
    assert Expectation(any_of=("VERIFIED", "AMBIGUOUS")).accepts("AMBIGUOUS")
    with pytest.raises(ValidationError):
        Expectation()
    with pytest.raises(ValidationError):
        Expectation(verdict="RIGHT")


def test_seeded_files_are_up_to_date(sources: dict) -> None:
    """eval/seeded.* equal a fresh generation (regenerate with `qv eval seed` after content edits)."""
    data, labels = generate_seeded_errors(sources)
    assert (EVAL_DIR / "seeded.csv").read_bytes() == data
    assert (EVAL_DIR / "seeded_labels.yaml").read_text(encoding="utf-8") == labels_to_yaml(labels)


def test_seeded_errors_are_real_edits(sources: dict) -> None:
    labels = load_seeded_labels()
    assert {lb.mutation for lb in labels} == set(Mutation)
    seeded = load_questions(EVAL_DIR / "seeded.csv")
    for lb in labels:
        assert lb.original != lb.seeded
        q = seeded[lb.eval_id]
        src = sources[lb.source_dataset][lb.source_id]
        assert js_trim(q.raw[lb.field]) == lb.seeded
        for col in ("question", "answer", "note"):
            if col != lb.field:
                assert getattr(q, col) == getattr(src, col), (lb.eval_id, col)
    report = run_structural_checks(parse_csv((EVAL_DIR / "seeded.csv").read_bytes()))
    assert report.ok_for_game


def test_seeding_is_deterministic(sources: dict) -> None:
    assert generate_seeded_errors(sources, seed=1) == generate_seeded_errors(sources, seed=1)
    assert generate_seeded_errors(sources, seed=1)[0] != generate_seeded_errors(sources, seed=2)[0]


def test_stratified_sample(sources: dict) -> None:
    always = {("world-tour", "120"), ("football-quest", "66")}
    picked = stratified_sample(sources, n=150, always=always)
    keys = [(d, q.ext_id) for d, q in picked]
    assert len(keys) == 150 and len(set(keys)) == 150
    assert always <= set(keys)
    assert {d for d, _ in keys} == set(EDITIONS)
    assert keys == [(d, q.ext_id) for d, q in stratified_sample(sources, n=150, always=always)]


@pytest.mark.parametrize("name", available_profiles())
def test_every_profile_loads(name: str) -> None:
    p = load_profile(name)
    assert p.structural.allowed_difficulties


def test_religious_frames_are_marked_draft() -> None:
    for name in ("prophets-stories", "swab-quest"):
        frame = load_profile(name).frame
        assert frame is not None and not frame.confirmed
        assert load_profile(name).conventions["quran_numbering"] == "bismillah_is_verse_1"


def test_unknown_profile() -> None:
    with pytest.raises(FileNotFoundError, match="available"):
        load_profile("nope")


# --- measuring phase 3 on the eval set ---------------------------------------------------

def test_eval_import_plan_splits_seeded_by_edition_and_adds_controls() -> None:
    from qv.domain.question import Question
    from qv.evaluation import (
        EVAL_DIR, KNOWN_ERRORS_DATASET, SEEDED_DATASET, eval_import_plan, load_questions, load_seeded_labels)
    labels = {lab.eval_id: lab for lab in load_seeded_labels()}
    seeded = load_questions(EVAL_DIR / "seeded.csv")
    plan = eval_import_plan()
    assert plan[0]["dataset"] == KNOWN_ERRORS_DATASET and plan[0]["profile"] == "football-quest"
    split = [p for p in plan if p["dataset"].startswith(SEEDED_DATASET + "-")]
    assert sorted(i for p in split for i in p["ids"]) == sorted(labels)  # every seeded question once
    for p in split:
        parsed = parse_csv(p["data"])
        qs = [Question.from_row(r, parsed.header) for r in parsed.rows]
        assert [q.ext_id for q in qs] == p["ids"]
        assert all(labels[q.ext_id].source_dataset == p["profile"] for q in qs)  # judged with its own edition
        assert all(q.question == seeded[q.ext_id].question and q.answer == seeded[q.ext_id].answer for q in qs)
    controls = {p["dataset"]: p["ids"] for p in plan if p["dataset"] in EDITIONS}
    assert {(e, i) for e, ids in controls.items() for i in ids} == \
        {(lab.source_dataset, lab.source_id) for lab in labels.values()}


def test_expectations_include_controls_and_seeded_subsets() -> None:
    from qv.evaluation import CONTROL, expectations_for, load_seeded_labels
    lab = load_seeded_labels()[0]
    assert expectations_for(f"eval-seeded-{lab.source_dataset}")[lab.eval_id][1] == "seeded"
    exp = expectations_for(lab.source_dataset)
    assert exp[lab.source_id] == (CONTROL, "control") or exp[lab.source_id][1] in ("hypothesis", "confirmed")


def test_score_many_combines_runs() -> None:
    from qv.evaluation import CONTROL, Expectation, score_many
    seeded = {"1": (Expectation(verdict="INCORRECT"), "seeded")}
    control = {"107": (CONTROL, "control")}
    res = score_many([([{"id": "1", "verdict": "INCORRECT", "review": "needs_review"}], seeded),
                      ([{"id": "107", "verdict": "UNVERIFIED", "review": "needs_evidence"},
                        {"id": "1", "verdict": "VERIFIED", "review": "auto_ok"}], control)])  # id 1 unlabelled here
    assert (res["labelled"], res["errors"], res["error_recall_pct"]) == (2, 1, 100.0)
    assert (res["good"], res["false_incorrect_pct"], res["verdict_agreement_pct"]) == (1, 0.0, 100.0)
