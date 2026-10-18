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

function makeUi(cards, general = []) {
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
  for (const f of ['js/shared/utils.js', 'js/shared/icon-registry.js', 'js/shared/icons.js', 'js/shared/config.js', 'js/host/ui.js']) {
    vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });
  }
  ctx.showToast = t => toasts.push(t); // ui.js defines its own; use the recorder
  ctx.ACTIONS_DATA = cards;
  ctx.GENERAL_ACTIONS_DATA = general;
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

describe('general action cards (C4)', () => {
  const GENERAL = [1, 2].map(id => ({ id, text: `General ${id}`, kind: 'explain', note: '' }));

  it('mixes the general cards in, with g-prefixed ids that never clash with the edition ids', () => {
    const { ctx } = makeUi(CARDS, GENERAL);
    const ids = [1, 2, 3, 4, 5].map(() => ctx._drawActionCard().id).map(String).sort();
    assert.deepEqual(ids, ['1', '2', '3', 'g1', 'g2']);
  });

  it('leaves them out when the rule is off', () => {
    const { ctx } = makeUi(CARDS, GENERAL);
    const ids = [1, 2, 3].map(() => ctx._drawActionCard(null, false).id);
    assert.ok(ids.every(id => typeof id === 'number'));
  });

  it('gives an edition without its own cards a digital deck', () => {
    const { ctx } = makeUi([], GENERAL);
    assert.match(ctx._drawActionCard().id, /^g\d$/);
    assert.equal(ctx._drawActionCard(null, false), null);
  });

  it('respects the allowed kinds for general cards too', () => {
    const { ctx } = makeUi(CARDS, GENERAL);
    for (let i = 0; i < 6; i++) assert.equal(ctx._drawActionCard(['act']).kind, 'act');
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
