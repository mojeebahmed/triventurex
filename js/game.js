/**
 * game.js
 * Main game controller — owns all state and wires everything together.
 */

// ── State ─────────────────────────────────────────────────────────────────────

let state = {
  gameId:             null,
  players:            [],
  board:              [],
  gameLength:         'medium',
  pathIndex:          'random',   // 'random' or a numeric index into PATH_TEMPLATES
  currentPlayerIndex: 0,
  phase:              'setup',    // 'setup' | 'playing' | 'ended'
  turnPhase:          'roll',     // 'roll' | 'resolving'
  finishCount:        0,
  history:            [],         // array of turn snapshots for undo + game log
};

// ── Multiplayer state ──────────────────────────────────────────────────────────
let _mpMode           = 'local';  // 'local' | 'host' | 'join'
let _isNetworkGame    = false;    // true once a network game is active
let _networkGameId    = null;
let _awaitingRoll     = false;    // true when host is waiting for server to roll
let _pendingNetworkSetup = null;  // { gameLength, pathIndex, isGMOnly, hostPlayer }
let _lobbyPlayers     = [];       // players accumulated via player_joined events
let _pendingHostRejoin = null;    // saved gameId to rejoin as host after refresh

// ── Score change hook ─────────────────────────────────────────────────────────
window._onScoreChange = (player, amount) => {
  showScoreFlyout(player, amount);
  // Scoreboard is refreshed in afterSpaceResolved / refreshUI — not here to avoid
  // triggering during animation mid-steps.
};

// ── History helpers ───────────────────────────────────────────────────────────

let _preRollSnapshot = null; // snapshot saved at the start of each roll
let _currentRoll     = 0;
let _turnToken       = 0;   // incremented each turn; stale async continuations check this

function _createSnapshot() {
  return {
    players:            state.players.map(p => ({ ...p })),
    currentPlayerIndex: state.currentPlayerIndex,
    finishCount:        state.finishCount,
  };
}

function _addHistoryEntry(roll, player, space, scoreBefore, posBefore) {
  state.history.push({
    roll,
    playerId:    player.id,
    playerName:  player.name,
    playerColor: player.color,
    playerToken: player.token,
    spaceType:   space?.type || 'unknown',
    spaceName:   space?.name || null,
    posBefore,
    posAfter:    player.position,
    scoreBefore,
    scoreAfter:  player.score,
    snapshot:    _preRollSnapshot, // state BEFORE this turn — restores on undo
  });
  renderHistoryPanel(state.history);
}

/**
 * Restores the last turn from the pre-roll snapshot.
 * _turnToken is incremented so any in-flight _processRoll continuation sees a
 * stale token and bails out — prevents a resolved space firing after undo.
 * state.players is replaced (not mutated) so no lingering object references
 * from the old turn can write back into the restored state.
 */
function undoLastMove() {
  if (!state.history.length) return;
  const entry    = state.history.pop();
  const snapshot = entry.snapshot;
  if (!snapshot) { renderHistoryPanel(state.history); return; }

  // Close any open modal and invalidate any ongoing async turn so stale
  // afterSpaceResolved / endTurn callbacks cannot fire after the undo.
  hideModal();
  ++_turnToken;
  state._pendingHistory = null;

  // Replace the players array with fresh copies from the snapshot so no
  // stale in-flight references can leak back in via Object.assign.
  state.players = snapshot.players.map(sp => ({ ...sp }));
  state.currentPlayerIndex = snapshot.currentPlayerIndex;
  state.finishCount        = snapshot.finishCount;
  state.turnPhase          = 'roll';

  console.log('[undo] restored currentPlayerIndex =', state.currentPlayerIndex,
              '→', state.players[state.currentPlayerIndex]?.name);

  updateBoardTokens(state.players);
  updateScoreboard(state.players);
  highlightSpace(currentPlayer().position);
  refreshUI();
  renderHistoryPanel(state.history);
  saveGame();
  _syncStateToServer();
}

// Expose board globally so ui.js deed effects can access it
Object.defineProperty(window, '_gameBoard', { get: () => state.board });
// Expose players globally so ui.js deed effects can access all players
Object.defineProperty(window, '_gamePlayers', { get: () => state.players });

// ── Helpers ───────────────────────────────────────────────────────────────────

function currentPlayer() { return state.players[state.currentPlayerIndex]; }

function generateGameId() {
  const prefix = CONFIG.GAME?.gameIdPrefix ?? 'TX';
  const rand   = Math.random().toString(36).slice(2, 6).toUpperCase();
  return `${prefix}-${Date.now().toString(36).toUpperCase()}-${rand}`;
}

/**
 * Inject CONFIG.GAME branding into the setup screen and document title.
 * Called once on load and can be re-called if the theme changes in future.
 */
function _applyBranding() {
  const g = CONFIG.GAME || {};
  const engine   = g.engineName || 'Triventurex';
  const theme    = g.themeName  || 'Swab Quest';
  const icon     = g.themeIcon  || '🎯';
  const subtitle = g.subtitle   || '';

  document.title = `${engine} — ${theme}`;

  const set = (id, text, isHtml = false) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (isHtml) el.innerHTML = text;
    else el.textContent = text;
  };

  set('brand-engine',       engine);
  set('brand-theme',        `${icon} ${theme}`, true);
  set('brand-subtitle',     subtitle);
  set('end-screen-message', g.endScreenMessage || 'All players have reached the finish!');
}

// ── LocalStorage ──────────────────────────────────────────────────────────────

function saveGame() {
  if (state.phase !== 'playing') return;
  try {
    const save = {
      ...state,
      savedAt: new Date().toISOString(),
      // board._gridRows/Cols are non-enumerable — save them explicitly
      gridRows: state.board._gridRows,
      gridCols: state.board._gridCols,
    };
    localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(save));
  } catch (e) {
    console.warn('Could not save game:', e);
  }
}

