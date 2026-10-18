/**
 * js/academy/academy.js — Triventurex Academy (academy.html), page shell.
 *
 * Loads ONE edition (config.js + questions.js as plain <script>s, so the page
 * also works opened from disk), keeps the shared filter (topic tree,
 * difficulty, search) and switches between the modes registered by modes.js.
 * Changing the edition reloads the page with ?edition=<id>; the mode lives in
 * the #hash. Marks and review ticks: js/shared/marks.js (shared with the game).
 */

const LS_ACADEMY_EDITION = 'triventurex_academy_edition';

let _activeEditionId = null;
function getActiveEditionId() { return _activeEditionId; }

/** Filter shared by every question mode. */
const ac = { path: [], diff: 'all', text: '', mode: 'explore' };

/** Modes, registered by modes.js: { id, icon, label, filter: bool, render(main, questions) } */
const AC_MODES = [];
let _acCleanup = null;       // a mode's timers / key handlers, undone when leaving it

function registerMode(mode) { AC_MODES.push(mode); }

/** Called by a mode that starts something to stop later (a timer, a key listener). */
function onLeaveMode(fn) { _acCleanup = fn; }

// ── Edition ─────────────────────────────────────────────────────────────────────

function _pickEditionId() {
  const ids = (window.TRIVENTUREX_EDITIONS || []).map(e => e.id);
  const fromUrl = new URLSearchParams(location.search).get('edition');
  let saved = null, lastGame = null;
  try { saved = localStorage.getItem(LS_ACADEMY_EDITION); lastGame = localStorage.getItem('triventurex_edition'); } catch {}
  return [fromUrl, saved, lastGame, ids[0]].find(id => id && ids.includes(id));
}

function _loadScript(src) {
  return new Promise(resolve => {
    const el = document.createElement('script');
    el.src = src;
    el.onload = resolve;
    el.onerror = () => { console.warn(`Academy: could not load ${src}`); resolve(); };
    document.head.appendChild(el);
  });
}

async function _loadEdition(id) {
  _activeEditionId = id;
  try { localStorage.setItem(LS_ACADEMY_EDITION, id); } catch {}
  window.EDITION_CONFIG = null;
  window.QUESTIONS_DATA = [];
  await _loadScript(`game_editions/${id}/config.js`);
  await _loadScript(`game_editions/${id}/questions.js`);
  mergeEditionConfig(CONFIG, window.EDITION_CONFIG);
  applyEditionColors(CONFIG);
  const name = CONFIG.GAME?.editionName ?? id;
  document.title = `${name} — Triventurex Academy`;
}

function _renderEditionPicker() {
  const sel = document.getElementById('ac-edition');
  sel.innerHTML = (window.TRIVENTUREX_EDITIONS || []).map(e =>
    `<option value="${esc(e.id)}" ${e.id === _activeEditionId ? 'selected' : ''}>${esc(e.icon)} ${esc(e.name)}</option>`).join('');
  sel.onchange = () => {
    try { localStorage.setItem(LS_ACADEMY_EDITION, sel.value); } catch {}
    const url = new URL(location.href);
    url.searchParams.set('edition', sel.value);
    location.href = url.toString();       // reload: a clean page for the new edition (keeps the #mode)
  };
}

// ── Filter (topic tree, difficulty, search) ─────────────────────────────────────

const acQuestions = () => window.QUESTIONS_DATA || [];

/** The questions the filter selects (every question mode starts from these). */
function filteredQuestions(extra = {}) {
  return filterQuestions(acQuestions(), { path: ac.path, text: ac.text, diff: ac.diff, ...extra });
}

const _acLabel = name => name || 'Other';

