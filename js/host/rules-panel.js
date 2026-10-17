/**
 * rules-panel.js
 * Rules for the next game and the setup screen's Rules tab (G12).
 *
 * gameRules() is what the rest of the host code reads:
 *   during a game → state.rules (copied at start, saved with the game)
 *   on the setup screen → the rules for the next game (_setupRules)
 * The pure model (defaults → preset → changes) lives in js/shared/rules.js.
 */

const LS_RULES_PREFIX = 'triventurex_rules_';   // + editionId → { preset, changes }

let _setupRules = null;   // rules for the next game, for the active edition
let _rulesDraft = null;   // what the Rules tab is editing (saved on every change)
let _rulesRendering = false; // true while the Rules tab is being redrawn
let _rulesSection = 'scoring'; // which side tab is open

/** The rules in force: the running game's, else the ones set up for the next game. */
function gameRules() {
  return (typeof state !== 'undefined' && state.rules) || _setupRules || buildRules(CONFIG, null, _rulesOpts());
}

/** A copy of the rules for a new game (so later panel edits don't touch it). */
function rulesForNewGame() {
  return JSON.parse(JSON.stringify(_setupRules || gameRules()));
}

function _hasActionCards() { return (window.ACTIONS_DATA || []).length > 0; }
function _rulesOpts() { return { hasActionCards: _hasActionCards() }; }
const _clone = o => JSON.parse(JSON.stringify(o));

// ── Storage (per edition: only the preset + what differs from it) ──────────

function _loadStoredRules(editionId) {
  try { return JSON.parse(localStorage.getItem(LS_RULES_PREFIX + editionId)); } catch { return null; }
}

function _storeRules(editionId, rules) {
  const changes = diffRules(rules, presetBase(CONFIG, rules.preset, _rulesOpts()));
  try { localStorage.setItem(LS_RULES_PREFIX + editionId, JSON.stringify({ preset: rules.preset, changes })); } catch {}
}

/** Before G12, exact finish + question tracking were global settings — carry them over once. */
function _rulesFromOldSettings() {
  const s = _loadGameSettings();
  if (!s) return null;
  const changes = {};
  if (s.exactFinish === false)        changes.turns     = { exactFinish: false };
  if (s.questionTracking === 'game')  changes.questions = { tracking: 'game' };
  return { preset: 'family', changes };
}

/** After an edition loads: rebuild the next game's rules for it. */
function loadSetupRules() {
  const ed = getActiveEditionId();
  const stored = _loadStoredRules(ed) ?? _rulesFromOldSettings();
  _setupRules = buildRules(CONFIG, stored, _rulesOpts());
  renderRulesSummary();
  if (!document.getElementById('setup-tab-rules')?.classList.contains('hidden')) renderRulesTab();
}

// ── Summary line on the setup screen ────────────────────────────────────────

function _changedCount(rules) {
  return countChanges(diffRules(rules, presetBase(CONFIG, rules.preset, _rulesOpts())));
}

/** The "N" badge on the Rules tab + the footer summary on the setup screen. */
function renderRulesSummary() {
  const badge = document.getElementById('rules-tab-badge');
  if (!_setupRules) return;
  const n = _changedCount(_setupRules);
  if (badge) { badge.textContent = n ? String(n) : ''; badge.classList.toggle('hidden', !n); }
  if (typeof renderSetupSummary === 'function') renderSetupSummary();
}

// ── The panel ───────────────────────────────────────────────────────────────

/**
 * What the panel shows, in order. One entry per setting; `key` is the path in
 * the rules object (see defaultRules in js/shared/rules.js).
 */
