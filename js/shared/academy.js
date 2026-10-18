/**
 * academy.js
 * Triventurex Academy (academy.html): building the rounds for the learning
 * modes from an edition's questions and landmarks. Pure — no page access —
 * unit-tested in test/academy.test.js. `rand` is a () => [0, 1) function so
 * tests can make rounds repeatable.
 *
 * A question: { id, q, opts, answer, diff, cat, subcat, topic, note } where a
 * multiple-choice `answer` is a letter ('A'…'D') and an open one is text.
 */

const _acPlain = s => String(s ?? '').replace(/<[^>]*>/g, '').trim();

/** A shuffled copy (Fisher–Yates). */
function shuffled(list, rand = Math.random) {
  const a = [...(list || [])];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const isMulti = q => Array.isArray(q.opts) && q.opts.length > 1;

/** The answer as plain text: the correct option, or the open answer. */
function answerText(q) {
  if (!isMulti(q)) return _acPlain(q.answer);
  return _acPlain(q.opts['ABCD'.indexOf(q.answer)] ?? '');
}

/** Index of the correct option of a multiple-choice question. */
const correctIndex = q => 'ABCD'.indexOf(q.answer);

/** Up to `n` questions in random order (all of them when n is 0 / missing). */
function quizRound(questions, n = 10, rand = Math.random) {
  const all = shuffled(questions, rand);
  return n ? all.slice(0, n) : all;
}

/**
 * Flashcards "Not yet": put the card back a few places later, so it comes
 * round again soon (or at the end of a short deck). Returns a new deck
 * without the first card; `deck[0]` is the card just answered.
 */
function requeue(deck, gap = 4) {
  const [card, ...rest] = deck;
  if (!card) return rest;
  const at = Math.min(gap, rest.length);
  return [...rest.slice(0, at), card, ...rest.slice(at)];
}

/**
 * True or false: a multiple-choice question shown with one option — the
 * correct one about half of the time. → [{ q, shown, isTrue }]
 */
function trueFalseItems(questions, n = 10, rand = Math.random) {
  return quizRound((questions || []).filter(isMulti), n, rand).map(q => {
    const isTrue = rand() < 0.5;
    const wrong = q.opts.map(_acPlain).filter((_, i) => i !== correctIndex(q));
    const shown = isTrue ? answerText(q) : wrong[Math.floor(rand() * wrong.length)];
    return { q, shown, isTrue };
  });
}

/**
 * Match pairs: `n` questions with short, different answers, so they fit on a
 * card and every answer belongs to exactly one question.
 * → [{ id, question, answer }] (the page shuffles the answer column itself)
 */
function matchPairs(questions, n = 6, rand = Math.random, { maxAnswer = 40, maxQuestion = 120 } = {}) {
  const seen = new Set();
  const out = [];
  for (const q of shuffled(questions, rand)) {
    const answer = answerText(q);
    const key = answer.toLowerCase();
    if (!answer || answer.length > maxAnswer || _acPlain(q.q).length > maxQuestion || seen.has(key)) continue;
    seen.add(key);
    out.push({ id: q.id, question: q.q, answer });
    if (out.length === n) break;
  }
  return out;
}

/** Speed round: multiple-choice questions only, in random order. */
const speedPool = (questions, rand = Math.random) => shuffled((questions || []).filter(isMulti), rand);

/**
 * "Where am I?": a landmark's photo with four names to choose from.
 * → [{ landmark, options: [name…], answer: index }] (landmarks without a photo are skipped)
 */
function placesQuiz(landmarks, n = 10, rand = Math.random) {
  const withPhoto = (landmarks || []).filter(l => l.image);
  return quizRound(withPhoto, n, rand).map(landmark => {
    const others = shuffled(withPhoto.filter(l => l.name !== landmark.name), rand).slice(0, 3).map(l => l.name);
    const options = shuffled([landmark.name, ...others], rand);
    return { landmark, options, answer: options.indexOf(landmark.name) };
  });
}

/** Reviewer progress for an edition. `reviewed` / `marked` are the stored id maps. */
function reviewStats(questions, reviewed = {}, marked = {}) {
  const ids = new Set((questions || []).map(q => String(q.id)));
  const done = Object.keys(reviewed).filter(id => ids.has(id)).length;
  const flagged = Object.keys(marked).filter(id => ids.has(id)).length;
  return { total: ids.size, reviewed: done, marked: flagged, left: ids.size - done };
}

if (typeof module !== 'undefined') {
  module.exports = { shuffled, answerText, correctIndex, isMulti, quizRound, requeue, trueFalseItems,
                     matchPairs, speedPool, placesQuiz, reviewStats };
}
