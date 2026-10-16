/**
 * turn-flow.js
 * Turn flow on the host: the turn pipeline (roll → move → resolve →
 * _finishTurn), undo, and GM controls. Pure turn logic lives in turn.js.
 */

// ── Turn state ──────────────────────────────────────────────────────────────────
// Pure turn logic (next player, snapshots, undo restore, history rows) lives in
// js/shared/turn.js. These helpers tie it to `state` and the page.

let _turnCounter = 0; // source of state.turn.token values

/** The player whose turn is in progress (state.turn), or undefined. */
function _turnPlayer() {
  return state.turn && state.players.find(p => p.id === state.turn.playerId);
}

/**
 * True when the turn that issued `token` is no longer the turn in progress —
 * it was finished, undone, or cancelled. Every async continuation and modal
 * callback of a turn checks this before touching state.
 */
function _isStale(token) { return state.turn?.token !== token; }

function _snapshotNow() {
  return takeSnapshot(state.players, state.currentPlayerIndex, state.finishCount);
}

/** Undo is possible mid-turn (cancels it) or when there's history to pop. */
function _updateUndoButton() {
  const btn = document.getElementById('undo-btn');
  if (btn) btn.disabled = !state.turn && !state.history.length;
}

/**
 * Undo.
 *  - During a turn: cancels ONLY that turn — back to just before the roll.
 *  - Between turns: pops the last history entry (a turn or a GM action).
 */
function undoLastMove() {
  if (state.turn) {
    _restoreSnapshot(state.turn.snapshot);
    showToast('Turn cancelled');
    return;
  }
  if (!state.history.length) return;
  const entry = state.history.pop();
  if (!entry.snapshot) { renderHistoryPanel(state.history); _updateUndoButton(); return; }
  _restoreSnapshot(entry.snapshot);
}

/**
 * Put the game back to `snapshot`. Clearing state.turn makes every in-flight
 * continuation of the current turn stale, so nothing fires after the restore.
 */
