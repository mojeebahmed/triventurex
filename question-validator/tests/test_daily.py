"""Automatic daily batch: settings, LaunchAgent file, and the day's loop (no launchctl, no network)."""

from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

from qv.services import daily


def test_turn_on_writes_settings_and_launch_agent(tmp_path: Path) -> None:
    data, home = tmp_path / "data", tmp_path / "home"
    path = daily.turn_on(data, daily.DailySettings(["swab-quest", "world-tour"], 9, 15), home=home, load=False)
    agent = plistlib.loads(path.read_bytes())
    assert agent["Label"] == daily.LABEL
    assert agent["ProgramArguments"][-3:] == ["qv.cli", "auto", "run"]
    assert agent["StartCalendarInterval"] == {"Hour": 9, "Minute": 15}
    assert agent["EnvironmentVariables"]["QV_DATA_DIR"] == str(data)
    st = daily.status(data, home=home)
    assert st.on and st.settings.datasets == ["swab-quest", "world-tour"] and st.settings.time_text == "09:15"
    assert daily.turn_off(home=home, load=False) and not daily.status(data, home=home).on
    assert daily.load_settings(data).datasets == ["swab-quest", "world-tour"]   # kept for next time


def test_turn_on_needs_a_file_and_a_valid_time(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        daily.turn_on(tmp_path, daily.DailySettings([], 9, 0), home=tmp_path, load=False)
    with pytest.raises(ValueError):
        daily.turn_on(tmp_path, daily.DailySettings(["a"], 24, 0), home=tmp_path, load=False)


def test_run_daily_goes_through_files_until_quota_is_used(tmp_path: Path) -> None:
    daily.save_settings(tmp_path, daily.DailySettings(["a", "b", "c"]))
    quota = [10, 4, 0]
    ran: list[str] = []
    done = daily.run_daily(tmp_path, batch_size_today=lambda: quota[len(ran)], run_next=lambda n: ran.append(n) or 0,
                           is_busy=lambda: False, echo=lambda *_: None)
    assert done == ran == ["a", "b"]


def test_run_daily_stops_when_a_batch_is_running(tmp_path: Path) -> None:
    daily.save_settings(tmp_path, daily.DailySettings(["a"]))
    assert daily.run_daily(tmp_path, batch_size_today=lambda: 10, run_next=lambda n: 0, is_busy=lambda: True,
                           echo=lambda *_: None) == []
