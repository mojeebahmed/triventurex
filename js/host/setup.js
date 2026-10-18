/**
 * setup.js
 * Setup screen: local / host / join tabs, player rows, host player row, game settings.
 */

let _mpMode           = 'local';  // 'local' | 'host' | 'join'

function _renderHostPlayerRow() {
  const saved = _loadHostPlayerPref();
  const def   = saved || CONFIG.PLAYERS.defaults[0];
  const { color, token, name } = def;
  _hostPlayerState = { color, token };
  const container = document.getElementById('host-player-setup');
  if (!container) return;
  container.innerHTML = '';

  const wrapper = document.createElement('div');
  wrapper.className = 'player-row-wrapper';
  const row = document.createElement('div');
  row.className = 'player-row';
  row.innerHTML = `
    <div class="player-token-setup" id="setup-badge-host"
         style="background:${esc(color)}" onclick="openBadgeModal('host')" title="Customize badge">
      <div class="token-emoji">${esc(token)}</div>
    </div>
    <input type="text" id="host-player-name" placeholder="${esc(name)}" value="${esc(name)}" maxlength="20">`;
  wrapper.appendChild(row);
  container.appendChild(wrapper);
  _hostPlayerState = { color, token };
}

let _hostPlayerState = null;

function _restoreGameSettings() {
  const s = _loadGameSettings();
  if (!s) return;
  const radio = document.querySelector(`input[name="gameLength"][value="${s.gameLength}"]`);
  if (!radio) return;
  radio.checked = true;
  renderBoardPicker(s.gameLength, s.pathIndex !== undefined ? String(s.pathIndex) : 'random');
}

function initSetupScreen() {
  renderEditionPicker(_activeEditionId);
  renderPlayerRows();
  _restoreGameSettings();
  initRulesPanel();
  renderRulesSummary();
  initBoardPicker();
  // Board thumbnails for the selected length (restored above if saved)
  renderBoardPicker(document.querySelector('input[name="gameLength"]:checked')?.value || 'medium');

  document.querySelectorAll('input[name="gameLength"]').forEach(radio => {
    // A path index means a different path in another length → back to Random
    radio.addEventListener('change', () => renderBoardPicker(radio.value, 'random'));
  });

  document.getElementById('add-player-btn').addEventListener('click', () => {
    if (state.players.length < 8) addPlayerRow();
  });
  document.getElementById('remove-player-btn').addEventListener('click', () => {
    if (state.players.length > 2) {
      document.getElementById('players-setup').lastElementChild.remove();
      state.players.pop();
    }
  });
  document.getElementById('reset-players-btn').addEventListener('click', () => {
    _clearPlayerPrefs();
    renderPlayerRows();
  });

  document.getElementById('start-game-btn').addEventListener('click', startGame);
  document.getElementById('play-again-btn').addEventListener('click', resetToSetup);
  document.getElementById('rematch-btn').addEventListener('click', rematch);
  initSetupFlow();
  initQuestionExplorer();
  initBoardDesigner();
  document.getElementById('gm-only-toggle')?.addEventListener('change', () => { _applyGMOnlyUI(); updateSetupValues(); });
}

function setMPMode(mode) {
  _mpMode = mode;
  document.querySelectorAll('.mp-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.mode === mode));
  const isHost = mode === 'host';

  // Step ④ shows the local player list or the host's own player
  document.getElementById('local-players-section')?.classList.toggle('hidden', isHost);
  document.getElementById('host-player-section')?.classList.toggle('hidden', !isHost);
  document.getElementById('start-game-btn').innerHTML = `${isHost ? 'Open lobby' : 'Start Game'} ${icon('startGame')}`;
  if (typeof updateSetupValues === 'function') updateSetupValues();

  if (isHost) {
    _renderHostPlayerRow();
    _applyGMOnlyUI();
  }
}

function _applyGMOnlyUI() {
  const gmOnly = document.getElementById('gm-only-toggle')?.checked;
  const hostSetup = document.getElementById('host-player-setup');
  if (hostSetup) hostSetup.style.opacity = gmOnly ? '0.4' : '';
  const hostInput = document.getElementById('host-player-name');
  if (hostInput) hostInput.disabled = gmOnly;
  const hostBadge = document.getElementById('setup-badge-host');
  if (hostBadge) hostBadge.style.pointerEvents = gmOnly ? 'none' : '';
}

function renderPlayerRows() {
  const container = document.getElementById('players-setup');
  container.innerHTML = '';
  state.players = [];
  const saved = _loadPlayerPrefs();
  const count = saved?.length ?? 2;
  for (let i = 0; i < Math.max(2, count); i++) addPlayerRow();
}

function addPlayerRow() {
  const index = state.players.length;
  const saved = _loadPlayerPrefs();
  const def   = saved?.[index] || CONFIG.PLAYERS.defaults[index] || CONFIG.PLAYERS.defaults[0];
  const { color, token, name } = def;

  const container = document.getElementById('players-setup');

  const wrapper = document.createElement('div');
  wrapper.className = 'player-row-wrapper';

  const row = document.createElement('div');
  row.className = 'player-row';
  row.innerHTML = `
    <div class="player-token-setup" id="setup-badge-${index}"
         style="background:${esc(color)}" onclick="openBadgeModal(${index})" title="Customize badge">
      <div class="token-emoji">${esc(token)}</div>
    </div>
    <input type="text" placeholder="${esc(name)}" value="${esc(name)}" maxlength="20">`;

  wrapper.appendChild(row);
  container.appendChild(wrapper);
  state.players.push({ color, token, nameInput: row.querySelector('input') });
}