function loadSave() {
  try {
    const raw = localStorage.getItem(CONFIG.STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function clearSave() {
  localStorage.removeItem(CONFIG.STORAGE_KEY);
}

function checkAndShowResume() {
  const save = loadSave();
  if (!save || save.phase !== 'playing') return;

  const prompt  = document.getElementById('resume-prompt');
  const meta    = document.getElementById('resume-meta');
  const elapsed = _friendlyTime(save.savedAt);
  meta.textContent =
    `${save.gameLength} game · ${save.players.length} players · saved ${elapsed}`;
  prompt.classList.remove('hidden');

  document.getElementById('resume-btn').addEventListener('click', () => {
    prompt.classList.add('hidden');
    _restoreGame(save);
  });
  document.getElementById('discard-btn').addEventListener('click', () => {
    clearSave();
    prompt.classList.add('hidden');
  });
}

function _friendlyTime(isoString) {
  const diff = Math.floor((Date.now() - new Date(isoString)) / 1000);
  if (diff < 60)  return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function _restoreGame(save) {
  // Re-attach the non-enumerable grid properties
  const board = save.board;
  board._gridRows = save.gridRows;
  board._gridCols = save.gridCols;

  Object.assign(state, save);
  state.board = board;

  // If the game was saved mid-action (modal was open, roll button disabled),
  // reset to 'roll' so the player isn't stuck — the modal will re-open below.
  const wasResolving = state.turnPhase === 'resolving';
  if (wasResolving) state.turnPhase = 'roll';

  state.history         = state.history || [];
  state._pendingHistory = null;

  showScreen('game-screen');
  renderBoard(state.board, state.players);
  renderLegend();
  _showGameIdBadge();
  wireGameControls();
  refreshUI();
  highlightSpace(currentPlayer().position);
  renderHistoryPanel(state.history);
  fitBoardInView();

  // Restore host network game connection if applicable
  const savedNetId = (() => { try { return localStorage.getItem('tx_net_game'); } catch { return null; } })();
  if (savedNetId) {
    _networkGameId = savedNetId;
    _isNetworkGame = true;
    TX_NET.setGameId(savedNetId);
    _pendingHostRejoin = savedNetId;
    document.getElementById('gm-network-section')?.classList.remove('hidden');
    _renderGMNetworkPlayers(state.players);
    _updateNetworkStatusBar();
  }

  // Re-open the space modal so the player can complete the interrupted action
  if (wasResolving) {
    const player = currentPlayer();
    const space  = state.board[player.position];
    if (space && space.type !== 'start' && space.type !== 'finish') {
      state.turnPhase = 'resolving'; // re-lock while modal is open
      document.getElementById('roll-btn').disabled = true;
      if (space.type === 'action') {
        showSpaceModal(space, player, (guessed) => {
          if (guessed) showGuesserModal(state.players, player, afterSpaceResolved);
          else afterSpaceResolved();
        });
      } else {
        showSpaceModal(space, player, afterSpaceResolved);
      }
    }
  }
}

// ── LocalStorage keys ─────────────────────────────────────────────────────────
const LS_PLAYER_PREFS  = 'triventurex_player_prefs';
const LS_HOST_PLAYER   = 'triventurex_host_player';
const LS_GAME_SETTINGS = 'triventurex_game_settings';
const LS_CAT_PREFIX    = 'triventurex_cats_';

function _savePlayerPrefs() {
  try {
    localStorage.setItem(LS_PLAYER_PREFS, JSON.stringify(
      state.players.map(p => ({
        name:  p.nameInput.value.trim() || '',
        color: p.color,
        token: p.token,
      }))
    ));
  } catch {}
}

function _loadPlayerPrefs() {
  try { return JSON.parse(localStorage.getItem(LS_PLAYER_PREFS)); } catch { return null; }
}

function _clearPlayerPrefs() {
  localStorage.removeItem(LS_PLAYER_PREFS);
}

// ── Host player prefs (separate from local game prefs) ────────────────────────

function _saveHostPlayerPref(name, color, token) {
  try { localStorage.setItem(LS_HOST_PLAYER, JSON.stringify({ name, color, token })); } catch {}
}

function _loadHostPlayerPref() {
  try { return JSON.parse(localStorage.getItem(LS_HOST_PLAYER)); } catch { return null; }
}

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
         style="background:${color}" onclick="openHostBadgeModal()" title="Customize badge">
      <div class="token-emoji">${token}</div>
    </div>
    <input type="text" id="host-player-name" placeholder="${name}" value="${name}" maxlength="20">`;
  wrapper.appendChild(row);
  container.appendChild(wrapper);
  _hostPlayerState = { color, token };
}

// openHostBadgeModal reuses the badge modal but saves to host prefs
function openHostBadgeModal() {
  const name = document.getElementById('host-player-name')?.value?.trim() || 'Host';
  _badgeModalIndex = 'host';

  const p = _hostPlayerState || CONFIG.PLAYERS.defaults[0];
  const tokens = CONFIG.PLAYERS.tokens;
  const colors = CONFIG.PLAYERS.colors;

  document.getElementById('badge-modal-title').textContent = name + "'s Badge";
  _renderHostBadgePreview(p);

  document.getElementById('badge-modal-body').innerHTML = `
    <div class="picker-section">
      <span class="picker-label">Icon</span>
      <div class="picker-grid picker-tokens">
        ${tokens.map(t =>
          `<div class="picker-token ${t === p.token ? 'selected' : ''}"
               onclick="selectHostToken('${t}')">${t}</div>`
        ).join('')}
      </div>
    </div>
    <div class="picker-section">
      <span class="picker-label">Colour</span>
      <div class="picker-grid picker-colors">
        ${colors.map(c =>
          `<div class="picker-color ${c === p.color ? 'selected' : ''}"
               style="background:${c}" data-color="${c}"
               onclick="selectHostColor('${c}')"></div>`
        ).join('')}
      </div>
    </div>`;

  document.getElementById('badge-modal-overlay').classList.remove('hidden');
}

function _renderHostBadgePreview(p) {
  const previewEl = document.getElementById('badge-preview');
  if (!previewEl) return;
  const name = document.getElementById('host-player-name')?.value?.trim() || 'Host';
  previewEl.style.background = p.color;
  const emojiEl = previewEl.querySelector('.token-emoji');
  const initEl  = previewEl.querySelector('.token-initial');
  if (emojiEl) emojiEl.textContent = p.token;
  if (initEl)  initEl.textContent  = name.slice(0, 2).toUpperCase();
}

function selectHostToken(token) {
  _hostPlayerState = { ..._hostPlayerState, token };
  document.querySelectorAll('#badge-modal-body .picker-token').forEach(el => {
    el.classList.toggle('selected', el.textContent === token);
  });
  const badgeEl = document.getElementById('setup-badge-host');
  if (badgeEl) badgeEl.querySelector('.token-emoji').textContent = token;
  _renderHostBadgePreview(_hostPlayerState);
}

function selectHostColor(color) {
  _hostPlayerState = { ..._hostPlayerState, color };
  document.querySelectorAll('#badge-modal-body .picker-color').forEach(el => {
    el.classList.toggle('selected', el.dataset.color === color);
  });
  const badgeEl = document.getElementById('setup-badge-host');
  if (badgeEl) { badgeEl.style.background = color; }
  _renderHostBadgePreview(_hostPlayerState);
}

let _hostPlayerState = null;

function _saveGameSettings(gameLength, pathIndex) {
  try {
    localStorage.setItem(LS_GAME_SETTINGS, JSON.stringify({
      gameLength, pathIndex, playerCount: state.players.length,
      exactFinish:      CONFIG.RULES.exactFinish,
      questionTracking: CONFIG.RULES.questionTracking,
    }));
  } catch {}
}

function _loadGameSettings() {
  try { return JSON.parse(localStorage.getItem(LS_GAME_SETTINGS)); } catch { return null; }
}

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

function _catKey(editionId) {
  return LS_CAT_PREFIX + (editionId || 'default');
}

function _getSavedTopics(editionId) {
  try { return JSON.parse(localStorage.getItem(_catKey(editionId))); } catch { return null; }
}

function _saveSelectedTopics(editionId, topicArray) {
  try { localStorage.setItem(_catKey(editionId), JSON.stringify(topicArray)); } catch {}
}

// Builds a nested hierarchy object: { cat: { subcat: [topic, …], … }, … }
function _buildCatTree() {
  const tree = {};
  for (const q of (window.QUESTIONS_DATA || [])) {
    const cat = q.cat || 'General'; const subcat = q.subcat || 'Other'; const topic = q.topic || 'General';
    if (!tree[cat]) tree[cat] = {};
    if (!tree[cat][subcat]) tree[cat][subcat] = new Set();
    tree[cat][subcat].add(topic);
  }
  // Sort everything
  const sorted = {};
  for (const cat of Object.keys(tree).sort()) {
    sorted[cat] = {};
    for (const subcat of Object.keys(tree[cat]).sort())
      sorted[cat][subcat] = [...tree[cat][subcat]].sort();
  }
  return sorted;
}

// Returns a Set of selected topic strings. If nothing saved, all topics are selected.
function getSelectedTopics() {
  const edId  = _activeThemeId || 'default';
  const tree  = _buildCatTree();
  const allTopics = Object.values(tree).flatMap(sc => Object.values(sc).flat());
  const saved = _getSavedTopics(edId);
  if (!saved) return new Set(allTopics);
  return new Set(saved.filter(t => allTopics.includes(t)));
}

function _populateCategoryFilter() {
  const edId = _activeThemeId || 'default';
  const tree = _buildCatTree();
  const row  = document.getElementById('category-filter-row');
  const box  = document.getElementById('category-checkboxes');
  if (!row || !box) return;

  const allTopics = Object.values(tree).flatMap(sc => Object.values(sc).flat());
  if (allTopics.length === 0) { row.style.display = 'none'; return; }

  const saved = _getSavedTopics(edId);
  const selTopics = new Set(saved || allTopics);

  const _allTopicsIn   = (topics) => topics.every(t => selTopics.has(t));
  const _someTopicsIn  = (topics) => topics.some(t => selTopics.has(t));

  const _saveCurrentState = () => {
    const nowSelected = [...box.querySelectorAll('input[data-level="topic"]:checked')].map(i => i.value);
    if (nowSelected.length === 0) return false; // block — must keep at least one
    _saveSelectedTopics(edId, nowSelected);
    return true;
  };

  const _syncParents = () => {
    // Sync subcat checkboxes
    box.querySelectorAll('input[data-level="subcat"]').forEach(scCb => {
      const topics = [...box.querySelectorAll(`input[data-subcat="${scCb.dataset.key}"][data-level="topic"]`)];
      const vals = topics.map(t => t.checked);
      scCb.checked = vals.every(Boolean);
      scCb.indeterminate = !scCb.checked && vals.some(Boolean);
    });
    // Sync cat checkboxes
    box.querySelectorAll('input[data-level="cat"]').forEach(cCb => {
      const topics = [...box.querySelectorAll(`input[data-cat="${cCb.dataset.key}"][data-level="topic"]`)];
      const vals = topics.map(t => t.checked);
      cCb.checked = vals.every(Boolean);
      cCb.indeterminate = !cCb.checked && vals.some(Boolean);
    });
  };

  // Build HTML
  let html = '';
  for (const [cat, subcats] of Object.entries(tree)) {
    const catTopics = Object.values(subcats).flat();
    const catAll    = _allTopicsIn(catTopics);
    const catSome   = _someTopicsIn(catTopics);
    const catInd    = !catAll && catSome;
    html += `<div class="cat-group">
      <label class="cat-label">
        <input type="checkbox" data-level="cat" data-key="${cat}"
          ${catAll ? 'checked' : ''} ${catInd ? 'data-indeterminate' : ''}>
        <span class="cat-name">${cat}</span>
        <button class="cat-toggle" type="button" aria-label="expand">▾</button>
      </label>
      <div class="subcat-list collapsed">`;
    for (const [subcat, topics] of Object.entries(subcats)) {
      const scKey  = `${cat}||${subcat}`;
      const scAll  = _allTopicsIn(topics);
      const scSome = _someTopicsIn(topics);
      const scInd  = !scAll && scSome;
      html += `<div class="subcat-group">
        <label class="subcat-label">
          <input type="checkbox" data-level="subcat" data-key="${scKey}" data-cat="${cat}"
            ${scAll ? 'checked' : ''} ${scInd ? 'data-indeterminate' : ''}>
          <span class="subcat-name">${subcat}</span>
          <button class="subcat-toggle" type="button" aria-label="expand">▾</button>
        </label>
        <div class="topic-list collapsed">`;
      for (const topic of topics) {
        html += `<label class="topic-label">
          <input type="checkbox" data-level="topic" data-cat="${cat}" data-subcat="${scKey}" value="${topic}"
            ${selTopics.has(topic) ? 'checked' : ''}>
          ${topic}
        </label>`;
      }
      html += `</div></div>`;
    }
    html += `</div></div>`;
  }
  box.innerHTML = html;

  // Set indeterminate state (can't do in HTML)
  box.querySelectorAll('[data-indeterminate]').forEach(el => { el.indeterminate = true; });

  // Cat expand/collapse toggles
  box.querySelectorAll('.cat-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const list = btn.closest('.cat-group').querySelector('.subcat-list');
      list.classList.toggle('collapsed');
      btn.textContent = list.classList.contains('collapsed') ? '▾' : '▴';
    });
  });
  box.querySelectorAll('.subcat-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const list = btn.closest('.subcat-group').querySelector('.topic-list');
      list.classList.toggle('collapsed');
      btn.textContent = list.classList.contains('collapsed') ? '▾' : '▴';
    });
  });

  // Cat checkbox → toggle all children
  box.querySelectorAll('input[data-level="cat"]').forEach(cb => {
    cb.addEventListener('change', () => {
      box.querySelectorAll(`input[data-cat="${cb.dataset.key}"][data-level="topic"]`)
        .forEach(t => { t.checked = cb.checked; });
      if (!_saveCurrentState()) {
        // Revert: re-check all if last one was being unchecked
        box.querySelectorAll(`input[data-cat="${cb.dataset.key}"][data-level="topic"]`)
          .forEach(t => { t.checked = true; });
        cb.checked = true;
      }
      _syncParents();
    });
  });

  // Subcat checkbox → toggle its topics
  box.querySelectorAll('input[data-level="subcat"]').forEach(cb => {
    cb.addEventListener('change', () => {
      box.querySelectorAll(`input[data-subcat="${cb.dataset.key}"][data-level="topic"]`)
        .forEach(t => { t.checked = cb.checked; });
      if (!_saveCurrentState()) {
        box.querySelectorAll(`input[data-subcat="${cb.dataset.key}"][data-level="topic"]`)
          .forEach(t => { t.checked = true; });
        cb.checked = true;
      }
      _syncParents();
    });
  });

  // Topic checkbox → save and sync parents
  box.querySelectorAll('input[data-level="topic"]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (!_saveCurrentState()) { cb.checked = true; }
      _syncParents();
    });
  });

  row.style.display = '';
}

// ── Setup Screen ──────────────────────────────────────────────────────────────

function initSetupScreen() {
  renderThemePicker(_activeThemeId);
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
    if (el.id === 'theme-section') return;
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
         style="background:${color}" onclick="openBadgeModal(${index})" title="Customize badge">
      <div class="token-emoji">${token}</div>
    </div>
    <input type="text" placeholder="${name}" value="${name}" maxlength="20">`;

  wrapper.appendChild(row);
  container.appendChild(wrapper);
  state.players.push({ color, token, nameInput: row.querySelector('input') });
}

// ── Badge picker modal ────────────────────────────────────────────────────────

let _badgeModalIndex = null;

function openBadgeModal(index) {
  _badgeModalIndex = index;
  const p      = state.players[index];
  const tokens = CONFIG.PLAYERS.tokens;
  const colors = CONFIG.PLAYERS.colors;

  document.getElementById('badge-modal-title').textContent =
    (p.nameInput?.value?.trim() || `Player ${index + 1}`) + "'s Badge";

  _renderBadgePreview(p);

  document.getElementById('badge-modal-body').innerHTML = `
    <div class="picker-section">
      <span class="picker-label">Icon</span>
      <div class="picker-grid picker-tokens">
        ${tokens.map(t =>
          `<div class="picker-token ${t === p.token ? 'selected' : ''}"
               onclick="selectPlayerToken(${index},'${t}')">${t}</div>`
        ).join('')}
      </div>
    </div>
    <div class="picker-section">
      <span class="picker-label">Colour</span>
      <div class="picker-grid picker-colors">
        ${colors.map(c =>
          `<div class="picker-color ${c === p.color ? 'selected' : ''}"
               style="background:${c}" data-color="${c}"
               onclick="selectPlayerColor(${index},'${c}')"></div>`
        ).join('')}
      </div>
    </div>`;

  document.getElementById('badge-modal-overlay').classList.remove('hidden');
}

function closeBadgeModal(e) {
  if (e && e.target !== document.getElementById('badge-modal-overlay')) return;
  document.getElementById('badge-modal-overlay').classList.add('hidden');
  _badgeModalIndex = null;
}

function _renderBadgePreview(p) {
  const name    = p.nameInput?.value?.trim() || '';
  const initials = name.slice(0, 2).toUpperCase() || '?';
  const preview  = document.getElementById('badge-modal-preview');
  if (!preview) return;
  preview.style.background = p.color;
  preview.innerHTML = `
    <div class="token-emoji">${p.token}</div>
    <div class="token-initial">${initials}</div>`;
}

function selectPlayerToken(index, token) {
  if (!state.players[index]) return;
  state.players[index].token = token;
  const badge = document.getElementById(`setup-badge-${index}`);
  if (badge) badge.querySelector('.token-emoji').textContent = token;
  document.getElementById('badge-modal-body')?.querySelectorAll('.picker-token')
    .forEach(el => el.classList.toggle('selected', el.textContent === token));
  _renderBadgePreview(state.players[index]);
}

function selectPlayerColor(index, color) {
  if (!state.players[index]) return;
  state.players[index].color = color;
  const badge = document.getElementById(`setup-badge-${index}`);
  if (badge) badge.style.background = color;
  document.getElementById('badge-modal-body')?.querySelectorAll('.picker-color')
    .forEach(el => el.classList.toggle('selected', el.dataset.color === color));
  _renderBadgePreview(state.players[index]);
}

// ── Start Game ────────────────────────────────────────────────────────────────

function startGame() {
  if (_mpMode === 'host') { _hostNetworkGame(); return; }

  const gameLength = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  const pathVal    = document.getElementById('path-select').value;
  const pathIndex  = pathVal === 'random' ? 'random' : parseInt(pathVal, 10);

  const players = state.players.map((p, i) => {
    const name = p.nameInput.value.trim() || CONFIG.PLAYERS.defaults[i]?.name || `Player ${i + 1}`;
    return createPlayer(i, name, p.color, p.token);
  });
  if (players.length < 2) { alert('Please add at least 2 players.'); return; }

  // Read rule toggles from setup UI
  CONFIG.RULES.exactFinish        = document.getElementById('exact-finish-select')?.value !== 'off';
  CONFIG.RULES.questionTracking   = document.getElementById('question-tracking-select')?.value ?? 'session';
  if (CONFIG.RULES.questionTracking === 'game') resetAskedQuestions();

  state.gameId             = generateGameId();
  _savePlayerPrefs(); _saveGameSettings(gameLength, pathIndex);
  state.players            = players;
  state.gameLength         = gameLength;
  state.pathIndex          = pathIndex;
  state.board              = _buildBoard(gameLength, pathIndex);
  state.currentPlayerIndex = 0;
  state.finishCount        = 0;
  state.phase              = 'playing';
  state.turnPhase          = 'roll';
  state.history            = [];
  state._pendingHistory    = null;

  showScreen('game-screen');
  renderBoard(state.board, state.players);
  renderLegend();
  _showGameIdBadge();
  wireGameControls();
  refreshUI();
  highlightSpace(0);
  renderHistoryPanel(state.history);
  fitBoardInView(); // calls _applyBoardBackground internally
  saveGame();
}

// ── Network game helpers ──────────────────────────────────────────────────────

function _hostNetworkGame() {
  const gameLength = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  const pathVal    = document.getElementById('path-select').value;
  const pathIndex  = pathVal === 'random' ? 'random' : parseInt(pathVal, 10);
  const isGMOnly   = document.getElementById('gm-only-toggle')?.checked || false;

  let hostPlayer = null;
  if (!isGMOnly) {
    const name  = document.getElementById('host-player-name')?.value?.trim() || 'Host';
    const color = _hostPlayerState?.color || CONFIG.PLAYERS.defaults[0].color;
    const token = _hostPlayerState?.token || CONFIG.PLAYERS.defaults[0].token;
    hostPlayer = { id: 0, name, token, color };
    _saveHostPlayerPref(name, color, token);
  }

  CONFIG.RULES.exactFinish      = document.getElementById('exact-finish-select')?.value !== 'off';
  CONFIG.RULES.questionTracking = document.getElementById('question-tracking-select')?.value ?? 'session';
  if (CONFIG.RULES.questionTracking === 'game') resetAskedQuestions();

  _pendingNetworkSetup = { gameLength, pathIndex, isGMOnly, hostPlayer };
  _lobbyPlayers = hostPlayer ? [hostPlayer] : [];

  TX_NET.hostGame({
    themeId: _activeThemeId,
    gameLength,
    pathIndex,
    hostPlayer,
    isGMOnly,
  });
}

function startNetworkGame() {
  if (!_pendingNetworkSetup || !_networkGameId) return;
  TX_NET.startGame(_networkGameId);
}

function cancelLobby() {
  _pendingNetworkSetup = null;
  _networkGameId       = null;
  _lobbyPlayers        = [];
  showScreen('setup-screen');
}

function _renderLobbyPlayers(players) {
  const el = document.getElementById('lobby-players');
  if (!el) return;
  el.innerHTML = players.length === 0
    ? '<p class="lobby-empty">No players yet...</p>'
    : players.map(p => `
        <div class="lobby-player-row">
          <div class="score-token" style="background:${p.color}">
            <div class="token-emoji">${p.token}</div>
          </div>
          <span>${p.name}</span>
        </div>`).join('');
}

function _renderGMNetworkPlayers(serverPlayers) {
  const el = document.getElementById('gm-network-list');
  if (!el) return;
  el.innerHTML = serverPlayers.map(p => `
    <div class="gm-net-player">
      <div class="score-token" style="background:${p.color}">
        <div class="token-emoji">${p.token}</div>
      </div>
      <span class="gm-net-name">${p.name}${p.disconnected ? ' ⚠️' : ''}${p.inactive ? ' 💤' : ''}</span>
      <button class="btn btn-small btn-danger" onclick="gmRemoveNetworkPlayer(${p.id})">✕</button>
    </div>`).join('');
}

function gmRemoveNetworkPlayer(playerId) {
  if (!confirm('Remove this player?')) return;
  TX_NET.removePlayer(_networkGameId, playerId);
}

function _syncStateToServer() {
  if (!_isNetworkGame || !_networkGameId) return;
  TX_NET.syncState(_networkGameId, {
    playerStates: state.players.map(p => ({
      id:                   p.id,
      name:                 p.name,
      token:                p.token,
      color:                p.color,
      position:             p.position,
      score:                p.score,
      finished:             p.finished,
      skipNextTurn:         p.skipNextTurn,
      finishOrder:          p.finishOrder,
      inactive:             p.inactive    || false,
      disconnected:         p.disconnected || false,
    })),
    currentPlayerIndex: state.currentPlayerIndex,
    turnPhase:          state.turnPhase,
    finishCount:        state.finishCount,
    phase:              state.phase,
  });
}

function _emitSpaceCard(space, player) {
  if (!_isNetworkGame || !_networkGameId) return;
  const card = {
    spaceType:  space.type,
    spaceName:  space.name || null,
    playerName: player.name,
    playerId:   player.id,
  };
  if ((space.type === 'good_deed' || space.type === 'bad_deed') && space.deed) {
    card.deedText     = space.deed.text;
    card.deedEffect   = space.deed.effect;
    card.deedValue    = space.deed.value;
    card.deedLandmark = space.deed.landmark;
  }
  TX_NET.emitSpaceCard(_networkGameId, card);
}

function _updateNetworkStatusBar() {
  const bar = document.getElementById('net-status-bar');
  if (!bar || !_isNetworkGame) return;
  bar.classList.remove('hidden');
  document.getElementById('net-status-text').textContent  = '📡 Network Game';
  document.getElementById('net-game-id-label').textContent = _networkGameId;
}

function _initSocketHandlers() {
  TX_NET.on('connect', () => {
    document.getElementById('mp-tabs')?.classList.remove('hidden');
    console.log('[game] Connected to server');
    if (_pendingHostRejoin) {
      TX_NET.hostRejoin(_pendingHostRejoin);
      _pendingHostRejoin = null;
    }
  });

  TX_NET.on('disconnect', () => {
    document.getElementById('mp-tabs')?.classList.add('hidden');
    console.log('[game] Disconnected from server');
  });

  TX_NET.on('hosted', ({ gameId }) => {
    _networkGameId = gameId;
    TX_NET.setGameId(gameId);
    try { localStorage.setItem('tx_net_game', _networkGameId); } catch {}
    document.getElementById('lobby-game-id').textContent      = gameId;
    document.getElementById('net-game-id-label').textContent  = gameId;
    _renderLobbyPlayers(_lobbyPlayers);
    showScreen('lobby-screen');
  });

  TX_NET.on('player_joined', ({ player, players }) => {
    _lobbyPlayers = players;
    _renderLobbyPlayers(players);
    const btn = document.getElementById('lobby-start-btn');
    if (btn) btn.disabled = players.length < 2;
    const statusEl = document.getElementById('lobby-status');
    if (statusEl) statusEl.textContent =
      `${players.length} player${players.length !== 1 ? 's' : ''} joined`;

    // Mid-game join
    if (_isNetworkGame && state.phase === 'playing') {
      state.players.push(createPlayer(player.id, player.name, player.color, player.token));
      updateScoreboard(state.players);
      updateGMPlayerSelect(state.players);
      _renderGMNetworkPlayers(players);
    }
  });

  TX_NET.on('game_started', ({ players }) => {
    const setup     = _pendingNetworkSetup;
    _isNetworkGame  = true;

    state.players            = players.map(p => createPlayer(p.id, p.name, p.color, p.token));
    state.gameId             = _networkGameId;
    state.gameLength         = setup.gameLength;
    state.pathIndex          = setup.pathIndex;
    state.board              = _buildBoard(setup.gameLength, setup.pathIndex);
    state.currentPlayerIndex = 0;
    state.finishCount        = 0;
    state.phase              = 'playing';
    state.turnPhase          = 'roll';
    state.history            = [];
    state._pendingHistory    = null;

    showScreen('game-screen');
    renderBoard(state.board, state.players);
    renderLegend();
    _showGameIdBadge();
    wireGameControls();
    refreshUI();
    highlightSpace(0);
    renderHistoryPanel(state.history);
    fitBoardInView();
    saveGame();

    try { localStorage.setItem('tx_net_game', _networkGameId); } catch {}
    _updateNetworkStatusBar();
    _renderGMNetworkPlayers(players);
    document.getElementById('gm-network-section')?.classList.remove('hidden');

    _syncStateToServer();
  });

  TX_NET.on('roll_result', ({ roll }) => {
    if (!_isNetworkGame) return;
    _awaitingRoll = false;
    _processRoll(roll);
  });

  TX_NET.on('player_disconnected', ({ playerId, playerName }) => {
    if (!_isNetworkGame) return;
    const p = state.players.find(pl => pl.id === playerId);
    if (p) p.disconnected = true;
    _updateNetworkStatusBar();
  });

  TX_NET.on('player_removed', ({ playerId }) => {
    if (!_isNetworkGame) return;
    state.players = state.players.filter(p => p.id !== playerId);
    if (state.currentPlayerIndex >= state.players.length) {
      state.currentPlayerIndex = 0;
    }
    updateScoreboard(state.players);
    updateGMPlayerSelect(state.players);
    _renderGMNetworkPlayers(state.players);
  });

  TX_NET.on('error', ({ message }) => {
    console.error('[game] Server error:', message);
  });

  TX_NET.on('host_rejoined', ({ players, phase }) => {
    _isNetworkGame = true;
    _renderGMNetworkPlayers(players);
    document.getElementById('gm-network-section')?.classList.remove('hidden');
    _updateNetworkStatusBar();
    console.log('[game] host rejoined network game');
  });
}

function _buildBoard(gameLength, pathIndex) {
  if (pathIndex === 'random') {
    return generateBoard(gameLength); // picks random template internally
  }
  // Specific template — temporarily override the random pick
  const template = CONFIG.PATH_TEMPLATES[gameLength][pathIndex];
  return generateBoard(gameLength, template); // we'll patch generateBoard below
}

/**
 * Flash a large dice result card in the centre of the board viewport.
 * Appears for CONFIG.ANIMATION.diceOverlayMs, then fades out.
 * Token animation starts after this resolves.
 */
async function _showDiceOverlay(result, player) {
  const overlay = document.getElementById('dice-overlay');
  if (!overlay) return;

  document.getElementById('dice-overlay-face').innerHTML = renderDie(result, 'die-xl');
  document.getElementById('dice-overlay-num').textContent  = result;
  document.getElementById('dice-overlay-name').textContent = player?.name || '';
  document.getElementById('dice-overlay-name').style.color = player?.color || '';

  overlay.classList.add('visible');
  const holdMs = CONFIG.ANIMATION?.diceOverlayMs ?? 900;
  await new Promise(r => setTimeout(r, holdMs));
  overlay.classList.remove('visible');
  await new Promise(r => setTimeout(r, 200)); // fade-out transition
}

function _showGameIdBadge() {
  const el = document.getElementById('game-id-badge');
  if (el) el.textContent = state.gameId;
}

/**
 * Apply BOARD_BACKGROUND config to #board-bg (inside #board-world).
 *
 * Loads the image to read its natural dimensions, then sizes #board-bg to
 * match the image's exact aspect ratio while being large enough to fill the
 * viewport at minimum zoom — so any image size and shape works correctly.
 *
 * Blur affects only this element, leaving board spaces above it crisp.
 */
// Keep a reference to the active probe so we can cancel stale loads.
let _bgProbe = null;

function _applyBoardBackground() {
  const bg  = document.getElementById('board-bg');
  const cfg = CONFIG.BOARD_BACKGROUND;
  if (!bg) return;

  // Cancel any previous pending load to avoid race conditions
  if (_bgProbe) { _bgProbe.onload = null; _bgProbe.onerror = null; _bgProbe = null; }

  if (!cfg?.image) {
    bg.style.display = 'none';
    _bgBounds = null;
    return;
  }

  const op   = cfg.overlayOpacity ?? 0.65;
  const pos  = cfg.position || 'center';
  const blur = cfg.blur || 0;

  const probe = new Image();
  _bgProbe = probe;
  probe.onload = () => {
    if (probe !== _bgProbe) return; // superseded by a newer call
    _bgProbe = null;
    const vp  = document.getElementById('board-viewport');
    const vpW = vp?.offsetWidth  || 1440;
    const vpH = vp?.offsetHeight || 900;

    // Use the current fit scale (view.scale set by fitBoardInView).
    // Sizing based on fit scale means the image appears roughly viewport-sized
    // at the default zoom — you see most of the image, not a tiny crop.
    // A safety factor of 1.5 gives panning room without making the image
    // look zoomed in at the default view.
    const fitScale = view.scale || 1.0;
    const neededW  = (vpW / fitScale) * 1.5;
    const neededH  = (vpH / fitScale) * 1.5;

    // Match the image's own aspect ratio exactly
    const aspect = probe.naturalWidth / probe.naturalHeight;
    let bgW = Math.max(neededW, neededH * aspect);
    let bgH = bgW / aspect;
    if (bgH < neededH) { bgH = neededH; bgW = bgH * aspect; }

    const boardEl = document.getElementById('board');
    const boardW  = boardEl ? boardEl.offsetWidth  : bW;
    const boardH  = boardEl ? boardEl.offsetHeight : bH;

    // Position using absolute px centred on the board grid.
    // % values would be relative to #board-world which has no explicit size
    // until fitBoardInView pins it — using px avoids any reflow-based jump.
    const bgLeft = Math.round((boardW - bgW) / 2);
    const bgTop  = Math.round((boardH - bgH) / 2);
    bg.style.width   = Math.round(bgW) + 'px';
    bg.style.height  = Math.round(bgH) + 'px';
    bg.style.left    = bgLeft + 'px';
    bg.style.top     = bgTop  + 'px';
    bg.style.display = 'block';

    // Store bounds so _clampView can keep the bg filling the viewport
    _bgBounds = { left: bgLeft, top: bgTop, width: bgW, height: bgH };

    // Gradient tint over the image — both set as background layers
    bg.style.backgroundImage = [
      `linear-gradient(150deg,` +
        `rgba(200,230,201,${op}) 0%,` +
        `rgba(178,223,219,${op}) 50%,` +
        `rgba(197,202,233,${op}) 100%)`,
      `url('${cfg.image}')`,
    ].join(', ');
    bg.style.backgroundSize     = `cover, cover`;
    bg.style.backgroundPosition = `center, ${pos}`;
    bg.style.filter = blur > 0 ? `blur(${blur}px)` : '';
  };

  probe.onerror = () => {
    if (probe !== _bgProbe) return;
    _bgProbe = null;
    console.warn(`BOARD_BACKGROUND: could not load image "${cfg.image}"`);
    bg.style.display = 'none';
    _bgBounds = null;
  };

  probe.src = cfg.image;
}

// ── Wire Game-Screen Controls ─────────────────────────────────────────────────

let _rollListenerAdded = false;
function wireGameControls() {
  if (!_rollListenerAdded) {
    document.getElementById('roll-btn').addEventListener('click', handleRoll);
    document.getElementById('gm-toggle').addEventListener('click', () => {
      document.getElementById('gm-controls').classList.toggle('hidden');
    });
    _rollListenerAdded = true;
  }
}

// ── Refresh UI ────────────────────────────────────────────────────────────────

function refreshUI() {
  const player    = currentPlayer();
  const phaseText = state.turnPhase === 'roll' ? 'Roll the dice' : 'Resolving…';
  updateCurrentPlayerDisplay(player, phaseText);
  updateScoreboard(state.players);
  updateGMPlayerSelect(state.players);
  updateBoardTokens(state.players);
  const canRoll = state.turnPhase === 'roll';
  document.getElementById('roll-btn').disabled = !canRoll;
  _setManualDiceDisabled(!canRoll);
}

// ── Turn Logic ────────────────────────────────────────────────────────────────

/**
 * Called when host clicks a manual die face (physical dice play).
 * Network: sends manual_roll to server (players get roll_result) then processes locally.
 * Offline: calls _processRoll directly. No _awaitingRoll involved — cannot get stuck.
 */
async function handleManualRoll(n) {
  if (state.turnPhase !== 'roll') return;
  const player = currentPlayer();
  if (player.skipNextTurn) { await handleRoll(); return; }

  state.turnPhase = 'resolving';
  const rollBtn = document.getElementById('roll-btn');
  rollBtn.disabled = true;
  _setManualDiceDisabled(true);

  _preRollSnapshot = _createSnapshot();
  const myTurnToken = ++_turnToken;
  _preRollSnapshot._turnToken = myTurnToken;

  if (_isNetworkGame) {
    // Notify player screens of the roll (server broadcasts roll_result to them only).
    // Host processes the roll locally — no waiting for roll_result, can't get stuck.
    TX_NET.manualRoll(_networkGameId, n);
    await _processRoll(n);
  } else {
    await _processRoll(n);
  }
}

// Disables/enables all manual die buttons in sync with the Roll Dice button.
function _setManualDiceDisabled(disabled) {
  document.querySelectorAll('.manual-die').forEach(btn => { btn.disabled = disabled; });
}

// Renders the CSS dot-die inside each .manual-die button on first load.
function _initManualDiceFaces() {
  document.querySelectorAll('.manual-die').forEach((btn, i) => {
    const n = i + 1;
    btn.innerHTML = renderDie(n, 'die-sm');
    btn.title = `Roll ${n}`;
  });
}

async function handleRoll() {
  if (state.turnPhase !== 'roll') return;
  const player = currentPlayer();

  if (player.skipNextTurn) {
    // Snapshot + token taken before the modal so the skip is undoable and the
    // OK callback bails if undo was pressed while the modal was open.
    player.skipNextTurn = false;
    _preRollSnapshot = _createSnapshot();
    const myToken = ++_turnToken;
    showModal({
      icon: '⏭', title: 'Turn Skipped',
      content: `<strong>${player.name}</strong> must skip this turn.`,
      actions: [{ label: 'OK', class: 'btn btn-primary', callback: () => {
        if (_turnToken !== myToken) return; // undo was pressed while modal was open
        state.history.push({
          roll:        0,
          playerId:    player.id,
          playerName:  player.name,
          playerColor: player.color,
          playerToken: player.token,
          spaceType:   'skip',
          spaceName:   'Turn Skipped',
          posBefore:   player.position,
          posAfter:    player.position,
          scoreBefore: player.score,
          scoreAfter:  player.score,
          snapshot:    _preRollSnapshot,
        });
        renderHistoryPanel(state.history);
        endTurn();
        saveGame();
        if (_isNetworkGame) {
          // Sync state + emit turn_result so player screens advance to next player
          // and the activity feed shows the skip instead of staying stuck.
          TX_NET.emitTurnResult(_networkGameId, {
            playerId:    player.id,
            playerName:  player.name,
            scoreDelta:  0,
            newPosition: player.position,
            posBefore:   player.position,
            spaceType:   'skip_turn',
            spaceName:   null,
          });
          _syncStateToServer();
        }
      }}],
    });
    return;
  }

  state.turnPhase = 'resolving';
  const rollBtn = document.getElementById('roll-btn');
  rollBtn.disabled = true;
  _setManualDiceDisabled(true);

  // Save snapshot before any changes (used for undo and history recording)
  _preRollSnapshot = _createSnapshot();
  const myTurnToken = ++_turnToken; // used to detect if undo invalidated this turn
  _preRollSnapshot._turnToken = myTurnToken;

  if (_isNetworkGame) {
    rollBtn.textContent = 'Waiting for roll...';
    _awaitingRoll = true;
    TX_NET.requestRoll(_networkGameId);
    // Execution continues in TX_NET.on('roll_result') → _processRoll(roll)
  } else {
    const roll = rollDice();
    await _processRoll(roll);
  }
}

async function _processRoll(roll) {
  const player = currentPlayer();
  _currentRoll = roll;
  const myToken = _turnToken; // snapshot; undo increments _turnToken to cancel this turn

  // Restore roll button text (may have been changed for network wait)
  const rollBtn = document.getElementById('roll-btn');
  if (rollBtn) rollBtn.textContent = 'Roll Dice';

  await animateDice(roll);

  // Show large dice result on the board (visible while players watch the token move)
  await _showDiceOverlay(roll, player);

  // Record position and score before the move
  const posBefore   = player.position;
  const scoreBefore = player.score;

  // Animate token hopping through each intermediate space
  const moveBlocked = await animatePlayerMovement(player, state.board, roll, state.players);

  // Exact-finish: move was blocked — show message and end turn without resolving a space
  if (moveBlocked) {
    if (_turnToken !== myToken) return;
    const spacesLeft = state.board.length - 1 - player.position;
    showToast(`Need exactly ${spacesLeft} to finish!`);
    updateScoreboard(state.players);
    saveGame();
    state._pendingHistory = { roll, player, posBefore, scoreBefore };
    _addHistoryEntry(roll, player, state.board[player.position], scoreBefore, posBefore);
    state._pendingHistory = null;
    if (_isNetworkGame) {
      TX_NET.emitTurnResult(_networkGameId, {
        playerId: player.id, playerName: player.name,
        scoreDelta: 0, newPosition: player.position, posBefore,
        spaceType: 'blocked', spaceName: null,
      });
      TX_NET.emitSpaceCardDone(_networkGameId);
    }
    endTurn();
    return;
  }

  // Award finishing bonus (after animation reaches the end)
  if (player.finished && player.finishOrder === null) {
    state.finishCount++;
    player.finishOrder = state.finishCount;
    addScore(player, CONFIG.FINISH_BONUS[state.finishCount - 1] ?? 1);
  }

  updateBoardTokens(state.players); // final stable render (no hop animation)
  updateScoreboard(state.players);
  saveGame();

  // Store these for afterSpaceResolved to record the history entry
  state._pendingHistory = { roll, player, posBefore, scoreBefore };

  const space = state.board[player.position];

  // Broadcast space info to player screens in network mode
  if (_isNetworkGame) _emitSpaceCard(space, player);

  // Guard: if undo was pressed during animation, this turn is cancelled.
  if (_turnToken !== myToken) return;

  if (space.type === 'action') {
    showSpaceModal(space, player, (guessed) => {
      if (_turnToken !== myToken) return;
      if (guessed) showGuesserModal(state.players, player, afterSpaceResolved);
      else afterSpaceResolved();
    });
  } else {
    showSpaceModal(space, player, afterSpaceResolved);
  }
}

function afterSpaceResolved() {
  // If undo was pressed while modal was open, bail out — state is already restored.
  if (!state._pendingHistory) return;

  // Broadcast turn outcome to players before clearing pendingHistory
  if (_isNetworkGame && state._pendingHistory) {
    const { player, posBefore, scoreBefore } = state._pendingHistory;
    TX_NET.emitTurnResult(_networkGameId, {
      playerId:   player.id,
      playerName: player.name,
      scoreDelta: player.score - scoreBefore,
      newPosition: player.position,
      posBefore,
      spaceType: state.board[player.position]?.type,
      spaceName: state.board[player.position]?.name || null,
    });
  }
  if (_isNetworkGame) TX_NET.emitSpaceCardDone(_networkGameId);
  updateScoreboard(state.players);
  updateBoardTokens(state.players);
  highlightSpace(currentPlayer().position);

  // Record history entry for this turn
  if (state._pendingHistory) {
    const { roll, player, posBefore, scoreBefore } = state._pendingHistory;
    const space = state.board[player.position];
    _addHistoryEntry(roll, player, space, scoreBefore, posBefore);
    state._pendingHistory = null;
  }

  if (currentPlayer().finished) {
    if (state.players.every(p => p.finished)) {
      clearSave();
      setTimeout(() => showEndScreen(state.players), 600);
      return;
    }
  }

  // Check for extra turn earned by a deed card
  if (currentPlayer().hasExtraTurn) {
    currentPlayer().hasExtraTurn = false;
    state.turnPhase = 'roll';
    document.getElementById('roll-btn').disabled = false;
    updateCurrentPlayerDisplay(currentPlayer(), '🎲 Roll again — extra turn!');
    return; // skip endTurn — same player goes again
  }

  endTurn();     // sets turnPhase = 'roll' — must happen BEFORE saveGame
  saveGame();    // saved state will have turnPhase='roll', not 'resolving',
                 // so resuming after refresh won't re-open the space modal
  _syncStateToServer();
}

function endTurn() {
  const total = state.players.length;
  let next = (state.currentPlayerIndex + 1) % total;
  let attempts = 0;
  while (state.players[next].finished && attempts < total) {
    next = (next + 1) % total;
    attempts++;
  }
  if (state.players[next].finished) { showEndScreen(state.players); return; }

  state.currentPlayerIndex = next;
  state.turnPhase = 'roll';
  refreshUI();
  highlightSpace(currentPlayer().position);
}

// ── GM Controls ───────────────────────────────────────────────────────────────

function getGMSelectedPlayer() {
  const id = parseInt(document.getElementById('gm-player-select').value, 10);
  return state.players.find(p => p.id === id);
}

function gmAdjustScore(amount) {
  const p = getGMSelectedPlayer();
  if (!p) return;
  addScore(p, amount);
  updateScoreboard(state.players);
  saveGame();
}

function gmMovePlayer(steps) {
  const p = getGMSelectedPlayer();
  if (!p) return;
  movePlayer(p, state.board, steps);
  updateBoardTokens(state.players);
  updateScoreboard(state.players);
  highlightSpace(p.position);
  saveGame();
}

function gmSkipTurn() {
  const p = getGMSelectedPlayer();
  if (!p) return;
  p.skipNextTurn = true;
  alert(`${p.name}'s next turn will be skipped.`);
}

// ── Pan + Zoom ────────────────────────────────────────────────────────────────

const view = { x: 0, y: 0, scale: 1 };
// Both limits are driven by CONFIG.ZOOM (see config.js).
// SCALE_MIN is recalculated in fitBoardInView() after the board renders.
let SCALE_MIN = 0.2;
let SCALE_MAX = CONFIG.ZOOM?.maxScale ?? 2.0;

// Background bounds in board-world coordinates — set when bg loads.
// Used to clamp panning so the background always covers the viewport.
let _bgBounds = null; // { left, top, width, height }

/** Clamp view.x / view.y so the background image always fills the viewport. */
function _clampView() {
  if (!_bgBounds) return;
  const vp = document.getElementById('board-viewport');
  if (!vp) return;
  const vpW = vp.offsetWidth;
  const vpH = vp.offsetHeight;
  const { left: bL, top: bT, width: bW, height: bH } = _bgBounds;
  const s = view.scale;
  // bg edge positions in viewport space: view.x + bL*s (left), view.x + (bL+bW)*s (right)
  // For bg to cover the viewport: left_vp ≤ 0 AND right_vp ≥ vpW
  view.x = Math.min(-(bL * s), Math.max(vpW - (bL + bW) * s, view.x));
  view.y = Math.min(-(bT * s), Math.max(vpH - (bT + bH) * s, view.y));
}
let _isPanning = false, _panOrigin = { x: 0, y: 0 }, _lastTouchDist = null;

function _applyView() {
  _clampView(); // keep view within bg image bounds (no-op if bg not loaded yet)
  const world = document.getElementById('board-world');
  if (world) world.style.transform = `translate(${view.x}px,${view.y}px) scale(${view.scale})`;
}

function _updateZoomLabel() {
  const lbl = document.getElementById('zoom-label');
  if (lbl) lbl.textContent = Math.round(view.scale * 100) + '%';
}

function _zoomAt(cx, cy, factor) {
  const ns = Math.min(SCALE_MAX, Math.max(SCALE_MIN, view.scale * factor));
  const r  = ns / view.scale;
  view.x = cx - r * (cx - view.x);
  view.y = cy - r * (cy - view.y);
  view.scale = ns;
  _applyView(); _updateZoomLabel();
}

function fitBoardInView() {
  const vp    = document.getElementById('board-viewport');
  const board = document.getElementById('board');
  if (!vp || !board) return;

  // Calling offsetWidth/Height forces a synchronous reflow so we get accurate
  // measurements right now — no requestAnimationFrame needed.
  // This also means the transform is applied before the first paint, eliminating
  // the visible jump from position (0,0) to the centred fit position.
  const pad = 32;
  const bW  = board.offsetWidth;
  const bH  = board.offsetHeight;
  if (!bW || !bH) return;

  const fitScale = Math.min(
    (vp.offsetWidth  - pad * 2) / bW,
    (vp.offsetHeight - pad * 2) / bH,
    1.0
  );

  view.scale = fitScale;
  view.x = (vp.offsetWidth  - bW * fitScale) / 2;
  view.y = (vp.offsetHeight - bH * fitScale) / 2;

  // Pin board-world to the board grid size so #board-bg loading never causes
  // a reflow that shifts the board.
  const boardWorld = document.getElementById('board-world');
  if (boardWorld) { boardWorld.style.width = bW + 'px'; boardWorld.style.height = bH + 'px'; }

  // Minimum zoom: a configurable fraction below the fit scale
  SCALE_MIN = Math.max(0.15, fitScale * (CONFIG.ZOOM?.outFactor ?? 0.65));

  _applyView();
  _updateZoomLabel();

  // Reveal the board now that transform is already applied.
  if (boardWorld) boardWorld.style.opacity = '1';

  // Apply background with the correct fit scale now that view.scale is set.
  _applyBoardBackground();
}

function initPanZoom() {
  const vp = document.getElementById('board-viewport');

  vp.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = vp.getBoundingClientRect();
    _zoomAt(e.clientX - rect.left, e.clientY - rect.top, e.deltaY < 0 ? 1.12 : 1/1.12);
  }, { passive: false });

  vp.addEventListener('mousedown', e => {
    if (e.button !== 0) return;
    _isPanning = true;
    _panOrigin = { x: e.clientX - view.x, y: e.clientY - view.y };
    vp.classList.add('panning');
  });
  window.addEventListener('mousemove', e => {
    if (!_isPanning) return;
    view.x = e.clientX - _panOrigin.x;
    view.y = e.clientY - _panOrigin.y;
    _applyView();
  });
  window.addEventListener('mouseup', () => {
    _isPanning = false;
    document.getElementById('board-viewport')?.classList.remove('panning');
  });

  vp.addEventListener('touchstart', e => {
    if (e.touches.length === 1) {
      _isPanning = true;
      _panOrigin = { x: e.touches[0].clientX - view.x, y: e.touches[0].clientY - view.y };
    }
    if (e.touches.length === 2) _lastTouchDist = _touchDist(e.touches);
  }, { passive: true });

  vp.addEventListener('touchmove', e => {
    e.preventDefault();
    if (e.touches.length === 1 && _isPanning) {
      view.x = e.touches[0].clientX - _panOrigin.x;
      view.y = e.touches[0].clientY - _panOrigin.y;
      _applyView();
    }
    if (e.touches.length === 2 && _lastTouchDist) {
      const dist = _touchDist(e.touches);
      const rect = vp.getBoundingClientRect();
      const cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
      const cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;
      _zoomAt(cx, cy, dist / _lastTouchDist);
      _lastTouchDist = dist;
    }
  }, { passive: false });

  vp.addEventListener('touchend', () => { _isPanning = false; _lastTouchDist = null; });
}

function _touchDist(t) {
  return Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
}

function zoomIn()    { const vp = document.getElementById('board-viewport'); _zoomAt(vp.offsetWidth/2, vp.offsetHeight/2, 1.2); }
function zoomOut()   { const vp = document.getElementById('board-viewport'); _zoomAt(vp.offsetWidth/2, vp.offsetHeight/2, 1/1.2); }
function zoomReset() { fitBoardInView(); }

// ── Reset ─────────────────────────────────────────────────────────────────────

function resetToSetup() {
  const legend = document.getElementById('board-legend');
  if (legend) legend.remove();
  timerStop();
  view.x = 0; view.y = 0; view.scale = 1; _applyView();
  // Hide board-world and bg; clear bounds so clamp doesn't affect the next game
  const world = document.getElementById('board-world');
  if (world) world.style.opacity = '0';
  const bg = document.getElementById('board-bg');
  if (bg) bg.style.display = 'none';
  _bgBounds = null;
  if (_bgProbe) { _bgProbe.onload = null; _bgProbe.onerror = null; _bgProbe = null; }
  try { localStorage.removeItem('tx_net_game'); } catch {}
  _isNetworkGame = false;
  _networkGameId = null;
  state = {
    gameId: null, players: [], board: [], gameLength: 'medium',
    pathIndex: 'random', currentPlayerIndex: 0,
    phase: 'setup', turnPhase: 'roll', finishCount: 0,
  };
  renderPlayerRows();
  populatePathSelector('medium');
  document.querySelector('input[name="gameLength"][value="medium"]').checked = true;
  showScreen('setup-screen');
}

// ── Theme loading ─────────────────────────────────────────────────────────────

let _activeThemeId = null;

function _resetToEngineDefaults() {
  Object.assign(CONFIG.GAME,             _ENGINE_DEFAULTS.GAME);
  Object.assign(CONFIG.THEME,            _ENGINE_DEFAULTS.THEME);
  Object.assign(CONFIG.BOARD_BACKGROUND, _ENGINE_DEFAULTS.BOARD_BACKGROUND);
  CONFIG.LANDMARKS = [];
  CONFIG.EDITION_SPACE_DISTRIBUTION = null;
  for (const [type, defaults] of Object.entries(_ENGINE_DEFAULTS.SPACE_INFO)) {
    if (CONFIG.SPACE_INFO[type]) Object.assign(CONFIG.SPACE_INFO[type], defaults);
  }
}

function _mergeThemeConfig() {
  const T = window.EDITION_CONFIG;
  if (!T) return;
  if (T.GAME)                Object.assign(CONFIG.GAME,             T.GAME);
  if (T.THEME)               Object.assign(CONFIG.THEME,            T.THEME);
  if (T.LANDMARKS)           CONFIG.LANDMARKS = T.LANDMARKS;
  if (T.BOARD_BACKGROUND)    Object.assign(CONFIG.BOARD_BACKGROUND, T.BOARD_BACKGROUND);
  if (T.SPACE_DISTRIBUTION)  CONFIG.EDITION_SPACE_DISTRIBUTION = T.SPACE_DISTRIBUTION;
  if (T.SPACE_INFO) {
    for (const [type, overrides] of Object.entries(T.SPACE_INFO)) {
      if (CONFIG.SPACE_INFO[type]) Object.assign(CONFIG.SPACE_INFO[type], overrides);
      else CONFIG.SPACE_INFO[type] = overrides;
    }
  }
}

async function loadTheme(themeId) {
  if (!themeId) return;
  if (_activeThemeId === themeId) return;
  _resetToEngineDefaults();
  window.EDITION_CONFIG   = null;
  window.QUESTIONS_DATA = [];
  window.DEEDS_DATA     = [];

  // Load JS files (config.js required; questions.js + deeds.js are fallbacks
  // used when the HTTP server isn't running and CSV fetch would fail)
  const files = ['config.js', 'questions.js', 'deeds.js'];
  for (const file of files) {
    const src = `game_editions/${themeId}/${file}`;
    await new Promise((resolve) => {
      document.querySelectorAll(`script[data-tx="${src}"]`).forEach(s => s.remove());
      const el = document.createElement('script');
      el.setAttribute('data-tx', src);
      el.src = src + '?_=' + Date.now();
      el.onload  = resolve;
      el.onerror = () => { console.warn(`Theme file not found: ${src}`); resolve(); };
      document.head.appendChild(el);
    });
  }

  // Try to load CSV files via fetch (requires HTTP server — python3 -m http.server 8080).
  // If successful they REPLACE the JS-loaded data, so CSV is the primary content source.
  // If fetch fails (file:// protocol) the JS fallback data is used silently.
  await _loadThemeCSV(themeId);

  _activeThemeId = themeId;
  _mergeThemeConfig();
  _populateCategoryFilter();
  try { localStorage.setItem('triventurex_edition', themeId); } catch {}
}

// ── CSV content loading ───────────────────────────────────────────────────────

/**
 * Try to fetch and parse questions.csv and deeds.csv for the given theme.
 * Overrides JS-loaded QUESTIONS_DATA / DEEDS_DATA if CSV has content.
 * Fails silently when running from file:// (fetch not allowed).
 */
async function _loadThemeCSV(themeId) {
  const get = async (url) => {
    try { const r = await fetch(url); return r.ok ? r.text() : null; }
    catch { return null; }
  };

  const qText = await get(`game_editions/${themeId}/questions.csv`);
  if (qText) {
    const parsed = _parseQuestionsCSV(qText);
    if (parsed.length) { window.QUESTIONS_DATA = parsed; }
  }

  const dText = await get(`game_editions/${themeId}/deeds.csv`);
  if (dText) {
    const parsed = _parseDeedsCSV(dText);
    if (parsed.length) { window.DEEDS_DATA = parsed; }
  }
}

/** Split one CSV line, respecting quoted fields. */
function _csvSplit(line) {
  const out = []; let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      if (inQ && line[i+1] === '"') { cur += '"'; i++; }
      else inQ = !inQ;
    } else if (c === ',' && !inQ) { out.push(cur); cur = ''; }
    else cur += c;
  }
  out.push(cur);
  return out;
}

