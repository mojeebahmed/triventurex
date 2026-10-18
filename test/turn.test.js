/**
 * test/turn.test.js
 * Unit tests for js/shared/turn.js — pure turn logic (T5).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const {
  isTurnEligible, nextTurnIndex, takeSnapshot, restoreFromSnapshot,
  indexAfterRemoval, makeHistoryEntry, turnRecap,
} = require('../js/shared/turn.js');

/** Minimal player for these tests. */
const P = (id, extra = {}) => ({
  id, name: `P${id}`, color: '#000', token: 'x',
  position: 0, score: 0, finished: false, inactive: false, disconnected: false,
  ...extra,
});

describe('isTurnEligible', () => {
  it('a normal player can play', () => assert.equal(isTurnEligible(P(0)), true));
  it('a finished player cannot', () => assert.equal(isTurnEligible(P(0, { finished: true })), false));
  it('a sitting-out player cannot', () => assert.equal(isTurnEligible(P(0, { inactive: true })), false));
});

describe('nextTurnIndex', () => {
  it('returns the next player in order', () => {
    assert.equal(nextTurnIndex([P(0), P(1), P(2)], 1), 1);
  });

  it('wraps around the end of the list', () => {
    assert.equal(nextTurnIndex([P(0), P(1), P(2)], 3), 0);
  });

  it('skips finished players', () => {
    assert.equal(nextTurnIndex([P(0), P(1, { finished: true }), P(2)], 1), 2);
  });

  it('skips sitting-out players (B8)', () => {
    assert.equal(nextTurnIndex([P(0), P(1, { inactive: true }), P(2)], 1), 2);
  });

  it('falls back to a sitting-out player rather than stalling', () => {
    const players = [P(0, { finished: true }), P(1, { inactive: true }), P(2, { finished: true })];
    assert.equal(nextTurnIndex(players, 2), 1);
  });

  it('returns -1 when everyone has finished', () => {
    assert.equal(nextTurnIndex([P(0, { finished: true }), P(1, { finished: true })], 0), -1);
  });

  it('returns -1 for no players', () => {
    assert.equal(nextTurnIndex([], 0), -1);
  });
});

describe('takeSnapshot', () => {
  it('copies players so later changes do not leak into the snapshot', () => {
    const players = [P(0, { score: 3 })];
    const snap = takeSnapshot(players, 0, 0);
    players[0].score = 99;
    assert.equal(snap.players[0].score, 3);
  });
});

describe('restoreFromSnapshot (undo by id)', () => {
  it('restores position and score from the snapshot', () => {
    const snap = takeSnapshot([P(0, { position: 2, score: 1 }), P(1)], 0, 0);
    const live = [P(0, { position: 9, score: 7 }), P(1)];
    const r = restoreFromSnapshot(live, 1, snap);
    assert.equal(r.players[0].position, 2);
    assert.equal(r.players[0].score, 1);
    assert.equal(r.currentPlayerIndex, 0);
  });

  it('keeps a player who joined after the snapshot', () => {
    const snap = takeSnapshot([P(0), P(1)], 1, 0);
    const live = [P(0), P(1), P(2, { name: 'Late' })];
    const r = restoreFromSnapshot(live, 0, snap);
    assert.deepEqual(r.players.map(p => p.id), [0, 1, 2]);
  });

  it('does not bring back a player removed after the snapshot', () => {
    const snap = takeSnapshot([P(0), P(1), P(2)], 0, 0);
    const live = [P(0), P(2)];
    const r = restoreFromSnapshot(live, 0, snap);
    assert.deepEqual(r.players.map(p => p.id), [0, 2]);
  });

  it('finds the current player by id when indexes shifted', () => {
    const snap = takeSnapshot([P(0), P(1), P(2)], 2, 0);   // P2's turn
    const live = [P(1), P(2)];                              // P0 removed since
    assert.equal(restoreFromSnapshot(live, 0, snap).currentPlayerIndex, 1);
  });

  it('stays in range if the current player was removed', () => {
    const snap = takeSnapshot([P(0), P(1), P(2)], 2, 0);
    const live = [P(0), P(1)];
    const r = restoreFromSnapshot(live, 5, snap);
    assert.ok(r.currentPlayerIndex >= 0 && r.currentPlayerIndex < live.length);
  });

  it('keeps live sit-out and connection flags', () => {
    const snap = takeSnapshot([P(0)], 0, 0);
    const live = [P(0, { inactive: true, disconnected: true })];
    const r = restoreFromSnapshot(live, 0, snap);
    assert.equal(r.players[0].inactive, true);
    assert.equal(r.players[0].disconnected, true);
  });

  it('restores finishCount', () => {
    const snap = takeSnapshot([P(0)], 0, 1);
    assert.equal(restoreFromSnapshot([P(0)], 0, snap).finishCount, 1);
  });

  it('returns fresh objects (no shared references with inputs)', () => {
    const snap = takeSnapshot([P(0)], 0, 0);
    const live = [P(0)];
    const r = restoreFromSnapshot(live, 0, snap);
    assert.notEqual(r.players[0], live[0]);
    assert.notEqual(r.players[0], snap.players[0]);
  });
});

