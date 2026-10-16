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
         style="background:${esc(color)}" onclick="openHostBadgeModal()" title="Customize badge">
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
  if (radio) { radio.checked = true; populatePathSelector(s.gameLength); }
  const pathSel = document.getElementById('path-select');
  if (pathSel && s.pathIndex !== undefined) pathSel.value = s.pathIndex;
  const exactSel = document.getElementById('exact-finish-select');
  if (exactSel && s.exactFinish !== undefined) exactSel.value = s.exactFinish ? 'on' : 'off';
  const qtSel = document.getElementById('question-tracking-select');
  if (qtSel && s.questionTracking) qtSel.value = s.questionTracking;
}

// ── Question category filter (3-level: cat > subcat > topic) ─────────────────

function initSetupScreen() {
  renderEditionPicker(_activeEditionId);
  renderPlayerRows();
  _restoreGameSettings();

  document.querySelectorAll('input[name="gameLength"]').forEach(radio => {
    radio.addEventListener('change', () => populatePathSelector(radio.value));
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
  document.getElementById('gm-only-toggle')?.addEventListener('change', _applyGMOnlyUI);
}

// ── Multiplayer mode UI ───────────────────────────────────────────────────────

function setMPMode(mode) {
  _mpMode = mode;
  document.querySelectorAll('.mp-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.mode === mode));
  const isHost = mode === 'host';
  const isJoin = mode === 'join';

  // Toggle which player section is visible
  document.getElementById('local-players-section')?.classList.toggle('hidden', isHost || isJoin);
  document.getElementById('host-player-section')?.classList.toggle('hidden', !isHost);

  document.getElementById('join-info-panel')?.classList.toggle('hidden', !isJoin);
  document.getElementById('start-game-btn').style.display = isJoin ? 'none' : '';

  // Hide/show other setup sections in join mode
  document.querySelectorAll('.setup-section').forEach(el => {
    if (el.contains(document.getElementById('join-info-panel'))) return;
    if (el.id === 'edition-section') return;
    if (el.id === 'local-players-section' || el.id === 'host-player-section') return; // handled above
    el.style.display = isJoin ? 'none' : '';
  });
  document.querySelector('.setup-details')?.style && (document.querySelector('.setup-details').style.display = isJoin ? 'none' : '');

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

// ── Badge picker modal ────────────────────────────────────────────────────────