function _restoreSnapshot(snapshot) {
  hideModal();
  state.turn = null;
  const restored = restoreFromSnapshot(state.players, state.currentPlayerIndex, snapshot);
  state.players            = restored.players;
  state.currentPlayerIndex = restored.currentPlayerIndex;
  state.finishCount        = restored.finishCount;
  state.turnPhase          = 'roll';
  document.getElementById('roll-btn').textContent = 'Roll Dice';

  updateBoardTokens(state.players);
  updateScoreboard(state.players);
  highlightSpace(currentPlayer().position);
  refreshUI();
  renderHistoryPanel(state.history);
  _updateUndoButton();
  saveGame();
  _syncStateToServer();
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

// ── Turn pipeline ───────────────────────────────────────────────────────────────
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

/** Enable/disable the Roll button and the manual dice together. */
function _setRollControlsEnabled(enabled) {
  document.getElementById('roll-btn').disabled = !enabled;
  _setManualDiceDisabled(!enabled);
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

/** Host clicked the Roll button. */
async function handleRoll() {
  if (state.turn) return;
  if (currentPlayer().skipNextTurn) { _skipTurn(); return; }

  _beginTurn();
  if (_isNetworkGame) {
    // Server rolls; the turn continues in TX_NET.on('roll_result') → _playRoll
    state.turn.awaitingRoll = true;
    document.getElementById('roll-btn').textContent = 'Waiting for roll...';
    TX_NET.requestRoll(_networkGameId);
  } else {
    await _playRoll(rollDice());
  }
}

/**
 * Host clicked a manual die face (physical dice play).
 * Network: phones get the value via manual_roll; the host plays it locally
 * straight away — no waiting on the server, so it can't get stuck.
 */
async function handleManualRoll(n) {
  if (state.turn) return;
  if (currentPlayer().skipNextTurn) { _skipTurn(); return; }

  _beginTurn();
  if (_isNetworkGame) TX_NET.manualRoll(_networkGameId, n);
  await _playRoll(n);
}

/**
 * Start a turn for the current player: lock the roll controls and record
 * everything undo needs. Returns the turn's token.
 */
function _beginTurn() {
  const player = currentPlayer();
  state.turn = {
    token:        ++_turnCounter,
    playerId:     player.id,
    roll:         null,
    posBefore:    player.position,
    scoreBefore:  player.score,
    snapshot:     _snapshotNow(),   // taken BEFORE any change (incl. clearing a skip)
    awaitingRoll: false,
  };
  state.turnPhase = 'resolving';
  _setRollControlsEnabled(false);
  _updateUndoButton();
  return state.turn.token;
}

/** The current player must skip this turn: consume the skip instead of rolling. */
function _skipTurn() {
  const token  = _beginTurn();
  const player = _turnPlayer();
  player.skipNextTurn = false; // undo re-arms it — the snapshot was taken first
  showModal({
    icon: '⏭', title: 'Turn Skipped',
    content: `<strong>${esc(player.name)}</strong> must skip this turn.`,
    actions: [{ label: 'OK', class: 'btn btn-primary', callback: () => {
      if (!_isStale(token)) _finishTurn({ outcome: 'skip' });
    }}],
  });
}

/** Animate the roll, move the token, then resolve the space landed on. */
async function _playRoll(roll) {
  const token  = state.turn.token;
  const player = _turnPlayer();
  state.turn.roll = roll;
  document.getElementById('roll-btn').textContent = 'Roll Dice';

  await animateDice(roll);
  await _showDiceOverlay(roll, player); // large result on the board while players watch
  if (_isStale(token)) return;

  const blocked = await animatePlayerMovement(player, state.board, roll, state.players);
  if (_isStale(token)) return;

  if (blocked) {
    // Exact finish: overshoot means no move and no space to resolve
    showToast(`Need exactly ${state.board.length - 1 - player.position} to finish!`);
    _finishTurn({ outcome: 'blocked' });
    return;
  }

  // Landed on the finish by roll: record it now so the finish modal can show
  // the place + bonus. (No toast — the finish modal announces it.)
  _recordFinish(player, { announce: false });
  updateBoardTokens(state.players); // final stable render (no hop animation)
  updateScoreboard(state.players);
  saveGame(); // mid-turn save — a refresh re-opens this space (see _restoreGame)

  const space = state.board[player.position];
  if (_isNetworkGame) _emitSpaceCard(space, player);
  _resolveSpace(space, player, token);
}

/** Show the space modal; when the player is done, finish the turn. */
function _resolveSpace(space, player, token) {
  const done = () => { if (!_isStale(token)) _finishTurn(); };
  if (space.type === 'action') {
    showSpaceModal(space, player, (guessed) => {
      if (_isStale(token)) return;
      if (guessed) showGuesserModal(state.players, player, done);
      else done();
    });
  } else {
    showSpaceModal(space, player, done);
  }
}

/**
 * Give a player who has just reached the finish their finish order + bonus.
 * Called after EVERY kind of movement (roll, deed effect, GM move) so the
 * bonus doesn't depend on how they got there. No-op if not finished or
 * already recorded. `announce` shows a toast for finishes without a finish modal.
 */
function _recordFinish(player, { announce = true } = {}) {
  if (!player?.finished || player.finishOrder !== null) return;
  state.finishCount++;
  player.finishOrder = state.finishCount;
  const bonus = CONFIG.FINISH_BONUS[state.finishCount - 1] ?? 1;
  addScore(player, bonus);
  if (announce) {
    const ordinal = ['1st','2nd','3rd'][state.finishCount - 1] || `${state.finishCount}th`;
    showToast(`🏁 ${player.name} finished ${ordinal}! +${bonus} ${CONFIG.GAME?.pointsName ?? 'pts'}`, 3500);
  }
}

/**
 * The ONLY way a turn ends. Always, in this order:
 *   finish bonus → history → tell phones → game over? → extra turn or next
 *   player → save → sync.
 * outcome: 'space' (normal) | 'blocked' (exact-finish overshoot) | 'skip'
 */
function _finishTurn({ outcome = 'space' } = {}) {
  const turn = state.turn;
  if (!turn) return;
  const player = _turnPlayer();
  const space  = state.board[player.position];

  // 1. A deed effect may have carried the player onto the finish
  _recordFinish(player);

  // 2. History (undo pops this entry → restores turn.snapshot)
  state.history.push(makeHistoryEntry({
    roll:        turn.roll ?? 0,
    player,
    spaceType:   outcome === 'skip' ? 'skip' : space?.type,
    spaceName:   outcome === 'skip' ? 'Turn Skipped' : (space?.name || null),
    posBefore:   turn.posBefore,
    scoreBefore: turn.scoreBefore,
    snapshot:    turn.snapshot,
  }));
  renderHistoryPanel(state.history);

  // 3. Phones: activity feed entry, then clear the space card
  if (_isNetworkGame) {
    TX_NET.emitTurnResult(_networkGameId, {
      playerId:    player.id,
      playerName:  player.name,
      scoreDelta:  player.score - turn.scoreBefore,
      newPosition: player.position,
      posBefore:   turn.posBefore,
      spaceType:   { skip: 'skip_turn', blocked: 'blocked' }[outcome] ?? space?.type,
      spaceName:   outcome === 'space' ? (space?.name || null) : null,
    });
    if (outcome !== 'skip') TX_NET.emitSpaceCardDone(_networkGameId);
  }

  state.turn = null;
  _updateUndoButton();
  updateScoreboard(state.players);
  updateBoardTokens(state.players);

  // 4. Game over?
  if (state.players.every(p => p.finished)) { _endGame(); return; }

  // 5. Extra turn (deed card) — same player rolls again, unless they can't play
  if (player.hasExtraTurn && isTurnEligible(player)) {
    player.hasExtraTurn = false;
    state.turnPhase = 'roll';
    refreshUI();
    highlightSpace(player.position);
    updateCurrentPlayerDisplay(player, '🎲 Roll again — extra turn!');
  } else {
    player.hasExtraTurn = false;
    endTurn();
  }

  // 6. Persist + tell the server (turnPhase is 'roll' again at this point)
  saveGame();
  _syncStateToServer();
}

/** Pass the turn to the next player who can play (no save/sync — callers do that). */
function endTurn() {
  const next = nextTurnIndex(state.players, state.currentPlayerIndex + 1);
  if (next === -1) { _endGame(); return; }

  state.currentPlayerIndex = next;
  state.turnPhase = 'roll';
  refreshUI();
  highlightSpace(currentPlayer().position);
}

/** All players finished — tell player screens, clear the save, show results. */
function _endGame() {
  state.phase     = 'ended';
  state.turn      = null;
  state.turnPhase = 'roll';
  _syncStateToServer(); // player screens switch to activity mode on phase 'ended'
  clearSave();
  setTimeout(() => showEndScreen(state.players), 600);
}

// ── GM controls ─────────────────────────────────────────────────────────────────

function getGMSelectedPlayer() {
  const id = parseInt(document.getElementById('gm-player-select').value, 10);
  return state.players.find(p => p.id === id);
}

/**
 * Apply a GM correction to a player, then refresh, save and sync.
 * Between turns it gets its own undoable history entry ('⚙️ GM').
 * During a turn (space modal open) it becomes part of that turn instead —
 * undoing the turn reverts it too, and the turn's entry shows the net change.
 */
function _gmAction(player, label, apply) {
  const recordOwnEntry = !state.turn;
  const snapshot    = recordOwnEntry ? _snapshotNow() : null;
  const posBefore   = player.position;
  const scoreBefore = player.score;

  apply(player);
  _recordFinish(player); // a GM move can carry a player onto the finish

  if (recordOwnEntry) {
    state.history.push(makeHistoryEntry({
      player, spaceType: 'gm', spaceName: label, posBefore, scoreBefore, snapshot,
    }));
    renderHistoryPanel(state.history);
    _updateUndoButton();
  }

  updateBoardTokens(state.players);
  updateScoreboard(state.players);
  highlightSpace(player.position);

  // Between turns: if that GM move finished the last player, the game is over.
  // (During a turn, _finishTurn handles this.)
  if (recordOwnEntry && state.players.every(p => p.finished)) { _endGame(); return; }
  // Between turns: a GM move that finished the player whose turn it is passes the turn on
  if (recordOwnEntry && player === currentPlayer() && player.finished) endTurn();

  saveGame();
  _syncStateToServer();
}

function gmAdjustScore(amount) {
  const p = getGMSelectedPlayer();
  if (!p) return;
  const pts = CONFIG.GAME?.pointsName ?? 'pts';
  _gmAction(p, `GM: ${amount > 0 ? '+' : ''}${amount} ${pts}`, pl => addScore(pl, amount));
}

function gmMovePlayer(steps) {
  const p = getGMSelectedPlayer();
  if (!p) return;
  _gmAction(p, `GM: move ${steps > 0 ? '+' : ''}${steps}`, pl => movePlayer(pl, state.board, steps));
}

function gmSkipTurn() {
  const p = getGMSelectedPlayer();
  if (!p) return;
  _gmAction(p, 'GM: skip next turn', pl => { pl.skipNextTurn = true; });
  showToast(`${p.name}'s next turn will be skipped.`);
}

/**
 * Toggle "sitting out" for the selected player. Sitting-out players keep their
 * position and score but are skipped in turn order until they rejoin.
 * Not part of undo history — it's a table-management action, not a game move.
 */
function gmToggleSitOut() {
  const p = getGMSelectedPlayer();
  if (!p) return;
  p.inactive = !p.inactive;
  showToast(p.inactive ? `💤 ${p.name} is sitting out` : `${p.name} is back in the game`);

  // If it's their turn and they haven't rolled yet, pass the turn on now
  if (p.inactive && p === currentPlayer() && !state.turn) {
    endTurn();
  } else {
    refreshUI();
  }
  _renderGMNetworkPlayers(state.players);
  saveGame();
  _syncStateToServer();
}
