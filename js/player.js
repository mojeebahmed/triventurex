/**
 * player.js
 * Logic for the player.html lightweight player screen.
 * Handles badge picker, form validation, TX_NET events, and game-view rendering.
 */

// ── Constants ─────────────────────────────────────────────────────────────────

const TOKENS = ['🌟','⚡','🔥','💎','🏆','🎯','🚀','🌙','🍀','🎲','🎸','🏅','🦁','🐉','🌊','🌺'];
const COLORS = [
  '#E53935','#8E24AA','#1E88E5','#00897B',
  '#43A047','#FB8C00','#F4511E','#6D4C41',
  '#546E7A','#D81B60','#3949AB','#00ACC1',
];
const DICE_FACES = ['⚀','⚁','⚂','⚃','⚄','⚅'];
const LS_IDENTITY = 'triventurex_player_identity';
const LS_SESSION  = 'triventurex_game_session';

// ── Player state ──────────────────────────────────────────────────────────────

let _myToken  = TOKENS[0];
let _myColor  = COLORS[3];
let _myName   = '';
let _myId     = null;
let _gameId   = null;
let _isMyTurn = false;
let _turnPhase = 'roll';
let _lastRoll  = null;
let _lastCurrentPlayerName = '';
let _pendingRejoin = null;
let _rollTimeout   = null;

// ── Activity log ──────────────────────────────────────────────────────────────

const _activityLog = [];

function _addActivity(icon, html) {
  _activityLog.push({ icon, html });
  if (_activityLog.length > 10) _activityLog.splice(0, _activityLog.length - 5);
  _renderActivityList();
}

function _renderActivityList() {
  const list = document.getElementById('ab-activity-list');
  if (!list) return;
  const entries = _activityLog.slice(-5).reverse(); // newest first
  if (!entries.length) {
    list.innerHTML = '<div class="ab-empty">Waiting for activity...</div>';
    return;
  }
  list.innerHTML = entries.map(e =>
    `<div class="ab-entry"><span class="ab-entry-icon">${e.icon}</span><span class="ab-entry-text">${e.html}</span></div>`
  ).join('');
}

// ── CSS die rendering ─────────────────────────────────────────────────────────

function renderDie(n, sizeClass = '') {
  const layouts = {
    1: [[50,50]],
    2: [[30,30],[70,70]],
    3: [[30,30],[50,50],[70,70]],
    4: [[30,30],[70,30],[30,70],[70,70]],
    5: [[30,30],[70,30],[50,50],[30,70],[70,70]],
    6: [[30,30],[70,30],[30,50],[70,50],[30,70],[70,70]],
  };
  const dots = layouts[n] || layouts[1];
  const cls  = sizeClass ? `die-face ${sizeClass}` : 'die-face';
  return `<div class="${cls}">${dots.map(([x,y]) =>
    `<span class="die-dot" style="left:${x}%;top:${y}%"></span>`
  ).join('')}</div>`;
}

// ── Action box ────────────────────────────────────────────────────────────────

function _setActionMode(mode) {
  // mode: 'dice' | 'rolled' | 'card' | 'activity'
  document.querySelectorAll('.ab-mode').forEach(el => el.classList.remove('active'));
  document.getElementById(`ab-${mode}`).classList.add('active');
  const box = document.getElementById('action-box');
  box.className = `action-box ${mode}-mode`;
}

function onActionBoxClick() {
  if (!document.getElementById('action-box').classList.contains('dice-mode')) return;
  playerRoll();
}

function playerRoll() {
  if (!_isMyTurn || _turnPhase !== 'roll') return;
  // Show a rolling state (keep dice mode border but remove click)
  document.getElementById('action-box').className = 'action-box rolling-mode';
  document.getElementById('ab-die-render').innerHTML = renderDie(Math.floor(Math.random()*6)+1, 'die-lg');
  TX_NET.requestRoll(_gameId);

  // Safety timeout: reset to dice mode if server never responds
  clearTimeout(_rollTimeout);
  _rollTimeout = setTimeout(() => {
    if (document.getElementById('action-box').classList.contains('rolling-mode')) {
      _setActionMode('dice');
    }
  }, 5000);
}

