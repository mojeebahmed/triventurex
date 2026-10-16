/**
 * game.js
 * Main game controller: shared game state, starting / resuming / resetting
 * a game, refreshing the game screen, and page bootstrap. Loaded last.
 */

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
  // The turn in progress, or null between turns. Plain data (saved with the game):
  // { token, playerId, roll, posBefore, scoreBefore, snapshot, awaitingRoll }
  turn:               null,
};

// ── Multiplayer state ──────────────────────────────────────────────────────────

window._onScoreChange = (player, amount) => {
  showScoreFlyout(player, amount);
  // Scoreboard is refreshed in _finishTurn / refreshUI — not here to avoid
  // triggering during animation mid-steps.
};

// ── Turn state helpers ────────────────────────────────────────────────────────
// Pure turn logic (next player, snapshots, undo restore, history rows) lives in
// js/turn.js. These helpers tie it to `state` and the page.

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

function _restoreGame(save) {
  // Re-attach the non-enumerable grid properties
  const board = save.board;
  board._gridRows = save.gridRows;
  board._gridCols = save.gridCols;

  // Saves from before the turn pipeline (A2) kept the mid-turn data as `pendingTurn`
  if (!save.turn && save.pendingTurn) {
    save.turn = { ...save.pendingTurn, playerId: save.players[save.currentPlayerIndex]?.id };
  }
  const { pendingTurn, turn: savedTurn, ...savedState } = save;
  Object.assign(state, savedState);
  state.board     = board;
  state.history   = state.history || [];
  state.turn      = null;
  state.turnPhase = 'roll';

  showScreen('game-screen');
  renderBoard(state.board, state.players);
  renderLegend();
  _showGameIdBadge();
  wireGameControls();
  refreshUI();
  highlightSpace(currentPlayer().position);
  renderHistoryPanel(state.history);
  _updateUndoButton();
  fitBoardInView();

  // Restore host network game connection if applicable
  const savedNetId = (() => { try { return localStorage.getItem('tx_net_game'); } catch { return null; } })();
  if (savedNetId) {
    _networkGameId = savedNetId;
    _isNetworkGame = true;
    TX_NET.setGameId(savedNetId);
    // The socket is usually already connected by the time Resume is clicked,
    // so the 'connect' handler won't fire again — rejoin now in that case.
    if (TX_NET.isConnected()) TX_NET.hostRejoin(savedNetId);
    else _pendingHostRejoin = savedNetId;
    document.getElementById('gm-network-section')?.classList.remove('hidden');
    _renderGMNetworkPlayers(state.players);
    _updateNetworkStatusBar();
  }

  // Saved mid-turn (space modal was open): resume that same turn — the space
  // modal re-opens and _finishTurn completes it normally (and it stays undoable).
  if (savedTurn && state.players.some(p => p.id === savedTurn.playerId)) {
    state.turn = { ...savedTurn, token: ++_turnCounter, awaitingRoll: false };
    state.turnPhase = 'resolving';
    _setRollControlsEnabled(false);
    _updateUndoButton();
    const player = _turnPlayer();
    _resolveSpace(state.board[player.position], player, state.turn.token);
  }
}

// ── LocalStorage keys ─────────────────────────────────────────────────────────

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
  state.turn               = null;

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

function _buildBoard(gameLength, pathIndex) {
  if (pathIndex === 'random') {
    return generateBoard(gameLength); // picks random template internally
  }
  // Specific template — temporarily override the random pick
  const template = CONFIG.PATH_TEMPLATES[gameLength][pathIndex];
  return generateBoard(gameLength, template); // we'll patch generateBoard below
}

function _showGameIdBadge() {
  const el = document.getElementById('game-id-badge');
  if (el) el.textContent = state.gameId;
}

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
  _setRollControlsEnabled(state.turnPhase === 'roll');
}

// ── Turn Logic ────────────────────────────────────────────────────────────────
//
// Every turn follows ONE path:
//
//   handleRoll / handleManualRoll / phone roll_result
//        │                                  └─ skipNextTurn ─▶ _skipTurn ──┐
//        ▼                                                                 │
//   _beginTurn ─▶ _playRoll ─▶ move ─▶ _resolveSpace (modal) ──────────────┤
//                               └─ exact-finish blocked ───────────────────┤
//                                                                          ▼
//                                                                    _finishTurn
//
// _finishTurn is the ONLY place a turn ends. Every async step checks
// _isStale(token) first, so undo / player removal (which clear state.turn)
// cancel whatever is still in flight.

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
    history: [], turn: null,
  };
  renderPlayerRows();
  populatePathSelector('medium');
  document.querySelector('input[name="gameLength"][value="medium"]').checked = true;
  showScreen('setup-screen');
}

// ── Edition loading ─────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  // Validate saved edition against the registry — if the ID no longer exists
  // (e.g. folder was renamed), fall back to the first registered edition.
  const savedRaw     = (() => { try { return localStorage.getItem('triventurex_edition'); } catch { return null; } })();
  const knownIds     = (window.TRIVENTUREX_EDITIONS || []).map(t => t.id);
  const savedEdition   = knownIds.includes(savedRaw) ? savedRaw : null;
  const defaultEdition = knownIds[0] || 'swab-quest';
  await loadEdition(savedEdition || defaultEdition);

  _applyColors();
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
