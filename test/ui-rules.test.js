/**
 * test/ui-rules.test.js
 * The space modals in js/host/ui.js follow the game's rules (G12):
 * question difficulty / points / timer, landmark points (roll and deed
 * arrivals), action card settings, finish bonus.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..');

/** Sandbox with ui.js and its real helpers; screen output is recorded. */
function makeUi(ruleChanges = {}, { phone = false } = {}) {
  const store = {}, modals = [], toasts = [], sent = [], asked = [];
  let cancelled = 0;
  const el = () => ({ textContent: '', innerHTML: '', style: {}, value: '',
                      classList: { add() {}, remove() {}, toggle() {}, contains: () => false } });
  const ctx = {
    console, Math, JSON,
    setInterval: () => 0, clearInterval() {},
    localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
    document: { getElementById: el, documentElement: { style: { setProperty() {}, removeProperty() {} } } },
    getActiveEditionId: () => 'test',
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of ['js/shared/utils.js', 'js/shared/config.js', 'js/shared/players.js',
                   'js/shared/rules.js', 'js/host/ui.js']) {
    vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });
  }
  ctx.__changes = ruleChanges;
  const rules = vm.runInContext('buildRules(CONFIG, { changes: __changes }, { hasActionCards: true })', ctx);
  Object.assign(ctx, {
    state: { turn: {} },
    gameRules: () => rules,
    showModal: m => modals.push(m),
    showToast: t => toasts.push(t),
    _sendPrivateCard: (player, card) => { sent.push(card); return false; },
    // Phone helpers from net-host.js: `phone` = the player is on a reachable phone
    _sendPhoneCard: (player, card) => { if (phone) sent.push(card); return phone; },
    _askOnPhone: (player, card, onChoice) => { if (phone) asked.push({ card, onChoice }); return phone; },
    _cancelPhonePrompt: () => { cancelled++; },
    _isStale: () => false,
    reportQuestionHtml: () => '',
    _onScoreChange: () => {},
  });
  vm.runInContext('setAllowNegativeScores(gameRules().scoring.negativeScores)', ctx);
  const player = vm.runInContext("createPlayer(0, 'Ali', '#111', 'a')", ctx);
  return { ctx, rules, modals, toasts, sent, asked, player, run: c => vm.runInContext(c, ctx),
           get cancelled() { return cancelled; } };
}
const last = list => list[list.length - 1];

