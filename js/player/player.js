/**
 * player.js
 * Logic for the player.html lightweight player screen.
 * Handles badge picker, form validation, TX_NET events, and game-view rendering.
 */

// ── Constants ─────────────────────────────────────────────────────────────────

const TOKENS = BADGES;         // the same badges and colours as the host's picker
const COLORS = BADGE_COLORS;   // (js/shared/icon-registry.js)
// The phone doesn't load an edition or config.js: the host sends the edition's
// icons and tile labels with every state update (`edition` in state_update), and
// icon() reads CONFIG.EDITION_ICONS — so the phone shows the edition's icons.
const CONFIG = { EDITION_ICONS: null };
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
let _wasMyTurn = false;   // to buzz only when my turn STARTS (G18)
let _turnPhase = 'roll';
let _lastRoll  = null;
let _lastCurrentPlayerName = '';
let _pendingRejoin = null;
let _rollTimeout   = null;

// ── Activity log ──────────────────────────────────────────────────────────────

const _activityLog = [];

function _addActivity(iconName, html) {   // iconName: a name in js/shared/icon-registry.js (or an emoji)
  _activityLog.push({ icon: iconName, html });
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
    `<div class="ab-entry"><span class="ab-entry-icon">${icon(e.icon) || esc(e.icon)}</span><span class="ab-entry-text">${e.html}</span></div>`
  ).join('');
}

