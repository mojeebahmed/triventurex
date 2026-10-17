/**
 * rules-panel.js
 * Rules for the next game (setup screen) and the rules panel (G12).
 *
 * gameRules() is what the rest of the host code reads:
 *   during a game → state.rules (copied at start, saved with the game)
 *   on the setup screen → the rules for the next game (_setupRules)
 * The pure model (defaults → preset → changes) lives in js/shared/rules.js.
 */

const LS_RULES_PREFIX = 'triventurex_rules_';   // + editionId → { preset, changes }

let _setupRules = null;   // rules for the next game, for the active edition
let _rulesDraft = null;   // working copy while the panel is open
let _rulesRendering = false; // true while the panel is being redrawn

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
}

// ── Summary line on the setup screen ────────────────────────────────────────

function _changedCount(rules) {
  return countChanges(diffRules(rules, presetBase(CONFIG, rules.preset, _rulesOpts())));
}

function renderRulesSummary() {
  const text  = document.getElementById('rules-summary-text');
  const badge = document.getElementById('rules-summary-badge');
  if (!text || !_setupRules) return;
  const preset = CONFIG.RULE_PRESETS?.[_setupRules.preset]?.label ?? 'Custom';
  text.textContent = [preset, ...summarizeRules(_setupRules, CONFIG)].join(' · ');
  const n = _changedCount(_setupRules);
  badge.textContent = n ? `${n} changed` : '';
  badge.classList.toggle('hidden', !n);
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
    { title: '🏆 Scoring', fields: [
      { key: 'scoring.questionEasy',    type: 'number', label: 'Easy question',  unit: pts },
      { key: 'scoring.questionHard',    type: 'number', label: 'Hard question',  unit: pts },
      { key: 'scoring.actionPerformer', type: 'number', label: 'Action card — performer', unit: pts },
      { key: 'scoring.actionGuesser',   type: 'number', label: 'Action card — first correct guesser', unit: pts },
      { key: 'scoring.finishBonus',     type: 'select', label: 'Finish bonus', options: [
          ['standard', `Standard (${(CONFIG.FINISH_BONUS || []).join(' / ')})`],
          ['small', 'Small (5 / 3 / 2 / 1)'], ['off', 'Off'] ] },
      { key: 'scoring.landmarkRoll',     type: 'number', label: 'Landmark — landing on it by a roll', unit: pts,
        hint: '0 = just information. Can be negative.' },
      { key: 'scoring.landmarkGoodDeed', type: 'number', label: 'Landmark — sent there by a good deed', unit: pts },
      { key: 'scoring.landmarkBadDeed',  type: 'number', label: 'Landmark — sent back there by a bad deed', unit: pts },
      { key: 'scoring.negativeScores',   type: 'toggle', label: 'Allow negative scores', hint: 'Off: scores never go below 0' },
    ] },
    { title: '❓ Questions', fields: [
      { key: 'questions.difficulty', type: 'select', label: 'Difficulty', options: [
          ['choose', 'Player chooses'], ['easy', 'Always easy'], ['hard', 'Always hard'] ] },
      { key: 'questions.timerAuto',    type: 'toggle', label: 'Start the timer automatically' },
      { key: 'questions.timerSeconds', type: 'number', label: 'Question timer', unit: 'seconds' },
      { key: 'questions.tracking',     type: 'select', label: 'Avoid repeated questions', options: [
          ['session', 'Remember across games'], ['game', 'Reset every game'] ] },
    ] },
    { title: '🎬 Action cards', fields: [
      { key: 'actions.cards', type: 'select', label: 'Cards', options: [
          ['digital', _hasActionCards() ? 'Digital cards' : 'Digital cards (none in this edition)'],
          ['physical', 'Physical deck'] ],
        disabled: v => v === 'digital' && !_hasActionCards(),
        hint: 'A digital card can always be swapped for a physical one during play' },
      { key: 'actions.kinds', type: 'kinds', label: 'Kinds allowed',
        options: Object.entries(kinds).map(([k, v]) => [k, `${v.icon} ${v.label}`]) },
      { key: 'actions.timerSeconds', type: 'number', label: 'Action timer', unit: 'seconds' },
    ] },
    { title: '🗺️ Board', fields: [
      { key: 'board.tileMix', type: 'tilemix', label: 'Tile mix' },
      { key: 'board.deedEffects', type: 'select', label: 'Deed card effects', options: [
          ['varied', 'Varied — a random effect each game'], ['first', "Always the card's first effect"] ] },
      { key: 'board.noBackwards', type: 'toggle', label: 'No going backwards',
        hint: 'Leaves out move-back, back-to-a-landmark and skip-turn deed effects' },
    ] },
    { title: '⏱ Turn & pace', fields: [
      { key: 'turns.exactFinish', type: 'toggle', label: 'Exact finish',
        hint: 'The exact number is needed to land on the finish — overshooting does not move' },
      { key: 'turns.whoStarts', type: 'select', label: 'Who starts', options: [
          ['order', 'First player in the list'], ['random', 'Random'] ] },
      { key: 'turns.animation', type: 'select', label: 'Animation speed', options: [
          ['normal', 'Normal'], ['fast', 'Fast'] ] },
    ] },
  ];
}