describe('questions', () => {
  function withQuestions(u) {
    u.ctx.QUESTIONS_DATA = [
      { id: 1, q: 'Easy?', opts: [], answer: 'a', diff: 'easy', cat: 'c', topic: '' },
      { id: 2, q: 'Hard?', opts: [], answer: 'b', diff: 'hard', cat: 'c', topic: '' },
    ];
    return u;
  }

  it('player chooses: the buttons show the configured points', () => {
    const u = withQuestions(makeUi({ scoring: { questionEasy: 2, questionHard: 4 } }));
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
    const labels = last(u.modals).actions.map(a => a.label).join(' ');
    assert.match(labels, /Easy\s+\(\+2/);
    assert.match(labels, /Hard\s+\(\+4/);
  });

  it('always easy: goes straight to an easy question', () => {
    const u = withQuestions(makeUi({ questions: { difficulty: 'easy' } }));
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
    assert.equal(u.modals.length, 1);
    assert.match(last(u.modals).title, /^Easy Question/);
  });

  it('auto-start timer: the timer is running when the question appears', () => {
    const u = withQuestions(makeUi({ questions: { difficulty: 'hard', timerAuto: true, timerSeconds: 45 } }));
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
    assert.equal(u.run('timer.running'), true);
    assert.equal(u.run('timer.duration'), 45);
  });
});

describe('landmarks', () => {
  const space = { type: 'landmark', name: 'Camp Nou', image: null, description: '' };

  it('landing by roll: points from the rules, one button, no GM choice', () => {
    const u = makeUi({ scoring: { landmarkRoll: 3 } });
    let done = 0;
    u.ctx.showSpaceModal(space, u.player, () => done++);
    const m = last(u.modals);
    assert.equal(m.actions.length, 1);
    assert.match(m.actions[0].label, /Collect \+3/);
    m.actions[0].callback();
    assert.equal(u.player.score, 3);
    assert.equal(done, 1);
  });

  it('0 points: just information', () => {
    const u = makeUi({ scoring: { landmarkRoll: 0 } });
    u.ctx.showSpaceModal(space, u.player, () => {});
    const m = last(u.modals);
    assert.equal(m.actions[0].label, 'Continue');
    m.actions[0].callback();
    assert.equal(u.player.score, 0);
  });

  it('arriving via a good / bad deed uses those settings, with a toast', () => {
    const u = makeUi({ scoring: { landmarkGoodDeed: 2, landmarkBadDeed: -1, negativeScores: true } });
    u.ctx._gameBoard = Array.from({ length: 10 }, (_, i) =>
      (i === 5 ? { id: 5, type: 'landmark', name: 'Wembley' } : { id: i, type: 'question' }));

    u.player.position = 3;
    u.ctx._applyDeedEffect({ type: 'good', effect: 'move_forward', value: 2 }, u.player);
    assert.equal(u.player.position, 5);
    assert.equal(u.player.score, 2);
    assert.match(last(u.toasts), /arrived at Wembley · \+2/);

    u.player.position = 7;
    u.ctx._applyDeedEffect({ type: 'bad', effect: 'move_back', value: 2 }, u.player);
    assert.equal(u.player.score, 1);
    assert.match(last(u.toasts), /arrived at Wembley · -1/);
  });

  it('a deed that does not end on a landmark gives nothing extra', () => {
    const u = makeUi({ scoring: { landmarkGoodDeed: 2 } });
    u.ctx._gameBoard = Array.from({ length: 10 }, (_, i) => ({ id: i, type: 'question' }));
    u.player.position = 3;
    u.ctx._applyDeedEffect({ type: 'good', effect: 'move_forward', value: 2 }, u.player);
    assert.equal(u.player.score, 0);
    assert.equal(u.toasts.length, 0);
  });
});

describe('action cards', () => {
  const CARDS = [
    { id: 1, text: 'Mime it', kind: 'act', note: '' },
    { id: 2, text: 'Hum it', kind: 'sound', note: '' },
  ];

  it('digital: draws only allowed kinds and uses the configured points + timer', () => {
    const u = makeUi({ actions: { kinds: ['sound'], timerSeconds: 60 }, scoring: { actionPerformer: 3, actionGuesser: 2 } });
    u.ctx.ACTIONS_DATA = CARDS;
    u.ctx.showSpaceModal({ type: 'action' }, u.player, () => {});
    assert.equal(u.ctx.state.turn.actionCard.kind, 'sound');
    assert.equal(u.run('timer.duration'), 60);
    const m = last(u.modals);
    assert.match(m.actions[0].label, /Guessed! \(\+3\)/);
    m.actions[0].callback();
    assert.equal(u.player.score, 3);
  });

  it('a digital card can be swapped for a physical one', () => {
    const u = makeUi();
    u.ctx.ACTIONS_DATA = CARDS;
    u.ctx.showSpaceModal({ type: 'action' }, u.player, () => {});
    const swap = last(u.modals).actions.find(a => /physical card instead/.test(a.label));
    assert.ok(swap, 'swap button offered');
    swap.callback();
    assert.equal(u.ctx.state.turn.actionCard, null);
    assert.match(last(u.modals).content, /from the deck/);
    assert.ok(!last(u.modals).actions.some(a => /physical card instead/.test(a.label)));
  });

  it("physical rule: no digital card is drawn", () => {
    const u = makeUi({ actions: { cards: 'physical' } });
    u.ctx.ACTIONS_DATA = CARDS;
    u.ctx.showSpaceModal({ type: 'action' }, u.player, () => {});
    assert.equal(u.ctx.state.turn.actionCard, null);
    assert.equal(u.sent.length, 0);
  });
});

describe('finish', () => {
  it('finish bonus off: no bonus line', () => {
    const u = makeUi({ scoring: { finishBonus: 'off' } });
    u.player.finishOrder = 1;
    u.ctx.showSpaceModal({ type: 'finish' }, u.player, () => {});
    assert.doesNotMatch(last(u.modals).content, /bonus awarded/);
  });

  it('small finish bonus: 1st gets 5', () => {
    const u = makeUi({ scoring: { finishBonus: 'small' } });
    u.player.finishOrder = 1;
    u.ctx.showSpaceModal({ type: 'finish' }, u.player, () => {});
    assert.match(last(u.modals).content, /\+5 .* bonus awarded/);
  });
});

describe('answering on the phone (G3)', () => {
  const MULTI = { id: 7, q: 'Capital of <em>Sweden</em>?', opts: ['Oslo', 'Stockholm', 'Bergen'], answer: 'B',
                  diff: 'hard', cat: 'c', topic: '', note: 'Since 1634' };
  function game(changes = {}, phone = true) {
    const u = makeUi({ scoring: { questionHard: 3 }, ...changes }, { phone });
    u.ctx.QUESTIONS_DATA = [MULTI, { id: 8, q: 'Name a planet', opts: [], answer: 'Mars', diff: 'easy', cat: 'c', topic: '' }];
    return u;
  }

  it('the player chooses the difficulty on the phone', () => {
    const u = game();
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
    assert.equal(u.asked.length, 1);
    assert.deepEqual([...u.asked[0].card.choices.map(c => c.id)], ['easy', 'hard']);
    assert.match(last(u.modals).content, /Waiting for <strong>Ali<\/strong> to choose/);
    u.asked[0].onChoice('hard');
    assert.match(last(u.modals).title, /^Hard Question/);
  });

  it('multiple choice goes to the phone without the answer', () => {
    const u = game({ questions: { difficulty: 'hard' } });
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
    const card = u.asked[0].card;
    assert.equal(card.text, 'Capital of Sweden?', 'HTML stripped for the phone');
    assert.deepEqual([...card.choices.map(c => c.id)], ['A', 'B', 'C']);
    assert.doesNotMatch(JSON.stringify(card), /Since 1634|"answer"/);
    assert.match(last(u.modals).content, /Waiting for <strong>Ali<\/strong> to answer/);
    assert.match(last(u.modals).actions[0].label, /judge here/);
  });

  it('a right answer scores automatically; both screens show the result', () => {
    const u = game({ questions: { difficulty: 'hard' } });
    let done = 0;
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => done++);
    u.asked[0].onChoice('B');
    assert.equal(u.player.score, 3);
    assert.match(last(u.modals).title, /Correct! \+3/);
    assert.match(last(u.modals).content, /option-correct/);
    assert.match(last(u.sent).title, /Correct/);
    assert.equal(done, 0, 'the GM continues');
    last(u.modals).actions[0].callback();
    assert.equal(done, 1);
  });

  it('a wrong answer scores nothing and shows the right one', () => {
    const u = game({ questions: { difficulty: 'hard' } });
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
    u.asked[0].onChoice('A');
    assert.equal(u.player.score, 0);
    assert.match(last(u.modals).content, /option-wrong/);
    assert.match(last(u.sent).text, /B — Stockholm/);
  });

  it('the GM can still judge on the host — the phone prompt is cancelled', () => {
    const u = game({ questions: { difficulty: 'hard' } });
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
    last(u.modals).actions[0].callback();           // Reveal answer (judge here)
    assert.equal(u.cancelled, 1);
    assert.match(last(u.modals).actions[0].label, /Correct/);
  });

  it('open questions are shown on the phone but judged by the GM', () => {
    const u = game({ questions: { difficulty: 'easy' } });
    u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
    assert.equal(u.asked.length, 0);
    assert.equal(last(u.sent).text, 'Name a planet');
    assert.doesNotMatch(JSON.stringify(last(u.sent)), /Mars/);
  });

  it('rule off, or no phone: asked on the host as before', () => {
    for (const u of [game({ questions: { difficulty: 'hard', answerOnPhone: false } }), game({ questions: { difficulty: 'hard' } }, false)]) {
      u.ctx.showSpaceModal({ type: 'question' }, u.player, () => {});
      assert.equal(u.asked.length, 0);
      assert.doesNotMatch(last(u.modals).content, /Waiting for/);
      assert.equal(last(u.modals).actions[0].label, '👁 Reveal Answer');
    }
  });
});
