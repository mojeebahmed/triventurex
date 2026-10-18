/**
 * board-designer.js
 * Setup screen tab *✏️ Boards* (G20): draw a board path on a grid, see it as
 * a thumbnail, save it as one of "My boards" (localStorage — they then appear
 * in the board picker for that game length), play it straight away, or copy
 * it as a CONFIG.PATH_TEMPLATES line for config.js.
 * Drawing: click a cell for the start, then click cells in a straight line
 * from the end of the path to add a run. Pure parts: js/shared/path-design.js.
 */

const _bd = {
  id: null,            // a saved board being edited, or null for a new one
  name: '', length: 'medium',
  gridRows: 12, gridCols: 12,
  start: null, segments: [],
  hover: null,         // [r, c] under the mouse — previews the next run
};

const _bdDesign = () => ({ name: _bd.name, start: _bd.start, segments: _bd.segments, gridRows: _bd.gridRows, gridCols: _bd.gridCols });
const _bdDefaultGrid = () => ({ rows: CONFIG.GRID_SIZE.rows, cols: CONFIG.GRID_SIZE.cols });

function renderBoardDesigner() {
  if (!document.getElementById('bd-grid')) return;
  document.getElementById('bd-name').value   = _bd.name;
  document.getElementById('bd-length').value = _bd.length;
  document.getElementById('bd-rows').value   = _bd.gridRows;
  document.getElementById('bd-cols').value   = _bd.gridCols;
  _renderBdLoad();
  _renderBdGrid();
  _renderBdSide();
  _renderBdSaved();
}

// ── Grid ─────────────────────────────────────────────────────────────────────────

function _renderBdGrid() {
  const grid  = document.getElementById('bd-grid');
  const cells = designCells(_bd.start, _bd.segments);
  const order = new Map(cells.map((p, i) => [`${p.r},${p.c}`, i]));
  const crowded = designCrowded(cells);

  // Preview of the run the next click would add
  const preview = new Map();
  if (_bd.hover && _bd.start) {
    const end = cells[cells.length - 1];
    const seg = segmentTowards([end.r, end.c], _bd.hover);
    if (seg) {
      const ok = segmentCells(_bdDesign(), seg);
      let { r, c } = end;
      const [dr, dc] = { up: [-1, 0], down: [1, 0], left: [0, -1], right: [0, 1] }[seg.dir];
      for (let i = 0; i < seg.steps; i++) {
        r += dr; c += dc;
        if (!order.has(`${r},${c}`)) preview.set(`${r},${c}`, ok ? 'bd-ok' : 'bd-bad');
      }
    }
  }

  grid.style.gridTemplateColumns = `repeat(${_bd.gridCols}, var(--bd-cell))`;
  let html = '';
  for (let r = 0; r < _bd.gridRows; r++) {
    for (let c = 0; c < _bd.gridCols; c++) {
      const key = `${r},${c}`;
      const i = order.get(key);
      let cls = 'bd-cell', label = '';
      if (i !== undefined) {
        const last = i === cells.length - 1;
        cls += i === 0 ? ' bd-start' : last && cells.length > 1 ? ' bd-finish' : ' bd-path';
        if (last) cls += ' bd-end';
        if (crowded.has(key)) cls += ' bd-crowded';
        label = icon(i === 0 ? 'tileStart' : last && cells.length > 1 ? 'tileFinish' : DIR_ICONS[cells[i].dir]);
      } else if (preview.has(key)) {
        cls += ' ' + preview.get(key);
      }
      html += `<div class="${cls}" data-r="${r}" data-c="${c}">${label}</div>`;
    }
  }
  grid.innerHTML = html;
  document.getElementById('bd-hint').innerHTML = !_bd.start
    ? `Click a cell to place the start ${icon('tileStart')}`
    : `Click a cell in a straight line from the end to add a run · ${icon('boardUndo')} Undo removes the last one`;
}

function _onBdClick(r, c) {
  if (!_bd.start) { _bd.start = [r, c]; _bd.segments = []; _renderBdAll(); return; }
  const cells = designCells(_bd.start, _bd.segments);
  const end = cells[cells.length - 1];
  const seg = segmentTowards([end.r, end.c], [r, c]);
  if (!seg) return;
  if (!segmentCells(_bdDesign(), seg)) { showToast("Can't go there — off the grid or across the path"); return; }
  _bd.segments = addSegment(_bd.segments, seg);
  _renderBdAll();
}

function boardDesignerUndo() {
  if (_bd.segments.length) {
    // Take back the last run (one segment, as drawn — merged runs go back as one)
    _bd.segments = _bd.segments.slice(0, -1);
  } else {
    _bd.start = null;
  }
  _renderBdAll();
}

