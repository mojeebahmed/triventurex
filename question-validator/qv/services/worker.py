"""One batch at a time, in the background: a lock file plus a detached `qv next` process.

The web page starts a batch with `start_background`; `qv next` in a terminal takes the same lock, so
two batches never run at once (they would compete for the same small free quota). A lock whose
process has gone (crash, reboot) is stale and ignored.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOCK_NAME = "batch.lock.json"


@dataclass(frozen=True)
class BatchStatus:
    """The running batch, if any."""

    running: bool
    dataset: str = ""
    pid: int = 0
    started: str = ""
    log: Path | None = None


def _alive(pid: int) -> bool:
    try:  # our own finished child (started by this web page) must be reaped, or it looks alive
        done, _ = os.waitpid(pid, os.WNOHANG)
        if done:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def status(data_dir: Path) -> BatchStatus:
    """Whether a batch is running now (a stale lock counts as not running)."""
    lock = data_dir / LOCK_NAME
    try:
        info = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return BatchStatus(False)
    if not _alive(int(info.get("pid", 0))):
        return BatchStatus(False)
    return BatchStatus(True, info.get("dataset", ""), int(info["pid"]), info.get("started", ""),
                       Path(info["log"]) if info.get("log") else None)


def acquire(data_dir: Path, dataset: str, log: Path | None = None) -> bool:
    """Take the lock for this process; False when another live batch holds it."""
    current = status(data_dir)
    if current.running and current.pid != os.getpid():
        return False
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / LOCK_NAME).write_text(json.dumps({
        "pid": os.getpid(), "dataset": dataset, "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "log": str(log) if log else ""}), encoding="utf-8")
    return True


def release(data_dir: Path) -> None:
    """Drop the lock if this process holds it."""
    lock = data_dir / LOCK_NAME
    try:
        if json.loads(lock.read_text(encoding="utf-8")).get("pid") == os.getpid():
            lock.unlink()
    except (OSError, ValueError):
        pass


def start_background(data_dir: Path, dataset: str, args: list[str]) -> Path:
    """Start `qv next <dataset> --yes <args>` detached from the web page; returns its log file."""
    logs = data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f"batch-{dataset}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    env = {**os.environ, "QV_DATA_DIR": str(data_dir), "QV_BATCH_LOG": str(log), "PYTHONUNBUFFERED": "1"}
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen([sys.executable, "-m", "qv.cli", "next", dataset, "--yes", *args],
                                stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                                start_new_session=True, cwd=Path(__file__).parents[2])
    # Hold the lock for the child at once, so the page shows it running before it has started up.
    (data_dir / LOCK_NAME).write_text(json.dumps({
        "pid": proc.pid, "dataset": dataset, "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "log": str(log)}), encoding="utf-8")
    return log


def tail(log: Path | None, lines: int = 15) -> str:
    """The last lines of a batch log."""
    if log is None or not log.exists():
        return ""
    return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def latest_log(data_dir: Path, dataset: str) -> Path | None:
    """The newest log of a dataset's batches."""
    logs = sorted((data_dir / "logs").glob(f"batch-{dataset}-*.log"))
    return logs[-1] if logs else None
