"""Knowledge base phase 5: decisions about question pairs on the same fact

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-17 18:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

# Frozen copy of qv.db.models.FACT_PAIR_DECISION_TRIGGERS at this revision.
FACT_PAIR_DECISION_TRIGGERS = {
    "fact_pair_decisions_no_update": """
        CREATE TRIGGER fact_pair_decisions_no_update BEFORE UPDATE ON fact_pair_decisions
        BEGIN SELECT RAISE(ABORT, 'fact pair decisions are append-only'); END
    """,
    "fact_pair_decisions_no_delete": """
        CREATE TRIGGER fact_pair_decisions_no_delete BEFORE DELETE ON fact_pair_decisions
        BEGIN SELECT RAISE(ABORT, 'fact pair decisions are append-only'); END
    """,
}


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        'fact_pair_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('a_dataset_id', sa.Integer(), nullable=False),
        sa.Column('a_ext_id', sa.String(length=50), nullable=False),
        sa.Column('a_content_hash', sa.String(length=64), nullable=False),
        sa.Column('b_dataset_id', sa.Integer(), nullable=False),
        sa.Column('b_ext_id', sa.String(length=50), nullable=False),
        sa.Column('b_content_hash', sa.String(length=64), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('who', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['a_dataset_id'], ['datasets.id'], ),
        sa.ForeignKeyConstraint(['b_dataset_id'], ['datasets.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('fact_pair_decisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fact_pair_decisions_a_dataset_id'), ['a_dataset_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fact_pair_decisions_b_dataset_id'), ['b_dataset_id'], unique=False)
    for sql in FACT_PAIR_DECISION_TRIGGERS.values():
        op.execute(sql)


def downgrade() -> None:
    """Revert this revision."""
    for name in FACT_PAIR_DECISION_TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    with op.batch_alter_table('fact_pair_decisions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fact_pair_decisions_b_dataset_id'))
        batch_op.drop_index(batch_op.f('ix_fact_pair_decisions_a_dataset_id'))
    op.drop_table('fact_pair_decisions')