/** A blank board for the length currently chosen on the New game tab. */
function boardDesignerNew() {
  const len = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  Object.assign(_bd, { id: null, name: '', length: len, start: null, segments: [],
                       gridRows: _bdDefaultGrid().rows, gridCols: _bdDefaultGrid().cols });
  document.getElementById('bd-export').classList.add('hidden');
  renderBoardDesigner();
}

function _renderBdAll() { _renderBdGrid(); _renderBdSide(); }

// ── Side: preview, checks, my boards ─────────────────────────────────────────────

function _renderBdSide() {
  const check = designCheck(_bdDesign(), _bd.length);
  const thumb = document.getElementById('bd-thumb');
  thumb.innerHTML = _bd.start && _bd.segments.length
    ? boardThumbSvg(_bd.length, designTemplate(_bdDesign(), _bdDefaultGrid()))
    : '<span class="bd-thumb-empty">Preview</span>';
  const n = check.spaces;
  document.getElementById('bd-stats').innerHTML = `
    <div class="bd-count"><strong>${n}</strong> space${n === 1 ? '' : 's'} <small>· ${esc(_bd.length)} boards have about ${check.target}</small></div>
    ${check.errors.map(e => `<div class="bd-msg bd-err">• ${esc(e)}</div>`).join('')}
    ${check.warnings.map(w => `<div class="bd-msg bd-warn">${icon('warning')} ${esc(w)}</div>`).join('')}
    ${!check.errors.length && !check.warnings.length ? `<div class="bd-msg bd-good">${icon('resultRight')} Ready to play</div>` : ''}`;
}

function _renderBdSaved() {
  const saved = loadCustomBoards();
  const rows = Object.entries(saved).flatMap(([len, list]) => list.map(t => ({ len, t })));
  document.getElementById('bd-saved').innerHTML = rows.length
    ? rows.map(({ len, t }) => `
        <div class="bd-saved-row ${t.id === _bd.id ? 'active' : ''}">
          <span class="bd-saved-name">${esc(t.name)} <small>${esc(len)}</small></span>
          <button type="button" class="link-btn" data-bd-edit="${esc(t.id)}">Edit</button>
          <button type="button" class="link-btn bd-del" data-bd-delete="${esc(t.id)}">Delete</button>
        </div>`).join('')
    : `<p class="bd-none">No boards yet — draw one and ${icon('save')} Save it.</p>`;
}

/** "Start from…" — copy a built-in board, or open one of mine. */
function _renderBdLoad() {
  const sel = document.getElementById('bd-load');
  const opts = ['<option value="">Start from a board…</option>'];
  for (const [len, list] of Object.entries(CONFIG.PATH_TEMPLATES)) {
    opts.push(`<optgroup label="${esc(len)}">` + list.map((t, i) =>
      `<option value="${esc(len)}:${i}">${t.custom ? iconText('boardCustom') + ' ' : ''}${esc(t.name)}</option>`).join('') + '</optgroup>');
  }
  sel.innerHTML = opts.join('');
}

function _loadBdTemplate(len, t, { asCopy }) {
  Object.assign(_bd, {
    id: asCopy ? null : t.id, length: len,
    name: asCopy ? `${_pathLabel(t)} (copy)` : t.name,
    gridRows: t.gridRows ?? _bdDefaultGrid().rows, gridCols: t.gridCols ?? _bdDefaultGrid().cols,
    start: [...t.start], segments: t.segments.map(s => [...s]),
  });
  document.getElementById('bd-export').classList.add('hidden');
  renderBoardDesigner();
}

// ── Save / play / copy ───────────────────────────────────────────────────────────

/** Save as one of "My boards". Returns the board's index in PATH_TEMPLATES[length], or -1. */
function saveDesignedBoard({ quiet = false } = {}) {
  const check = designCheck(_bdDesign(), _bd.length);
  if (check.errors.length) { showToast(check.errors[0]); return -1; }
  const saved = loadCustomBoards();
  for (const len of Object.keys(saved)) saved[len] = saved[len].filter(t => t.id !== _bd.id);   // length may have changed
  _bd.id ??= `b${Date.now().toString(36)}`;
  saved[_bd.length].push({ id: _bd.id, ...designTemplate(_bdDesign(), _bdDefaultGrid()) });
  saveCustomBoards(saved);
  applyCustomBoards();
  _renderBdSaved();
  _renderBdLoad();
  const len = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  renderBoardPicker(len);                // the New game tab shows it too
  if (!quiet) showToast(`Saved — it's in the ${_bd.length} boards`, undefined, 'save');
  return CONFIG.PATH_TEMPLATES[_bd.length].findIndex(t => t.id === _bd.id);
}

