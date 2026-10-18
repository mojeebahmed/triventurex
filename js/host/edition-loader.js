/**
 * edition-loader.js
 * Edition loading: injects an edition's config/questions/deeds, merges its
 * config into CONFIG, renders the edition picker, applies colours + branding.
 */

// ── Loading ─────────────────────────────────────────────────────────────────────

let _activeEditionId = null;

/** Active edition id for other scripts (a top-level `let` is not on `window`). */
function getActiveEditionId() { return _activeEditionId; }

function _resetToEngineDefaults() {
  Object.assign(CONFIG.GAME,             _ENGINE_DEFAULTS.GAME);
  Object.assign(CONFIG.COLORS,           _ENGINE_DEFAULTS.COLORS);
  Object.assign(CONFIG.BOARD_BACKGROUND, _ENGINE_DEFAULTS.BOARD_BACKGROUND);
  Object.assign(CONFIG.SCORE_VALUES,     _ENGINE_DEFAULTS.SCORE_VALUES);
  CONFIG.FINISH_BONUS = [..._ENGINE_DEFAULTS.FINISH_BONUS];
  CONFIG.AWARDS = JSON.parse(JSON.stringify(_ENGINE_DEFAULTS.AWARDS));
  CONFIG.LANDMARKS = [];
  CONFIG.EDITION_SPACE_DISTRIBUTION = null;
  for (const [type, defaults] of Object.entries(_ENGINE_DEFAULTS.SPACE_INFO)) {
    if (CONFIG.SPACE_INFO[type]) Object.assign(CONFIG.SPACE_INFO[type], defaults);
  }
}

function _mergeEditionConfig() { mergeEditionConfig(CONFIG, window.EDITION_CONFIG, _activeEditionId); }

async function loadEdition(editionId) {
  if (!editionId) return;
  if (_activeEditionId === editionId) return;
  _resetToEngineDefaults();
  window.EDITION_CONFIG   = null;
  window.QUESTIONS_DATA = [];
  window.DEEDS_DATA     = [];
  window.ACTIONS_DATA   = [];

  // Load JS files (config.js required; questions.js / deeds.js / actions.js are
  // fallbacks used when the HTTP server isn't running and CSV fetch would fail).
  // An edition without actions.js simply has no digital action cards.
  const files = ['config.js', 'questions.js', 'deeds.js', 'actions.js'];
  for (const file of files) {
    const src = `game_editions/${editionId}/${file}`;
    await new Promise((resolve) => {
      document.querySelectorAll(`script[data-tx="${src}"]`).forEach(s => s.remove());
      const el = document.createElement('script');
      el.setAttribute('data-tx', src);
      el.src = src + '?_=' + Date.now();
      el.onload  = resolve;
      el.onerror = () => { console.warn(`Edition file not found: ${src}`); resolve(); };
      document.head.appendChild(el);
    });
  }

  // Try to load CSV files via fetch (requires HTTP server — python3 -m http.server 8080).
  // If successful they REPLACE the JS-loaded data, so CSV is the primary content source.
  // If fetch fails (file:// protocol) the JS fallback data is used silently.
  await _loadEditionCSV(editionId);

  _activeEditionId = editionId;
  _mergeEditionConfig();
  _populateCategoryFilter();
  loadSetupRules();          // this edition's rules for the next game (G12)
  try { localStorage.setItem('triventurex_edition', editionId); } catch {}
}

/**
 * Try to fetch and parse questions.csv and deeds.csv for the given edition.
 * Overrides JS-loaded QUESTIONS_DATA / DEEDS_DATA if CSV has content.
 * Fails silently when running from file:// (fetch not allowed).
 */
// ── CSV content ─────────────────────────────────────────────────────────────────

async function _loadEditionCSV(editionId) {
  const get = async (url) => {
    try { const r = await fetch(url); return r.ok ? r.text() : null; }
    catch { return null; }
  };

  const qText = await get(`game_editions/${editionId}/questions.csv`);
  if (qText) {
    const parsed = _parseQuestionsCSV(qText);
    if (parsed.length) { window.QUESTIONS_DATA = parsed; }
  }

  const dText = await get(`game_editions/${editionId}/deeds.csv`);
  if (dText) {
    const parsed = _parseDeedsCSV(dText);
    if (parsed.length) { window.DEEDS_DATA = parsed; }
  }

  const aText = await get(`game_editions/${editionId}/actions.csv`);
  if (aText) {
    const parsed = _parseActionsCSV(aText);
    if (parsed.length) { window.ACTIONS_DATA = parsed; }
  }

  // General action cards (C4) — the same for every edition
  const gText = await get('game_editions/shared/actions.csv');
  if (gText) {
    const parsed = _parseActionsCSV(gText);
    if (parsed.length) { window.GENERAL_ACTIONS_DATA = parsed; }
  }
}

// ── Edition picker ──────────────────────────────────────────────────────────────

function renderEditionPicker(currentId) {
  const section = document.getElementById('edition-section');
  const picker  = document.getElementById('edition-picker');
  if (!picker) return;
  const editions = window.TRIVENTUREX_EDITIONS || [];
  if (editions.length <= 1) { if (section) section.style.display = 'none'; return; }
  if (section) section.style.display = '';
  picker.innerHTML = editions.map(t => `
    <div class="edition-card ${t.id === currentId ? 'selected' : ''}"
         style="${t.id === currentId ? `border-color:${t.accentColor};background:${t.accentColor}18` : ''}"
         onclick="onEditionPicked('${t.id}')">
      <div class="edition-card-icon">${t.icon}</div>
      <div class="edition-card-name">${t.name}</div>
      <div class="edition-card-desc">${t.description}</div>
    </div>`).join('');
}

async function onEditionPicked(editionId) {
  if (editionId === _activeEditionId) { onSetupChoice('edition-section'); return; }
  const picker = document.getElementById('edition-picker');
  if (picker) picker.style.opacity = '0.5';
  await loadEdition(editionId);
  _applyColors(); _applyBranding();
  renderEditionPicker(editionId);
  const len = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  populatePathSelector(len);
  if (picker) picker.style.opacity = '1';
  resetQuestionExplorer();            // 📚 Questions tab: this edition's questions + marks
  onSetupChoice('edition-section');   // heading shows the edition; move on to length
}

/**
 * Apply CONFIG.COLORS and CONFIG.SPACE_INFO colours as CSS custom properties.
 * This is the single handoff point: config.js controls all colours,
 * CSS rules read them via var(--name) — no hardcoded hex in CSS needed.
 */
// ── Colours + branding ──────────────────────────────────────────────────────────

function _applyColors() { applyEditionColors(CONFIG); }

/**
 * Inject CONFIG.GAME branding into the setup screen and document title.
 * Called once on load and can be re-called if the edition changes in future.
 */
function _applyBranding() {
  const g = CONFIG.GAME || {};
  const engine   = g.engineName || 'Triventurex';
  const edition  = g.editionName  || '';
  const mark     = icon(g.editionIcon || 'appLogo') || esc(g.editionIcon);   // a name or an emoji
  const subtitle = g.subtitle   || '';

  document.title = edition ? `${engine} — ${edition}` : engine;

  const set = (id, text, isHtml = false) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (isHtml) el.innerHTML = text;
    else el.textContent = text;
  };

  set('brand-engine',       engine);
  set('brand-edition',        edition ? `${mark} ${esc(edition)}` : '', true);
  set('brand-subtitle',     subtitle);
  set('end-screen-message', g.endScreenMessage || 'All players have reached the finish!');
}
