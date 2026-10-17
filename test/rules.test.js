/**
 * test/rules.test.js
 * js/shared/rules.js — the per-game rules model (G12).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const R = require('../js/shared/rules.js');

/** A fresh engine CONFIG (config.js is a browser script). */
function config() {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/shared/config.js'), 'utf8') + ';this.CONFIG = CONFIG;', ctx);
  return JSON.parse(JSON.stringify(ctx.CONFIG));
}
const WITH_CARDS = { hasActionCards: true };

describe('defaults', () => {
  it("match today's behaviour", () => {
    const C = config();
    const r = R.defaultRules(C, WITH_CARDS);
    assert.equal(r.scoring.questionEasy, C.SCORE_VALUES.question_easy);
    assert.equal(r.scoring.landmarkRoll, C.SCORE_VALUES.landmark);
    assert.equal(r.scoring.landmarkGoodDeed, 0);
    assert.equal(r.scoring.negativeScores, false);
    assert.equal(r.questions.difficulty, 'choose');
    assert.equal(r.turns.exactFinish, true);
    assert.equal(r.board.tileMix, null);
    assert.equal(r.actions.cards, 'digital');
    assert.deepEqual([...r.actions.kinds], Object.keys(C.ACTION_KINDS));
  });

  it('use the physical deck when the edition has no action cards', () => {
    assert.equal(R.defaultRules(config(), { hasActionCards: false }).actions.cards, 'physical');
  });

  it("take an edition's score overrides", () => {
    const C = config();
    C.SCORE_VALUES.question_hard = 3;
    assert.equal(R.defaultRules(C).scoring.questionHard, 3);
  });
});

describe('presets', () => {
  it('every preset in config.js builds into valid rules', () => {
    const C = config();
    for (const id of Object.keys(C.RULE_PRESETS)) {
      const r = R.buildRules(C, { preset: id, changes: {} }, WITH_CARDS);
      assert.equal(r.preset, id);
      assert.deepEqual(R.normalizeRules(r, WITH_CARDS).scoring, r.scoring, `${id} is already normalized`);
    }
  });

  it('family = defaults; kids and quiz change what they say', () => {
    const C = config();
    const d = R.defaultRules(C, WITH_CARDS);
    const fam = R.buildRules(C, { preset: 'family' }, WITH_CARDS);
    assert.equal(R.countChanges(R.diffRules(fam, d)), 0);
    const kids = R.buildRules(C, { preset: 'kids' }, WITH_CARDS);
    assert.equal(kids.questions.difficulty, 'easy');
    assert.equal(kids.board.noBackwards, true);
    const quiz = R.buildRules(C, { preset: 'quiz' }, WITH_CARDS);
    assert.equal(quiz.scoring.questionHard, 4);
    assert.equal(quiz.scoring.finishBonus, 'small');
  });

  it('an unknown preset falls back to family', () => {
    assert.equal(R.buildRules(config(), { preset: 'gone' }).preset, 'family');
  });
});

describe('storage: preset + changes', () => {
  it('round-trips: diff from the preset, rebuilt = the same rules', () => {
    const C = config();
    const rules = R.buildRules(C, { preset: 'kids', changes: { scoring: { landmarkBadDeed: -3 }, turns: { animation: 'fast' } } }, WITH_CARDS);
    const changes = R.diffRules(rules, R.presetBase(C, 'kids', WITH_CARDS));
    assert.deepEqual(JSON.parse(JSON.stringify(changes)), { scoring: { landmarkBadDeed: -3 }, turns: { animation: 'fast' } });
    assert.equal(R.countChanges(changes), 2);
    const rebuilt = R.buildRules(C, { preset: 'kids', changes }, WITH_CARDS);
    assert.deepEqual(rebuilt, rules);
  });

  it('a changed code default reaches settings nobody touched', () => {
    const C = config();
    const stored = { preset: 'family', changes: { turns: { exactFinish: false } } };
    C.SCORE_VALUES.landmark = 7;                       // new default in code
    const r = R.buildRules(C, stored);
    assert.equal(r.scoring.landmarkRoll, 7);
    assert.equal(r.turns.exactFinish, false);           // the user's own change stays
  });

  it('a tile mix counts as one change', () => {
    const C = config();
    const r = R.buildRules(C, { changes: { board: { tileMix: { action: 30, good_deed: 0, bad_deed: 0, landmark: 0, skip: 0 } } } });
    assert.equal(R.countChanges(R.diffRules(r, R.defaultRules(C))), 1);
  });
});

