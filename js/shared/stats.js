/**
 * stats.js
 * End-screen stats and fun awards (G13), worked out from the game history
 * (state.history — one entry per turn, see makeHistoryEntry in turn.js).
 * Pure: no page access. Used by the host end screen, sent to the TV display.
 */

/**
 * Per-player numbers for the game. GM corrections are left out.
 * @returns {Array<Object>} one entry per player, in `players` order
 */
function gameStats(history, players) {
  const byId = new Map(players.map(p => [p.id, {
    id: p.id, rolls: 0, rollTotal: 0, avgRoll: 0, sixes: 0,
    questions: 0, questionsRight: 0, actions: 0, actionsGuessed: 0,
    good: 0, bad: 0, landmarks: 0, skipped: 0, spaces: 0, bestTurn: 0,
  }]));

  for (const e of history || []) {
    const s = byId.get(e.playerId);
    if (!s || e.spaceType === 'gm') continue;
    if (e.roll > 0) { s.rolls++; s.rollTotal += e.roll; if (e.roll === 6) s.sixes++; }
    if (e.spaceType === 'skip' && !e.roll) s.skipped++;

    // Where the roll landed. Older saves have no landedOn: the end space is the best guess.
    const landed = e.landedOn ?? (e.roll > 0 ? e.spaceType : null);
    const gained = e.scoreAfter > e.scoreBefore;
    if (landed === 'question')  { s.questions++; if (e.result?.question ?? gained) s.questionsRight++; }
    if (landed === 'action')    { s.actions++;   if (e.result?.action ?? gained)   s.actionsGuessed++; }
    if (landed === 'good_deed') s.good++;
    if (landed === 'bad_deed')  s.bad++;
    if (landed === 'landmark')  s.landmarks++;

    s.spaces   += Math.max(0, e.posAfter - e.posBefore);
    s.bestTurn  = Math.max(s.bestTurn, e.scoreAfter - e.scoreBefore);
  }
  for (const s of byId.values()) s.avgRoll = s.rolls ? Math.round((s.rollTotal / s.rolls) * 10) / 10 : 0;
  return [...byId.values()];
}

// Which number each award is for, and whether the most or the least wins
const AWARD_RULES = {
  quizMaster:    { value: s => s.questionsRight, best: 'max' },
  performer:     { value: s => s.actionsGuessed, best: 'max' },
  goodDeeds:     { value: s => s.good,           best: 'max' },
  badDeeds:      { value: s => s.bad,            best: 'max' },
  explorer:      { value: s => s.landmarks,      best: 'max' },
  bigTurn:       { value: s => s.bestTurn,       best: 'max' },
  luckyRoller:   { value: s => s.avgRoll,        best: 'max', rolls: true },
  unluckyRoller: { value: s => s.avgRoll,        best: 'min', rolls: true },
  patience:      { value: s => s.skipped,        best: 'max' },
};

/**
 * Awards for this game: [{ id, icon, title, value, playerIds }]. An award
 * goes to everyone tied for the best value; it's left out when nobody has
 * earned it (0), or when every player ties (nothing to celebrate).
 * Roll awards need `minRolls` rolls per player and two such players.
 */
function gameAwards(stats, awardDefs, { minRolls = 3 } = {}) {
  const out = [];
  for (const [id, def] of Object.entries(awardDefs || {})) {
    const rule = AWARD_RULES[id];
    if (!rule) continue;
    const pool = rule.rolls ? stats.filter(s => s.rolls >= minRolls) : stats;
    if (pool.length < 2) continue;
    const values = pool.map(rule.value);
    const best = rule.best === 'max' ? Math.max(...values) : Math.min(...values);
    if (rule.best === 'max' && best <= 0) continue;
    const winners = pool.filter(s => rule.value(s) === best);
    if (winners.length === pool.length) continue;
    out.push({ id, icon: def.icon, title: def.title, text: def.text, value: best, playerIds: winners.map(s => s.id) });
  }
  return out;
}

/** "{n} × {good}" → "3 × Good Deed", "{n} turn{s}" → "1 turn" — labels: { good, bad, landmark, points }. */
function awardText(award, labels = {}) {
  return String(award.text || '')
    .replace('{n}', award.value)
    .replace('{s}', award.value === 1 ? '' : 's')
    .replace('{good}', labels.good ?? 'good deeds')
    .replace('{bad}', labels.bad ?? 'bad deeds')
    .replace('{landmark}', labels.landmark ?? 'landmarks')
    .replace('{points}', labels.points ?? 'pts');
}

/** A question's answer as text: the option for a multiple-choice letter, else the answer itself. */
function answerOf(q) {
  const i = ['A', 'B', 'C', 'D'].indexOf(q.answer);
  return q.opts?.length && i >= 0 ? (q.opts[i] ?? q.answer) : q.answer;
}

/**
 * "What we learned today" for the end screen: from the questions asked in the
 * game (history entries with result.question + result.qid, see _noteQuestion).
 *   facts   up to `max` questions, each once — answered right first, then
 *           those with a fact (note) first, in game order: [{ id, q, answer, note, right, playerName }]
 *   topics  [[name, count]] — the subcategory (else category) of every question asked, most first
 *   asked / right  how many questions were asked / answered right (physical cards included)
 * Text is the edition's own (it may hold a little HTML, like the question cards).
 */
function learnedToday(history, questions, { max = 3 } = {}) {
  const byId = new Map((questions || []).map(q => [q.id, q]));
  const asked = [];
  for (const e of history || []) {
    const r = e.result;
    if (e.spaceType === 'gm' || typeof r?.question !== 'boolean') continue;
    asked.push({ q: r.qid != null ? byId.get(r.qid) : null, right: r.question, playerName: e.playerName });
  }
  const seen = new Set();
  const once = asked.filter(a => a.q && !seen.has(a.q.id) && seen.add(a.q.id));
  const facts = once
    .map((a, i) => ({ a, i }))
    .sort((x, y) => (y.a.right - x.a.right) || (!!y.a.q.note - !!x.a.q.note) || (x.i - y.i))
    .slice(0, max)
    .map(({ a }) => ({ id: a.q.id, q: a.q.q, answer: answerOf(a.q), note: a.q.note || '', right: a.right, playerName: a.playerName }));
  const counts = new Map();
  for (const { q } of asked) {
    const topic = q && (q.subcat || q.cat);
    if (topic) counts.set(topic, (counts.get(topic) || 0) + 1);
  }
  const topics = [...counts].sort((a, b) => b[1] - a[1]);
  return { asked: asked.length, right: asked.filter(a => a.right).length, facts, topics };
}

if (typeof module !== 'undefined') module.exports = { gameStats, gameAwards, awardText, learnedToday, answerOf };