// renderDie() comes from js/shared/dice.js (loaded before this file)

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
  document.getElementById('ab-card-icon').innerHTML = icon(meta.icon) || esc(meta.icon);
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
    body = `${icon('celebrate')} Reached the finish!`;
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
    `<div class="picker-token ${t === _myToken ? 'selected' : ''}" data-token="${esc(t)}"
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
    el.classList.toggle('selected', el.dataset.token === t));   // emoji are drawn as images, so not textContent
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
  question:  { icon: 'tileQuestion', label: 'Question'   },
  action:    { icon: 'tileAction',   label: 'Action'     },
  good_deed: { icon: 'tileGoodDeed', label: 'Good Deed'  },
  bad_deed:  { icon: 'tileBadDeed',  label: 'Bad Deed'   },
  landmark:  { icon: 'tileLandmark', label: 'Landmark'   },
  skip:      { icon: 'tileSkip',     label: 'Skip Turn'  },
  finish:    { icon: 'tileFinish',   label: 'Finish!'    },
};

/** Use the edition the host sent: its icons, and its names for the tiles. */
function _applyEdition(edition) {
  if (!edition) return;
  CONFIG.EDITION_ICONS = edition.icons || null;
  for (const [type, label] of Object.entries(edition.labels || {})) {
    if (SPACE_META[type]) SPACE_META[type].label = label;
  }
}

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
  _adoptHostBadge(playerStates);

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

  // "You're next" (G18) — the next player who will actually play
  // (nextTurnIndex skips finished and sitting-out players, like the host)
  const playing = phase !== 'ended';
  const nextIdx = nextTurnIndex(playerStates, currentPlayerIndex + 1);
  const amNext  = playing && !_isMyTurn && playerStates[nextIdx]?.id === _myId;
  const nextEl  = document.getElementById('ab-next');
  nextEl.innerHTML = `${icon('tileSkip')} ${me.skipNextTurn ? "You're next — but your turn will be skipped" : "You're next — get ready!"}`;
  nextEl.classList.toggle('visible', amNext);

  // A short buzz when my turn starts (phones that support it; iPhones ignore it)
  if (playing && _isMyTurn && !_wasMyTurn) navigator.vibrate?.([80, 60, 80]);
  _wasMyTurn = _isMyTurn;

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
        <div class="mini-badge" style="background:${esc(p.color)}">
          <span class="badge-emoji">${esc(p.token)}</span>
          <span class="badge-initials">${esc(_initials(p.name))}</span>
        </div>
        <span class="other-name">${esc(p.name)}${p.finished ? ' ' + icon('finished') : ''}${p.disconnected ? ' ' + icon('disconnected') : ''}${p.inactive ? ' ' + icon('sittingOut') : ''}</span>
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
      <div class="mini-badge" style="background:${esc(p.color)}">
        <span class="badge-emoji">${esc(p.token)}</span>
        <span class="badge-initials">${esc(_initials(p.name))}</span>
      </div>
      <span class="lobby-player-name">${esc(p.name)}</span>
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

TX_NET.on('rejoined', ({ gameId, playerId, phase, players, playerStates, currentPlayerIndex, turnPhase, finishCount, edition }) => {
  _applyEdition(edition);
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
  _addActivity('reconnecting', `<strong>${esc(playerName)}</strong> reconnected`);
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

// Every roll is animated on every phone, roughly in step with the host's dice
// (G10): the roller sees it big in the action box, everyone else in a small
// strip above the activity feed. The feed entry comes after the animation so
// it doesn't give the number away early.
let _rollAnimToken = 0;

TX_NET.on('roll_result', async ({ roll }) => {
  clearTimeout(_rollTimeout);
  _lastRoll = roll;
  const name  = _lastCurrentPlayerName || 'Someone';
  const token = ++_rollAnimToken; // a newer roll supersedes this animation

  if (_isMyTurn) {
    // Rolled mode: tumbling die, then the result, until the space card arrives
    const dieEl = document.getElementById('ab-rolled-die');
    const numEl = document.getElementById('ab-rolled-num');
    numEl.textContent = 'Rolling…';
    _setActionMode('rolled');
    dieEl.classList.add('die-rolling');
    await animateDieInto(dieEl, roll, { sizeClass: 'die-lg' });
    dieEl.classList.remove('die-rolling');
    if (token !== _rollAnimToken) return;
    numEl.textContent = `Rolled ${roll}`;
    navigator.vibrate?.(60);
  } else {
    const strip = document.getElementById('ab-roll-strip');
    const dieEl = document.getElementById('ab-roll-die');
    const text  = document.getElementById('ab-roll-text');
    text.innerHTML = `${icon('rolled')} ${esc(name)} is rolling…`;
    strip.classList.add('visible');
    dieEl.classList.add('die-rolling');
    await animateDieInto(dieEl, roll, { sizeClass: 'die-sm' });
    dieEl.classList.remove('die-rolling');
    if (token !== _rollAnimToken) return;
    text.textContent = `${name} rolled ${roll}`;
  }
  _addActivity('rolled', `<strong>${esc(name)}</strong> rolled <strong>${roll}</strong>`);
});

TX_NET.on('state_update', (data) => {
  _applyEdition(data.edition);
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
    _addActivity(meta.icon, `<strong>${esc(name)}</strong> landed on ${meta.label}: ${detail}`);
  }
});

// A card only this phone receives (the server forwards it to one socket).
// With `choices` it's a question for this player (G3): tap one → card_choice
// to the host, which scores it and sends the result as the next card.
TX_NET.on('private_card', ({ title, text, rule, note, hint, choices, promptId } = {}) => {
  document.getElementById('ab-card-title').textContent = title || '';
  const body = document.getElementById('ab-card-body');
  body.innerHTML = `
    <div class="ab-private">${hint ? esc(hint) : `${icon('secret')} Only you can see this`}</div>
    <div class="ab-private-text">${esc(text)}</div>
    ${rule ? `<div class="ab-private-rule">${esc(rule)}</div>` : ''}
    ${note ? `<div class="ab-private-rule">${esc(note)}</div>` : ''}
    ${choices?.length ? `<div class="ab-choices">${choices.map(c =>
      `<button type="button" class="ab-choice" data-choice="${esc(c.id)}">${esc(c.label)}</button>`).join('')}</div>` : ''}`;
  body.querySelectorAll('.ab-choice').forEach(btn => btn.addEventListener('click', () => {
    body.querySelectorAll('.ab-choice').forEach(b => { b.disabled = true; });
    btn.classList.add('picked');
    btn.insertAdjacentHTML('afterend', '<div class="ab-choice-sent">Sent ✓ — look at the main screen</div>');
    TX_NET.sendCardChoice(_gameId, promptId, btn.dataset.choice);
  }));
  _setActionMode('card');
});

TX_NET.on('space_card_done', () => {
  if (_isMyTurn) {
    _setActionMode('activity');
  }
});

TX_NET.on('turn_result', ({ playerName, scoreDelta, newPosition, spaceType }) => {
  const name = playerName || 'Someone';
  if (spaceType === 'skip_turn') {
    _addActivity('tileSkip', `<strong>${esc(name)}</strong>'s turn was skipped`);
    return;
  }
  let parts = [];
  if (scoreDelta > 0)  parts.push(`+${scoreDelta} pts`);
  if (scoreDelta < 0)  parts.push(`${scoreDelta} pts`);
  if (spaceType === 'skip_turn') parts.push('skip next turn');
  if (spaceType === 'finish')    parts.push('reached the finish!');
  const summary = parts.length ? parts.join(', ') : 'no change';
  _addActivity('stats', `<strong>${esc(name)}</strong>: ${summary}`);
});

