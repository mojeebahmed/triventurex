/**
 * turn.js
 * Pure turn logic — no DOM, no globals, no network. Every function takes data
 * and returns data, so it can be unit-tested in Node (test/turn.test.js).
 *
 * Browser: loaded as a plain <script> before game.js (functions become globals).
 * Node:    require('../js/turn.js') via the module.exports guard at the bottom.
 */

/** A player takes turns unless they have finished or are sitting out. */
function isTurnEligible(p) { return !p.finished && !p.inactive; }

/**
 * Index of the next player who should take a turn, searching from `from`
 * (inclusive) and wrapping. If every unfinished player is sitting out, falls
 * back to the next unfinished player so the game never stalls.
 * Returns -1 when everyone has finished (or there are no players).
 */
function nextTurnIndex(players, from) {
  const total = players.length;
  for (const canPlay of [isTurnEligible, p => !p.finished]) {
    for (let i = 0; i < total; i++) {
      const idx = (((from + i) % total) + total) % total;
      if (canPlay(players[idx])) return idx;
    }
  }
  return -1;
}

/** Copy of everything undo needs to put the game back to this moment. */
function takeSnapshot(players, currentPlayerIndex, finishCount) {
  return {
    players: players.map(p => ({ ...p })),
    currentPlayerIndex,
    finishCount,
  };
}

/**
 * Undo: restore players from a snapshot BY ID.
 *  - players who joined after the snapshot are kept as they are now
 *  - players removed after the snapshot stay removed
 *  - `inactive` (sitting out) and `disconnected` keep their live values —
 *    they're table/connection state, not game moves
 * Returns fresh objects — no references shared with the inputs.
 */
function restoreFromSnapshot(livePlayers, liveIndex, snapshot) {
  const snapById      = new Map(snapshot.players.map(sp => [sp.id, sp]));
  const snapCurrentId = snapshot.players[snapshot.currentPlayerIndex]?.id;
  const players = livePlayers.map(p => {
    const sp = snapById.get(p.id);
    return sp ? { ...sp, inactive: p.inactive, disconnected: p.disconnected } : { ...p };
  });
  const idx = players.findIndex(p => p.id === snapCurrentId);
  return {
    players,
    currentPlayerIndex: idx !== -1 ? idx : Math.max(0, Math.min(liveIndex, players.length - 1)),
    finishCount: snapshot.finishCount,
  };
}

/**
 * currentPlayerIndex after the player at `removedIndex` was taken out of a
 * list that now has `newLength` players — keeps pointing at the same player,
 * or wraps to 0 if the last player in the order was the one removed.
 */
function indexAfterRemoval(currentIndex, removedIndex, newLength) {
  let idx = currentIndex;
  if (removedIndex < idx) idx--;
  if (idx >= newLength) idx = 0;
  return idx;
}

/** One row of the move history (also what undo pops). */
function makeHistoryEntry({ roll = 0, player, spaceType, spaceName = null,
                            posBefore, scoreBefore, snapshot }) {
  return {
    roll,
    playerId:    player.id,
    playerName:  player.name,
    playerColor: player.color,
    playerToken: player.token,
    spaceType:   spaceType || 'unknown',
    spaceName,
    posBefore,
    posAfter:    player.position,
    scoreBefore,
    scoreAfter:  player.score,
    snapshot,    // state BEFORE this entry — restored on undo
  };
}

if (typeof module !== 'undefined') {
  module.exports = {
    isTurnEligible, nextTurnIndex, takeSnapshot, restoreFromSnapshot,
    indexAfterRemoval, makeHistoryEntry,
  };
}
