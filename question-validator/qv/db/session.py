"""Engine/session creation and schema migration (Alembic, configured in code)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def make_engine(url: str) -> Engine:
    """Create an engine. SQLite gets WAL mode, foreign keys and a busy timeout."""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"timeout": 30} if url.startswith("sqlite") else {})
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
    return engine


def alembic_config(url: str) -> Config:
    """An Alembic Config pointing at the packaged migrations (no alembic.ini needed)."""
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def upgrade_database(url: str, revision: str = "head") -> None:
    """Bring the database schema up to `revision` (creates the file if needed)."""
    make_engine(url).dispose()  # ensures the parent directory exists
    command.upgrade(alembic_config(url), revision)


class Database:
    """Owns the engine and hands out short-lived sessions."""

    def __init__(self, url: str, *, migrate: bool = True) -> None:
        """Connect to `url`, migrating the schema to the latest version first if `migrate`."""
        if migrate:
            upgrade_database(url)
        self.url = url
        self.engine = make_engine(url)
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A transactional session: commits on success, rolls back on error."""
        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def dispose(self) -> None:
        """Close all pooled connections."""
        self.engine.dispose()