describe('normalizeRules', () => {
  it('clamps numbers and fixes unknown choices', () => {
    const C = config();
    const r = R.buildRules(C, { changes: {
      scoring: { questionEasy: 999, landmarkRoll: -999 },
      questions: { timerSeconds: 1, difficulty: 'nightmare' },
      turns: { whoStarts: 'oldest' },
    } }, WITH_CARDS);
    assert.equal(r.scoring.questionEasy, 50);
    assert.equal(r.scoring.landmarkRoll, -50);
    assert.equal(r.questions.timerSeconds, 5);
    assert.equal(r.questions.difficulty, 'choose');
    assert.equal(r.turns.whoStarts, 'order');
  });

  it('keeps at least one action kind, and only known ones', () => {
    const r = R.buildRules(config(), { changes: { actions: { kinds: ['dance'] } } }, WITH_CARDS);
    assert.deepEqual([...r.actions.kinds], ['act', 'explain', 'sound']);
  });

  it('caps the special tiles at MAX_SPECIAL_PERCENT in total', () => {
    const { mix, capped } = R.normalizeTileMix({ action: 50, good_deed: 50, bad_deed: 50, landmark: 0, skip: 0 });
    assert.equal(capped, true);
    assert.ok(Object.values(mix).reduce((s, v) => s + v, 0) <= R.MAX_SPECIAL_PERCENT);
    assert.equal(R.normalizeTileMix({ action: 10 }).capped, false);
  });
});

describe('scoring helpers', () => {
  const C = config();
  const rules = choice => R.buildRules(C, { changes: { scoring: { finishBonus: choice } } });

  it('finish bonus: standard / small / off', () => {
    assert.deepEqual([1, 2, 3, 9].map(n => R.finishBonusFor(rules('standard'), C, n)), [10, 7, 5, 1]);
    assert.deepEqual([1, 2, 4, 5].map(n => R.finishBonusFor(rules('small'), C, n)), [5, 3, 1, 0]);
    assert.equal(R.finishBonusFor(rules('off'), C, 1), 0);
  });

  it('landmark points by how the player got there', () => {
    const r = R.buildRules(C, { changes: { scoring: { landmarkRoll: 4, landmarkGoodDeed: 2, landmarkBadDeed: -1 } } });
    assert.equal(R.landmarkPoints(r, 'roll'), 4);
    assert.equal(R.landmarkPoints(r, 'good'), 2);
    assert.equal(R.landmarkPoints(r, 'bad'), -1);
  });
});

describe('board helpers', () => {
  it('tileDistribution: null = edition default, else fractions', () => {
    const C = config();
    assert.equal(R.tileDistribution(R.defaultRules(C)), null);
    const r = R.buildRules(C, { changes: { board: { tileMix: { action: 20, good_deed: 10, bad_deed: 0, landmark: 5, skip: 0 } } } });
    assert.deepEqual({ ...R.tileDistribution(r) }, { action: 0.2, good_deed: 0.1, bad_deed: 0, landmark: 0.05, skip: 0 });
  });

  it('tileCounts: questions fill the rest; landmarks capped by the edition', () => {
    const c = R.tileCounts({ action: 0.1, landmark: 0.5 }, 38, 6);
    assert.equal(c.action, 4);
    assert.equal(c.landmark, 6);
    assert.equal(c.question, 38 - 4 - 6);
  });

  const card = (id, ...effects) => ({ id, type: 'bad', text: `c${id}`,
    effects: effects.map(([effect, value]) => ({ effect, value, landmark: null })),
    effect: effects[0][0], value: effects[0][1] });

  it('noBackwards drops backward effects and cards with nothing left', () => {
    const rules = { board: { noBackwards: true, deedEffects: 'varied' } };
    const out = R.deedCardsForBoard([
      card(1, ['move_back', 2], ['score_remove', 1]),
      card(2, ['skip_turn', 0]),
      card(3, ['move_to_prev_landmark', 1]),
    ], rules);
    assert.deepEqual(out.map(c => c.id), [1]);
    assert.deepEqual(out[0].effects.map(e => e.effect), ['score_remove']);
    assert.equal(out[0].effect, 'score_remove');
  });

  it("deedEffects 'first' keeps only the first effect", () => {
    const out = R.deedCardsForBoard([card(1, ['score_add', 2], ['move_forward', 3])], { board: { deedEffects: 'first' } });
    assert.deepEqual(out[0].effects.map(e => e.effect), ['score_add']);
  });

  it('animation factor', () => {
    assert.equal(R.animationFactor({ turns: { animation: 'fast' } }), 0.5);
    assert.equal(R.animationFactor({ turns: { animation: 'normal' } }), 1);
  });
});

describe('summary and preset export', () => {
  it('summarizes the key rules', () => {
    const C = config();
    const parts = R.summarizeRules(R.buildRules(C, { preset: 'kids' }), C);
    assert.ok(parts.includes('Always easy'));
    assert.ok(parts.includes('No going backwards'));
  });

  it('exports a paste-ready RULE_PRESETS entry that rebuilds the same rules', () => {
    const C = config();
    const rules = R.buildRules(C, { preset: 'quiz', changes: { scoring: { landmarkRoll: 0 } } }, WITH_CARDS);
    const text = R.exportPreset(rules, C, WITH_CARDS, { id: 'test', label: 'Test' });
    assert.match(text, /^test: \{/);
    const entry = JSON.parse(text.replace(/^test: /, '').replace(/,$/, ''));
    C.RULE_PRESETS.test = entry;
    const again = R.buildRules(C, { preset: 'test', changes: {} }, WITH_CARDS);
    assert.deepEqual({ ...again, preset: 'quiz' }, rules);
  });
});
