/**
 * net-host.js
 * Host side of network play (V2): lobby, hosting, syncing state to the
 * server and all Socket.IO event handlers. Phones run js/player/player.js instead.
 */

let _isNetworkGame    = false;    // true once a network game is active

let _networkGameId    = null;

let _pendingNetworkSetup = null;  // { gameLength, pathIndex, isGMOnly, hostPlayer }

let _lobbyPlayers     = [];       // players accumulated via player_joined events

let _pendingHostRejoin = null;    // saved gameId to rejoin as host after refresh

// ── Lobby ───────────────────────────────────────────────────────────────────────

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
    editionId: _activeEditionId,
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
  if (_networkGameId) TX_NET.closeRoom(_networkGameId); // phones see "host ended the game"
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
          <div class="score-token" style="background:${esc(p.color)}">
            <div class="token-emoji">${esc(p.token)}</div>
          </div>
          <span>${esc(p.name)}</span>
        </div>`).join('');
}

function _renderGMNetworkPlayers(serverPlayers) {
  const el = document.getElementById('gm-network-list');
  if (!el) return;
  el.innerHTML = serverPlayers.map(p => `
    <div class="gm-net-player">
      <div class="score-token" style="background:${esc(p.color)}">
        <div class="token-emoji">${esc(p.token)}</div>
      </div>
      <span class="gm-net-name">${esc(p.name)}${p.disconnected ? ' ⚠️' : ''}${p.inactive ? ' 💤' : ''}</span>
      <button class="btn btn-small btn-danger" onclick="gmRemoveNetworkPlayer(${p.id})">✕</button>
    </div>`).join('');
}

function gmRemoveNetworkPlayer(playerId) {
  if (!confirm('Remove this player?')) return;
  TX_NET.removePlayer(_networkGameId, playerId);
}

// ── Host → server ───────────────────────────────────────────────────────────────

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
      // `disconnected` is NOT sent — the server owns connection state
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

// ── Socket event handlers ───────────────────────────────────────────────────────

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

    // Mid-game join — add them to the host's game state and sync, so the
    // server stops treating them as "not yet seen by the host"
    if (_isNetworkGame && state.phase === 'playing' && !state.players.some(p => p.id === player.id)) {
      state.players.push(createPlayer(player.id, player.name, player.color, player.token));
      refreshUI();
      _renderGMNetworkPlayers(state.players);
      saveGame();
      _syncStateToServer();
    }
  });

  TX_NET.on('game_started', ({ players }) => {
    const setup     = _pendingNetworkSetup;
    _isNetworkGame  = true;

    _startNewGame({
      gameId:     _networkGameId,
      players:    players.map(p => createPlayer(p.id, p.name, p.color, p.token)),
      gameLength: setup.gameLength,
      pathIndex:  setup.pathIndex,
    });

    try { localStorage.setItem('tx_net_game', _networkGameId); } catch {}
    _updateNetworkStatusBar();
    _renderGMNetworkPlayers(players);
    document.getElementById('gm-network-section')?.classList.remove('hidden');

    _syncStateToServer();
  });

  TX_NET.on('roll_result', ({ roll }) => {
    if (!_isNetworkGame) return;
    if (state.turn?.awaitingRoll) {
      // Host pressed Roll — the turn already began in handleRoll()
      state.turn.awaitingRoll = false;
    } else {
      // Roll came from the current player's phone — start the turn here.
      // Ignore duplicates / late rolls while a turn is already in progress.
      if (state.turn) return;
      if (currentPlayer().skipNextTurn) { _skipTurn(); return; }
      _beginTurn();
    }
    _playRoll(roll);
  });

  // Connection state is owned by the server; the host mirrors it for the GM list
  TX_NET.on('player_disconnected', ({ playerId }) => {
    if (!_isNetworkGame) return;
    const p = state.players.find(pl => pl.id === playerId);
    if (p) p.disconnected = true;
    _renderGMNetworkPlayers(state.players);
    _updateNetworkStatusBar();
  });

  TX_NET.on('player_reconnected', ({ playerId }) => {
    if (!_isNetworkGame) return;
    const p = state.players.find(pl => pl.id === playerId);
    if (p) p.disconnected = false;
    _renderGMNetworkPlayers(state.players);
  });

  TX_NET.on('player_removed', ({ playerId }) => {
    if (!_isNetworkGame) return;
    const idx = state.players.findIndex(p => p.id === playerId);
    if (idx === -1) return;
    const wasCurrent = idx === state.currentPlayerIndex;

    state.players = state.players.filter(p => p.id !== playerId);
    // Keep pointing at the same player when someone earlier in the order leaves
    state.currentPlayerIndex = indexAfterRemoval(state.currentPlayerIndex, idx, state.players.length);

    if (wasCurrent) {
      // Cancel the removed player's in-progress turn — clearing state.turn makes
      // its pending modal callbacks / animations stale
      if (state.turn) {
        hideModal();
        state.turn = null;
        document.getElementById('roll-btn').textContent = 'Roll Dice';
      }
      state.turnPhase = 'roll';
      // The index now points at the next player — make sure they can play
      const next = nextTurnIndex(state.players, state.currentPlayerIndex);
      if (next === -1) { _endGame(); return; }
      state.currentPlayerIndex = next;
    }

    refreshUI();
    _updateUndoButton();
    if (state.players.length) highlightSpace(currentPlayer().position);
    _renderGMNetworkPlayers(state.players);
    saveGame();
    _syncStateToServer();
  });

  TX_NET.on('error', ({ message }) => {
    console.error('[game] Server error:', message);
  });

  TX_NET.on('host_rejoined', ({ players, phase }) => {
    _isNetworkGame = true;
    _renderGMNetworkPlayers(players);
    document.getElementById('gm-network-section')?.classList.remove('hidden');
    _updateNetworkStatusBar();
    _syncStateToServer(); // refresh server's turnPhase/index from the host's restored state
    console.log('[game] host rejoined network game');
  });
}
