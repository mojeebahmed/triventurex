"""SQLAlchemy ORM models (ARCHITECTURE.md §4).

Phase 1 tables: datasets, dataset versions, questions and structural issues.
Imported data is append-only: questions and the original file bytes cannot be
updated (enforced by SQLite triggers created in the migration, see
`IMMUTABLE_TRIGGERS`). Corrections live elsewhere (human decisions, later phase)
and are applied only when exporting.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Timezone-aware current time (UTC)."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for all tables."""


class Dataset(Base):
    """A named collection of questions (e.g. one edition) with immutable versions."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    profile: Mapped[str] = mapped_column(String(100), default="general")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    versions: Mapped[list[DatasetVersion]] = relationship(
        back_populates="dataset", order_by="DatasetVersion.version_no"
    )


class DatasetVersion(Base):
    """One imported file. The original bytes are stored and never changed."""

    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    parent_version_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_versions.id"), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(500))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    original_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    file_format_json: Mapped[dict] = mapped_column(JSON)
    header_json: Mapped[list] = mapped_column(JSON)
    profile: Mapped[str] = mapped_column(String(100))
    row_count: Mapped[int] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    info_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset: Mapped[Dataset] = relationship(back_populates="versions")
    questions: Mapped[list[QuestionRow]] = relationship(
        back_populates="version", order_by="QuestionRow.row_no"
    )
    issues: Mapped[list[StructuralIssueRow]] = relationship(back_populates="version")


class QuestionRow(Base):
    """One CSV data row of a dataset version, exactly as imported."""

    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "row_no"),
        Index("ix_questions_version_ext_id", "dataset_version_id", "ext_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"))
    row_no: Mapped[int] = mapped_column(Integer)
    line_no: Mapped[int] = mapped_column(Integer)
    ext_id: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(20))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    opt_a: Mapped[str] = mapped_column(Text)
    opt_b: Mapped[str] = mapped_column(Text)
    opt_c: Mapped[str] = mapped_column(Text)
    opt_d: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(Text)
    subcategory: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)
    raw_json: Mapped[dict] = mapped_column(JSON)
    raw_line: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    resolved_answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_errors: Mapped[bool] = mapped_column(Boolean, default=False)

    version: Mapped[DatasetVersion] = relationship(back_populates="questions")


class StructuralIssueRow(Base):
    """A structural finding for a dataset version (file-level when question_id is NULL)."""

    __tablename__ = "structural_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ext_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    column: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_ext_ids_json: Mapped[list] = mapped_column(JSON, default=list)

    version: Mapped[DatasetVersion] = relationship(back_populates="issues")


#: SQLite triggers that make imported data append-only. Created by the migration.
IMMUTABLE_TRIGGERS: dict[str, str] = {
    "questions_no_update": """
        CREATE TRIGGER questions_no_update BEFORE UPDATE ON questions
        BEGIN SELECT RAISE(ABORT, 'imported questions are immutable'); END
    """,
    "dataset_versions_no_file_update": """
        CREATE TRIGGER dataset_versions_no_file_update
        BEFORE UPDATE OF original_bytes, file_sha256, header_json, file_format_json, row_count
        ON dataset_versions
        BEGIN SELECT RAISE(ABORT, 'imported files are immutable'); END
    """,
}
