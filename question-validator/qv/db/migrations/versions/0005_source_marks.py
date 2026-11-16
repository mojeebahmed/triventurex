"""Websites: the person's marks (use / don't use / needs access)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16 23:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

# Frozen copy of qv.db.models.SOURCE_MARK_TRIGGERS at this revision.
SOURCE_MARK_TRIGGERS = {
    "source_marks_no_update": """
        CREATE TRIGGER source_marks_no_update BEFORE UPDATE ON source_marks
        BEGIN SELECT RAISE(ABORT, 'source marks are append-only'); END
    """,
    "source_marks_no_delete": """
        CREATE TRIGGER source_marks_no_delete BEFORE DELETE ON source_marks
        BEGIN SELECT RAISE(ABORT, 'source marks are append-only'); END
    """,
}


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        'source_marks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=200), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('tier', sa.String(length=1), nullable=True),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('source_marks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_source_marks_domain'), ['domain'], unique=False)
    for sql in SOURCE_MARK_TRIGGERS.values():
        op.execute(sql)


def downgrade() -> None:
    """Revert this revision."""
    for name in SOURCE_MARK_TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    with op.batch_alter_table('source_marks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_source_marks_domain'))
    op.drop_table('source_marks')
