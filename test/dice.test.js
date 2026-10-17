/**
 * test/dice.test.js
 * js/shared/dice.js — die faces and the shared rolling animation (G10).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { renderDie, rollDice, animateDieInto } = require('../js/shared/dice.js');

const dots = html => (html.match(/die-dot/g) || []).length;

describe('renderDie', () => {
  it('draws the right number of dots for 1–6', () => {
    for (let n = 1; n <= 6; n++) assert.equal(dots(renderDie(n)), n);
  });

  it('adds the size class', () => {
    assert.match(renderDie(3, 'die-lg'), /class="die-face die-lg"/);
  });
});

describe('rollDice', () => {
  it('always returns 1–6', () => {
    for (let i = 0; i < 500; i++) {
      const r = rollDice();
      assert.ok(Number.isInteger(r) && r >= 1 && r <= 6);
    }
  });
});

describe('animateDieInto', () => {
  it('flashes faces, then always ends on the actual result', async () => {
    for (const result of [1, 4, 6]) {
      const seen = [];
      const el = { set innerHTML(v) { seen.push(v); }, get innerHTML() { return seen.at(-1); } };
      await animateDieInto(el, result, { sizeClass: 'die-sm', flashes: 5, intervalMs: 1 });
      assert.equal(seen.length, 6, '5 random faces + the result');
      assert.equal(dots(seen.at(-1)), result);
      assert.match(seen.at(-1), /die-sm/);
    }
  });

  it('resolves straight away when there is no element', async () => {
    await animateDieInto(null, 3);
  });
});