function _renderTree() {
  const node = (n, path, depth) => {
    const active = path.length === ac.path.length && path.every((v, i) => v === ac.path[i]);
    return `<button type="button" class="qx-node depth-${depth} ${active ? 'active' : ''}" data-path="${esc(JSON.stringify(path))}">
              ${esc(_acLabel(n.name))} <small>${n.count}</small></button>` +
      n.children.map(c => node(c, [...path, c.name], depth + 1)).join('');
  };
  const all = `<button type="button" class="qx-node ${ac.path.length ? '' : 'active'}" data-path="[]">
                 All questions <small>${acQuestions().length}</small></button>`;
  document.getElementById('ac-tree').innerHTML = all + questionTree(acQuestions()).map(n => node(n, [n.name], 0)).join('');
  const n = filteredQuestions().length;
  document.getElementById('ac-filter-summary').textContent =
    `· ${ac.path.length ? ac.path.map(_acLabel).join(' › ') : 'All'} · ${n} question${n === 1 ? '' : 's'}`;
}

function _initFilter() {
  document.getElementById('ac-tree').addEventListener('click', e => {
    const btn = e.target.closest('[data-path]');
    if (!btn) return;
    ac.path = JSON.parse(btn.dataset.path);
    _filterChanged();
    if (window.matchMedia('(max-width: 720px)').matches) document.getElementById('ac-filter').open = false;
  });
  document.getElementById('ac-diff').addEventListener('change', e => { ac.diff = e.target.value; _filterChanged(); });
  let t = null;
  document.getElementById('ac-search').addEventListener('input', e => {
    clearTimeout(t);
    t = setTimeout(() => { ac.text = e.target.value; _filterChanged(); }, 200);
  });
  // Phones: the filter starts folded so the mode is visible
  if (window.matchMedia('(max-width: 720px)').matches) document.getElementById('ac-filter').open = false;
}

function _filterChanged() {
  _renderTree();
  showMode(ac.mode);
}

// ── Modes ───────────────────────────────────────────────────────────────────────

function _renderModeTabs() {
  document.getElementById('ac-modes').innerHTML = AC_MODES.map(m =>
    `<button type="button" role="tab" class="ac-mode-btn ${m.id === ac.mode ? 'active' : ''}" data-mode="${m.id}"
             aria-selected="${m.id === ac.mode}" title="${esc(m.hint || '')}">${m.icon} ${esc(m.label)}</button>`).join('');
}

function showMode(id) {
  const mode = AC_MODES.find(m => m.id === id) || AC_MODES[0];
  if (_acCleanup) { try { _acCleanup(); } catch {} _acCleanup = null; }
  ac.mode = mode.id;
  if (location.hash !== `#${mode.id}`) history.replaceState(null, '', `#${mode.id}`);
  document.body.classList.toggle('ac-no-filter', !mode.filter);
  _renderModeTabs();
  const main = document.getElementById('ac-main');
  main.scrollTop = 0;
  main.innerHTML = '';
  mode.render(main, mode.filter ? filteredQuestions() : acQuestions());
}

/** "Not enough questions" message for a mode, with a hint to widen the filter. */
function emptyHtml(what) {
  return `<div class="ac-empty"><p>${what}</p><p>Choose a wider topic or "Easy + hard" on the left.</p></div>`;
}

/** Copy text to the clipboard, or show it to copy by hand. */
function copyText(text, okMessage) {
  const box = document.getElementById('ac-export');
  const show = () => { box.value = text; box.classList.remove('hidden'); box.focus(); box.select(); };
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).then(() => alert(okMessage), show);
  else show();
}

// ── Start ───────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  startIcons();   // emoji + control icons from the bundled sets (js/shared/icons.js)
  const id = _pickEditionId();
  if (!id) { document.getElementById('ac-main').innerHTML = emptyHtml('No editions found.'); return; }
  await _loadEdition(id);
  _renderEditionPicker();
  _initFilter();
  _renderTree();
  document.getElementById('ac-modes').addEventListener('click', e => {
    const btn = e.target.closest('[data-mode]');
    if (btn) showMode(btn.dataset.mode);
  });
  showMode(location.hash.slice(1) || 'explore');
});
