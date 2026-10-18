/**
 * turn.js
 * Pure turn logic — no DOM, no globals, no network. Every function takes data
 * and returns data, so it can be unit-tested in Node (test/turn.test.js).
 *
 * Browser: loaded as a plain <script> before game.js (functions become globals).
 * Node:    require('../js/shared/turn.js') via the module.exports guard at the bottom.
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
    // Who the player is (badge, phone) isn't game progress — undo keeps it live
    return sp ? { ...sp, inactive: p.inactive, disconnected: p.disconnected,
                  token: p.token, color: p.color, noPhone: p.noPhone } : { ...p };
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
                            posBefore, scoreBefore, snapshot, landedOn = null, result = null, outcome = null }) {
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
    landedOn,    // the space type the roll landed on (spaceType = where the turn ENDED, after deed moves)
    result,      // { question: true/false, qid, diff } | { action: true/false } — end-screen stats (G13) + learned today
    outcome,     // 'space' | 'skip' (turn skipped) | 'blocked' (exact finish needed) — for the turn recap
    snapshot,    // state BEFORE this entry — restored on undo
  };
}

// ── "What just happened" ────────────────────────────────────────────────────────

const TILE_ICON = {
  start: 'tileStart', finish: 'tileFinish', question: 'tileQuestion', action: 'tileAction',
  good_deed: 'tileGoodDeed', bad_deed: 'tileBadDeed', landmark: 'tileLandmark', skip: 'tileSkip',
};

/**
 * One plain sentence for a history entry, for the board's "last turn" line:
 *   { icon, text }  e.g. { icon: 'tileQuestion', text: 'Sara rolled 5 · Question: hard one, right · +2 Goals' }
 * `words`: { points, finish, labels: { question: 'Question', good_deed: 'Good Play', … } }.
 * Plain text (escape it when drawing as HTML). null without an entry.
 */
function turnRecap(e, words = {}) {
  if (!e) return null;
  const label  = t => words.labels?.[t] || String(t || '').replace(/_/g, ' ');
  const finish = words.finish || 'the finish';
  const pts    = words.points || 'points';
  const name   = e.playerName || 'Someone';

  if (e.spaceType === 'gm') return { icon: 'historyGm', text: `${e.spaceName || 'GM change'} (${name})` };
  if (e.outcome === 'skip' || (!e.roll && e.spaceType === 'skip')) return { icon: 'tileSkip', text: `${name} missed this turn` };
  if (e.outcome === 'blocked') return { icon: 'rolled', text: `${name} rolled ${e.roll} — needs the exact number to reach ${finish}` };

  const landed = e.landedOn ?? e.spaceType;
  const parts  = [`${name} rolled ${e.roll}`];
  const r = e.result || {};
  if (landed === 'finish') parts.push(`reached ${finish}!`);
  else if (landed === 'question' && typeof r.question === 'boolean') {
    parts.push(`${label('question')}: ${r.diff ? `${r.diff} one, ` : ''}${r.question ? 'right' : 'not this time'}`);
  } else if (landed === 'action' && typeof r.action === 'boolean') {
    parts.push(`${label('action')}: ${r.action ? 'guessed!' : 'nobody guessed'}`);
  } else if (landed === 'landmark' && e.spaceName && e.posAfter === e.posBefore + e.roll) {
    parts.push(`${label('landmark')}: ${e.spaceName}`);
  } else if (landed === 'skip') parts.push(`${label('skip')} — misses the next turn`);
  else if (landed) parts.push(label(landed));

  // A card moved them on after landing
  const extra = e.posAfter - (e.posBefore + e.roll);
  if (extra && landed !== 'finish') {
    const where = e.spaceType === 'finish' ? ` to ${finish}`
      : (e.spaceType === 'landmark' && e.spaceName ? ` to ${e.spaceName}` : '');
    parts.push(`${extra > 0 ? 'forward' : 'back'} ${Math.abs(extra)}${where}`);
  }
  const d = e.scoreAfter - e.scoreBefore;
  if (d) parts.push(`${d > 0 ? '+' : '−'}${Math.abs(d)} ${pts}`);
  return { icon: TILE_ICON[landed] || 'rolled', text: parts.join(' · ') };
}

if (typeof module !== 'undefined') {
  module.exports = {
    isTurnEligible, nextTurnIndex, takeSnapshot, restoreFromSnapshot,
    indexAfterRemoval, makeHistoryEntry, turnRecap,
  };
}