/** Save, then pick it on the New game tab (length + board) — ready to Start. */
function playDesignedBoard() {
  const index = saveDesignedBoard({ quiet: true });
  if (index < 0) return;
  const radio = document.querySelector(`input[name="gameLength"][value="${_bd.length}"]`);
  if (radio) radio.checked = true;
  renderBoardPicker(_bd.length, String(index));
  updateSetupValues();
  showSetupTab('new');
  showToast('Board chosen — press Start', undefined, 'playBoard');
}

function copyBoardTemplate() {
  if (!_bd.start || !_bd.segments.length) { showToast('Draw a board first'); return; }
  const text = templateText(designTemplate({ ..._bdDesign(), name: _bd.name || 'My board' }, _bdDefaultGrid()));
  const box = document.getElementById('bd-export');
  box.value = `// Paste into CONFIG.PATH_TEMPLATES.${_bd.length} in js/shared/config.js\n${text}`;
  box.classList.remove('hidden');
  box.select();
  navigator.clipboard?.writeText(text).then(() => showToast('Copied', undefined, 'copy'), () => {});
}

function _deleteSavedBoard(id) {
  const saved = loadCustomBoards();
  const name = Object.values(saved).flat().find(t => t.id === id)?.name;
  if (!confirm(`Delete "${name}"?`)) return;
  // The New game tab may have one of my boards chosen: its index shifts → back to Random
  const len = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  const chosen = CONFIG.PATH_TEMPLATES[len]?.[Number(document.getElementById('path-select')?.value)];
  for (const l of Object.keys(saved)) saved[l] = saved[l].filter(t => t.id !== id);
  saveCustomBoards(saved);
  applyCustomBoards();
  if (_bd.id === id) _bd.id = null;    // keep the drawing; saving makes a new one
  renderBoardPicker(len, chosen?.custom ? 'random' : undefined);
  updateSetupValues();
  renderBoardDesigner();
}

// ── Wiring ───────────────────────────────────────────────────────────────────────

function initBoardDesigner() {
  const grid = document.getElementById('bd-grid');
  if (!grid) return;
  _bd.gridRows = _bdDefaultGrid().rows;
  _bd.gridCols = _bdDefaultGrid().cols;
  _bd.length = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';

  grid.addEventListener('click', e => {
    const cell = e.target.closest('.bd-cell');
    if (cell) _onBdClick(Number(cell.dataset.r), Number(cell.dataset.c));
  });
  grid.addEventListener('mouseover', e => {
    const cell = e.target.closest('.bd-cell');
    if (!cell) return;
    const h = [Number(cell.dataset.r), Number(cell.dataset.c)];
    if (_bd.hover?.[0] === h[0] && _bd.hover?.[1] === h[1]) return;
    _bd.hover = h;
    _renderBdGrid();
  });
  grid.addEventListener('mouseleave', () => { _bd.hover = null; _renderBdGrid(); });

  document.getElementById('bd-name').addEventListener('input', e => { _bd.name = e.target.value; _renderBdSide(); });
  document.getElementById('bd-length').addEventListener('change', e => { _bd.length = e.target.value; _renderBdSide(); });
  const resize = () => {
    const clamp = v => Math.min(PD_GRID.max, Math.max(PD_GRID.min, parseInt(v, 10) || 12));
    const rows = clamp(document.getElementById('bd-rows').value);
    const cols = clamp(document.getElementById('bd-cols').value);
    // The path must still fit — otherwise keep the old size
    const fits = designCells(_bd.start, _bd.segments).every(p => p.r < rows && p.c < cols);
    if (!fits) { showToast('The path doesn’t fit in a smaller grid'); renderBoardDesigner(); return; }
    _bd.gridRows = rows; _bd.gridCols = cols;
    renderBoardDesigner();
  };
  document.getElementById('bd-rows').addEventListener('change', resize);
  document.getElementById('bd-cols').addEventListener('change', resize);
  document.getElementById('bd-load').addEventListener('change', e => {
    const [len, i] = e.target.value.split(':');
    const t = CONFIG.PATH_TEMPLATES[len]?.[Number(i)];
    if (t) _loadBdTemplate(len, t, { asCopy: !t.custom });
  });
  document.getElementById('bd-saved').addEventListener('click', e => {
    const editId = e.target.dataset.bdEdit, delId = e.target.dataset.bdDelete;
    if (delId) { _deleteSavedBoard(delId); return; }
    if (!editId) return;
    const [len, t] = Object.entries(loadCustomBoards()).flatMap(([l, list]) => list.map(x => [l, x])).find(([, x]) => x.id === editId) || [];
    if (t) _loadBdTemplate(len, t, { asCopy: false });
  });
}
