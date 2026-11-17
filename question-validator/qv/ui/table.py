"""Our own read-only table for the web page (a Streamlit v2 component: plain HTML + JS, no build step).

Why not `st.dataframe`: its grid (glide) highlights single cells, shows a tick-box column for selection and
opens a cell editor on double-click. Here a click anywhere on a row picks and highlights the whole row,
there are no tick boxes, nothing is editable and double-click does nothing. Every table sorts by a click on a
column header (again = reverse, a third time = file order) and can have a search box; both work in the browser
only, so they never lose the picked row (rows are reported by their position in the data, not on screen).

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
.qv-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.qv-search { flex: 1; max-width: 420px; padding: 6px 10px; border: 1px solid var(--st-border-color, #d5d8de);
  border-radius: 8px; font: inherit; font-size: 14px; background: var(--st-background-color, #fff);
  color: var(--st-text-color, #31333f); }
.qv-search:focus { outline: 2px solid #ff4b4b55; border-color: #ff4b4b; }
.qv-count { font-size: 13px; opacity: 0.7; }
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
  color: var(--st-text-color, #31333f); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  cursor: pointer; user-select: none; }
th:hover { background: #eceef2; }
th .arrow { opacity: 0.35; margin-left: 4px; font-size: 11px; }
th.sorted .arrow { opacity: 1; color: #ff4b4b; }
td { padding: 7px 10px; border-bottom: 1px solid var(--st-border-color, #eef0f4); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
td.num, th.num { text-align: right; }
tr:last-child td { border-bottom: none; }
tbody tr { user-select: none; }
.pick tbody tr { cursor: pointer; }
.pick tbody tr:hover td { background: rgba(127, 127, 127, 0.08); }
tbody tr.on td, .pick tbody tr.on:hover td { background: #fff3c4; color: #31333f; font-weight: 600; }
mark { background: #ffe066; color: inherit; padding: 0 1px; border-radius: 3px; }
.qv-empty { padding: 10px; opacity: 0.7; font-size: 14px; }
"""

_JS = """
// Put a cell's text into the page, the search words wrapped in <mark> — built from text nodes, never as HTML
function fillCell(td, v, marks) {
  if (!marks.length) { td.textContent = v; return; }
  const low = v.toLowerCase();
  const words = marks.map(w => w.toLowerCase()).sort((a, b) => b.length - a.length);
  const isWordChar = ch => !!ch && (ch.toLowerCase() !== ch.toUpperCase() || (ch >= '0' && ch <= '9'));
  let at = 0, i = 0;
  while (i < low.length) {
    const w = isWordChar(low[i - 1]) ? null : words.find(x => low.startsWith(x, i));
    if (w) {
      if (i > at) td.appendChild(document.createTextNode(v.slice(at, i)));
      const mk = document.createElement('mark');
      mk.textContent = v.slice(i, i + w.length);
      td.appendChild(mk);
      i += w.length;
      at = i;
    } else {
      i += 1;
    }
  }
  if (at < v.length) td.appendChild(document.createTextNode(v.slice(at)));
}

export default function(component) {
  const { data, parentElement, setStateValue } = component;
  let root = parentElement.querySelector('.qv-root');
  if (!root) {
    root = document.createElement('div');
    root.className = 'qv-root';
    const bar = document.createElement('div');
    bar.className = 'qv-bar';
    const input = document.createElement('input');
    input.type = 'search';
    input.className = 'qv-search';
    const count = document.createElement('span');
    count.className = 'qv-count';
    bar.append(input, count);
    const wrap = document.createElement('div');
    wrap.className = 'qv-wrap';
    root.append(bar, wrap);
    parentElement.appendChild(root);
    root.qvSort = { col: -1, dir: 1 };
  }
  const bar = root.querySelector('.qv-bar');
  const input = root.querySelector('.qv-search');
  const count = root.querySelector('.qv-count');
  const wrap = root.querySelector('.qv-wrap');
  bar.style.display = data.search ? 'flex' : 'none';
  input.placeholder = data.search || '';
  if (!data.search) input.value = '';
  wrap.style.maxHeight = data.height + 'px';
  if (root.qvSort.col >= data.columns.length) root.qvSort = { col: -1, dir: 1 };
  const coll = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

  function draw() {
    const keepScroll = wrap.scrollTop;
    const words = input.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
    let order = data.rows.map((_, i) => i);
    if (words.length) {
      order = order.filter(i => {
        const t = data.rows[i].join(' ').toLowerCase();
        return words.every(w => t.includes(w));
      });
    }
    const s = root.qvSort;
    if (s.col >= 0) {
      const num = data.columns[s.col].num;
      order.sort((a, b) => {
        const x = data.rows[a][s.col], y = data.rows[b][s.col];
        if (x === '' && y !== '') return 1;          // empty cells always last
        if (y === '' && x !== '') return -1;
        let c = num ? parseFloat(x) - parseFloat(y) : coll.compare(x, y);
        if (Number.isNaN(c)) c = coll.compare(x, y);
        return (c || a - b) * s.dir;
      });
    }
    count.textContent = words.length ? order.length + ' of ' + data.rows.length : '';
    const table = document.createElement('table');
    if (data.select) table.classList.add('pick');
    const head = document.createElement('tr');
    data.columns.forEach((c, j) => {
      const th = document.createElement('th');
      const label = document.createElement('span');
      label.textContent = c.label;
      const arrow = document.createElement('span');
      arrow.className = 'arrow';
      arrow.textContent = s.col === j ? (s.dir > 0 ? '▲' : '▼') : '↕';
      th.append(label, arrow);
      th.title = 'Sort by ' + c.label;
      th.style.maxWidth = c.width;
      if (c.num) th.classList.add('num');
      if (s.col === j) th.classList.add('sorted');
      th.addEventListener('click', () => {
        if (s.col !== j) { s.col = j; s.dir = 1; }
        else if (s.dir > 0) { s.dir = -1; }
        else { s.col = -1; s.dir = 1; }
        draw();
      });
      head.appendChild(th);
    });
    const thead = document.createElement('thead');
    thead.appendChild(head);
    const tbody = document.createElement('tbody');
    order.forEach(i => {
      const tr = document.createElement('tr');
      if (i === data.selected) tr.classList.add('on');
      data.rows[i].forEach((v, j) => {
        const td = document.createElement('td');
        fillCell(td, v, data.marks || []);
        td.title = v;
        td.style.maxWidth = data.columns[j].width;
        if (data.columns[j].num) td.classList.add('num');
        tr.appendChild(td);
      });
      if (data.select) {
        tr.addEventListener('click', () => {
          tbody.querySelectorAll('tr.on').forEach(r => r.classList.remove('on'));
          tr.classList.add('on');
          setStateValue('picked', { row: i, sig: data.sig, n: Date.now() + Math.random(), order: order });
        });
      }
      tbody.appendChild(tr);
    });
    table.append(thead, tbody);
    wrap.replaceChildren(table);
    if (!order.length) {
      const empty = document.createElement('div');
      empty.className = 'qv-empty';
      empty.textContent = 'No row matches the search.';
      wrap.appendChild(empty);
    }
    wrap.scrollTop = keepScroll;
  }
  input.oninput = draw;
  draw();
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


def component_key(key: str | None) -> str | None:
    """A component id Streamlit accepts: page keys may hold any text (e.g. "review_x__" with empty filters),
    but a component id must not contain "__", so the key is hashed."""
    return f"qv_table_{hashlib.sha1(key.encode()).hexdigest()[:16]}" if key else None


def pick_nonce(state: Any) -> float | None:
    """The click's id: every click on a row (also on the same row again) has a new one."""
    n = state.get("n") if isinstance(state, dict) else None
    return n if isinstance(n, (int, float)) else None


