"""KB phase 5 — same fact, different result: candidate pairs, answer normalisation, decisions history."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from qv.db.session import Database
from qv.services import fact_pairs as fp
from qv.services.datasets import import_dataset
from tests.conftest import make_csv

SWAB = make_csv(
    "127,Who was the mother of Hadhrat Isa (Jesus)?,multi,3,Hadhrat Khadija,Hadhrat Asiya,Hadhrat Maryam,,easy,"
    "Prophets,Isa,Family,",
    "285,Who was the mother of Hadhrat Isa (Jesus)(as)?,multi,1,Hadhrat Maryam,Hadhrat Khadija,Hadhrat Asiya,,easy,"
    "Prophets,Isa,Family,",
    "8,How old was the Holy Prophet Muhammad(sa) when his mother died?,open,6 years old,,,,,hard,Seerah,Life,Youth,",
    "40,How old was the Holy Prophet Muhammad(sa) when he died?,open,63 years old,,,,,hard,Seerah,Life,End,",
    "202,When did the Promised Messiah(as) pass away?,open,26 May 1908,,,,,hard,History,PM,Death,",
    "203,In which city did the Promised Messiah(as) pass away?,open,Lahore,,,,,hard,History,PM,Death,",
    "379,What is Tehrik-e-Jadid?,open,A financial scheme launched by Khalifa II in 1934 to spread Ahmadiyyat "
    "globally,,,,,hard,History,Schemes,TJ,",
    "380,When was Tehrik-e-Jadid launched?,open,1934,,,,,hard,History,Schemes,TJ,",
    "90,What is the capital of France?,open,Paris,,,,,easy,Geo,Capitals,Europe,",
    "91,What is the capital of Spain?,open,Madrid,,,,,easy,Geo,Capitals,Europe,",
)
PROPHETS = make_csv(
    "133,Who was the mother of Hadhrat Isa (as) (Jesus)?,open,Hadhrat Maryam,,,,,easy,Isa,Family,Mother,",
    "192,In which year did the Promised Messiah (as) pass away?,open,1908,,,,,hard,PM,Life,Death,",
    "9,Which prophet built a great Ark?,open,Hadhrat Nuh (as) (Noah),,,,,easy,Nuh,Ark,Ark,",
    "10,What was the capital of France in 1900?,open,Lyon,,,,,easy,Geo,Capitals,Europe,",
)


@pytest.fixture
def two_files(db: Database) -> Database:
    with db.session() as s:
        import_dataset(s, SWAB, dataset_name="swab-quest", source_filename="s.csv", profile_name="swab-quest")
        import_dataset(s, PROPHETS, dataset_name="prophets-stories", source_filename="p.csv",
                       profile_name="prophets-stories")
    return db


def labels(pairs: list[fp.FactPair]) -> set[frozenset[str]]:
    return {frozenset((p.a.ref.label, p.b.ref.label)) for p in pairs}


def pair_of(a: str, b: str) -> frozenset[str]:
    return frozenset((a, b))


def test_known_pair_and_its_copy_in_another_edition_are_found(two_files: Database) -> None:
    found = labels(fp.find_pairs(two_files))
    assert pair_of("swab-quest #127", "swab-quest #285") in found
    assert pair_of("prophets-stories #133", "swab-quest #127") in found
    assert pair_of("prophets-stories #192", "swab-quest #202") in found  # 1908 inside "26 May 1908"


def test_other_facts_about_the_same_subject_are_not_pairs(two_files: Database) -> None:
    found = labels(fp.find_pairs(two_files))
    assert pair_of("swab-quest #8", "swab-quest #40") not in found      # his mother died / he died
    assert pair_of("swab-quest #202", "swab-quest #203") not in found   # when / where
    assert pair_of("swab-quest #379", "swab-quest #380") not in found   # a year inside a long description
    assert pair_of("swab-quest #90", "swab-quest #91") not in found     # template: capital of X


def test_one_extra_word_makes_another_question(two_files: Database) -> None:
    """'capital of France' vs 'capital of France in 1900': different answers and one more word → not a pair."""
    assert pair_of("swab-quest #90", "prophets-stories #10") not in labels(fp.find_pairs(two_files))


def test_same_question_other_answer(db: Database) -> None:
    a = make_csv("1,How many goals did Haaland score in 2022-23?,open,36,,,,,hard,Records,PL,Goals,")
    b = make_csv("7,How many goals did Haaland score in 2022–23?,open,34,,,,,hard,Records,PL,Goals,")
    with db.session() as s:
        import_dataset(s, a, dataset_name="football-quest", source_filename="a.csv", profile_name="football-quest")
        import_dataset(s, b, dataset_name="world-tour", source_filename="b.csv", profile_name="world-tour")
    [p] = fp.find_pairs(db)
    assert not p.same_answer and p.kind == "other answer" and p.differs
    assert "36" in p.differences[0] and "34" in p.differences[0]
    assert fp.in_group(p, "differ")


@pytest.mark.parametrize("a,b,same", [
    ("Hadhrat Maryam", "Maryam", True), ("Mecca (Makkah)", "Makkah", True), ("Hadhrat Amina", "Hadhrat Aminah", True),
    ("Hadhrat Nuh (as) (Noah)", "Hadhrat Nuh", True), ("About 25", "25", True), ("1908", "26 May 1908", True),
    ("6 years old", "63 years old", False), ("Lahore", "26 May 1908", False),
    ("1934", "A financial scheme launched by Khalifa II in 1934 to spread Ahmadiyyat globally", False),
    ('"O fire, be cool and safe for Ibrahim"', "Hadhrat Ibrahim", False), ("", "x", False)])
def test_answers_match(a: str, b: str, same: bool) -> None:
    assert fp.answers_match(a, b) is same


def test_accepted_equivalents_from_research_count() -> None:
    assert not fp.answers_match("Eve", "Hawwa")
    assert fp.answers_match("Eve", "Hawwa", ({"hawwa", "eve"}, set()))


def test_tokens_drop_honorifics_and_keep_question_words() -> None:
    assert fp.tokens("When did Hadhrat Isa (as) pass away?") == ["when", "isa", "pass", "away"]
    assert fp.tokens("Which prophets built the Ark?") == ["prophet", "built", "ark"]


def test_decisions_are_append_only_newest_wins_and_follow_the_wording(two_files: Database) -> None:
    p = next(p for p in fp.find_pairs(two_files) if {p.a.ref.ext_id, p.b.ref.ext_id} == {"127", "285"})
    fp.record_decision(two_files, p.a.ref, p.b.ref, "different_fact", reason="first look")
    fp.record_decision(two_files, p.b.ref, p.a.ref, "same_fact", reason="same question twice")  # order-free
    again = next(q for q in fp.find_pairs(two_files) if q.key == p.key)
    assert again.decision == "same_fact" and again.decision_reason == "same question twice"
    assert fp.in_group(again, "same_fact") and not fp.in_group(again, "undecided")
    assert [h["action"] for h in fp.decision_history(two_files, p.a.ref, p.b.ref)] == ["different_fact",
                                                                                       "same_fact"]
    fp.record_decision(two_files, p.a.ref, p.b.ref, "clear")
    assert next(q for q in fp.find_pairs(two_files) if q.key == p.key).decision == ""
    with pytest.raises(ValueError):
        fp.record_decision(two_files, p.a.ref, p.b.ref, "merge")
    with two_files.session() as s, pytest.raises(DatabaseError):
        s.execute(text("UPDATE fact_pair_decisions SET action = 'ignore'"))
    with two_files.session() as s, pytest.raises(DatabaseError):
        s.execute(text("DELETE FROM fact_pair_decisions"))
    # a decision belongs to the exact wording: another hash is another pair
    other = fp.QRef(p.a.ref.dataset, p.a.ref.dataset_id, p.a.ref.ext_id, "0" * 64)
    assert fp.pair_key(other, p.b.ref) != p.key


def test_differences_name_results_and_kinds() -> None:
    a = fp.QInfo(fp.QRef("x", 1, "1", "h"), "q", "Maryam", "verified", "VERIFIED", "biography")
    b = fp.QInfo(fp.QRef("y", 2, "2", "h"), "q", "Maryam", "to_review", "UNVERIFIED", "scripture_content")
    assert fp.differences(a, b, True) == ["results: VERIFIED vs UNVERIFIED",
                                          "kind of fact: biography vs scripture content"]


def test_cli_pairs(two_files: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner
    from qv.cli import app
    monkeypatch.setattr("qv.cli._db", lambda: two_files)
    out = CliRunner().invoke(app, ["pairs", "--group", "all"]).output
    assert "swab-quest #127" in out and "All pairs:" in out