/** Parse a full CSV text into an array of objects keyed by the header row. */
function _parseCSV(text) {
  const lines  = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const headers = _csvSplit(lines[0]).map(h => h.trim().toLowerCase().replace(/\s+/g,'_'));
  return lines.slice(1)
    .map(l => l.trim()).filter(Boolean)
    .map(l => {
      const vals = _csvSplit(l);
      const row = {};
      headers.forEach((h, i) => { row[h] = (vals[i] ?? '').trim(); });
      return row;
    });
}

/**
 * Parse questions.csv into the QUESTIONS_DATA format.
 *
 * CSV columns (header row required):
 *   question, type, answer, opt_a, opt_b, opt_c, opt_d, difficulty, category, subcategory, topic, note
 *
 * type = "multi"  → answer is the correct option NUMBER (1=opt_a, 2=opt_b, …)
 * type = "open"   → answer is the text; opt_a-d left blank
 */
function _parseQuestionsCSV(text) {
  return _parseCSV(text)
    .filter(r => r.question && r.type)
    .map((r, i) => {
      const isMulti = r.type.trim() === 'multi';
      const opts    = [r.opt_a, r.opt_b, r.opt_c, r.opt_d].filter(Boolean);
      const answer  = isMulti
        ? (['A','B','C','D'][parseInt(r.answer, 10) - 1] ?? 'A')
        : r.answer;
      return {
        id:     i + 1,
        q:      r.question,
        opts:   isMulti ? opts : [],
        answer,
        diff:   r.difficulty   || 'easy',
        cat:    r.category     || 'general',
        subcat: r.subcategory  || '',
        topic:  r.topic        || '',
        note:   r.note         || '',
      };
    });
}