function _rulesSchema() {
  const pts = CONFIG.GAME?.pointsName ?? 'pts';
  const kinds = CONFIG.ACTION_KINDS || {};
  return [
    { id: 'scoring', title: '🏆 Scoring', fields: [
      { group: 'Questions', key: 'scoring.questionEasy', type: 'number', label: 'Easy question', unit: pts },
      { group: 'Questions', key: 'scoring.questionHard', type: 'number', label: 'Hard question', unit: pts },
      { group: 'Action cards', key: 'scoring.actionPerformer', type: 'number', label: 'Performer', unit: pts },
      { group: 'Action cards', key: 'scoring.actionGuesser',   type: 'number', label: 'First correct guesser', unit: pts },
      { group: 'Landmarks', hint: 'Points by how a player gets there — 0 = just information, negative is allowed',
        key: 'scoring.landmarkRoll', type: 'number', label: 'Landing on it by a roll', unit: pts },
      { group: 'Landmarks', key: 'scoring.landmarkGoodDeed', type: 'number', label: 'Sent there by a good deed', unit: pts },
      { group: 'Landmarks', key: 'scoring.landmarkBadDeed',  type: 'number', label: 'Sent back there by a bad deed', unit: pts },
      { group: 'Finishing', key: 'scoring.finishBonus', type: 'select', label: 'Finish bonus', options: [
          ['standard', `Standard (${(CONFIG.FINISH_BONUS || []).join(' / ')})`],
          ['small', 'Small (5 / 3 / 2 / 1)'], ['off', 'Off'] ] },
      { group: 'Finishing', key: 'scoring.negativeScores', type: 'toggle', label: 'Allow negative scores',
        hint: 'Off: scores never go below 0' },
    ] },
    { id: 'questions', title: '❓ Questions', fields: [
      { group: 'Asking', key: 'questions.difficulty', type: 'select', label: 'Difficulty', options: [
          ['choose', 'Player chooses'], ['easy', 'Always easy'], ['hard', 'Always hard'] ] },
      { group: 'Asking', key: 'questions.tracking', type: 'select', label: 'Avoid repeated questions', options: [
          ['session', 'Remember across games'], ['game', 'Reset every game'] ] },
      { group: 'Timer', key: 'questions.timerAuto',    type: 'toggle', label: 'Start the timer automatically' },
      { group: 'Timer', key: 'questions.timerSeconds', type: 'number', label: 'Time per question', unit: 'seconds' },
    ] },
    { id: 'actions', title: '🎬 Action cards', fields: [
      { group: 'Cards', key: 'actions.cards', type: 'select', label: 'Cards', options: [
          ['digital', _hasActionCards() ? 'Digital cards' : 'Digital (none in this edition)'],
          ['physical', 'Physical deck'] ],
        disabled: v => v === 'digital' && !_hasActionCards(),
        hint: 'A digital card can always be swapped for a physical one during play' },
      { group: 'Cards', key: 'actions.kinds', type: 'kinds', label: 'Kinds allowed',
        options: Object.entries(kinds).map(([k, v]) => [k, `${v.icon} ${v.label}`]) },
      { group: 'Timer', key: 'actions.timerSeconds', type: 'number', label: 'Time per action', unit: 'seconds' },
    ] },
    { id: 'board', title: '🗺️ Board', fields: [
      { group: 'Tile mix', key: 'board.tileMix', type: 'tilemix', label: 'Tile mix' },
      { group: 'Deed cards', key: 'board.deedEffects', type: 'select', label: 'Effects', options: [
          ['varied', 'Varied — random each game'], ['first', "Always the card's first effect"] ] },
      { group: 'Deed cards', key: 'board.noBackwards', type: 'toggle', label: 'No going backwards',
        hint: 'Leaves out move-back, back-to-a-landmark and skip-turn effects' },
    ] },
    { id: 'turns', title: '⏱ Turn & pace', fields: [
      { group: 'Turns', key: 'turns.exactFinish', type: 'toggle', label: 'Exact finish',
        hint: 'The exact number is needed to land on the finish — overshooting does not move' },
      { group: 'Turns', key: 'turns.whoStarts', type: 'select', label: 'Who starts', options: [
          ['order', 'First player in the list'], ['random', 'Random'] ] },
      { group: 'Pace', key: 'turns.animation', type: 'select', label: 'Animation speed', options: [
          ['normal', 'Normal'], ['fast', 'Fast'] ] },
    ] },
  ];
}

const _get = (obj, key) => key.split('.').reduce((o, k) => o?.[k], obj);
function _set(obj, key, value) {
  const ks = key.split('.'); const last = ks.pop();
  ks.reduce((o, k) => (o[k] ??= {}), obj)[last] = value;
}

/** Draw the Rules tab for the current edition (called when the tab is shown). */
function renderRulesTab() {
  _rulesDraft = _clone(_setupRules || gameRules());
  document.getElementById('rules-export').classList.add('hidden');
  _renderRulesPanel();
}

/** Save what the Rules tab shows: rules for the next game, stored per edition. */
function _commitRules() {
  const preset = _rulesDraft.preset;
  _setupRules = normalizeRules(_rulesDraft, { ..._rulesOpts(), actionKinds: Object.keys(CONFIG.ACTION_KINDS || {}) });
  _setupRules.preset = preset;
  _storeRules(getActiveEditionId(), _setupRules);
  renderRulesSummary();
}

function showRulesSection(id) {
  _rulesSection = id;
  _renderRulesPanel();
}

function onRulesPresetChange(presetId) {
  _rulesDraft = presetBase(CONFIG, presetId, _rulesOpts());
  _commitRules();
  _renderRulesPanel();
}

function resetRulesToPreset() {
  onRulesPresetChange(_rulesDraft.preset);
}

/** "📋 Copy as preset": a RULE_PRESETS entry for js/shared/config.js. */
function copyRulesAsPreset() {
  const text = exportPreset(_rulesDraft, CONFIG, _rulesOpts());
  const box = document.getElementById('rules-export');
  box.value = text;
  box.classList.remove('hidden');
  box.select();
  navigator.clipboard?.writeText(text).then(
    () => showToast('Preset copied — paste it into RULE_PRESETS in js/shared/config.js'),
    () => showToast('Select the text below and copy it'));
}