const _get = (obj, key) => key.split('.').reduce((o, k) => o?.[k], obj);
function _set(obj, key, value) {
  const ks = key.split('.'); const last = ks.pop();
  ks.reduce((o, k) => (o[k] ??= {}), obj)[last] = value;
}

function openRulesPanel() {
  _rulesDraft = _clone(_setupRules || gameRules());
  _renderRulesPanel();
  document.getElementById('rules-export').classList.add('hidden');
  document.getElementById('rules-overlay').classList.remove('hidden');
}

/** Close without saving (Cancel / click outside). */
function closeRulesPanel(e) {
  if (e && e.target !== document.getElementById('rules-overlay')) return;
  document.getElementById('rules-overlay').classList.add('hidden');
  _rulesDraft = null;
}

function saveRulesPanel() {
  _setupRules = normalizeRules(_rulesDraft, { ..._rulesOpts(), actionKinds: Object.keys(CONFIG.ACTION_KINDS || {}) });
  _setupRules.preset = _rulesDraft.preset;
  _storeRules(getActiveEditionId(), _setupRules);
  renderRulesSummary();
  document.getElementById('rules-overlay').classList.add('hidden');
  _rulesDraft = null;
}

function onRulesPresetChange(presetId) {
  _rulesDraft = presetBase(CONFIG, presetId, _rulesOpts());
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

  // Redrawing removes the focused input, and the browser then fires a late
  // "change" for it with its old value — ignore events while redrawing.
  _rulesRendering = true;
  const body = document.getElementById('rules-body');
  body.innerHTML = _rulesSchema().map(section => `
    <section class="rules-section">
      <h3>${section.title}</h3>
      ${section.fields.map(_rulesFieldHtml).join('')}
    </section>`).join('');
  // (Question topics are a static section below #rules-body — category-filter.js)
  _rulesRendering = false;

  _updateRulesPreview();
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
  return `<div class="rules-field rules-field-wide">
    <div class="rules-label">Tile mix
      <span class="rules-hint">Share of the board per tile type — 0 removes it. Questions fill the rest.</span></div>
    <div class="rules-control">
      <select class="settings-select" data-rule-mix>${Object.entries(TILE_MIX_PRESETS).map(([id, p]) =>
        `<option value="${id}" ${id === presetId ? 'selected' : ''}>${esc(p.label)}</option>`).join('')}
        <option value="custom" ${presetId === 'custom' ? 'selected' : ''}>Custom</option>
      </select>
    </div>
    <div class="rules-tiles">${TILE_TYPES.map(t => `
      <label class="rules-tile"><span>${esc(labels[t])}</span>
        <input type="number" class="rules-number" min="0" max="100" data-tile="${t}" value="${mix[t]}"> %</label>`).join('')}
    </div>
    <div class="rules-tile-preview" id="rules-tile-preview"></div>
  </div>`;
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
    _renderRulesPanel();
    return;
  } else if (el.dataset.tile) {
    const mix = {};
    document.querySelectorAll('[data-tile]').forEach(i => { mix[i.dataset.tile] = Number(i.value) || 0; });
    _rulesDraft.board.tileMix = mix;
    document.querySelector('[data-rule-mix]').value = 'custom';
  }
  _updateRulesPreview();
}

/** Wire the panel once (called from initSetupScreen). */
function initRulesPanel() {
  const body = document.getElementById('rules-body');
  body.addEventListener('change', _onRulesInput);
  body.addEventListener('input', e => { if (e.target.dataset.tile) _onRulesInput(e); });
}