/**
 * Parse deeds.csv into the DEEDS_DATA format.
 *
 * CSV columns (header row required):
 *   type, text, effect, value, landmark, effect_2, value_2, landmark_2,
 *   effect_3, value_3, landmark_3, mood
 *
 * type   = "good" or "bad"
 * effect = score_add | score_remove | move_forward | move_back | move_to_landmark |
 *          move_to_next_landmark | skip_turn | extra_turn | all_players_gain |
 *          all_players_lose | protection
 * value  = number of points or spaces (0 for landmark-targeting effects)
 * landmark = landmark name (only for move_to_landmark, otherwise blank)
 * effect_2/value_2/landmark_2 — optional second effect for variable rewards
 * effect_3/value_3/landmark_3 — optional third effect for variable rewards
 * mood   = flavour tag (e.g. blessing, social, challenge, reflection, funny, risk)
 */
function _parseDeedsCSV(text) {
  return _parseCSV(text)
    .filter(r => r.type && r.text && r.effect)
    .map((r, i) => {
      const buildEffect = (eff, val, lm) =>
        eff ? { effect: eff, value: parseFloat(val) || 0, landmark: lm || null } : null;

      const effects = [
        buildEffect(r.effect,   r.value,   r.landmark),
        buildEffect(r.effect_2, r.value_2, r.landmark_2),
        buildEffect(r.effect_3, r.value_3, r.landmark_3),
      ].filter(Boolean);

      return {
        id:       i + 1,
        type:     r.type,
        text:     r.text,
        effects,                        // all possible effects (for variable rewards)
        effect:   effects[0]?.effect,   // primary (used as default)
        value:    effects[0]?.value  ?? 0,
        landmark: effects[0]?.landmark ?? null,
        mood:     r.mood || '',
      };
    });
}

