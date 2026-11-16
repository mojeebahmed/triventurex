"""Our own read-only table for the web page (a Streamlit v2 component: plain HTML + JS, no build step).

Why not `st.dataframe`: its grid (glide) highlights single cells, shows a tick-box column for selection and
opens a cell editor on double-click. Here a click anywhere on a row picks and highlights the whole row,
there are no tick boxes, nothing is editable and double-click does nothing.

Values are put into the page with `textContent` only (never as HTML), so question text cannot inject markup.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import pandas as pd
import streamlit as st

_CSS = """
:host { display: block; }
.qv-wrap { overflow: auto; border: 1px solid var(--st-border-color, #e3e5eb); border-radius: 8px;
  font-family: var(--st-font, "Source Sans Pro", sans-serif); font-size: 14px; color: var(--st-text-color, #31333f);
  background: var(--st-background-color, #fff); scrollbar-gutter: stable; }
.qv-wrap::-webkit-scrollbar { width: 11px; height: 11px; }
.qv-wrap::-webkit-scrollbar-track { background: #f1f2f6; border-radius: 6px; }
.qv-wrap::-webkit-scrollbar-thumb { background: #b8bcc8; border-radius: 6px; border: 2px solid #f1f2f6; }
.qv-wrap::-webkit-scrollbar-thumb:hover { background: #8d92a1; }
table { border-collapse: separate; border-spacing: 0; width: max-content; min-width: 100%; }
th { position: sticky; top: 0; z-index: 1; text-align: left; font-weight: 600; padding: 7px 10px;
  background: var(--st-secondary-background-color, #f6f7f9); border-bottom: 1px solid var(--st-border-color, #e3e5eb);
  color: var(--st-text-color, #31333f); opacity: 0.95; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
td { padding: 7px 10px; border-bottom: 1px solid var(--st-border-color, #eef0f4); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
td.num, th.num { text-align: right; }
tr:last-child td { border-bottom: none; }
tbody tr { user-select: none; }
.pick tbody tr { cursor: pointer; }
.pick tbody tr:hover td { background: rgba(127, 127, 127, 0.08); }
tbody tr.on td, .pick tbody tr.on:hover td { background: #fff3c4; color: #31333f; font-weight: 600; }
"""

_JS = """
export default function(component) {
  const { data, parentElement, setStateValue } = component;
  let wrap = parentElement.querySelector('.qv-wrap');
  const keepScroll = wrap ? wrap.scrollTop : 0;
  if (!wrap) { wrap = document.createElement('div'); wrap.className = 'qv-wrap'; parentElement.appendChild(wrap); }
  wrap.replaceChildren();
  wrap.style.maxHeight = data.height + 'px';
  const table = document.createElement('table');
  if (data.select) table.classList.add('pick');
  const head = document.createElement('tr');
  data.columns.forEach(c => {
    const th = document.createElement('th');
    th.textContent = c.label;
    th.title = c.label;
    th.style.maxWidth = c.width;
    if (c.num) th.classList.add('num');
    head.appendChild(th);
  });
  const thead = document.createElement('thead');
  thead.appendChild(head);
  const tbody = document.createElement('tbody');
  data.rows.forEach((cells, i) => {
    const tr = document.createElement('tr');
    if (i === data.selected) tr.classList.add('on');
    cells.forEach((v, j) => {
      const td = document.createElement('td');
      td.textContent = v;
      td.title = v;
      td.style.maxWidth = data.columns[j].width;
      if (data.columns[j].num) td.classList.add('num');
      tr.appendChild(td);
    });
    if (data.select) {
      tr.addEventListener('click', () => {
        tbody.querySelectorAll('tr.on').forEach(r => r.classList.remove('on'));
        tr.classList.add('on');
        setStateValue('picked', { row: i, sig: data.sig });
      });
    }
    tbody.appendChild(tr);
  });
  table.append(thead, tbody);
  wrap.appendChild(table);
  wrap.scrollTop = keepScroll;
}
"""

_WIDTH = {"small": "120px", "medium": "260px", "large": "520px"}   # most a column grows to; longer text gets "…"
_DEFAULT_WIDTH = "260px"


@st.cache_resource
def _component() -> Any:
    """Register the component once per server process."""
    return st.components.v2.component("qv_table", css=_CSS, js=_JS)


def cell_text(value: Any) -> str:
    """How a value is shown in a cell (None/NaN → empty, whole floats without '.0')."""
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if value.is_integer():
            return str(int(value))
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def table_spec(df: pd.DataFrame, columns: dict | None) -> tuple[list[str], list[dict]]:
    """Visible column names and their header specs, from Streamlit-style column config.

    A column mapped to None, or whose name starts with "_", is hidden. A config dict gives the label,
    width (small / medium / large) and number alignment.
    """
    columns = columns or {}
    names: list[str] = []
    specs: list[dict] = []
    for name in df.columns:
        cfg = columns.get(name, {})
        if cfg is None or str(name).startswith("_"):
            continue
        cfg = cfg if isinstance(cfg, dict) else {}
        num = (cfg.get("type_config") or {}).get("type") == "number" or pd.api.types.is_numeric_dtype(df[name])
        names.append(name)
        specs.append({"label": cfg.get("label") or str(name), "width": _WIDTH.get(cfg.get("width") or "", _DEFAULT_WIDTH),
                      "num": bool(num)})
    return names, specs


ID_COLUMNS = ("_qid", "id", "batch", "run", "version_id", "file")


def signature(df: pd.DataFrame) -> str:
    """Short hash of which rows are shown, in order, by their id column (or the first column).

    A pick made on other rows (e.g. before a filter changed) is ignored; a pick survives when only other
    values change (a running batch updating its counts, a decision changing a status).
    """
    col = next((c for c in ID_COLUMNS if c in df.columns), df.columns[0])
    ids = [cell_text(v) for v in df[col].tolist()]
    return hashlib.sha1(json.dumps([str(col), ids], ensure_ascii=False).encode()).hexdigest()[:16]


def picked_row(state: Any, sig: str, n_rows: int) -> int | None:
    """The row the viewer clicked, if it was clicked on exactly these rows."""
    if not isinstance(state, dict) or state.get("sig") != sig:
        return None
    row = state.get("row")
    return row if isinstance(row, int) and 0 <= row < n_rows else None


def render_table(df: pd.DataFrame, *, key: str | None, select: bool, columns: dict | None, height: int,
                 highlight: int | None) -> int | None:
    """Draw the table; with `select`, return the clicked row (or `highlight` until something is clicked)."""
    names, specs = table_spec(df, columns)
    rows = [[cell_text(v) for v in rec] for rec in df[names].itertuples(index=False, name=None)]
    sig = signature(df)
    comp_key = f"qv_table_{key}" if key else None
    state = st.session_state.get(comp_key) if comp_key else None
    clicked = picked_row(getattr(state, "picked", None) if state is not None and not isinstance(state, dict)
                         else (state or {}).get("picked"), sig, len(rows))
    shown = clicked if clicked is not None else highlight
    data = {"columns": specs, "rows": rows, "select": select, "height": height, "sig": sig,
            "selected": shown if shown is not None and shown < len(rows) else -1}
    kwargs: dict[str, Any] = {"key": comp_key, "data": data}
    if select:
        kwargs["on_picked_change"] = lambda: None
    result = _component()(**kwargs)
    if not select:
        return None
    now = picked_row(getattr(result, "picked", None), sig, len(rows))
    return now if now is not None else clicked
