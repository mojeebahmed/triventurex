"""Command-line interface (`qv`). Thin: parses arguments and calls services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from qv.config import DEFAULT_PROFILE, Settings, available_profiles, load_profile
from qv.db.session import Database
from qv.domain.structural import Severity, StructuralReport
from qv.services import datasets as ds_service
from qv.services import exports as export_service

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Question Validator — check, import and export Triventurex question CSVs.")
eval_app = typer.Typer(no_args_is_help=True, help="Evaluation set tools.")
app.add_typer(eval_app, name="eval")

_state: dict[str, Settings] = {}


@app.callback()
def main(data_dir: Annotated[Path | None, typer.Option(help="Data directory (default: ./data or $QV_DATA_DIR)")]
         = None) -> None:
    """Global options."""
    _state["settings"] = Settings(data_dir=data_dir) if data_dir else Settings()


def _settings() -> Settings:
    """Settings chosen in the callback (or defaults when called programmatically)."""
    return _state.get("settings") or Settings()


def _db() -> Database:
    """Open (and migrate) the configured database."""
    return Database(_settings().database_url)


def _print_report(report: StructuralReport, *, show: str = "warning", limit: int = 50) -> None:
    """Print counts and the issues at or above `show` severity."""
    order = [Severity.ERROR, Severity.WARNING, Severity.INFO]
    typer.echo(f"{report.row_count} questions ({report.multi_count} multi, {report.open_count} open) — "
               f"{report.count(Severity.ERROR)} error(s), {report.count(Severity.WARNING)} warning(s), "
               f"{report.count(Severity.INFO)} info")
    cutoff = order.index(Severity(show))
    shown = [i for i in report.issues if order.index(i.severity) <= cutoff]
    for i in shown[:limit]:
        where = f"line {i.line_no}" if i.line_no else "file"
        ident = f" id {i.ext_id}" if i.ext_id else ""
        typer.echo(f"  {i.severity.value.upper():7} {where}{ident}  [{i.code.value}] {i.message}")
    if len(shown) > limit:
        typer.echo(f"  … {len(shown) - limit} more (use --limit)")
    typer.echo("OK for the game." if report.ok_for_game else "NOT OK: the game's checker would fail.")


@app.command()
def check(file: Path, profile: Annotated[str, typer.Option(help="Profile name")] = DEFAULT_PROFILE,
          show: Annotated[str, typer.Option(help="error | warning | info")] = "warning",
          limit: int = 50) -> None:
    """Check a CSV without storing it. Exit code 1 when there are errors."""
    result = ds_service.check_bytes(file.read_bytes(), load_profile(profile))
    _print_report(result.report, show=show, limit=limit)
    raise typer.Exit(0 if result.report.ok_for_game else 1)


@app.command("import")
def import_cmd(file: Path,
               dataset: Annotated[str, typer.Option(help="Dataset name (e.g. world-tour)")],
               profile: Annotated[str | None, typer.Option(help="Profile (default: dataset name if a "
                                                                "profile exists, else general)")] = None,
               show: str = "warning", limit: int = 50) -> None:
    """Import a CSV as a new immutable version of a dataset."""
    db = _db()
    with db.session() as s:
        res = ds_service.import_dataset(s, file.read_bytes(), dataset_name=dataset,
                                        source_filename=file.name, profile_name=profile)
    if not res.created:
        typer.echo(f"{dataset}: identical to version {res.version_no} — nothing imported.")
        return
    typer.echo(f"{dataset}: imported as version {res.version_no} (sha256 {res.file_sha256[:12]}…)")
    _print_report(res.report, show=show, limit=limit)
    if res.diff is not None:
        d = res.diff
        typer.echo(f"Changes since previous version: {len(d.added)} added, {len(d.removed)} removed, "
                   f"{len(d.changed)} changed, {d.unchanged_count} unchanged")


@app.command("datasets")
def list_datasets() -> None:
    """List datasets and their versions."""
    db = _db()
    with db.session() as s:
        for d in ds_service.list_datasets(s):
            typer.echo(f"{d.name}  (profile {d.profile})")
            for v in d.versions:
                typer.echo(f"  v{v.version_no}  {v.imported_at:%Y-%m-%d %H:%M}  {v.row_count} rows  "
                           f"{v.error_count}E {v.warning_count}W {v.info_count}I  {v.source_filename}")


@app.command()
def issues(dataset: str, version: Annotated[int | None, typer.Option(help="Version (default latest)")] = None,
           severity: str = "info") -> None:
    """List the stored structural issues of a dataset version."""
    order = ["error", "warning", "info"]
    db = _db()
    with db.session() as s:
        v = ds_service.get_version(s, dataset, version)
        for i in ds_service.version_issues(s, v):
            if order.index(i.severity) <= order.index(severity):
                where = f"line {i.line_no}" if i.line_no else "file"
                typer.echo(f"{i.severity.upper():7} {where} id {i.ext_id or '-'}  [{i.code}] {i.message}")


@app.command()
def diff(dataset: str, old: int, new: int) -> None:
    """Show what changed between two versions (by CSV id)."""
    db = _db()
    with db.session() as s:
        d = ds_service.diff_versions(s, ds_service.get_version(s, dataset, old),
                                     ds_service.get_version(s, dataset, new))
    typer.echo(f"added: {', '.join(d.added) or '-'}")
    typer.echo(f"removed: {', '.join(d.removed) or '-'}")
    for c in d.changed:
        typer.echo(f"changed: id {c.ext_id} ({', '.join(c.fields)})")
    typer.echo(f"unchanged: {d.unchanged_count}")
    if d.duplicate_ids:
        typer.echo(f"duplicate ids (compared by first occurrence): {', '.join(d.duplicate_ids)}")


@app.command()
def export(kind: Annotated[str, typer.Argument(help="original | report | corrected")], dataset: str,
           version: Annotated[int | None, typer.Option(help="Version (default latest)")] = None,
           out: Annotated[Path | None, typer.Option(help="Output file (default: data/exports/…)")] = None,
           changes: Annotated[Path | None, typer.Option(
               help='corrected: JSON {"<id>": {"<column>": "<new value>"}} of APPROVED changes')] = None) -> None:
    """Export the original file, the structural report, or a corrected CSV."""
    db = _db()
    with db.session() as s:
        v = ds_service.get_version(s, dataset, version)
        if kind == "original":
            data, suffix = export_service.export_original(v), "original.csv"
        elif kind == "report":
            data, suffix = export_service.structural_report_csv(s, v), "structural-report.csv"
        elif kind == "corrected":
            if changes is None:
                raise typer.BadParameter("--changes is required for a corrected export")
            result = export_service.corrected_csv(v, json.loads(changes.read_text(encoding="utf-8")))
            data, suffix = result.data, "corrected.csv"
            typer.echo(f"Changed ids: {', '.join(result.changed_ids) or '-'}")
        else:
            raise typer.BadParameter("kind must be original, report or corrected")
        target = out or _settings().exports_dir / f"{dataset}-v{v.version_no}-{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    typer.echo(f"Wrote {target} ({len(data)} bytes)")


@app.command()
def profiles() -> None:
    """List available profiles."""
    for name in available_profiles():
        p = load_profile(name)
        frame = f"frame: {p.frame.name}{'' if p.frame.confirmed else ' (draft)'}" if p.frame else "no frame"
        typer.echo(f"{name:18} {p.audience} — {frame}")


# --- evaluation set -----------------------------------------------------------

@eval_app.command("check")
def eval_check() -> None:
    """Check that every case in eval/cases.yaml points at the intended row."""
    from qv.evaluation import check_case_targets, load_cases
    cases = load_cases()
    problems = check_case_targets(cases)
    for p in problems:
        typer.echo(f"  {p}")
    typer.echo(f"{len(cases)} cases, {len(problems)} problem(s)")
    raise typer.Exit(1 if problems else 0)


@eval_app.command("seed")
def eval_seed(per_mutation: int = 10, seed: int = 20261115) -> None:
    """Regenerate eval/seeded.csv and eval/seeded_labels.yaml from the current editions."""
    from qv.evaluation import EVAL_DIR, generate_seeded_errors, labels_to_yaml
    data, labels = generate_seeded_errors(_edition_sources(), seed=seed, per_mutation=per_mutation)
    (EVAL_DIR / "seeded.csv").write_bytes(data)
    (EVAL_DIR / "seeded_labels.yaml").write_text(labels_to_yaml(labels), encoding="utf-8")
    typer.echo(f"Wrote {len(labels)} seeded questions to {EVAL_DIR}")


@eval_app.command("sample")
def eval_sample(out: Path, n: int = 150, seed: int = 20261115) -> None:
    """Write a stratified sample of questions as a labelling sheet (CSV)."""
    import csv

    from qv.evaluation import load_cases, stratified_sample
    always = {(c.dataset, c.id) for c in load_cases()}
    picked = stratified_sample(_edition_sources(), n=n, seed=seed, always=always)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["dataset", "id", "question", "key", "category", "expected_verdict", "defect", "comment"])
        for ds, q in picked:
            w.writerow([ds, q.ext_id, q.question, q.resolved_answer_text or "", q.category, "", "", ""])
    typer.echo(f"Wrote {len(picked)} questions to {out}")


def _edition_sources() -> dict:
    """Current questions of every edition (template excluded)."""
    from qv.evaluation import EDITIONS_DIR, load_questions
    return {p.parent.name: load_questions(p) for p in sorted(EDITIONS_DIR.glob("*/questions.csv"))
            if p.parent.name != "template"}


if __name__ == "__main__":
    app()
