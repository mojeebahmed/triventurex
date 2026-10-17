/**
 * test/questions.test.js
 * js/shared/questions.js — question explorer tree / filter and the marked
 * questions report (G14 + G19).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { questionTree, filterQuestions, answerLabel, markedReport, topicKey, selectedTopicKeys } = require('../js/shared/questions.js');

const Q = [
  { id: 1, q: 'Capital of <em>Sweden</em>?', opts: ['Oslo', 'Stockholm'], answer: 'B', diff: 'easy', cat: 'Geo', subcat: 'Europe', topic: 'Capitals', note: '' },
  { id: 2, q: 'Longest river?', opts: [], answer: 'Nile', diff: 'hard', cat: 'Geo', subcat: 'Africa', topic: 'Rivers', note: 'Some say the Amazon' },
  { id: 3, q: 'Who won in 1930?', opts: ['Brazil', 'Uruguay'], answer: 'B', diff: 'easy', cat: 'history', subcat: '', topic: '', note: '' },
  { id: 4, q: 'Capital of Norway?', opts: ['Oslo', 'Bergen'], answer: 'A', diff: 'hard', cat: 'Geo', subcat: 'Europe', topic: 'Capitals', note: '' },
];

describe('questionTree', () => {
  it('counts per category > subcategory > topic; category-only editions get one level', () => {
    const t = questionTree(Q);
    assert.deepEqual(t.map(c => [c.name, c.count]), [['Geo', 3], ['history', 1]]);
    const europe = t[0].children.find(s => s.name === 'Europe');
    assert.equal(europe.count, 2);
    assert.deepEqual(europe.children.map(x => [x.name, x.count]), [['Capitals', 2]]);
    assert.deepEqual(t[1].children, [], 'no subcategory / topic level');
  });
});

describe('filterQuestions', () => {
  const ids = opts => filterQuestions(Q, opts).map(q => q.id);
  it('by branch of the tree', () => {
    assert.deepEqual(ids({ path: ['Geo'] }), [1, 2, 4]);
    assert.deepEqual(ids({ path: ['Geo', 'Europe', 'Capitals'] }), [1, 4]);
  });
  it('by words (question, options, answer, note — HTML ignored), all must match', () => {
    assert.deepEqual(ids({ text: 'sweden' }), [1], 'inside <em>');
    assert.deepEqual(ids({ text: 'oslo capital' }), [1, 4]);
    assert.deepEqual(ids({ text: 'amazon' }), [2], 'notes are searched');
    assert.deepEqual(ids({ text: 'oslo norway' }), [4]);
  });
  it('by difficulty and by a set of ids (marked only)', () => {
    assert.deepEqual(ids({ diff: 'hard' }), [2, 4]);
    assert.deepEqual(ids({ onlyIds: new Set([3, 4]) }), [3, 4]);
  });
});

describe('marked report', () => {
  it('answerLabel: letter + option, or the open answer', () => {
    assert.equal(answerLabel(Q[0]), 'B — Stockholm');
    assert.equal(answerLabel(Q[1]), 'Nile');
  });

  it('lists each marked question with where it is, the answer and the note — in id order', () => {
    const text = markedReport({ 2: { note: 'Amazon is longer?' }, 1: { note: '' }, 99: { note: 'gone' } }, Q, 'Test');
    assert.match(text, /^Reported questions — Test \(3\)/);
    assert.ok(text.indexOf('#1 ') < text.indexOf('#2 ') && text.indexOf('#2 ') < text.indexOf('#99'));
    assert.match(text, /#2 \[hard\] Geo > Africa > Rivers\n {3}Longest river\?\n {3}Answer: Nile\n {3}Note: Amazon is longer\?/);
    assert.match(text, /Capital of Sweden\?/, 'HTML removed');
    assert.match(text, /#99 \(no longer in questions.csv\)/);
  });
});

describe('topic filter keys (same topic name under several branches)', () => {
  const T = [
    { id: 1, cat: 'Capitals', subcat: 'Capitals', topic: 'Europe' },
    { id: 2, cat: 'Flags', subcat: 'Flags', topic: 'Europe' },
    { id: 3, cat: 'Flags', subcat: 'Flags', topic: 'Asia' },
    { id: 4, cat: 'Misc', subcat: '', topic: '' },
  ];

  it('keys a question by its full path, with the tree fallbacks', () => {
    assert.equal(topicKey(T[0]), 'Capitals › Capitals › Europe');
    assert.equal(topicKey(T[3]), 'Misc › Other › General');
  });

  it('nothing saved = everything selected', () => {
    assert.equal(selectedTopicKeys(null, T).size, 4);
  });

  it('a saved path selects only that branch — "Europe" under Flags stays off', () => {
    const sel = selectedTopicKeys(['Capitals › Capitals › Europe', 'Flags › Flags › Asia'], T);
    assert.ok(sel.has(topicKey(T[0])));
    assert.ok(!sel.has(topicKey(T[1])));
    assert.ok(sel.has(topicKey(T[2])));
  });

  it('old saves (plain topic names) select every branch with that name', () => {
    const sel = selectedTopicKeys(['Europe'], T);
    assert.deepEqual([...sel].sort(), ['Capitals › Capitals › Europe', 'Flags › Flags › Europe']);
  });

  it('keys for branches that no longer exist are dropped', () => {
    assert.equal(selectedTopicKeys(['Gone › Gone › Gone'], T).size, 0);
  });
});
