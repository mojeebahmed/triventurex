"""The web page's table helper (pure parts; the browser side is checked by hand)."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from qv.ui.table import cell_text, picked_row, signature, table_spec


def test_cell_text() -> None:
    assert [cell_text(v) for v in (None, math.nan, 3.0, 2.5, "x", ["a"])] == ["", "", "3", "2.5", "x", '["a"]']


def test_table_spec_hides_and_labels_columns() -> None:
    df = pd.DataFrame([{"id": "1", "question": "Q", "points": 3, "_qid": 9, "version_id": 4}])
    names, specs = table_spec(df, {"question": st.column_config.TextColumn("Question", width="large"),
                                   "version_id": None})
    assert names == ["id", "question", "points"]
    assert specs[1] == {"label": "Question", "width": "520px", "num": False}
    assert specs[2]["num"] is True


def test_pick_follows_the_id_column_not_other_values() -> None:
    a = pd.DataFrame([{"batch": 1, "done": 2}, {"batch": 2, "done": 0}])
    b = pd.DataFrame([{"batch": 1, "done": 3}, {"batch": 2, "done": 0}])      # a running batch moved on
    c = pd.DataFrame([{"batch": 2, "done": 0}])                                # filtered: other rows
    assert signature(a) == signature(b) != signature(c)
    state = {"row": 1, "sig": signature(a)}
    assert picked_row(state, signature(b), 2) == 1
    assert picked_row(state, signature(c), 1) is None
    assert picked_row({"row": 5, "sig": signature(a)}, signature(a), 2) is None
    assert picked_row(None, signature(a), 2) is None


def test_component_key_never_contains_double_underscore() -> None:
    from qv.ui.table import component_key
    k = component_key("review_swab-quest_all__")          # empty search + no categories
    assert k and "__" not in k and k == component_key("review_swab-quest_all__")
    assert component_key(None) is None


def test_every_help_page_has_titled_sections() -> None:
    from qv.ui.help_text import HELP, help_for
    for page in HELP:
        sections = help_for(page)
        assert sections and all(title and text.strip() for title, text in sections), page
    assert "| Signal | Points |" in dict(help_for("validate"))["Fact-heavy wording"]
