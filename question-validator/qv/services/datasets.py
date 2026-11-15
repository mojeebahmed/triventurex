"""Dataset service: check, import (versioned, immutable) and diff question files.

Services hold the application logic; the CLI and (later) the UI only call these.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from qv.config import Profile, available_profiles, load_profile
from qv.db.models import Dataset, DatasetVersion, QuestionRow, StructuralIssueRow
from qv.domain.dataset import ChangedQuestion, DatasetDiff, ImportResult
from qv.domain.question import STANDARD_COLUMNS, ParsedCsv, Question
from qv.domain.structural import Severity, StructuralReport
from qv.io.csv_format import parse_csv
from qv.pipeline.structural import run_structural_checks

#: Columns compared when diffing versions.
DIFF_COLUMNS: tuple[str, ...] = tuple(c for c in STANDARD_COLUMNS if c != "id")


class DatasetError(ValueError):
    """A dataset operation was refused (unknown name/version, bad input)."""


@dataclass(frozen=True)
class CheckResult:
    """Result of checking a file without storing it."""

    parsed: ParsedCsv
    questions: list[Question]
    report: StructuralReport


def check_bytes(data: bytes, profile: Profile) -> CheckResult:
    """Parse and structurally check a file in memory (no database)."""
    parsed = parse_csv(data)
    questions = [Question.from_row(r, parsed.header) for r in parsed.rows]
    return CheckResult(parsed, questions, run_structural_checks(parsed, profile.structural))


def import_dataset(session: Session, data: bytes, *, dataset_name: str, source_filename: str,
                   profile_name: str | None = None) -> ImportResult:
    """Store a file as a new immutable version of `dataset_name`.

    The dataset is created on first import. Importing bytes identical to the
    latest version creates nothing and returns that version (`created=False`).
    Files with structural errors are still imported — every row is kept so it
    can be reported — but `report.ok_for_game` is False.
    """
    dataset = session.scalar(select(Dataset).where(Dataset.name == dataset_name))
    if dataset is None:
        dataset = Dataset(name=dataset_name, profile=profile_name or _guess_profile(dataset_name))
        session.add(dataset)
        session.flush()
    elif profile_name and profile_name != dataset.profile:
        raise DatasetError(
            f"Dataset '{dataset_name}' uses profile '{dataset.profile}', not '{profile_name}'"
        )
    profile = load_profile(dataset.profile)
    checked = check_bytes(data, profile)
    latest = latest_version(session, dataset_name)

    if latest is not None and latest.file_sha256 == checked.parsed.sha256:
        return ImportResult(
            dataset_name=dataset_name, dataset_id=dataset.id, version_id=latest.id,
            version_no=latest.version_no, created=False, file_sha256=latest.file_sha256,
            report=checked.report, diff=DatasetDiff(unchanged_count=latest.row_count),
        )

    counts = Counter(i.severity for i in checked.report.issues)
    version = DatasetVersion(
        dataset_id=dataset.id,
        version_no=(latest.version_no + 1) if latest else 1,
        parent_version_id=latest.id if latest else None,
        source_filename=source_filename,
        file_sha256=checked.parsed.sha256,
        original_bytes=checked.parsed.original_bytes,
        file_format_json=checked.parsed.format.model_dump(mode="json"),
        header_json=list(checked.parsed.header),
        profile=dataset.profile,
        row_count=len(checked.questions),
        error_count=counts[Severity.ERROR],
        warning_count=counts[Severity.WARNING],
        info_count=counts[Severity.INFO],
    )
    session.add(version)
    session.flush()

    error_rows = {i.row_no for i in checked.report.issues if i.severity == Severity.ERROR and i.row_no}
    by_row: dict[int, QuestionRow] = {}
    for q, row in zip(checked.questions, checked.parsed.rows):
        qr = QuestionRow(
            dataset_version_id=version.id, row_no=q.row_no, line_no=q.line_no, ext_id=q.ext_id,
            type=q.type, question=q.question, answer=q.answer,
            opt_a=q.options[0], opt_b=q.options[1], opt_c=q.options[2], opt_d=q.options[3],
            difficulty=q.difficulty, category=q.category, subcategory=q.subcategory, topic=q.topic,
            note=q.note, raw_json=q.raw, raw_line=row.raw_line, content_hash=q.content_hash(),
            resolved_answer_text=q.resolved_answer_text, has_errors=q.row_no in error_rows,
        )
        session.add(qr)
        by_row[q.row_no] = qr
    session.flush()

    for issue in checked.report.issues:
        session.add(StructuralIssueRow(
            dataset_version_id=version.id,
            question_id=by_row[issue.row_no].id if issue.row_no in by_row else None,
            row_no=issue.row_no, line_no=issue.line_no, ext_id=issue.ext_id, code=issue.code.value,
            severity=issue.severity.value, message=issue.message, column=issue.column,
            related_ext_ids_json=list(issue.related_ext_ids),
        ))
    session.flush()

    diff = diff_versions(session, latest, version) if latest else None
    return ImportResult(
        dataset_name=dataset_name, dataset_id=dataset.id, version_id=version.id,
        version_no=version.version_no, created=True, file_sha256=version.file_sha256,
        report=checked.report, diff=diff,
    )


def _guess_profile(dataset_name: str) -> str:
    """Use the edition profile with the dataset's name if there is one, else 'general'."""
    return dataset_name if dataset_name in available_profiles() else "general"


