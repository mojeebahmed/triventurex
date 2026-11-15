"""Dataset service: import, versions, diff, check."""

from __future__ import annotations

import pytest

from qv.config import load_profile
from qv.db.session import Database
from qv.domain.structural import Severity
from qv.services.datasets import (
    DatasetError, check_bytes, diff_versions, get_version, import_dataset, list_datasets, version_issues,
    version_questions,
)
from tests.conftest import EDITIONS, GOOD_ROWS, edition_bytes, make_csv


def test_check_bytes_stores_nothing(good_csv: bytes) -> None:
    result = check_bytes(good_csv, load_profile())
    assert result.report.ok_for_game and len(result.questions) == 3


def test_first_import_creates_version_1(db: Database, good_csv: bytes) -> None:
    with db.session() as s:
        res = import_dataset(s, good_csv, dataset_name="geo", source_filename="geo.csv")
        assert res.created and res.version_no == 1 and res.diff is None
        v = get_version(s, "geo")
        qs = version_questions(s, v)
        assert [q.ext_id for q in qs] == ["1", "2", "3"]
        assert qs[0].resolved_answer_text == "Paris"
        assert qs[1].raw_json["question"] == "Which river flows through Cairo, Egypt?"
        assert v.original_bytes == good_csv
        assert v.profile == "general"


def test_reimport_identical_is_a_no_op(db: Database, good_csv: bytes) -> None:
    with db.session() as s:
        import_dataset(s, good_csv, dataset_name="geo", source_filename="geo.csv")
    with db.session() as s:
        res = import_dataset(s, good_csv, dataset_name="geo", source_filename="again.csv")
        assert not res.created and res.version_no == 1
        assert len(list_datasets(s)[0].versions) == 1


def test_new_version_and_diff(db: Database, good_csv: bytes) -> None:
    edited = make_csv(
        GOOD_ROWS[0].replace("Paris,Lyon", "Paris,Marseille"),
        GOOD_ROWS[2],
        "4,New question?,open,Yes,,,,,easy,Geo,,,",
    )
    with db.session() as s:
        import_dataset(s, good_csv, dataset_name="geo", source_filename="a.csv")
        res = import_dataset(s, edited, dataset_name="geo", source_filename="b.csv")
        assert res.created and res.version_no == 2
        d = res.diff
        assert d.added == ("4",) and d.removed == ("2",)
        assert [(c.ext_id, c.fields) for c in d.changed] == [("1", ("opt_b",))]
        assert d.unchanged_count == 1
        v2 = get_version(s, "geo", 2)
        assert v2.parent_version_id == get_version(s, "geo", 1).id
        # Versions are independent: v1 still has the original rows
        assert [q.opt_b for q in version_questions(s, get_version(s, "geo", 1))][0] == "Lyon"


def test_whitespace_only_edit_is_not_a_content_change(db: Database, good_csv: bytes) -> None:
    with db.session() as s:
        import_dataset(s, good_csv, dataset_name="geo", source_filename="a.csv")
        res = import_dataset(s, good_csv.replace(b",Paris,", b", Paris ,"), dataset_name="geo",
                             source_filename="b.csv")
        assert res.created and res.diff.is_empty


def test_malformed_file_is_imported_with_its_issues(db: Database) -> None:
    data = make_csv("1,Q?,multi,7,A,B,,,easy,c,,,", "1,Dup?,open,A,,,,,easy,c,,,", '3,"Open,open,A')
    with db.session() as s:
        res = import_dataset(s, data, dataset_name="bad", source_filename="bad.csv")
        assert not res.report.ok_for_game
        v = get_version(s, "bad")
        assert v.error_count == res.report.count(Severity.ERROR) > 0
        stored = version_issues(s, v)
        assert len(stored) == len(res.report.issues)
        assert all(i.question_id is not None for i in stored if i.row_no)
        assert [q.has_errors for q in version_questions(s, v)] == [True, True, True]


def test_profile_is_guessed_from_name_and_cannot_change(db: Database, good_csv: bytes) -> None:
    with db.session() as s:
        import_dataset(s, good_csv, dataset_name="world-tour", source_filename="x.csv")
        assert get_version(s, "world-tour").profile == "world-tour"
        with pytest.raises(DatasetError, match="uses profile"):
            import_dataset(s, good_csv + b"", dataset_name="world-tour", source_filename="x.csv",
                           profile_name="general")


def test_unknown_dataset_or_version(db: Database, good_csv: bytes) -> None:
    with db.session() as s:
        with pytest.raises(DatasetError):
            get_version(s, "nope")
        import_dataset(s, good_csv, dataset_name="geo", source_filename="a.csv")
        with pytest.raises(DatasetError, match="version 5"):
            get_version(s, "geo", 5)


def test_diff_reports_duplicate_ids(db: Database, good_csv: bytes) -> None:
    with db.session() as s:
        import_dataset(s, good_csv, dataset_name="geo", source_filename="a.csv")
        import_dataset(s, make_csv(*GOOD_ROWS, GOOD_ROWS[0]), dataset_name="geo", source_filename="b.csv")
        d = diff_versions(s, get_version(s, "geo", 1), get_version(s, "geo", 2))
        assert d.duplicate_ids == ("1",) and d.is_empty


@pytest.mark.parametrize("edition", EDITIONS)
def test_every_edition_imports_cleanly(db: Database, edition: str) -> None:
    """Phase 1 exit criterion: all five edition CSVs import without errors."""
    with db.session() as s:
        res = import_dataset(s, edition_bytes(edition), dataset_name=edition, source_filename="questions.csv")
        assert res.report.ok_for_game
        assert len(version_questions(s, get_version(s, edition))) == res.report.row_count