def pick_order(state: Any, n_rows: int) -> list[int] | None:
    """The rows as the viewer saw them when clicking (after their sort and search), as positions in the data."""
    order = state.get("order") if isinstance(state, dict) else None
    if isinstance(order, list) and all(isinstance(i, int) and 0 <= i < n_rows for i in order):
        return order
    return None


def picked_row(state: Any, sig: str, n_rows: int) -> int | None:
    """The row the viewer clicked, if it was clicked on exactly these rows."""
    if not isinstance(state, dict) or state.get("sig") != sig:
        return None
    row = state.get("row")
    return row if isinstance(row, int) and 0 <= row < n_rows else None


def render_table(df: pd.DataFrame, *, key: str | None, select: bool, columns: dict | None, height: int,
                 highlight: int | None, search: str = "", marks: list[str] | None = None
                 ) -> tuple[int | None, float | None, list[int] | None]:
    """Draw the table (click a header to sort; `search` = placeholder of a filter box above it).

    With `select`, returns (clicked row, click id, visible order) — rows as positions in `df`, whatever the viewer's
    sort or search; the order is what the viewer saw when clicking — or (None, None, None) until something is
    clicked. `marks` = words marked in every cell (whole words and word starts, any case).
    """
    names, specs = table_spec(df, columns)
    rows = [[cell_text(v) for v in rec] for rec in df[names].itertuples(index=False, name=None)]
    sig = signature(df)
    comp_key = component_key(key)
    state = st.session_state.get(comp_key) if comp_key else None
    old = getattr(state, "picked", None) if state is not None and not isinstance(state, dict) else (state or {}).get(
        "picked")
    clicked = picked_row(old, sig, len(rows))
    shown = clicked if clicked is not None else highlight
    data = {"columns": specs, "rows": rows, "select": select, "height": height, "sig": sig, "search": search,
            "marks": [w for w in (marks or []) if w],
            "selected": shown if shown is not None and shown < len(rows) else -1}
    kwargs: dict[str, Any] = {"key": comp_key, "data": data}
    if select:
        kwargs["on_picked_change"] = lambda: None
    result = _component()(**kwargs)
    if not select:
        return None, None, None
    new = getattr(result, "picked", None)
    now = picked_row(new, sig, len(rows))
    if now is not None:
        return now, pick_nonce(new), pick_order(new, len(rows))
    if clicked is not None:
        return clicked, pick_nonce(old), pick_order(old, len(rows))
    return None, None, None
