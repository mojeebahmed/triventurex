/**
 * test/stats.test.js
 * js/shared/stats.js — end-screen stats and awards from the game history (G13).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { gameStats, gameAwards, awardText, learnedToday, answerOf } = require('../js/shared/stats.js');

const players = [{ id: 0 }, { id: 1 }, { id: 2 }];
/** A history entry: player, roll, where it landed, score/position changes. */
const turn = (playerId, roll, landedOn, { score = 0, move = roll, result = null, spaceType = landedOn } = {}) =>
  ({ playerId, roll, landedOn, spaceType, result, posBefore: 0, posAfter: move, scoreBefore: 10, scoreAfter: 10 + score });

const DEFS = {
  quizMaster:    { icon: '🧠', title: 'Quiz master', text: '{n} questions right' },
  explorer:      { icon: '🌍', title: 'Explorer',    text: '{n} × {landmark}' },
  luckyRoller:   { icon: '🍀', title: 'Lucky',       text: 'average roll {n}' },
  unluckyRoller: { icon: '🐢', title: 'Unlucky',     text: 'average roll {n}' },
  patience:      { icon: '⏳', title: 'Patience',    text: '{n} turns skipped' },
};

describe('gameStats', () => {
  it('counts rolls, questions, actions, deeds, landmarks, skips and spaces per player', () => {
    const s = gameStats([
      turn(0, 6, 'question', { score: 2, result: { question: true } }),
      turn(0, 3, 'question', { result: { question: false } }),
      turn(0, 4, 'bad_deed', { move: 2, spaceType: 'question' }),       // deed moved them back onto a question
      turn(0, 0, null, { spaceType: 'skip', move: 0 }),                 // a skipped turn
      turn(1, 2, 'action', { score: 1, result: { action: true } }),
      turn(1, 5, 'landmark', { score: 5 }),
      { playerId: 1, roll: 0, spaceType: 'gm', posBefore: 0, posAfter: 9, scoreBefore: 0, scoreAfter: 50 },  // GM: ignored
    ], players);
    const [a, b] = s;
    assert.equal(a.rolls, 3);
    assert.equal(a.avgRoll, 4.3);
    assert.equal(a.sixes, 1);
    assert.equal(a.questions, 2, 'the deed turn counts as a deed, not a question');
    assert.equal(a.questionsRight, 1);
    assert.equal(a.bad, 1);
    assert.equal(a.skipped, 1);
    assert.equal(a.spaces, 6 + 3 + 2);
    assert.equal(a.bestTurn, 2);
    assert.equal(b.actions, 1);
    assert.equal(b.actionsGuessed, 1);
    assert.equal(b.landmarks, 1);
    assert.equal(b.bestTurn, 5, 'GM corrections are not counted');
  });

  it('old saves without landedOn / result: guesses from the space and score', () => {
    const [a] = gameStats([{ playerId: 0, roll: 3, spaceType: 'question', posBefore: 0, posAfter: 3, scoreBefore: 0, scoreAfter: 1 }], players);
    assert.equal(a.questions, 1);
    assert.equal(a.questionsRight, 1);
  });
});

describe('gameAwards', () => {
  it('goes to the best player; ties share it', () => {
    const stats = gameStats([
      turn(0, 3, 'question', { result: { question: true } }),
      turn(1, 3, 'question', { result: { question: true } }),
      turn(2, 3, 'question', { result: { question: false } }),
    ], players);
    const quiz = gameAwards(stats, DEFS).find(a => a.id === 'quizMaster');
    assert.deepEqual(quiz.playerIds, [0, 1]);
    assert.equal(quiz.value, 1);
  });

  it('left out when nobody earned it or everyone ties', () => {
    const stats = gameStats([turn(0, 3, 'question', { result: { question: true } }),
                             turn(1, 3, 'question', { result: { question: true } }),
                             turn(2, 3, 'question', { result: { question: true } })], players);
    const ids = gameAwards(stats, DEFS).map(a => a.id);
    assert.ok(!ids.includes('quizMaster'), 'everyone tied');
    assert.ok(!ids.includes('explorer'), 'nobody visited a landmark');
    assert.ok(!ids.includes('patience'));
  });

  it('roll awards need enough rolls and pick the highest / lowest average', () => {
    const rolls = (id, ...rs) => rs.map(r => turn(id, r, 'question'));
    const stats = gameStats([...rolls(0, 6, 6, 5), ...rolls(1, 1, 2, 1), ...rolls(2, 6, 6)], players);
    const awards = gameAwards(stats, DEFS, { minRolls: 3 });
    assert.deepEqual(awards.find(a => a.id === 'luckyRoller').playerIds, [0], 'player 2 rolled only twice');
    assert.deepEqual(awards.find(a => a.id === 'unluckyRoller').playerIds, [1]);
  });

  it('awardText fills in the value and the edition labels', () => {
    assert.equal(awardText({ text: '{n} × {landmark}', value: 3 }, { landmark: 'Stadium' }), '3 × Stadium');
    assert.equal(awardText({ text: '+{n} {points} in one turn', value: 7 }, { points: 'Sawab' }), '+7 Sawab in one turn');
    assert.equal(awardText({ text: '{n} turn{s} skipped', value: 1 }), '1 turn skipped');
    assert.equal(awardText({ text: '{n} turn{s} skipped', value: 2 }), '2 turns skipped');
  });
});

describe('learnedToday — what we learned today', () => {
  const Q = [
    { id: 1, q: 'Capital of France?', opts: [], answer: 'Paris', subcat: 'Capitals', cat: 'Geo', note: '' },
    { id: 2, q: 'Largest ocean?', opts: ['Atlantic', 'Pacific'], answer: 'B', subcat: 'Nature', cat: 'Geo', note: 'It covers a third of the Earth' },
    { id: 3, q: 'Tallest mountain?', opts: [], answer: 'Everest', subcat: '', cat: 'Geo', note: 'Over 8,800 m' },
    { id: 4, q: 'Longest river?', opts: [], answer: 'The Nile', subcat: 'Nature', cat: 'Geo', note: '' },
  ];
  const asked = (qid, right, who = 'Sara') => ({ playerName: who, spaceType: 'question', result: { question: right, qid, diff: 'easy' } });

  it('right answers first, then ones with a fact, each question once, at most 3', () => {
    const l = learnedToday([asked(4, false), asked(1, true), asked(3, false), asked(2, true, 'Ali'), asked(1, true)], Q);
    assert.deepEqual(l.facts.map(f => f.id), [2, 1, 3]);
    assert.deepEqual(l.facts[0], { id: 2, q: 'Largest ocean?', answer: 'Pacific', note: 'It covers a third of the Earth', right: true, playerName: 'Ali' });
    assert.equal(l.asked, 5);
    assert.equal(l.right, 3);
  });

  it('topics: the subcategory (else category) of every question asked, most first', () => {
    assert.deepEqual(learnedToday([asked(2, true), asked(4, false), asked(3, true)], Q).topics, [['Nature', 2], ['Geo', 1]]);
  });

  it('physical cards count, but have no fact; GM entries and other turns are ignored', () => {
    const l = learnedToday([{ spaceType: 'question', result: { question: true, qid: null } }, { spaceType: 'gm', result: { question: true, qid: 1 } }, { result: { action: true } }], Q);
    assert.deepEqual(l, { asked: 1, right: 1, facts: [], topics: [] });
  });

  it('answerOf: the option for a letter, else the answer', () => {
    assert.equal(answerOf(Q[1]), 'Pacific');
    assert.equal(answerOf(Q[0]), 'Paris');
  });
});