def latest_version(session: Session, dataset_name: str) -> DatasetVersion | None:
    """The newest version of a dataset, or None (also when the dataset does not exist)."""
    return session.scalar(
        select(DatasetVersion).join(Dataset).where(Dataset.name == dataset_name)
        .order_by(DatasetVersion.version_no.desc()).limit(1)
    )


def get_version(session: Session, dataset_name: str, version_no: int | None = None) -> DatasetVersion:
    """A specific version (latest when `version_no` is None); raises DatasetError if missing."""
    if version_no is None:
        version = latest_version(session, dataset_name)
    else:
        version = session.scalar(
            select(DatasetVersion).join(Dataset)
            .where(Dataset.name == dataset_name, DatasetVersion.version_no == version_no)
        )
    if version is None:
        suffix = f" version {version_no}" if version_no is not None else ""
        raise DatasetError(f"No dataset '{dataset_name}'{suffix}")
    return version


def list_datasets(session: Session) -> list[Dataset]:
    """All datasets, by name."""
    return list(session.scalars(select(Dataset).order_by(Dataset.name)))


def version_questions(session: Session, version: DatasetVersion) -> list[QuestionRow]:
    """Questions of a version in file order."""
    return list(session.scalars(
        select(QuestionRow).where(QuestionRow.dataset_version_id == version.id).order_by(QuestionRow.row_no)
    ))


def version_issues(session: Session, version: DatasetVersion) -> list[StructuralIssueRow]:
    """Structural issues of a version in file order (file-level first)."""
    return list(session.scalars(
        select(StructuralIssueRow).where(StructuralIssueRow.dataset_version_id == version.id)
        .order_by(StructuralIssueRow.line_no.is_not(None), StructuralIssueRow.line_no, StructuralIssueRow.id)
    ))


def diff_versions(session: Session, old: DatasetVersion, new: DatasetVersion) -> DatasetDiff:
    """Compare two versions by CSV id: added, removed, changed (with the changed columns)."""
    old_rows = version_questions(session, old)
    new_rows = version_questions(session, new)
    dupes = sorted(
        {i for rows in (old_rows, new_rows) for i, n in Counter(r.ext_id for r in rows).items() if n > 1},
        key=_id_sort_key,
    )
    old_by = _first_by_id(old_rows)
    new_by = _first_by_id(new_rows)
    added = sorted(set(new_by) - set(old_by), key=_id_sort_key)
    removed = sorted(set(old_by) - set(new_by), key=_id_sort_key)
    changed: list[ChangedQuestion] = []
    unchanged = 0
    for ext_id in sorted(set(old_by) & set(new_by), key=_id_sort_key):
        a, b = old_by[ext_id], new_by[ext_id]
        if a.content_hash == b.content_hash:
            unchanged += 1
            continue
        fields = tuple(c for c in DIFF_COLUMNS if getattr(a, c) != getattr(b, c))
        changed.append(ChangedQuestion(ext_id=ext_id, fields=fields))
    return DatasetDiff(added=tuple(added), removed=tuple(removed), changed=tuple(changed),
                       unchanged_count=unchanged, duplicate_ids=tuple(dupes))


def _first_by_id(rows: list[QuestionRow]) -> dict[str, QuestionRow]:
    """Map ext_id → first row with that id."""
    out: dict[str, QuestionRow] = {}
    for r in rows:
        out.setdefault(r.ext_id, r)
    return out


def _id_sort_key(ext_id: str) -> tuple[int, int, str]:
    """Numeric ids in numeric order, anything else after them."""
    return (0, int(ext_id), "") if ext_id.isdigit() else (1, 0, ext_id)
