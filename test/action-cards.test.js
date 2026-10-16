/**
 * test/action-cards.test.js
 * Drawing and showing action cards (C3) — js/host/ui.js loaded in a sandbox.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..');

function makeUi(cards) {
  const store = {};
  const toasts = [];
  const ctx = {
    console, Math,
    localStorage: {
      getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); },
      removeItem: k => { delete store[k]; },
    },
    document: { getElementById: () => null },
    getActiveEditionId: () => 'test-edition',
    showToast: t => toasts.push(t),
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of ['js/shared/utils.js', 'js/shared/config.js', 'js/host/ui.js']) {
    vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });
  }
  ctx.showToast = t => toasts.push(t); // ui.js defines its own; use the recorder
  ctx.ACTIONS_DATA = cards;
  return { ctx, store, toasts };
}

const CARDS = [1, 2, 3].map(id => ({ id, text: `Card ${id}`, kind: 'act', note: '' }));

describe('_drawActionCard', () => {
  it('returns null when the edition has no action cards', () => {
    const { ctx } = makeUi([]);
    assert.equal(ctx._drawActionCard(), null);
  });

  it('never repeats a card until all have been drawn, then reshuffles', () => {
    const { ctx, toasts } = makeUi(CARDS);
    const first = [1, 2, 3].map(() => ctx._drawActionCard().id).sort();
    assert.deepEqual(first, [1, 2, 3]);
    assert.equal(toasts.length, 0);
    ctx._drawActionCard();
    assert.match(toasts[0], /reshuffling/);
  });

  it('remembers used cards per edition across games (session tracking)', () => {
    const { ctx, store } = makeUi(CARDS);
    ctx._drawActionCard();
    assert.equal(JSON.parse(store['triventurex_asked_test-edition_actions']).length, 1);
  });

  it('resetAskedQuestions also resets action cards (per-game tracking)', () => {
    const { ctx, store } = makeUi(CARDS);
    ctx._drawActionCard();
    ctx.resetAskedQuestions();
    assert.equal(store['triventurex_asked_test-edition_actions'], undefined);
  });
});

describe('_actionCardHtml', () => {
  const player = { name: '<b>Ali</b>' };
  const card = { id: 1, text: 'Mime <a goal>', kind: 'sound', note: 'No "words"' };

  it('keeps the card text hidden until revealed, and escapes it', () => {
    const { ctx } = makeUi(CARDS);
    const html = ctx._actionCardHtml(card, player, false);
    assert.match(html, /class="action-card-secret hidden"/);
    assert.match(html, /Mime &lt;a goal&gt;/);
    assert.match(html, /No &quot;words&quot;/);
    assert.match(html, /&lt;b&gt;Ali&lt;\/b&gt;<\/strong>, reveal your card/);
    assert.match(html, /Hum or sound/);
  });

  it('says the card is on the phone when it was sent there', () => {
    const { ctx } = makeUi(CARDS);
    const html = ctx._actionCardHtml(card, player, true);
    assert.match(html, /The card is on <strong>&lt;b&gt;Ali&lt;\/b&gt;<\/strong>'s phone/);
    assert.match(html, /GM: show \/ hide card/);
  });
});
