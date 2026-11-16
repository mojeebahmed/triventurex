"""Simple workflow: review decisions

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-16 18:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

# Frozen copy of qv.db.models.DECISION_TRIGGERS at this revision.
DECISION_TRIGGERS = {
    "decisions_no_update": """
        CREATE TRIGGER decisions_no_update BEFORE UPDATE ON decisions
        BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END
    """,
    "decisions_no_delete": """
        CREATE TRIGGER decisions_no_delete BEFORE DELETE ON decisions
        BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END
    """,
}


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        'decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('ext_id', sa.String(length=50), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('validation_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('changes_json', sa.JSON(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.ForeignKeyConstraint(['validation_id'], ['validations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('decisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_decisions_dataset_id'), ['dataset_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_decisions_ext_id'), ['ext_id'], unique=False)
    for sql in DECISION_TRIGGERS.values():
        op.execute(sql)


def downgrade() -> None:
    """Revert this revision."""
    for name in DECISION_TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    with op.batch_alter_table('decisions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_decisions_ext_id'))
        batch_op.drop_index(batch_op.f('ix_decisions_dataset_id'))
    op.drop_table('decisions')