function _renderRulesPanel() {
  const presetSel = document.getElementById('rules-preset');
  presetSel.innerHTML = Object.entries(CONFIG.RULE_PRESETS || {}).map(([id, p]) =>
    `<option value="${esc(id)}" ${id === _rulesDraft.preset ? 'selected' : ''}>${esc(p.label)}</option>`).join('');
  document.getElementById('rules-preset-desc').textContent =
    CONFIG.RULE_PRESETS?.[_rulesDraft.preset]?.description ?? '';

  const edition = (window.TRIVENTUREX_EDITIONS || []).find(e => e.id === getActiveEditionId());
  document.getElementById('rules-for').textContent =
    edition ? `Rules for ${edition.icon} ${edition.name} — each edition keeps its own` : '';

  // Side tabs: one per section, plus the question topics
  const schema = _rulesSchema();
  const tabs = [...schema.map(sec => [sec.id, sec.title]), ['topics', '🏷️ Topics']];
  if (!tabs.some(([id]) => id === _rulesSection)) _rulesSection = 'scoring';
  document.getElementById('rules-nav').innerHTML = tabs.map(([id, title]) =>
    `<button type="button" class="rules-nav-btn ${id === _rulesSection ? 'active' : ''}" role="tab"
             onclick="showRulesSection('${id}')">${title}</button>`).join('');

  // Redrawing removes the focused input, and the browser then fires a late
  // "change" for it with its old value — ignore events while redrawing.
  _rulesRendering = true;
  const section = schema.find(sec => sec.id === _rulesSection);
  document.getElementById('rules-body').innerHTML = section ? `
    <section class="rules-section">
      <h3>${section.title}</h3>
      ${_groupedFieldsHtml(section.fields)}
    </section>` : '';
  // The topic tree is static DOM (category-filter.js, saved on its own)
  document.getElementById('rules-topics').classList.toggle('hidden', _rulesSection !== 'topics');
  _rulesRendering = false;

  _updateRulesPreview();
}

/** Consecutive fields with the same `group` go into one card. */
function _groupedFieldsHtml(fields) {
  const groups = [];
  for (const f of fields) {
    if (!groups.length || groups.at(-1).name !== f.group) groups.push({ name: f.group, fields: [] });
    groups.at(-1).fields.push(f);
  }
  return groups.map(g => `
    <div class="rules-group">
      ${g.name ? `<div class="rules-group-title">${esc(g.name)}</div>` : ''}
      ${g.fields.map(_rulesFieldHtml).join('')}
    </div>`).join('');
}

function _rulesFieldHtml(f) {
  const v = _get(_rulesDraft, f.key);
  const hint = f.hint ? `<span class="rules-hint">${esc(f.hint)}</span>` : '';
  let control = '';
  if (f.type === 'number') {
    control = `<input type="number" class="rules-number" data-rule="${f.key}" value="${esc(v)}">
               ${f.unit ? `<span class="rules-unit">${esc(f.unit)}</span>` : ''}`;
  } else if (f.type === 'toggle') {
    control = `<input type="checkbox" class="rules-toggle" data-rule="${f.key}" ${v ? 'checked' : ''}>`;
  } else if (f.type === 'select') {
    control = `<select class="settings-select" data-rule="${f.key}">${f.options.map(([val, label]) =>
      `<option value="${esc(val)}" ${val === v ? 'selected' : ''} ${f.disabled?.(val) ? 'disabled' : ''}>${esc(label)}</option>`).join('')}</select>`;
  } else if (f.type === 'kinds') {
    control = f.options.map(([val, label]) =>
      `<label class="rules-kind"><input type="checkbox" data-rule-kind="${esc(val)}" ${v.includes(val) ? 'checked' : ''}> ${esc(label)}</label>`).join('');
  } else if (f.type === 'tilemix') {
    return _tileMixHtml();
  }
  return `<div class="rules-field">
            <div class="rules-label">${esc(f.label)}${hint}</div>
            <div class="rules-control">${control}</div>
          </div>`;
}

const _TILE_LABELS = () => ({
  action:    CONFIG.SPACE_INFO.action?.label    ?? 'Action',
  good_deed: CONFIG.SPACE_INFO.good_deed?.label ?? 'Good deed',
  bad_deed:  CONFIG.SPACE_INFO.bad_deed?.label  ?? 'Bad deed',
  landmark:  CONFIG.SPACE_INFO.landmark?.label  ?? 'Landmark',
  skip:      CONFIG.SPACE_INFO.skip?.label      ?? 'Skip',
});

