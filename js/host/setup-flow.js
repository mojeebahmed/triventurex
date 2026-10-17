/**
 * setup-flow.js
 * The setup screen's guided flow (G6): two tabs (New game / Rules), the
 * steps as an accordion — one open at a time, each collapsed heading shows the
 * current choice, choosing moves on to the next step — and the sticky footer
 * that always shows the whole setup next to Start.
 */

const SETUP_STEPS = ['edition-section', 'length-section', 'board-section', 'players-section'];

/** Steps the user can see (the edition step is hidden when there's one edition). */
const _visibleSteps = () => SETUP_STEPS.map(id => document.getElementById(id))
  .filter(el => el && el.style.display !== 'none' && !el.classList.contains('hidden'));

function showSetupTab(tab) {
  document.querySelectorAll('.setup-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.setup-tab-panel').forEach(p => p.classList.toggle('hidden', p.id !== `setup-tab-${tab}`));
  if (tab === 'rules') renderRulesTab();
  if (tab === 'questions') renderQuestionExplorer();
  if (tab === 'boards') renderBoardDesigner();
}

/** Open one step (or none with null); the others collapse. */
function openSetupStep(id) {
  for (const el of document.querySelectorAll('.setup-step')) {
    const open = el.id === id;
    el.classList.toggle('open', open);
    el.querySelector('.step-head')?.setAttribute('aria-expanded', String(open));
  }
}

/** After a choice in a step: refresh the headings + footer and open the next step. */
function onSetupChoice(stepId) {
  updateSetupValues();
  const steps = _visibleSteps();
  const i = steps.findIndex(el => el.id === stepId);
  if (i !== -1 && steps[i].classList.contains('open')) openSetupStep(steps[i + 1]?.id ?? null);
}

// ── What each collapsed heading shows ───────────────────────────────────────

function _editionChoice() {
  const ed = (window.TRIVENTUREX_EDITIONS || []).find(e => e.id === getActiveEditionId());
  return ed ? `${ed.icon} ${ed.name}` : '';
}
function _lengthChoice() {
  const v = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  return v[0].toUpperCase() + v.slice(1);
}
function _boardChoice() {
  const v = document.getElementById('path-select')?.value ?? 'random';
  if (v === 'random') return '🎲 Random';
  const len = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  const t = CONFIG.PATH_TEMPLATES[len]?.[Number(v)];
  return t ? _pathLabel(t) : '🎲 Random';
}
function _playersChoice() {
  if (_mpMode === 'host') {
    const gm = document.getElementById('gm-only-toggle')?.checked;
    return gm ? '📱 On phones · you are the GM' : '📱 On phones · you play too';
  }
  const names = state.players.map((p, i) => p.nameInput?.value.trim() || CONFIG.PLAYERS.defaults[i]?.name || `Player ${i + 1}`);
  const list = names.length > 3 ? `${names.slice(0, 3).join(', ')} +${names.length - 3}` : names.join(', ');
  return `${names.length} players · ${list}`;
}

/** Refresh every collapsed heading and the footer summary. */
function updateSetupValues() {
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
  set('edition-section-value', _editionChoice());
  set('length-section-value',  _lengthChoice());
  set('board-section-value',   _boardChoice());
  set('players-section-value', _playersChoice());
  renderSetupSummary();
}

/** Footer: the whole setup in one line, next to Start. */
function renderSetupSummary() {
  const el = document.getElementById('setup-summary');
  if (!el || !_setupRules) return;
  const preset = CONFIG.RULE_PRESETS?.[_setupRules.preset]?.label ?? 'Custom';
  const changed = _changedCount(_setupRules);
  const parts = [_editionChoice(), _lengthChoice(), _boardChoice(),
                 _mpMode === 'host' ? '📱 On phones' : `${state.players.length} players`]
    .filter(Boolean);
  el.innerHTML = `${esc(parts.join(' · '))}<br>
    <span class="setup-summary-rules">Rules: <strong>${esc(preset)}</strong>${changed ? ` (${changed} changed)` : ''}
      · <button type="button" class="link-btn" onclick="showSetupTab('rules')">change</button></span>`;
}

/** Wire the tabs, the accordion and the shortcuts (called from initSetupScreen). */
function initSetupFlow() {
  document.querySelectorAll('.setup-tab').forEach(t =>
    t.addEventListener('click', () => showSetupTab(t.dataset.tab)));

  for (const el of document.querySelectorAll('.setup-step')) {
    el.querySelector('.step-head').addEventListener('click', () =>
      openSetupStep(el.classList.contains('open') ? null : el.id));
  }

  // Choices that move the flow on
  // 'click' (not 'change'): clicking the already-selected length must move on too
  document.querySelectorAll('input[name="gameLength"]').forEach(r =>
    r.addEventListener('click', () => onSetupChoice('length-section')));
  document.getElementById('board-picker').addEventListener('click', e => {
    if (e.target.closest('.board-card')) onSetupChoice('board-section');
  });
  // Typing names / adding players only updates the headings
  document.getElementById('players-section').addEventListener('input', updateSetupValues);
  document.getElementById('players-section').addEventListener('click', () => setTimeout(updateSetupValues, 0));

  // Enter starts the game — e.g. right after typing the last player name.
  // (On a focused button Enter keeps pressing that button; selects/textareas are left alone.)
  document.addEventListener('keydown', e => {
    if (e.key !== 'Enter' || !document.getElementById('setup-screen').classList.contains('active')) return;
    if (!e.target.isConnected) return;   // its element was just redrawn away — can't tell where it was
    if (e.target.closest('textarea, select, button, #setup-tab-rules, #setup-tab-questions, #setup-tab-boards')) return;
    e.preventDefault();
    document.getElementById('start-game-btn').click();
  });

  // First visit: walk through from the first step. Later: all collapsed,
  // showing last time's choices — most games are just "Start".
  openSetupStep(_loadGameSettings() ? null : (_visibleSteps()[0]?.id ?? null));
  updateSetupValues();
}
