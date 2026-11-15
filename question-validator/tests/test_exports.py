"""Exports: original (byte-identical), structural report, corrected CSV."""

from __future__ import annotations

import csv
import io

import pytest
from sqlalchemy import text

from qv.db.session import Database
from qv.io.csv_format import parse_csv
from qv.services.datasets import get_version, import_dataset
from qv.services.exports import ExportError, corrected_csv, export_original, structural_report_csv
from tests.conftest import EDITIONS, FIXTURES, GOOD_ROWS, edition_bytes, make_csv


def _import(db: Database, data: bytes, name: str = "geo"):
    with db.session() as s:
        import_dataset(s, data, dataset_name=name, source_filename=f"{name}.csv")
        return get_version(s, name)


@pytest.mark.parametrize("edition", EDITIONS)
def test_round_trip_is_byte_identical(db: Database, edition: str) -> None:
    """Phase 1 exit criterion: import → export → identical bytes."""
    data = edition_bytes(edition)
    v = _import(db, data, edition)
    assert export_original(v) == data
    assert corrected_csv(v, {}).data == data


def test_round_trip_tricky_file(db: Database) -> None:
    data = (FIXTURES / "tricky.csv").read_bytes()
    assert export_original(_import(db, data)) == data


def test_original_export_detects_tampering(db: Database, good_csv: bytes) -> None:
    v = _import(db, good_csv)
    v.original_bytes = good_csv + b"x"  # in memory only (the database refuses this)
    with pytest.raises(ExportError, match="checksum"):
        export_original(v)


def test_structural_report_csv(db: Database) -> None:
    v = _import(db, make_csv(GOOD_ROWS[0], "1,Dup id?,open,A,,,,,medium,c,,,"))
    with db.session() as s:
        rows = list(csv.DictReader(io.StringIO(structural_report_csv(s, v).decode())))
    assert {(r["code"], r["line"], r["id"]) for r in rows} >= {("duplicate_id", "3", "1"),
                                                                ("invalid_difficulty", "3", "1")}


def test_corrected_csv_changes_only_approved_fields(db: Database, good_csv: bytes) -> None:
    v = _import(db, good_csv)
    result = corrected_csv(v, {"2": {"answer": "The Nile, Egypt"}, "3": {}})
    assert result.changed_ids == ("2",)
    rows = parse_csv(result.data).rows
    assert rows[1].get("answer") == "The Nile, Egypt"
    assert [r.raw_line for i, r in enumerate(rows) if i != 1] == \
        [r.raw_line for i, r in enumerate(parse_csv(good_csv).rows) if i != 1]
    assert result.report.ok_for_game
    # The stored original is untouched
    with db.session() as s:
        assert s.execute(text("SELECT answer FROM questions WHERE ext_id='2'")).scalar() == "The Nile"


def test_corrected_csv_refusals(db: Database, good_csv: bytes) -> None:
    v = _import(db, good_csv)
    with pytest.raises(ExportError, match="not in version"):
        corrected_csv(v, {"99": {"answer": "x"}})
    with pytest.raises(ExportError, match="ids are permanent"):
        corrected_csv(v, {"1": {"id": "5"}})
    with pytest.raises(ExportError, match="introduce structural errors"):
        corrected_csv(v, {"1": {"answer": "7"}})


def test_corrected_csv_refuses_duplicate_ids(db: Database) -> None:
    v = _import(db, make_csv(GOOD_ROWS[0], GOOD_ROWS[0]))
    with pytest.raises(ExportError, match="occurs 2 times"):
        corrected_csv(v, {"1": {"note": "x"}})


def test_corrected_csv_allows_fixing_an_existing_error(db: Database) -> None:
    v = _import(db, make_csv("1,Q?,multi,7,A,B,,,easy,c,,,"))
    result = corrected_csv(v, {"1": {"answer": "2"}})
    assert result.report.ok_for_game
