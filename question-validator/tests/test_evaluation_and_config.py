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