function renderThemePicker(currentId) {
  const section = document.getElementById('theme-section');
  const picker  = document.getElementById('theme-picker');
  if (!picker) return;
  const themes = window.TRIVENTUREX_EDITIONS || [];
  if (themes.length <= 1) { if (section) section.style.display = 'none'; return; }
  if (section) section.style.display = '';
  picker.innerHTML = themes.map(t => `
    <div class="theme-card ${t.id === currentId ? 'selected' : ''}"
         style="${t.id === currentId ? `border-color:${t.accentColor};background:${t.accentColor}18` : ''}"
         onclick="onThemePicked('${t.id}')">
      <div class="theme-card-icon">${t.icon}</div>
      <div class="theme-card-name">${t.name}</div>
      <div class="theme-card-desc">${t.description}</div>
    </div>`).join('');
}

async function onThemePicked(themeId) {
  if (themeId === _activeThemeId) return;
  const picker = document.getElementById('theme-picker');
  if (picker) picker.style.opacity = '0.5';
  await loadTheme(themeId);
  _applyTheme(); _applyBranding();
  renderThemePicker(themeId);
  const len = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
  populatePathSelector(len);
  if (picker) picker.style.opacity = '1';
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  // Validate saved theme against the registry — if the ID no longer exists
  // (e.g. folder was renamed), fall back to the first registered theme.
  const savedRaw     = (() => { try { return localStorage.getItem('triventurex_edition'); } catch { return null; } })();
  const knownIds     = (window.TRIVENTUREX_EDITIONS || []).map(t => t.id);
  const savedTheme   = knownIds.includes(savedRaw) ? savedRaw : null;
  const defaultTheme = knownIds[0] || 'swab-quest';
  await loadTheme(savedTheme || defaultTheme);

  _applyTheme();
  _applyBranding();
  initSetupScreen();
  initPanZoom();
  _initManualDiceFaces();
  checkAndShowResume();
  showScreen('setup-screen');

  // Try to load Socket.IO client (only served by Node.js server, not Python/file://).
  // Silent fail in offline mode — TX_NET does nothing when io is undefined.
  const socketScript    = document.createElement('script');
  socketScript.src      = '/socket.io/socket.io.js';
  socketScript.onload   = () => {
    if (TX_NET.connect()) {
      _initSocketHandlers();
    }
  };
  socketScript.onerror  = () => {
    // Not served by Node.js — multiplayer tabs stay hidden, game works normally
  };
  document.head.appendChild(socketScript);
});

/**
 * Apply CONFIG.THEME and CONFIG.SPACE_INFO colours as CSS custom properties.
 * This is the single handoff point: config.js controls all colours,
 * CSS rules read them via var(--name) — no hardcoded hex in CSS needed.
 */
function _applyTheme() {
  const root = document.documentElement;

  // 1. Explicit THEME overrides (UI colours, gradients, etc.)
  for (const [prop, value] of Object.entries(CONFIG.THEME || {})) {
    root.style.setProperty(prop, value);
  }

  // 2. Space type colours from SPACE_INFO → --c-<type> CSS variables
  //    e.g. SPACE_INFO.question.color → --c-question
  //    These drive both the board space backgrounds and the legend dots.
  for (const [type, info] of Object.entries(CONFIG.SPACE_INFO || {})) {
    if (info.color) {
      root.style.setProperty(`--c-${type.replace(/_/g, '-')}`, info.color);
    }
  }
}
