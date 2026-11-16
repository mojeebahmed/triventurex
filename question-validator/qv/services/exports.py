"""Exports: the original file, the structural report, and a corrected CSV.

The corrected CSV is built by patching the original bytes (qv.io.csv_format.
apply_patches): only the requested fields change, ids never change, and the
result is structurally re-checked before it is returned.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass

from sqlalchemy.orm import Session

from qv.config import load_profile
from qv.db.models import DatasetVersion
from qv.domain.structural import Severity, StructuralReport
from qv.io.csv_format import PatchError, apply_patches, parse_csv
from qv.pipeline.structural import run_structural_checks
from qv.services.datasets import version_issues

REPORT_COLUMNS: tuple[str, ...] = (
    "severity", "code", "line", "row", "id", "column", "message", "related_ids",
)


class ExportError(RuntimeError):
    """An export could not be produced safely."""


def export_original(version: DatasetVersion) -> bytes:
    """The imported file, byte for byte. Verifies the stored checksum first."""
    data = version.original_bytes
    if hashlib.sha256(data).hexdigest() != version.file_sha256:
        raise ExportError(f"Stored file for version {version.id} does not match its checksum")
    return data


def structural_report_csv(session: Session, version: DatasetVersion) -> bytes:
    """One row per structural issue, as UTF-8 CSV (opens in Excel / Numbers)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(REPORT_COLUMNS)
    for i in version_issues(session, version):
        writer.writerow([
            i.severity, i.code, i.line_no or "", i.row_no or "", i.ext_id or "", i.column or "",
            i.message, " ".join(i.related_ext_ids_json or []),
        ])
    return buf.getvalue().encode("utf-8")


@dataclass(frozen=True)
class CorrectedExport:
    """A corrected file and its structural re-check."""

    data: bytes
    report: StructuralReport
    changed_ids: tuple[str, ...]


def corrected_csv(version: DatasetVersion, changes: dict[str, dict[str, str]]) -> CorrectedExport:
    """Apply field changes, keyed by CSV id, to the original file.

    `changes` must only contain approved changes (later phases build it from
    human decisions). Refuses ids that are missing or not unique, changes to
    `id`, and any result with structural errors the original did not have.
    """
    parsed = parse_csv(export_original(version))
    lines_by_id: dict[str, list[int]] = {}
    for row in parsed.rows:
        lines_by_id.setdefault(row.get("id"), []).append(row.line_no)

    patches: dict[int, dict[str, str]] = {}
    for ext_id, fields in changes.items():
        lines = lines_by_id.get(ext_id, [])
        if not lines:
            raise ExportError(f"id {ext_id} is not in version {version.version_no}")
        if len(lines) > 1:
            raise ExportError(f"id {ext_id} occurs {len(lines)} times; fix the duplicate first")
        if fields:
            patches[lines[0]] = dict(fields)
    try:
        data = apply_patches(parsed, patches)
    except PatchError as exc:
        raise ExportError(str(exc)) from exc

    rules = load_profile(version.profile).structural
    before = run_structural_checks(parsed, rules)
    after = run_structural_checks(parse_csv(data), rules)
    old_errors = {(i.code, i.line_no) for i in before.issues if i.severity == Severity.ERROR}
    new_errors = [i for i in after.issues if i.severity == Severity.ERROR and (i.code, i.line_no) not in old_errors]
    if new_errors:
        detail = "; ".join(f"line {i.line_no}: {i.message}" for i in new_errors[:5])
        raise ExportError(f"Corrections would introduce structural errors: {detail}")
    return CorrectedExport(data=data, report=after,
                           changed_ids=tuple(i for i, f in changes.items() if f))


# --- exports built from the simple workflow's decisions ---------------------------------

def drop_rows(data: bytes, line_nos: set[int]) -> bytes:
    """Remove whole physical lines (one CSV row each in the game's format), keeping every other byte."""
    if not line_nos:
        return data
    lines = data.splitlines(keepends=True)
    return b"".join(line for i, line in enumerate(lines, start=1) if i not in line_nos)


def workflow_export(db, dataset: str, kind: str) -> tuple[bytes, str, dict]:  # noqa: ANN001
    """The simple workflow's downloads for the dataset's latest version.

    - "corrected": the whole file, decided edits applied, removed questions left out
    - "verified":  only questions that were verified or that a person approved/edited (edits applied)
    - "results":   one row per question: status, verdict, decision, suggestion, reasons, sources

    Returns (bytes, file name, summary).
    """
    from qv.services.datasets import get_version
    from qv.services.workflow import question_states
    states = question_states(db, dataset)
    with db.session() as s:
        v = get_version(s, dataset)
        stem = f"{dataset}-v{v.version_no}"
        if kind == "results":
            return results_csv(db, states), f"{stem}-results.csv", {"rows": len(states)}
        edits = {st.ext_id: st.decision_changes for st in states if st.decision == "edit" and st.decision_changes}
        result = corrected_csv(v, edits)
        parsed = parse_csv(v.original_bytes)
        line_of = {r.get("id"): r.line_no for r in parsed.rows}
        if kind == "corrected":
            drop = {st.ext_id for st in states if st.status == "removed"}
        elif kind == "verified":
            keep = {st.ext_id for st in states if st.status in ("verified", "approved", "edited")}
            drop = {st.ext_id for st in states} - keep
        else:
            raise ExportError(f"Unknown export {kind!r}")
        data = drop_rows(result.data, {line_of[i] for i in drop if i in line_of})
        summary = {"rows": len(states) - len(drop), "edited": len(edits), "left_out": len(drop)}
        return data, f"{stem}-{kind}.csv", summary


RESULTS_COLUMNS = ("id", "question", "answer", "status", "verdict", "next_step", "your_decision", "your_comment",
                   "suggested_answer", "suggested_question", "why", "sources", "priority", "category")


def results_csv(db, states: list) -> bytes:  # noqa: ANN001
    """One row per question with its result, decision and up to three source links."""
    from sqlalchemy import select

    from qv.db.models import Document, Passage, QuestionDocument, Validation
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(RESULTS_COLUMNS)
    with db.session() as s:
        for st in states:
            val = s.get(Validation, st.validation_id) if st.validation_id else None
            urls: list[str] = []
            if val is not None:
                for (url,) in s.execute(
                        select(Document.final_url).join(Passage, Passage.document_id == Document.id)
                        .join(QuestionDocument, QuestionDocument.id == Passage.question_document_id)
                        .where(Passage.run_id == val.run_id, Passage.question_id == val.question_id,
                               QuestionDocument.status == "extracted")
                        .order_by(QuestionDocument.effective_tier, Passage.id)):
                    if url not in urls:
                        urls.append(url)
            w.writerow([st.ext_id, st.question, st.answer_text, st.label, st.verdict,
                        st.review_status.replace("_", " "), st.decision, st.decision_comment,
                        val.suggested_answer or "" if val else "", val.suggested_question or "" if val else "",
                        " | ".join(val.reasons_json) if val else "", " ".join(urls[:3]),
                        st.priority_level, " > ".join(x for x in (st.category, st.subcategory, st.topic) if x)])
    return buf.getvalue().encode("utf-8")
