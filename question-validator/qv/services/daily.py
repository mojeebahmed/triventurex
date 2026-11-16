"""Continue automatically every day: a macOS LaunchAgent runs `qv auto run` once a day.

`qv auto run` validates the next batch of each chosen file in turn (the same as pressing *Validate next
batch*), until the day's free requests are used up or nothing is left. The settings (which files, what
time) live in `<data_dir>/auto.json`; the LaunchAgent only starts the command. A Mac that is asleep at
that time runs it when it wakes up (launchd catches up on a missed calendar time).

Turning it on or off is always the person's choice (web page or `qv auto on|off`); nothing here turns
itself on.
"""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

LABEL = "com.triventurex.question-validator.daily"
SETTINGS_NAME = "auto.json"
PROJECT_DIR = Path(__file__).parents[2]


@dataclass
class DailySettings:
    """What runs every day."""

    datasets: list[str] = field(default_factory=list)
    hour: int = 9
    minute: int = 30

    @property
    def time_text(self) -> str:
        """HH:MM"""
        return f"{self.hour:02d}:{self.minute:02d}"


@dataclass(frozen=True)
class DailyStatus:
    """Whether the daily run is on, and what it does."""

    on: bool
    settings: DailySettings
    log: Path


def plist_path(home: Path | None = None) -> Path:
    """Where the LaunchAgent file lives."""
    return (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def log_path(data_dir: Path) -> Path:
    """The daily run's log (every day appends)."""
    return data_dir / "logs" / "daily.log"


def load_settings(data_dir: Path) -> DailySettings:
    """Saved settings, or the defaults."""
    try:
        raw = json.loads((data_dir / SETTINGS_NAME).read_text(encoding="utf-8"))
        return DailySettings(list(raw.get("datasets", [])), int(raw.get("hour", 9)), int(raw.get("minute", 30)))
    except (OSError, ValueError):
        return DailySettings()


def save_settings(data_dir: Path, s: DailySettings) -> None:
    """Write auto.json."""
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / SETTINGS_NAME).write_text(json.dumps({"datasets": s.datasets, "hour": s.hour, "minute": s.minute},
                                                     indent=2), encoding="utf-8")


def launch_agent(data_dir: Path, s: DailySettings, python: str = sys.executable) -> dict:
    """The LaunchAgent definition (a plist dict)."""
    log = str(log_path(data_dir))
    return {
        "Label": LABEL,
        "ProgramArguments": [python, "-m", "qv.cli", "auto", "run"],
        "WorkingDirectory": str(PROJECT_DIR),
        "EnvironmentVariables": {"QV_DATA_DIR": str(data_dir), "PYTHONUNBUFFERED": "1"},
        "StartCalendarInterval": {"Hour": s.hour, "Minute": s.minute},
        "StandardOutPath": log,
        "StandardErrorPath": log,
        "ProcessType": "Background",
    }


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)


def turn_on(data_dir: Path, s: DailySettings, *, home: Path | None = None, load: bool = True) -> Path:
    """Save the settings and install (or replace) the LaunchAgent. Returns the plist path."""
    if not s.datasets:
        raise ValueError("Choose at least one file to continue every day")
    if not (0 <= s.hour < 24 and 0 <= s.minute < 60):
        raise ValueError("Time must be between 00:00 and 23:59")
    save_settings(data_dir, s)
    log_path(data_dir).parent.mkdir(parents=True, exist_ok=True)
    path = plist_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    if load and path.exists():
        _launchctl("bootout", f"gui/{os.getuid()}", str(path))
    path.write_bytes(plistlib.dumps(launch_agent(data_dir, s)))
    if load:
        res = _launchctl("bootstrap", f"gui/{os.getuid()}", str(path))
        if res.returncode != 0:
            raise RuntimeError(f"launchctl could not load the daily run: {res.stderr.strip() or res.stdout.strip()}")
    return path


def turn_off(*, home: Path | None = None, load: bool = True) -> bool:
    """Remove the LaunchAgent; True when there was one. The saved settings are kept for next time."""
    path = plist_path(home)
    if not path.exists():
        return False
    if load:
        _launchctl("bootout", f"gui/{os.getuid()}", str(path))
    path.unlink()
    return True


def status(data_dir: Path, *, home: Path | None = None) -> DailyStatus:
    """On when the LaunchAgent file is installed."""
    return DailyStatus(plist_path(home).exists(), load_settings(data_dir), log_path(data_dir))


def run_daily(data_dir: Path, *, batch_size_today, run_next, is_busy, echo=print) -> list[str]:  # noqa: ANN001
    """One day's work: the next batch of each chosen file in turn, while free requests are left.

    `batch_size_today()` → questions today's free quota allows (0 = used up); `run_next(dataset)` → runs
    `qv next <dataset> --yes` and returns its exit code; `is_busy()` → a batch is already running.
    Returns the files it started a batch for. Injected so tests need no database or network.
    """
    s = load_settings(data_dir)
    echo(f"--- daily run {datetime.now():%Y-%m-%d %H:%M} · files: {', '.join(s.datasets) or '(none)'}")
    done: list[str] = []
    for name in s.datasets:
        if is_busy():
            echo("A batch is already running — the daily run stops here; it continues tomorrow.")
            break
        if batch_size_today() == 0:
            echo("Today's free requests are used up — continuing tomorrow.")
            break
        echo(f"{name}: next batch")
        code = run_next(name)
        done.append(name)
        if code != 0:
            echo(f"{name}: batch ended with exit code {code}")
    echo("--- daily run finished")
    return done