TX_NET.on('host_left', ({ msg } = {}) => {
  if (msg) document.getElementById('host-left-msg').textContent = msg;
  document.getElementById('host-left-overlay').classList.add('visible');
});

// Host refreshed / reconnected — the game carries on
TX_NET.on('host_back', () => {
  document.getElementById('host-left-overlay').classList.remove('visible');
});

TX_NET.on('player_disconnected', ({ playerId, playerName }) => {
  console.log(`[player] ${playerName} disconnected`);
  _addActivity('disconnected', `<strong>${esc(playerName)}</strong> disconnected`);
});

// The host changed someone's badge in the lobby
TX_NET.on('player_updated', ({ players } = {}) => {
  if (!players) return;
  _adoptHostBadge(players);
  if (document.getElementById('lobby-view').classList.contains('active')) renderLobbyPlayers(players);
});

/** The host may change this phone's badge (lobby or GM panel): use and remember it. */
function _adoptHostBadge(players) {
  const me = players.find(p => p.id === _myId);
  if (!me || (me.token === _myToken && me.color === _myColor)) return;
  _myToken = me.token;
  _myColor = me.color;
  _saveIdentity();       // next join starts with this badge
  _refreshJoinBadge();
}

TX_NET.on('player_removed', ({ playerId, players }) => {
  // Someone left the lobby — refresh the list we're showing
  if (players && document.getElementById('lobby-view').classList.contains('active')) renderLobbyPlayers(players);
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

/**
 * Leave the lobby (G21): the server removes me, the host's list updates, and
 * I'm back on the join form with the Game ID still filled in — change the
 * name or badge and join again.
 */
function leaveLobby() {
  const gameId = _gameId;
  TX_NET.leaveGame(gameId);
  _clearSession();
  _myId = null;
  _gameId = null;
  document.getElementById('input-game-id').value = gameId || '';
  showView('join-view');
}

function leaveAndReset() {
  _clearSession();
  document.getElementById('host-left-overlay').classList.remove('visible');
  showView('join-view');
}

// ── Init ──────────────────────────────────────────────────────────────────────

(function init() {
  startIcons();   // emoji + control icons from the bundled sets (js/shared/icons.js)
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

  // Opened from the host's QR code / link: player?game=4823 fills in the Game ID (G11).
  // Read it ONCE and remove it from the address: otherwise a refresh would
  // re-apply an old link and drop the session for the game actually joined.
  const linkedGame = new URLSearchParams(location.search).get('game')?.replace(/\D/g, '').slice(0, 4) || '';
  if (location.search) history.replaceState(null, '', location.pathname);
  if (linkedGame) {
    document.getElementById('input-game-id').value = linkedGame;
    // Name already known → just tap Join; otherwise type the name first
    const nameEl = document.getElementById('input-name');
    setTimeout(() => (nameEl.value ? document.querySelector('#join-view .btn-primary') : nameEl)?.focus(), 0);
  }

  // Check for saved game session (rejoin after refresh). A link to a
  // DIFFERENT game wins over an old session for another game.
  let session = _loadSession();
  if (session && linkedGame && session.gameId !== linkedGame) { _clearSession(); session = null; }
  if (session) {
    _pendingRejoin = session;
    _myId   = session.playerId;
    _gameId = session.gameId;
    document.getElementById('reconnecting-overlay').classList.add('visible');
  }

  // Connect to server
  TX_NET.connect();
})();
