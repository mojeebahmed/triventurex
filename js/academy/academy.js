/**
 * js/academy/academy.js — Triventurex Academy (academy.html), page shell.
 *
 * Loads ONE edition (config.js + questions.js as plain <script>s, so the page
 * also works opened from disk), keeps the shared filter (topic tree,
 * difficulty, search) and switches between the modes registered by modes.js.
 * Changing the edition reloads the page with ?edition=<id>; the mode lives in
 * the #hash. Marks and review ticks: js/shared/marks.js (shared with the game).
 *
 * Phones (isPhone(), same width as the CSS): the filter opens as a sheet from
 * the bottom, and modes marked `phone: false` (print, review) move from the
 * tabs to a More sheet — learning comes first on a small screen.
 *
 * As an app (served over http(s), e.g. GitHub Pages; not from disk): registers
 * academy-sw.js (scope ./academy — only this page) so the Academy installs from
 * the browser and works offline; More offers Install / Save photos for offline.
 */

const LS_ACADEMY_EDITION = 'triventurex_academy_edition';

let _activeEditionId = null;
function getActiveEditionId() { return _activeEditionId; }

/** Filter shared by every question mode. */
const ac = { path: [], diff: 'all', text: '', mode: 'explore' };

/** Same width as the phone layout in css/academy.css. */
const AC_PHONE_QUERY = '(max-width: 720px)';
const isPhone = () => window.matchMedia(AC_PHONE_QUERY).matches;

/** Modes, registered by modes.js: { id, icon, label, filter: bool, phone?: false, render(main, questions) } */
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
  mergeEditionConfig(CONFIG, window.EDITION_CONFIG, id);
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
  document.getElementById('ac-filter-done').textContent = `Show ${n} question${n === 1 ? '' : 's'}`;
}

function _initFilter() {
  document.getElementById('ac-tree').addEventListener('click', e => {
    const btn = e.target.closest('[data-path]');
    if (!btn) return;
    ac.path = JSON.parse(btn.dataset.path);
    _filterChanged();   // on a phone the sheet stays open: its button shows the new count
  });
  document.getElementById('ac-diff').addEventListener('change', e => { ac.diff = e.target.value; _filterChanged(); });
  let t = null;
  document.getElementById('ac-search').addEventListener('input', e => {
    clearTimeout(t);
    t = setTimeout(() => { ac.text = e.target.value; _filterChanged(); }, 200);
  });
  // Phones: the filter starts folded so the mode is visible; opening it opens the sheet
  const filter = document.getElementById('ac-filter');
  if (isPhone()) filter.open = false;
  filter.addEventListener('toggle', () => {
    if (filter.open && isPhone()) _showBackdrop(true);
    else if (!filter.open && document.getElementById('ac-more').classList.contains('hidden')) _showBackdrop(false);
  });
}

// ── Sheets (phones): the filter and the More list slide up from the bottom ──────

function _showBackdrop(on) {
  document.getElementById('ac-backdrop').classList.toggle('hidden', !on);
  document.body.classList.toggle('ac-sheet-open', on);
}

function closeSheets() {
  if (isPhone()) document.getElementById('ac-filter').open = false;
  document.getElementById('ac-more').classList.add('hidden');
  _showBackdrop(false);
}

// ── As an app: install + offline (academy-sw.js) ────────────────────────────────

/** Same name as ACADEMY_CACHE in academy-sw.js (test/academy-offline.test.js checks it). */
const ACADEMY_CACHE = 'tx-academy-v1';
let _installPrompt = null;   // Chrome / Android: the browser's install prompt, kept for our button

const offlineCapable = () => 'serviceWorker' in navigator && /^https?:$/.test(location.protocol) && window.isSecureContext;
const _isStandalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const _isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

function _startApp() {
  if (!offlineCapable()) return;
  navigator.serviceWorker.register('academy-sw.js', { scope: './academy' })
    .catch(err => console.warn('Academy: offline mode is not available', err));
  window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); _installPrompt = e; });
  window.addEventListener('appinstalled', () => { _installPrompt = null; });
}

/** The place photos of the edition on screen. */
const _photoUrls = () => (CONFIG.LANDMARKS || []).map(l => l.image).filter(Boolean);

/** More → "Use it like an app": install (or how to, on an iPhone) + save photos. */
function _appSectionHtml() {
  if (!offlineCapable()) return '';
  let install = '';
  if (!_isStandalone()) {
    if (_installPrompt) {
      install = `<button type="button" class="ac-more-item" data-app="install">
          <span class="ac-more-icon">${icon('installApp')}</span>
          <span><strong>Install the Academy</strong><small>Opens from your home screen like an app, and works without internet</small></span></button>`;
    } else if (_isIos()) {
      install = `<div class="ac-more-item ac-more-static">
          <span class="ac-more-icon">${icon('shareIos')}</span>
          <span><strong>Add to your home screen</strong><small>In Safari, tap Share, then <b>Add to Home Screen</b>. It then opens like an app and works without internet.</small></span></div>`;
    }
  }
  const photos = _photoUrls().length ? `<button type="button" class="ac-more-item" data-app="photos">
      <span class="ac-more-icon">${icon('saveOffline')}</span>
      <span><strong>Save photos for offline</strong><small id="ac-photos-status">The ${_photoUrls().length} photos in Places, for ${esc(CONFIG.GAME?.editionName ?? 'this edition')} — questions are saved already</small></span></button>` : '';
  if (!install && !photos) return '';
  return `<h3 class="ac-more-title">${icon('installApp')} Use it like an app</h3><div class="ac-more-list">${install}${photos}</div>`;
}

