/**
 * test/players.test.js
 * Unit tests for js/shared/players.js — the player model (T2).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load() {
  const ctx = {};
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of ['js/shared/config.js', 'js/shared/players.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', f), 'utf8'), ctx, { filename: f });
  }
  return ctx;
}
const BOARD = Array.from({ length: 10 }, (_, i) => ({ id: i }));   // 0 = start, 9 = finish

describe('createPlayer', () => {
  it('starts at 0 with no score and no flags', () => {
    const p = load().createPlayer(3, 'Ali', '#111', '🚀');
    assert.equal(p.id, 3);
    assert.equal(p.position, 0);
    assert.equal(p.score, 0);
    assert.equal(p.finished, false);
    assert.equal(p.finishOrder, null);
    assert.equal(p.skipNextTurn, false);
    assert.equal(p.hasExtraTurn, false);
    assert.equal(p.protectedFromBadDeed, false);
  });

  it('falls back to a default token', () => {
    assert.ok(load().createPlayer(0, 'A', '#111', '').token);
  });
});

describe('movePlayer', () => {
  it('moves forward and back', () => {
    const ctx = load(); const p = ctx.createPlayer(0, 'A', '#1', 'x');
    ctx.movePlayer(p, BOARD, 4); assert.equal(p.position, 4);
    ctx.movePlayer(p, BOARD, -3); assert.equal(p.position, 1);
  });

  it('never goes below the start', () => {
    const ctx = load(); const p = ctx.createPlayer(0, 'A', '#1', 'x');
    ctx.movePlayer(p, BOARD, -5);
    assert.equal(p.position, 0);
  });

  it('stops at the finish and marks the player finished', () => {
    const ctx = load(); const p = ctx.createPlayer(0, 'A', '#1', 'x');
    ctx.movePlayer(p, BOARD, 20);
    assert.equal(p.position, 9);
    assert.equal(p.finished, true);
  });
});

describe('movePlayerToPosition', () => {
  it('jumps to a position, clamped to the board, finishing at the end', () => {
    const ctx = load(); const p = ctx.createPlayer(0, 'A', '#1', 'x');
    ctx.movePlayerToPosition(p, BOARD, 5); assert.equal(p.position, 5);
    ctx.movePlayerToPosition(p, BOARD, -2); assert.equal(p.position, 0);
    ctx.movePlayerToPosition(p, BOARD, 99);
    assert.equal(p.position, 9);
    assert.equal(p.finished, true);
  });
});

describe('addScore', () => {
  it('adds and removes points but never below 0', () => {
    const ctx = load(); const p = ctx.createPlayer(0, 'A', '#1', 'x');
    ctx.addScore(p, 5); assert.equal(p.score, 5);
    ctx.addScore(p, -2); assert.equal(p.score, 3);
    ctx.addScore(p, -10); assert.equal(p.score, 0);
  });

  it('reports non-zero changes to window._onScoreChange (score flyout)', () => {
    const ctx = load(); const p = ctx.createPlayer(0, 'A', '#1', 'x');
    const calls = [];
    ctx._onScoreChange = (pl, amount) => calls.push(amount);
    ctx.addScore(p, 2); ctx.addScore(p, 0); ctx.addScore(p, -1);
    assert.deepEqual(calls, [2, -1]);
  });
});

describe('getSortedPlayers', () => {
  const P = (name, score, finishOrder = null) => ({ name, score, finishOrder });

  it('sorts by score, highest first', () => {
    const order = [...load().getSortedPlayers([P('a', 1), P('b', 5), P('c', 3)])].map(p => p.name);
    assert.deepEqual(order, ['b', 'c', 'a']);
  });

  it('breaks ties by finish order, finished players before unfinished', () => {
    const order = [...load().getSortedPlayers([P('late', 4), P('2nd', 4, 2), P('1st', 4, 1)])].map(p => p.name);
    assert.deepEqual(order, ['1st', '2nd', 'late']);
  });

  it('does not change the original array', () => {
    const list = [P('a', 1), P('b', 5)];
    load().getSortedPlayers(list);
    assert.deepEqual(list.map(p => p.name), ['a', 'b']);
  });
});
