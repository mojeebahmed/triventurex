"""Knowledge base phase 2: saved searches (topics) and relevance judgements

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-17 03:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

# Frozen copy of qv.db.models.RELEVANCE_LABEL_TRIGGERS at this revision.
RELEVANCE_LABEL_TRIGGERS = {
    "relevance_labels_no_update": """
        CREATE TRIGGER relevance_labels_no_update BEFORE UPDATE ON relevance_labels
        BEGIN SELECT RAISE(ABORT, 'relevance labels are append-only'); END
    """,
    "relevance_labels_no_delete": """
        CREATE TRIGGER relevance_labels_no_delete BEFORE DELETE ON relevance_labels
        BEGIN SELECT RAISE(ABORT, 'relevance labels are append-only'); END
    """,
}


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        'topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('filters_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'relevance_labels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('ext_id', sa.String(length=50), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('doc_key', sa.String(length=300), nullable=False),
        sa.Column('label', sa.String(length=20), nullable=False),
        sa.Column('who', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('relevance_labels', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_relevance_labels_dataset_id'), ['dataset_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_relevance_labels_doc_key'), ['doc_key'], unique=False)
    for sql in RELEVANCE_LABEL_TRIGGERS.values():
        op.execute(sql)


def downgrade() -> None:
    """Revert this revision."""
    for name in RELEVANCE_LABEL_TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    with op.batch_alter_table('relevance_labels', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_relevance_labels_doc_key'))
        batch_op.drop_index(batch_op.f('ix_relevance_labels_dataset_id'))
    op.drop_table('relevance_labels')
    op.drop_table('topics')