async function _onAppAction(action, btn) {
  if (action === 'install' && _installPrompt) {
    _installPrompt.prompt();
    try { await _installPrompt.userChoice; } catch {}
    _installPrompt = null;
    closeSheets();
  }
  if (action === 'photos') {
    const status = document.getElementById('ac-photos-status');
    const urls = _photoUrls();
    btn.disabled = true;
    let done = 0, failed = 0;
    try {
      const cache = await caches.open(ACADEMY_CACHE);
      for (const url of urls) {
        try { if (!(await cache.match(url))) await cache.add(url); } catch { failed++; }
        status.textContent = `Saving… ${++done} of ${urls.length}`;
      }
      status.textContent = failed ? `Saved ${urls.length - failed} of ${urls.length} photos — try again with a better connection` : 'All photos are saved on this device';
    } catch { status.textContent = 'Could not save the photos on this device'; }
    btn.disabled = false;
  }
}

/** More (phones): the modes that work best on a computer, and the app options. */
function _openMore() {
  const more = document.getElementById('ac-more');
  const desk = AC_MODES.filter(m => m.phone === false);
  more.innerHTML = `
    <div class="ac-bsheet-head">
      <strong>${icon('computerOnly')} Best on a computer</strong>
      <button type="button" class="ac-bsheet-close" data-close-sheet aria-label="Close">${icon('close')}</button>
    </div>
    <p class="ac-hint">These work on a phone too, but they are easier on a bigger screen.</p>
    <div class="ac-more-list">${desk.map(m => `
      <button type="button" class="ac-more-item" data-mode="${m.id}">
        <span class="ac-more-icon">${icon(m.icon)}</span>
        <span><strong>${esc(m.label)}</strong><small>${esc(m.hint || '')}</small></span>
      </button>`).join('')}</div>
    ${_appSectionHtml()}`;
  more.classList.remove('hidden');
  _showBackdrop(true);
}

function _filterChanged() {
  _renderTree();
  showMode(ac.mode);
}

// ── Modes ───────────────────────────────────────────────────────────────────────

/** Tabs: every mode on a computer; on a phone the learning modes (+ the one on
 *  screen) and More. The tab on screen is scrolled into view. */
function _renderModeTabs() {
  const nav = document.getElementById('ac-modes');
  const phone = isPhone();
  const shown = AC_MODES.filter(m => !phone || m.phone !== false || m.id === ac.mode);
  nav.innerHTML = shown.map(m =>
    `<button type="button" role="tab" class="ac-mode-btn ${m.id === ac.mode ? 'active' : ''}" data-mode="${m.id}"
             aria-selected="${m.id === ac.mode}" title="${esc(m.hint || '')}">${icon(m.icon)} ${esc(m.label)}</button>`).join('') +
    (phone && AC_MODES.some(m => m.phone === false)
      ? `<button type="button" class="ac-mode-btn ac-more-btn" data-more title="More">${icon('moreModes')} More</button>` : '');
  const active = nav.querySelector('.ac-mode-btn.active');
  if (active) nav.scrollLeft = active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2;
  _updateTabFades();
}

/** Fade the edge of the tab row where more tabs are hidden. */
function _updateTabFades() {
  const nav = document.getElementById('ac-modes');
  nav.classList.toggle('fade-left', nav.scrollLeft > 4);
  nav.classList.toggle('fade-right', nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 4);
}

/** The help for the mode on screen (js/shared/help.js); each links to the Academy's general help. */
const academyHelpTopic = () => (HELP[`academy-${ac.mode}`] ? `academy-${ac.mode}` : 'academy');

function showMode(id) {
  const mode = AC_MODES.find(m => m.id === id) || AC_MODES[0];
  if (_acCleanup) { try { _acCleanup(); } catch {} _acCleanup = null; }
  if (mode.id !== ac.mode) closeSheets();   // a filter change redraws the same mode: the sheet stays open
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
  return `<div class="ac-empty"><p>${what}</p><p>Choose a wider topic or "Easy + hard" in <b>Choose what to learn</b>.</p></div>`;
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
  startHelp(academyHelpTopic);   // ? button + the ? key (js/shared/help.js)
  _startApp();                   // install + offline (academy-sw.js)
  const id = _pickEditionId();
  if (!id) { document.getElementById('ac-main').innerHTML = emptyHtml('No editions found.'); return; }
  await _loadEdition(id);
  _renderEditionPicker();
  _initFilter();
  _renderTree();
  const nav = document.getElementById('ac-modes');
  nav.addEventListener('click', e => {
    if (e.target.closest('[data-more]')) { _openMore(); return; }
    const btn = e.target.closest('[data-mode]');
    if (btn) showMode(btn.dataset.mode);
  });
  nav.addEventListener('scroll', _updateTabFades, { passive: true });
  document.getElementById('ac-more').addEventListener('click', e => {
    const app = e.target.closest('[data-app]');
    if (app) { _onAppAction(app.dataset.app, app); return; }
    const btn = e.target.closest('[data-mode]');
    if (btn) { showMode(btn.dataset.mode); closeSheets(); }
  });
  document.addEventListener('click', e => { if (e.target.closest('[data-close-sheet]')) { e.preventDefault(); closeSheets(); } });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && document.body.classList.contains('ac-sheet-open')) closeSheets(); });
  // Turning a tablet or resizing a window across the phone width: tabs and filter follow
  window.matchMedia(AC_PHONE_QUERY).addEventListener?.('change', () => {
    closeSheets();
    document.getElementById('ac-filter').open = !isPhone();
    _renderModeTabs();
  });
  showMode(location.hash.slice(1) || 'explore');
});