/** The game length chosen on the setup screen. */
const _setupLength = () => document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';

/** Percent per tile type currently in effect (edition default when tileMix is null). */
function _effectiveMix() {
  if (_rulesDraft.board.tileMix) return _rulesDraft.board.tileMix;
  const d = editionTileDistribution(_setupLength());
  return Object.fromEntries(TILE_TYPES.map(t => [t, Math.round((d[t] || 0) * 100)]));
}

function _tileMixHtml() {
  const mix = _effectiveMix();
  const labels = _TILE_LABELS();
  const current = _rulesDraft.board.tileMix;
  const presetId = Object.entries(TILE_MIX_PRESETS)
    .find(([, p]) => JSON.stringify(p.mix) === JSON.stringify(current))?.[0] ?? 'custom';
  return `<div class="rules-field">
      <div class="rules-label">Mix
        <span class="rules-hint">Share of the board per tile type — 0 removes it. Questions fill the rest.</span></div>
      <div class="rules-control">
        <select class="settings-select" data-rule-mix>${Object.entries(TILE_MIX_PRESETS).map(([id, p]) =>
          `<option value="${id}" ${id === presetId ? 'selected' : ''}>${esc(p.label)}</option>`).join('')}
          <option value="custom" ${presetId === 'custom' ? 'selected' : ''}>Custom</option>
        </select>
      </div>
    </div>
    <div class="rules-tiles">${TILE_TYPES.map(t => `
      <label class="rules-tile"><span class="rules-tile-name">${esc(labels[t])}</span>
        <span class="rules-tile-input"><input type="number" class="rules-number" min="0" max="100"
          data-tile="${t}" value="${mix[t]}"> %</span></label>`).join('')}
    </div>
    <div class="rules-tile-preview" id="rules-tile-preview"></div>`;
}

/** Live bits: tile counts for the chosen length + "N changed" next to the preset. */
function _updateRulesPreview() {
  const preview = document.getElementById('rules-tile-preview');
  if (preview) {
    const len = _setupLength();
    const middle = (CONFIG.BOARD_SIZES?.[len] ?? 40) - 2;
    const pct = _effectiveMix();
    const { capped } = normalizeTileMix(pct);
    const counts = tileCounts(Object.fromEntries(TILE_TYPES.map(t => [t, pct[t] / 100])), middle, CONFIG.LANDMARKS.length);
    const labels = _TILE_LABELS();
    preview.innerHTML = `${esc(len[0].toUpperCase() + len.slice(1))} board, about: ` +
      [...TILE_TYPES.map(t => `${counts[t] ?? 0} ${esc(labels[t].toLowerCase())}`), `${counts.question} questions`].join(' · ') +
      (capped ? `<br><span class="rules-warn">Special tiles are capped at ${MAX_SPECIAL_PERCENT}% in total — values will be scaled down.</span>` : '');
  }
  const n = countChanges(diffRules(_rulesDraft, presetBase(CONFIG, _rulesDraft.preset, _rulesOpts())));
  document.getElementById('rules-changed').textContent = n ? `${n} changed from this preset` : 'No changes from this preset';
}

/** One listener for every control in the panel. */
function _onRulesInput(e) {
  const el = e.target;
  if (!_rulesDraft || _rulesRendering || !el.isConnected) return;
  if (el.dataset.rule) {
    const f = _rulesSchema().flatMap(s => s.fields).find(x => x.key === el.dataset.rule);
    const value = f?.type === 'number' ? Number(el.value)
                : f?.type === 'toggle' ? el.checked
                : el.value;
    _set(_rulesDraft, el.dataset.rule, value);
  } else if (el.dataset.ruleKind !== undefined) {
    const kinds = [...document.querySelectorAll('[data-rule-kind]:checked')].map(c => c.dataset.ruleKind);
    if (!kinds.length) { el.checked = true; showToast('Keep at least one kind'); return; }
    _rulesDraft.actions.kinds = kinds;
  } else if (el.dataset.ruleMix !== undefined) {
    if (el.value === 'custom') return;
    _rulesDraft.board.tileMix = _clone(TILE_MIX_PRESETS[el.value].mix);
    _commitRules();
    _renderRulesPanel();
    return;
  } else if (el.dataset.tile) {
    const mix = {};
    document.querySelectorAll('[data-tile]').forEach(i => { mix[i.dataset.tile] = Number(i.value) || 0; });
    _rulesDraft.board.tileMix = mix;
    document.querySelector('[data-rule-mix]').value = 'custom';
  }
  _commitRules();
  _updateRulesPreview();
}

/** Wire the Rules tab once (called from initSetupScreen). */
function initRulesPanel() {
  const body = document.getElementById('rules-body');
  body.addEventListener('change', _onRulesInput);
  body.addEventListener('input', e => { if (e.target.dataset.tile) _onRulesInput(e); });
}