function _showCardMode({ spaceType, spaceName, playerName, deedText, deedEffect, deedValue, deedLandmark }) {
  const meta = SPACE_META[spaceType] || { icon: '•', label: spaceType };
  document.getElementById('ab-card-icon').textContent = meta.icon;
  document.getElementById('ab-card-type').textContent = meta.label;
  document.getElementById('ab-card-title').textContent = spaceName || (playerName ? `${playerName} landed here` : '');

  let body = '';
  const isGood = spaceType === 'good_deed' || spaceType === 'landmark' || spaceType === 'finish';
  if (spaceType === 'question') {
    body = 'Get ready — a question is coming!';
  } else if (spaceType === 'action') {
    body = 'Perform the action card!';
  } else if (spaceType === 'skip') {
    body = 'This player will skip their next turn.';
  } else if (spaceType === 'finish') {
    body = '🎉 Reached the finish!';
  } else if (deedText) {
    body = `<em>${deedText}</em>`;
    if (deedEffect) {
      const effectLabel = EFFECT_LABELS[deedEffect]?.(deedValue, deedLandmark) || deedEffect;
      const cls = isGood ? 'good' : 'bad';
      body += `<br><span class="ab-effect ${cls}">${effectLabel}</span>`;
    }
  }
  document.getElementById('ab-card-body').innerHTML = body;
  _setActionMode('card');
}

// ── Views ─────────────────────────────────────────────────────────────────────

function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

// ── Identity persistence ──────────────────────────────────────────────────────

