"""Alembic environment: uses the URL set by qv.db.session.alembic_config."""

from __future__ import annotations

from alembic import context

from qv.db.models import Base
from qv.db.session import make_engine

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a database connection."""
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""
    engine = make_engine(config.get_main_option("sqlalchemy.url"))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