describe('indexAfterRemoval (B5)', () => {
  it('shifts down when an earlier player is removed', () => {
    assert.equal(indexAfterRemoval(2, 0, 2), 1);
  });

  it('stays the same when a later player is removed', () => {
    assert.equal(indexAfterRemoval(0, 2, 2), 0);
  });

  it('wraps to 0 when the current last player is removed', () => {
    assert.equal(indexAfterRemoval(2, 2, 2), 0);
  });

  it('points at the next player when the current (middle) player is removed', () => {
    assert.equal(indexAfterRemoval(1, 1, 2), 1);
  });
});

describe('makeHistoryEntry', () => {
  it('records before/after and the snapshot', () => {
    const player = P(3, { position: 7, score: 5 });
    const snap   = takeSnapshot([P(3)], 0, 0);
    const e = makeHistoryEntry({ roll: 4, player, spaceType: 'question',
                                 posBefore: 3, scoreBefore: 4, snapshot: snap });
    assert.equal(e.roll, 4);
    assert.equal(e.playerId, 3);
    assert.equal(e.posBefore, 3);
    assert.equal(e.posAfter, 7);
    assert.equal(e.scoreBefore, 4);
    assert.equal(e.scoreAfter, 5);
    assert.equal(e.snapshot, snap);
  });

  it('defaults roll to 0 and spaceType to unknown', () => {
    const e = makeHistoryEntry({ player: P(0), posBefore: 0, scoreBefore: 0, snapshot: null });
    assert.equal(e.roll, 0);
    assert.equal(e.spaceType, 'unknown');
  });
});

describe('turnRecap — "what just happened"', () => {
  const words = { points: 'Goals', finish: 'The Final', labels: { question: 'Question', action: 'Action', good_deed: 'Good Play', bad_deed: 'Foul Play', landmark: 'Stadium', skip: 'Red Card' } };
  const e = o => ({ roll: 4, playerName: 'Sara', spaceType: 'question', landedOn: 'question', spaceName: null,
                    posBefore: 3, posAfter: 7, scoreBefore: 2, scoreAfter: 2, result: null, outcome: 'space', ...o });

  it('a question: difficulty, right or not, points', () => {
    assert.deepEqual(turnRecap(e({ result: { question: true, diff: 'hard' }, scoreAfter: 4 }), words),
      { icon: 'tileQuestion', text: 'Sara rolled 4 · Question: hard one, right · +2 Goals' });
    assert.equal(turnRecap(e({ result: { question: false, diff: 'easy' } }), words).text, 'Sara rolled 4 · Question: easy one, not this time');
  });

  it('an action card', () => {
    assert.equal(turnRecap(e({ landedOn: 'action', spaceType: 'action', result: { action: false } }), words).text, 'Sara rolled 4 · Action: nobody guessed');
  });

  it('a card that moves the player on, to a landmark', () => {
    const r = turnRecap(e({ landedOn: 'good_deed', spaceType: 'landmark', spaceName: 'Wembley', posAfter: 10, scoreAfter: 5 }), words);
    assert.deepEqual(r, { icon: 'tileGoodDeed', text: 'Sara rolled 4 · Good Play · forward 3 to Wembley · +3 Goals' });
    assert.equal(turnRecap(e({ landedOn: 'bad_deed', spaceType: 'question', posAfter: 5, scoreAfter: 1 }), words).text,
      'Sara rolled 4 · Foul Play · back 2 · −1 Goals');
  });

  it('a landmark by roll, the finish, a skip space', () => {
    assert.equal(turnRecap(e({ landedOn: 'landmark', spaceType: 'landmark', spaceName: 'Maracanã', scoreAfter: 5 }), words).text,
      'Sara rolled 4 · Stadium: Maracanã · +3 Goals');
    assert.equal(turnRecap(e({ landedOn: 'finish', spaceType: 'finish', scoreAfter: 12 }), words).text, 'Sara rolled 4 · reached The Final! · +10 Goals');
    assert.equal(turnRecap(e({ landedOn: 'skip', spaceType: 'skip' }), words).text, 'Sara rolled 4 · Red Card — misses the next turn');
  });

  it('skipped turns, exact-finish blocks and GM changes', () => {
    assert.equal(turnRecap(e({ roll: 0, outcome: 'skip', spaceType: 'skip', posAfter: 3 }), words).text, 'Sara missed this turn');
    assert.equal(turnRecap(e({ roll: 5, outcome: 'blocked', posAfter: 3 }), words).text, 'Sara rolled 5 — needs the exact number to reach The Final');
    assert.deepEqual(turnRecap(e({ spaceType: 'gm', spaceName: 'GM: +2 Goals' }), words), { icon: 'historyGm', text: 'GM: +2 Goals (Sara)' });
  });

  it('no entry, no recap; older saves without landedOn / outcome still read', () => {
    assert.equal(turnRecap(null), null);
    assert.equal(turnRecap(e({ landedOn: undefined, outcome: undefined }), words).text, 'Sara rolled 4 · Question');
  });
});
