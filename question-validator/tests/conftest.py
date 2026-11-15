"""Shared fixtures."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from qv.db.session import Database

REPO_ROOT = Path(__file__).resolve().parents[2]
EDITIONS_DIR = REPO_ROOT / "game_editions"
EDITIONS = ["swab-quest", "football-quest", "world-tour", "animal-safari", "prophets-stories"]
HEADER = "id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note"
FIXTURES = Path(__file__).parent / "fixtures"


def make_csv(*rows: str, header: str = HEADER, newline: str = "\n", final_newline: bool = True) -> bytes:
    """Build CSV bytes from a header and row strings."""
    text = newline.join([header, *rows]) + (newline if final_newline else "")
    return text.encode("utf-8")


GOOD_ROWS = (
    "1,What is the capital of France?,multi,1,Paris,Lyon,Nice,Lille,easy,Geo,Capitals,Europe,",
    '2,"Which river flows through Cairo, Egypt?",open,The Nile,,,,,hard,Geo,Rivers,Africa,"Longest, maybe"',
    "3,How many legs does a spider have?,multi,2,6,8,10,,easy,Animals,Bugs,World,",
)


@pytest.fixture
def good_csv() -> bytes:
    """A small, structurally clean CSV."""
    return make_csv(*GOOD_ROWS)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """A fresh, migrated SQLite database in a temp directory."""
    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    yield database
    database.dispose()


@pytest.fixture(scope="session")
def node() -> str:
    """Path to node, or skip (parity tests need the game's JS)."""
    path = shutil.which("node")
    if not path:
        pytest.skip("node is not installed")
    return path


def edition_bytes(edition: str) -> bytes:
    """Bytes of an edition's questions.csv."""
    return (EDITIONS_DIR / edition / "questions.csv").read_bytes()
