"""CLI: commands run end to end against a temp data directory."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from qv.cli import app
from tests.conftest import EDITIONS_DIR, make_csv

runner = CliRunner()


def run(tmp_path: Path, *args: str):
    """Invoke `qv --data-dir <tmp> …`."""
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_check_exit_codes(tmp_path: Path, good_csv: bytes) -> None:
    good = tmp_path / "good.csv"
    good.write_bytes(good_csv)
    bad = tmp_path / "bad.csv"
    bad.write_bytes(make_csv("x,Q?,quiz,A,,,,,easy,c,,,"))
    assert run(tmp_path, "check", str(good)).exit_code == 0
    res = run(tmp_path, "check", str(bad))
    assert res.exit_code == 1 and "invalid_id" in res.output and "NOT OK" in res.output


def test_import_list_diff_export(tmp_path: Path, good_csv: bytes) -> None:
    f = tmp_path / "geo.csv"
    f.write_bytes(good_csv)
    assert "version 1" in run(tmp_path, "import", str(f), "--dataset", "geo").output
    assert "identical to version 1" in run(tmp_path, "import", str(f), "--dataset", "geo").output
    f.write_bytes(good_csv.replace(b"Paris,Lyon", b"Paris,Lyons"))
    assert "1 changed" in run(tmp_path, "import", str(f), "--dataset", "geo").output
    assert "v2" in run(tmp_path, "datasets").output
    assert "changed: id 1 (opt_b)" in run(tmp_path, "diff", "geo", "1", "2").output

    out = tmp_path / "orig.csv"
    assert run(tmp_path, "export", "original", "geo", "--version", "1", "--out", str(out)).exit_code == 0
    assert out.read_bytes() == good_csv

    changes = tmp_path / "changes.json"
    changes.write_text(json.dumps({"2": {"note": "Fixed note"}}))
    res = run(tmp_path, "export", "corrected", "geo", "--changes", str(changes))
    assert res.exit_code == 0 and "Changed ids: 2" in res.output
    assert (tmp_path / "data/exports/geo-v2-corrected.csv").is_file()

    res = run(tmp_path, "export", "report", "geo")
    assert res.exit_code == 0


def test_issues_and_profiles(tmp_path: Path) -> None:
    run(tmp_path, "import", str(EDITIONS_DIR / "swab-quest/questions.csv"), "--dataset", "swab-quest")
    res = run(tmp_path, "issues", "swab-quest", "--severity", "warning")
    assert "near_duplicate_question" in res.output and "id 285" in res.output
    assert "prophets-stories" in run(tmp_path, "profiles").output


def test_eval_check_passes(tmp_path: Path) -> None:
    res = run(tmp_path, "eval", "check")
    assert res.exit_code == 0, res.output
