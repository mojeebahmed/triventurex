/**
 * test/academy.test.js
 * js/shared/academy.js — rounds for the Triventurex Academy learning modes —
 * plus a check that every edition can fill each mode.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const A = require('../js/shared/academy.js');
const { listEditions, loadEdition } = require('../scripts/content.js');

/** Repeatable "random" numbers. */
function seeded(seed = 1) {
  return () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
}

const Q = [
  { id: 1, q: 'Capital of <em>France</em>?', opts: ['Rome', 'Paris', 'Oslo'], answer: 'B', diff: 'easy' },
  { id: 2, q: 'Largest ocean?', opts: [], answer: 'The Pacific', diff: 'easy' },
  { id: 3, q: 'Capital of Italy?', opts: ['Rome', 'Paris', 'Madrid'], answer: 'A', diff: 'hard' },
  { id: 4, q: 'Capital of Spain?', opts: ['Lisbon', 'Madrid'], answer: 'B', diff: 'easy' },
  { id: 5, q: 'A question with a very long answer?', opts: [], answer: 'x'.repeat(80), diff: 'hard' },
  { id: 6, q: 'Same answer as #2?', opts: [], answer: 'the pacific', diff: 'hard' },
];

describe('basics', () => {
  it('shuffled keeps every item and does not change the input', () => {
    const input = [1, 2, 3, 4, 5];
    const out = A.shuffled(input, seeded(3));
    assert.deepEqual([...out].sort(), input);
    assert.deepEqual(input, [1, 2, 3, 4, 5]);
  });

  it('answerText: the correct option, or the open answer, as plain text', () => {
    assert.equal(A.answerText(Q[0]), 'Paris');
    assert.equal(A.answerText(Q[1]), 'The Pacific');
  });

  it('quizRound: n questions, or all of them with n = 0', () => {
    assert.equal(A.quizRound(Q, 3, seeded()).length, 3);
    assert.equal(A.quizRound(Q, 0, seeded()).length, Q.length);
    assert.equal(A.quizRound(Q, 50, seeded()).length, Q.length);
  });

  it('requeue: "Not yet" puts the card a few places later, or last in a short deck', () => {
    assert.deepEqual(A.requeue(['a', 'b', 'c', 'd', 'e', 'f'], 3), ['b', 'c', 'd', 'a', 'e', 'f']);
    assert.deepEqual(A.requeue(['a', 'b'], 4), ['b', 'a']);
    assert.deepEqual(A.requeue(['a'], 4), ['a']);
    assert.deepEqual(A.requeue([], 4), []);
  });
});

describe('true or false', () => {
  it('uses multiple choice only, and shows the right option exactly when it is true', () => {
    const items = A.trueFalseItems(Q, 20, seeded(7));
    assert.equal(items.length, 3, 'three multiple-choice questions');
    for (const { q, shown, isTrue } of items) {
      assert.ok(A.isMulti(q));
      assert.equal(shown === A.answerText(q), isTrue);
      assert.ok(q.opts.includes(shown));
    }
    const many = Array.from({ length: 40 }, (_, i) => A.trueFalseItems(Q, 3, seeded(i + 1))).flat();
    assert.ok(many.some(i => i.isTrue) && many.some(i => !i.isTrue), 'both true and false statements');
  });
});

describe('match pairs', () => {
  it('only short, different answers — every answer belongs to one question', () => {
    const pairs = A.matchPairs(Q, 10, seeded(2));
    const answers = pairs.map(p => p.answer.toLowerCase());
    assert.equal(new Set(answers).size, answers.length, 'answers are unique');
    assert.ok(!pairs.some(p => p.id === 5), 'long answer left out');
    assert.ok(!(pairs.some(p => p.id === 2) && pairs.some(p => p.id === 6)), 'same answer only once');
    assert.ok(pairs.length <= 10);
  });
});

describe('speed round + places', () => {
  it('speedPool is multiple choice only', () => {
    assert.ok(A.speedPool(Q, seeded()).every(A.isMulti));
  });

  it('placesQuiz: four different names including the right one; photo-less landmarks skipped', () => {
    const lms = ['A', 'B', 'C', 'D', 'E'].map(n => ({ name: n, image: `${n}.jpg` })).concat({ name: 'NoPhoto', image: null });
    const round = A.placesQuiz(lms, 10, seeded(5));
    assert.equal(round.length, 5);
    for (const r of round) {
      assert.equal(new Set(r.options).size, 4);
      assert.equal(r.options[r.answer], r.landmark.name);
      assert.ok(!r.options.includes('NoPhoto'));
    }
  });
});

describe('reviewStats', () => {
  it('counts reviewed and marked questions of this edition only', () => {
    const s = A.reviewStats(Q, { 1: 'x', 2: 'x', 99: 'x' }, { 3: { note: '' }, 98: {} });
    assert.deepEqual(s, { total: 6, reviewed: 2, marked: 1, left: 4 });
  });
});

// Every edition must give each mode something to play with
for (const id of listEditions().filter(id => id !== 'template')) {
  describe(`academy content: ${id}`, () => {
    const ed = loadEdition(id);
    it('has multiple-choice questions for quiz / true-false / speed, pairs for match, places', () => {
      assert.ok(A.speedPool(ed.questions).length >= 10, 'speed round');
      assert.equal(A.trueFalseItems(ed.questions, 10).length, 10, 'true or false');
      assert.equal(A.matchPairs(ed.questions, 6).length, 6, 'match pairs');
      assert.ok((ed.config.LANDMARKS || []).length >= 4, 'places');
    });
  });
}
