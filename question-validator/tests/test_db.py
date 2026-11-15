"""Database: migrations match the models, SQLite settings, immutability triggers."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from qv.db.models import Base
from qv.db.session import Database, alembic_config, make_engine, upgrade_database
from qv.services.datasets import import_dataset


def test_migrations_match_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    upgrade_database(url)
    engine = make_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_downgrade_and_upgrade_again(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    upgrade_database(url)
    command.downgrade(alembic_config(url), "base")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
    upgrade_database(url)


def test_sqlite_pragmas(db: Database) -> None:
    with db.engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_questions_cannot_be_updated(db: Database, good_csv: bytes) -> None:
    with db.session() as s:
        import_dataset(s, good_csv, dataset_name="d", source_filename="d.csv")
    with pytest.raises((IntegrityError, OperationalError), match="immutable"):
        with db.session() as s:
            s.execute(text("UPDATE questions SET answer = 'changed' WHERE ext_id = '1'"))
    with db.session() as s:
        assert s.execute(text("SELECT answer FROM questions WHERE ext_id='1'")).scalar() == "1"


def test_original_file_cannot_be_updated(db: Database, good_csv: bytes) -> None:
    with db.session() as s:
        import_dataset(s, good_csv, dataset_name="d", source_filename="d.csv")
    with pytest.raises((IntegrityError, OperationalError), match="immutable"):
        with db.session() as s:
            s.execute(text("UPDATE dataset_versions SET original_bytes = x'00'"))


def test_foreign_keys_enforced(db: Database) -> None:
    with pytest.raises(IntegrityError):
        with db.session() as s:
            s.execute(text(
                "INSERT INTO structural_issues (dataset_version_id, code, severity, message, related_ext_ids_json)"
                " VALUES (999, 'x', 'info', 'm', '[]')"))