function _loadIdentity() {
  try {
    const raw = localStorage.getItem(LS_IDENTITY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function _saveIdentity() {
  try {
    localStorage.setItem(LS_IDENTITY, JSON.stringify({
      name:  _myName,
      token: _myToken,
      color: _myColor,
    }));
  } catch {}
}

// ── Session persistence (for rejoin on refresh) ───────────────────────────────

function _saveSession(gameId, playerId, token) {
  try { localStorage.setItem(LS_SESSION, JSON.stringify({ gameId, playerId, token })); } catch {}
}
function _loadSession() {
  try { const r = localStorage.getItem(LS_SESSION); return r ? JSON.parse(r) : null; } catch { return null; }
}
function _clearSession() {
  try { localStorage.removeItem(LS_SESSION); } catch {}
}

// ── Badge helpers ─────────────────────────────────────────────────────────────

function _initials(name) {
  return (name || '').slice(0, 2).toUpperCase() || '?';
}

function _applyBadge(badgeEl, emojiEl, initialsEl, colorSrc) {
  if (badgeEl)    badgeEl.style.background = colorSrc || _myColor;
  if (emojiEl)    emojiEl.textContent      = _myToken;
  if (initialsEl) initialsEl.textContent   = _initials(_myName);
}

function updateBadgeInitials() {
  _myName = document.getElementById('input-name').value.trim();
  document.getElementById('join-badge-initials').textContent = _initials(_myName);
}

function _refreshJoinBadge() {
  document.getElementById('join-badge').style.background = _myColor;
  document.getElementById('join-badge-emoji').textContent = _myToken;
  document.getElementById('join-badge-initials').textContent = _initials(_myName);
}

// ── Badge picker ──────────────────────────────────────────────────────────────

function openBadgePicker() {
  // Render tokens
  document.getElementById('picker-tokens').innerHTML = TOKENS.map(t =>
    `<div class="picker-token ${t === _myToken ? 'selected' : ''}"
         onclick="selectToken('${t}')">${t}</div>`
  ).join('');

  // Render colors
  document.getElementById('picker-colors').innerHTML = COLORS.map(c =>
    `<div class="picker-color ${c === _myColor ? 'selected' : ''}"
         style="background:${c}"
         onclick="selectColor('${c}')"></div>`
  ).join('');

  document.getElementById('badge-picker-overlay').classList.add('open');
}

function closeBadgePicker() {
  document.getElementById('badge-picker-overlay').classList.remove('open');
}

function closeBadgePickerOutside(e) {
  if (e.target === document.getElementById('badge-picker-overlay')) closeBadgePicker();
}

function selectToken(t) {
  _myToken = t;
  document.querySelectorAll('.picker-token').forEach(el =>
    el.classList.toggle('selected', el.textContent === t));
  _refreshJoinBadge();
}

function selectColor(c) {
  _myColor = c;
  document.querySelectorAll('.picker-color').forEach(el =>
    el.classList.toggle('selected', el.style.background === c || el.style.backgroundColor === c));
  _refreshJoinBadge();
}

// ── Join game ─────────────────────────────────────────────────────────────────

function joinGame() {
  const nameInput = document.getElementById('input-name');
  const idInput   = document.getElementById('input-game-id');

  _myName = nameInput.value.trim();
  _gameId = idInput.value.trim();

  if (!_myName) { showError('Please enter your name.'); nameInput.focus(); return; }
  if (!_gameId) { showError('Please enter a Game ID.'); idInput.focus();   return; }

  TX_NET.joinGame({
    gameId:     _gameId,
    playerName: _myName,
    token:      _myToken,
    color:      _myColor,
  });
}

// ── Error / status ────────────────────────────────────────────────────────────

function showError(msg) {
  const el = document.getElementById('error-toast');
  el.textContent = msg;
  el.classList.add('visible');
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove('visible'), 3500);
}

// ── Space metadata ────────────────────────────────────────────────────────────

const SPACE_META = {
  question:  { icon: '❓', label: 'Question'   },
  action:    { icon: '🎬', label: 'Action'     },
  good_deed: { icon: '✅', label: 'Good Deed'  },
  bad_deed:  { icon: '❌', label: 'Bad Deed'   },
  landmark:  { icon: '🌍', label: 'Landmark'   },
  skip:      { icon: '⏭', label: 'Skip Turn'  },
  finish:    { icon: '🏁', label: 'Finish!'    },
};

const EFFECT_LABELS = {
  score_add:             (v) => `+${v} points`,
  score_remove:          (v) => `−${v} points`,
  move_forward:          (v) => `Move forward ${v} space${v !== 1 ? 's' : ''}`,
  move_back:             (v) => `Move back ${v} space${v !== 1 ? 's' : ''}`,
  move_to_landmark:      (_, lm) => `Go to: ${lm}`,
  move_to_next_landmark: () => 'Advance to next landmark',
  skip_turn:             () => 'Skip your next turn',
  extra_turn:            () => 'Roll again!',
  all_players_gain:      (v) => `Everyone +${v} points`,
  all_players_lose:      (v) => `Everyone −${v} points`,
  protection:            () => 'Next bad deed cancelled',
};

// ── Render game view from state_update ────────────────────────────────────────

function renderGameView({ playerStates, currentPlayerIndex, turnPhase, phase }) {
  if (!playerStates) return;

  _turnPhase = turnPhase || 'roll';

  const me = playerStates.find(p => p.id === _myId);
  if (!me) return;

  // Own badge + score
  document.getElementById('game-own-badge').style.background = me.color;
  document.getElementById('game-badge-emoji').textContent    = me.token;
  document.getElementById('game-badge-initials').textContent = _initials(me.name);
  document.getElementById('game-own-name').textContent       = me.name;
  document.getElementById('game-own-score').textContent      = me.score ?? 0;

  // Track current player name for roll_result activity entries
  const currentPlayer = playerStates[currentPlayerIndex];
  _lastCurrentPlayerName = currentPlayer?.name || '';
  _isMyTurn = currentPlayer?.id === _myId;

  // Set action box mode — never override rolled/card mode mid-resolve
  const box = document.getElementById('action-box');
  const currentMode = box.className.replace('action-box ', '').replace('-mode', '');
  if (phase === 'ended') {
    _setActionMode('activity');
  } else if (_isMyTurn && _turnPhase === 'roll') {
    _setActionMode('dice');
  } else if (_isMyTurn && _turnPhase === 'resolving') {
    // Keep rolled or card mode if active
    if (currentMode !== 'rolled' && currentMode !== 'card') {
      _setActionMode('activity');
    }
  } else {
    // Watching another player — keep card mode if showing
    if (currentMode !== 'card') {
      _setActionMode('activity');
    }
  }

  // Other players list
  const othersList = document.getElementById('other-players-list');
  othersList.innerHTML = playerStates.map((p, idx) => {
    const isActive = idx === currentPlayerIndex;
    return `
      <div class="other-player-row">
        <div class="mini-badge" style="background:${p.color}">
          <span class="badge-emoji">${p.token}</span>
          <span class="badge-initials">${_initials(p.name)}</span>
        </div>
        <span class="other-name">${p.name}${p.finished ? ' ✅' : ''}${p.disconnected ? ' ⚠️' : ''}</span>
        <span class="other-pos">pos ${p.position ?? 0}</span>
        <span class="other-score">${p.score ?? 0} pts</span>
        <div class="other-active-indicator ${isActive ? '' : 'inactive'}"></div>
      </div>`;
  }).join('');
}

// ── Lobby player list ─────────────────────────────────────────────────────────

function renderLobbyPlayers(players) {
  const list = document.getElementById('lobby-player-list');
  list.innerHTML = players.map(p => `
    <div class="lobby-player-row">
      <div class="mini-badge" style="background:${p.color}">
        <span class="badge-emoji">${p.token}</span>
        <span class="badge-initials">${_initials(p.name)}</span>
      </div>
      <span class="lobby-player-name">${p.name}</span>
    </div>`).join('');
}

// ── TX_NET event handlers ─────────────────────────────────────────────────────

TX_NET.on('connect', () => {
  document.getElementById('conn-status').classList.remove('visible');
  console.log('[player] connected');
  if (_pendingRejoin) {
    TX_NET.rejoinGame(_pendingRejoin.gameId, _pendingRejoin.playerId, _pendingRejoin.token);
    _pendingRejoin = null;
  } else if (_myId && _gameId) {
    // Socket reconnected mid-session (e.g. phone screen turned off briefly).
    // Re-register with the server so state_update events route to this socket again.
    const session = _loadSession();
    if (session && session.playerId === _myId) {
      TX_NET.rejoinGame(session.gameId, session.playerId, session.token);
    }
  }
});

TX_NET.on('disconnect', () => {
  document.getElementById('conn-status').classList.add('visible');
  console.log('[player] disconnected');
});

TX_NET.on('error', ({ message, msg }) => {
  const text = message || msg || 'An error occurred.';
  // Silently reset if we sent a roll request that was rejected
  if (text === 'Not your turn.') {
    const box = document.getElementById('action-box');
    if (box.classList.contains('rolling-mode')) {
      clearTimeout(_rollTimeout);
      _setActionMode('activity');
    }
    return;
  }
  showError(text);
});

TX_NET.on('joined', ({ gameId, playerId, phase, players, rejoinToken }) => {
  _myId   = playerId;
  _gameId = gameId;
  TX_NET.setGameId(gameId);
  TX_NET.setPlayerId(playerId);
  _saveIdentity();
  if (rejoinToken) _saveSession(gameId, playerId, rejoinToken);

  if (phase === 'playing') {
    document.getElementById('game-id-chip').textContent = gameId;
    showView('game-view');
    // state_update will follow from server
  } else {
    document.getElementById('lobby-game-id-display').textContent = gameId;
    renderLobbyPlayers(players || []);
    showView('lobby-view');
  }
});

TX_NET.on('rejoined', ({ gameId, playerId, phase, players, playerStates, currentPlayerIndex, turnPhase, finishCount }) => {
  _myId   = playerId;
  _gameId = gameId;
  TX_NET.setGameId(gameId);
  TX_NET.setPlayerId(playerId);
  document.getElementById('reconnecting-overlay').classList.remove('visible');
  document.getElementById('game-id-chip').textContent = gameId;

  if (phase === 'playing') {
    renderGameView({ playerStates: playerStates || players, currentPlayerIndex, turnPhase, phase });
    showView('game-view');
  } else if (phase === 'lobby') {
    document.getElementById('lobby-game-id-display').textContent = gameId;
    renderLobbyPlayers(players || []);
    showView('lobby-view');
  } else {
    // Already in correct view — just re-render if state was provided
    if (playerStates) {
      renderGameView({ playerStates, currentPlayerIndex, turnPhase, phase });
    }
  }
});

TX_NET.on('rejoin_failed', () => {
  _clearSession();
  document.getElementById('reconnecting-overlay').classList.remove('visible');
  showView('join-view');
});

TX_NET.on('player_reconnected', ({ playerId, playerName }) => {
  _addActivity('🔄', `<strong>${playerName}</strong> reconnected`);
});

TX_NET.on('player_joined', ({ players }) => {
  // Update lobby list if still in lobby
  const lobbyView = document.getElementById('lobby-view');
  if (lobbyView.classList.contains('active')) {
    renderLobbyPlayers(players || []);
  }
});

TX_NET.on('game_started', ({ players }) => {
  // Switch to game view; initial render will come via state_update
  document.getElementById('game-id-chip').textContent = _gameId;

  // Set own badge in game view immediately
  const me = players?.find(p => p.id === _myId);
  if (me) {
    document.getElementById('game-own-badge').style.background = me.color;
    document.getElementById('game-badge-emoji').textContent    = me.token;
    document.getElementById('game-badge-initials').textContent = _initials(me.name);
    document.getElementById('game-own-name').textContent       = me.name;
  }

  showView('game-view');
});

TX_NET.on('roll_result', ({ roll, playerId }) => {
  clearTimeout(_rollTimeout);
  _lastRoll = roll;
  const name = _lastCurrentPlayerName || 'Someone';
  _addActivity('🎲', `<strong>${name}</strong> rolled <strong>${roll}</strong>`);

  if (_isMyTurn) {
    // Show rolled mode: die face + number until space_card arrives
    document.getElementById('ab-rolled-die').innerHTML = renderDie(roll, 'die-lg');
    document.getElementById('ab-rolled-num').textContent = roll;
    _setActionMode('rolled');
  }
});

TX_NET.on('state_update', (data) => {
  renderGameView(data);
});

TX_NET.on('space_card', (data) => {
  if (_isMyTurn) {
    _showCardMode(data);
  } else {
    const meta = SPACE_META[data.spaceType] || { icon: '•', label: data.spaceType };
    const name = data.playerName || 'Someone';
    const detail = data.deedText
      ? data.deedText.slice(0, 60) + (data.deedText.length > 60 ? '…' : '')
      : (data.spaceName || meta.label);
    _addActivity(meta.icon, `<strong>${name}</strong> landed on ${meta.label}: ${detail}`);
  }
});

TX_NET.on('space_card_done', () => {
  if (_isMyTurn) {
    _setActionMode('activity');
  }
});

TX_NET.on('turn_result', ({ playerName, scoreDelta, newPosition, spaceType }) => {
  const name = playerName || 'Someone';
  if (spaceType === 'skip_turn') {
    _addActivity('⏭', `<strong>${name}</strong>'s turn was skipped`);
    return;
  }
  let parts = [];
  if (scoreDelta > 0)  parts.push(`+${scoreDelta} pts`);
  if (scoreDelta < 0)  parts.push(`${scoreDelta} pts`);
  if (spaceType === 'skip_turn') parts.push('skip next turn');
  if (spaceType === 'finish')    parts.push('reached the finish!');
  const summary = parts.length ? parts.join(', ') : 'no change';
  _addActivity('📊', `<strong>${name}</strong>: ${summary}`);
});

TX_NET.on('host_left', () => {
  document.getElementById('host-left-overlay').classList.add('visible');
});

TX_NET.on('player_disconnected', ({ playerId, playerName }) => {
  console.log(`[player] ${playerName} disconnected`);
  _addActivity('⚠️', `<strong>${playerName}</strong> disconnected`);
});

TX_NET.on('player_removed', ({ playerId }) => {
  if (playerId === _myId) {
    _clearSession();
    showError('You were removed from the game.');
    setTimeout(() => showView('join-view'), 2000);
  }
});

// ── Leave / cancel ────────────────────────────────────────────────────────────

function leaveGame() {
  if (_gameId) TX_NET.leaveGame(_gameId);
  _clearSession();
  _myId   = null;
  _gameId = null;
  _isMyTurn = false;
  showView('join-view');
}

function cancelRejoin() {
  _clearSession();
  _pendingRejoin = null;
  document.getElementById('reconnecting-overlay').classList.remove('visible');
  showView('join-view');
}

function leaveAndReset() {
  _clearSession();
  document.getElementById('host-left-overlay').classList.remove('visible');
  showView('join-view');
}

// ── Init ──────────────────────────────────────────────────────────────────────

(function init() {
  // Try to restore saved identity
  const saved = _loadIdentity();
  if (saved) {
    if (saved.name)  {
      _myName = saved.name;
      document.getElementById('input-name').value = saved.name;
    }
    if (saved.token) _myToken = saved.token;
    if (saved.color) _myColor = saved.color;
  }

  _refreshJoinBadge();

  // Check for saved game session (rejoin after refresh)
  const session = _loadSession();
  if (session) {
    _pendingRejoin = session;
    _myId   = session.playerId;
    _gameId = session.gameId;
    document.getElementById('reconnecting-overlay').classList.add('visible');
  }

  // Connect to server
  TX_NET.connect();
})();
