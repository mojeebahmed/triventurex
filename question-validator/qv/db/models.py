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


# ---------------------------------------------------------------------------
# Phase 2 — research runs, provider usage, documents and evidence
# ---------------------------------------------------------------------------

class Run(Base):
    """One processing run over (part of) a dataset version, with its full configuration."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # research | validate (later)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|stopped|done|failed
    stop_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RunQuestion(Base):
    """Progress of one question in a run; lets an interrupted run resume where it stopped."""

    __tablename__ = "run_questions"
    __table_args__ = (UniqueConstraint("run_id", "question_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|done|failed|stopped
    step: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StageOutput(Base):
    """A validated (or failed) model output. Reused whenever the same input hash comes up again."""

    __tablename__ = "stage_outputs"
    __table_args__ = (Index("ix_stage_outputs_lookup", "stage", "input_hash", "valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    stage: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(40))
    schema_version: Mapped[str] = mapped_column(String(20))
    input_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checks_json: Mapped[list] = mapped_column(JSON, default=list)
    valid: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiCall(Base):
    """Every external call (model, search, fetch) with usage and cost."""

    __tablename__ = "api_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"), nullable=True, index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80), default="")
    kind: Mapped[str] = mapped_column(String(10))  # llm | search | fetch
    stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # ok | error | quota | refused | blocked
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    thinking_tokens: Mapped[int] = mapped_column(Integer, default=0)
    credits: Mapped[float] = mapped_column(default=0.0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    response_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class QuotaUsage(Base):
    """Free-tier usage per provider/model and period (day or month)."""

    __tablename__ = "quota_usage"
    __table_args__ = (UniqueConstraint("provider", "model", "period", "period_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80), default="")
    period: Mapped[str] = mapped_column(String(10))  # day | month
    period_key: Mapped[str] = mapped_column(String(20))  # 2026-11-15 | 2026-11
    used: Mapped[float] = mapped_column(default=0.0)
    exhausted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SearchQuery(Base):
    """Cached search results (snippets only choose what to fetch; they are never evidence)."""

    __tablename__ = "search_queries"
    __table_args__ = (UniqueConstraint("provider", "query_norm", "params_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    query: Mapped[str] = mapped_column(Text)
    query_norm: Mapped[str] = mapped_column(Text)
    params_hash: Mapped[str] = mapped_column(String(64))
    results_json: Mapped[list] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Document(Base):
    """Stored text of a fetched page or direct source. Text is never modified after storing."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("final_url", "content_sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    source_kind: Mapped[str] = mapped_column(String(20))  # web | wikipedia | quran
    ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    content_sha256: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    extract_method: Mapped[str] = mapped_column(String(40))
    char_len: Mapped[int] = mapped_column(Integer)


class Fetch(Base):
    """Fetch log per requested URL (also caches failures so they are not retried every time)."""

    __tablename__ = "fetches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(String(30))  # ok|error|robots_disallowed|too_large|not_text|empty
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QuestionDocument(Base):
    """A document retrieved for a question in a run, with how it was found and how it was rated."""

    __tablename__ = "question_documents"
    __table_args__ = (UniqueConstraint("run_id", "question_id", "document_id", "mode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    mode: Mapped[str] = mapped_column(String(1))  # A (blind) | B (note claims)
    found_by_json: Mapped[list] = mapped_column(JSON, default=list)  # [{via, query/ref, purpose}]
    registry_tier: Mapped[str] = mapped_column(String(1))
    effective_tier: Mapped[str | None] = mapped_column(String(1), nullable=True)
    frame_authority: Mapped[bool] = mapped_column(Boolean, default=False)
    page_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    about_right_subject: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    publisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    concerns_json: Mapped[list] = mapped_column(JSON, default=list)
    stage_output_id: Mapped[int | None] = mapped_column(ForeignKey("stage_outputs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|extracted|failed|excluded
    grounded_count: Mapped[int] = mapped_column(Integer, default=0)
    dropped_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Passage(Base):
    """A grounded verbatim passage. Only passages found in the stored document text are saved."""

    __tablename__ = "passages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    question_document_id: Mapped[int] = mapped_column(ForeignKey("question_documents.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    stage_output_id: Mapped[int] = mapped_column(ForeignKey("stage_outputs.id"))
    mode: Mapped[str] = mapped_column(String(1))
    target: Mapped[str] = mapped_column(String(20))
    quote: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    asserted_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    matches_option: Mapped[str | None] = mapped_column(String(4), nullable=True)
    stance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    qualifiers: Mapped[str | None] = mapped_column(Text, nullable=True)
    as_of: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributed_origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary_for_claim: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# Phase 3 — judgement
# ---------------------------------------------------------------------------

class Validation(Base):
    """The S8 result for one question in one run (METHODOLOGY.md §9), with the stage outputs it used."""

    __tablename__ = "validations"
    __table_args__ = (UniqueConstraint("run_id", "question_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    verdict: Mapped[str] = mapped_column(String(20))  # VERIFIED|INCORRECT|OUTDATED|CONTESTED|AMBIGUOUS|UNVERIFIED
    defect_location: Mapped[str | None] = mapped_column(String(30), nullable=True)
    evidence_strength: Mapped[str] = mapped_column(String(10))  # STRONG|MODERATE|WEAK|NONE
    factual_accuracy: Mapped[str | None] = mapped_column(String(20), nullable=True)
    claim_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    frame_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    claim_statuses_json: Mapped[dict] = mapped_column(JSON, default=dict)
    note_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note_statuses_json: Mapped[dict] = mapped_column(JSON, default=dict)
    blind_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    blind_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    blind_matches_key: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    within_frame: Mapped[bool] = mapped_column(Boolean, default=False)
    contested_outside_frame: Mapped[bool] = mapped_column(Boolean, default=False)
    question_quality: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quality_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_status: Mapped[str] = mapped_column(String(30))
    routes_json: Mapped[list] = mapped_column(JSON, default=list)
    reasons_json: Mapped[list] = mapped_column(JSON, default=list)
    support_json: Mapped[dict] = mapped_column(JSON, default=dict)
    suggested_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptable_alternatives_json: Mapped[list] = mapped_column(JSON, default=list)
    passage_map_json: Mapped[dict] = mapped_column(JSON, default=dict)  # "P1" → passages.id, cluster
    s4_output_id: Mapped[int | None] = mapped_column(ForeignKey("stage_outputs.id"), nullable=True)
    s5_output_id: Mapped[int | None] = mapped_column(ForeignKey("stage_outputs.id"), nullable=True)
    s6_output_id: Mapped[int | None] = mapped_column(ForeignKey("stage_outputs.id"), nullable=True)
    rules_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


#: Phase 2 triggers: stored document text and passages are append-only.
EVIDENCE_TRIGGERS: dict[str, str] = {
    "documents_no_text_update": """
        CREATE TRIGGER documents_no_text_update BEFORE UPDATE OF text, content_sha256, final_url ON documents
        BEGIN SELECT RAISE(ABORT, 'stored documents are immutable'); END
    """,
    "passages_no_update": """
        CREATE TRIGGER passages_no_update BEFORE UPDATE ON passages
        BEGIN SELECT RAISE(ABORT, 'passages are immutable'); END
    """,
}
