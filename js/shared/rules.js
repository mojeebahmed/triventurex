/**
 * rules.js
 * Per-game rules (G12). Pure — no DOM. Unit-tested in test/rules.test.js.
 *
 * A game's rules are built in three layers:
 *   defaults (engine CONFIG + the active edition)  →  a preset (CONFIG.RULE_PRESETS)
 *   →  the player's own changes in the rules panel
 * The result is copied into state.rules when a game starts and saved with it,
 * so a resumed game keeps its rules. Only the layers are stored per edition
 * ({ preset, changes }), so a default changed in code later still applies to
 * settings nobody touched.
 */

const TILE_TYPES = ['action', 'good_deed', 'bad_deed', 'landmark', 'skip'];

// Special tiles can't exceed this share of the board: the "no two identical
// special tiles in a row" rule would turn the surplus into questions anyway.
const MAX_SPECIAL_PERCENT = 70;

// Named tile mixes for the rules panel (percent of the middle spaces;
// questions fill the rest). `balanced` = the edition's own mix for the length.
const TILE_MIX_PRESETS = {
  balanced:      { label: 'Balanced (edition default)', mix: null },
  moreQuestions: { label: 'More questions', mix: { action: 8,  good_deed: 8,  bad_deed: 8,  landmark: 6, skip: 3 } },
  moreAction:    { label: 'More action',    mix: { action: 20, good_deed: 15, bad_deed: 10, landmark: 8, skip: 0 } },
  questionsOnly: { label: 'Questions only', mix: { action: 0,  good_deed: 0,  bad_deed: 0,  landmark: 0, skip: 0 } },
};

// Finish bonus choices; 'standard' = the edition's / engine's FINISH_BONUS
const FINISH_BONUS_CHOICES = {
  small: [5, 3, 2, 1],
  off:   [],
};

// Deed effects removed by "No going backwards"
const BACKWARD_EFFECTS = new Set(['move_back', 'move_to_prev_landmark', 'move_to_landmark', 'skip_turn']);

/**
 * Today's behaviour, from the engine config merged with the active edition.
 * @param {Object} config           CONFIG (after the edition was merged in)
 * @param {Object} [opts]
 * @param {boolean} [opts.hasActionCards]  edition ships actions.csv
 */
function defaultRules(config, { hasActionCards = false } = {}) {
  const sv = config.SCORE_VALUES || {};
  return {
    preset: 'family',
    scoring: {
      questionEasy:     sv.question_easy    ?? 1,
      questionHard:     sv.question_hard    ?? 2,
      actionPerformer:  sv.action_performer ?? 1,
      actionGuesser:    sv.action_guesser   ?? 1,
      finishBonus:      'standard',
      landmarkRoll:     sv.landmark ?? 5,
      landmarkGoodDeed: 0,
      landmarkBadDeed:  0,
      negativeScores:   false,
    },
    questions: {
      difficulty:   'choose',     // 'choose' | 'easy' | 'hard'
      timerAuto:    false,
      timerSeconds: config.TIMER?.question ?? 30,
      tracking:     config.RULES?.questionTracking ?? 'session',
      answerOnPhone: true,        // network games: multiple choice answered + scored on the phone (G3)
    },
    actions: {
      cards:        hasActionCards ? 'digital' : 'physical',
      kinds:        Object.keys(config.ACTION_KINDS || { act: 1, explain: 1, sound: 1 }),
      timerSeconds: config.TIMER?.action ?? 90,
    },
    board: {
      tileMix:     null,          // null = edition default for the length, else { type: percent }
      deedEffects: 'varied',      // 'varied' (random effect per game) | 'first'
      noBackwards: false,
    },
    turns: {
      exactFinish: config.RULES?.exactFinish ?? true,
      whoStarts:   'order',       // 'order' | 'random'
      animation:   'normal',      // 'normal' | 'fast'
    },
  };
}

const _isObj = v => v && typeof v === 'object' && !Array.isArray(v);

/** Deep merge: objects merge, everything else (incl. arrays, null) replaces. */
function mergeRules(base, changes) {
  const out = { ...base };
  for (const [k, v] of Object.entries(changes || {})) {
    out[k] = (_isObj(v) && _isObj(base[k])) ? mergeRules(base[k], v) : (_isObj(v) ? { ...v } : (Array.isArray(v) ? [...v] : v));
  }
  return out;
}

/** The leaves of `rules` that differ from `base`, as a nested object ({} if none). */
function diffRules(rules, base) {
  const out = {};
  for (const [k, v] of Object.entries(rules || {})) {
    if (k === 'preset') continue;
    const b = base?.[k];
    if (_isObj(v) && _isObj(b) && k !== 'tileMix') {
      const d = diffRules(v, b);
      if (Object.keys(d).length) out[k] = d;
    } else if (JSON.stringify(v) !== JSON.stringify(b)) {
      out[k] = Array.isArray(v) ? [...v] : (_isObj(v) ? { ...v } : v);
    }
  }
  return out;
}

/** Number of changed settings in a diff. */
function countChanges(diff) {
  return Object.entries(diff || {}).reduce((n, [k, v]) =>
    n + (_isObj(v) && k !== 'tileMix' ? countChanges(v) : 1), 0);
}

const _clampInt = (v, lo, hi, fallback) => {
  const n = Math.round(Number(v));
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : fallback;
};

/**
 * Keep a tile mix within bounds: whole percents 0–100 per type and at most
 * MAX_SPECIAL_PERCENT in total (scaled down proportionally).
 * Returns { mix, capped } — capped = true if it had to be scaled.
 */
function normalizeTileMix(mix) {
  if (!mix) return { mix: null, capped: false };
  const out = {};
  for (const t of TILE_TYPES) out[t] = _clampInt(mix[t], 0, 100, 0);
  const total = TILE_TYPES.reduce((s, t) => s + out[t], 0);
  if (total <= MAX_SPECIAL_PERCENT) return { mix: out, capped: false };
  const f = MAX_SPECIAL_PERCENT / total;
  for (const t of TILE_TYPES) out[t] = Math.floor(out[t] * f);
  return { mix: out, capped: true };
}

/** Clamp every value into a playable range. Returns a new object. */
function normalizeRules(rules, { hasActionCards = false, actionKinds = ['act', 'explain', 'sound'] } = {}) {
  const r = mergeRules(rules, {});
  const s = r.scoring;
  for (const k of ['questionEasy', 'questionHard', 'actionPerformer', 'actionGuesser',
                   'landmarkRoll', 'landmarkGoodDeed', 'landmarkBadDeed']) {
    s[k] = _clampInt(s[k], -50, 50, 0);
  }
  if (!['standard', 'small', 'off'].includes(s.finishBonus)) s.finishBonus = 'standard';
  s.negativeScores = !!s.negativeScores;

  const q = r.questions;
  if (!['choose', 'easy', 'hard'].includes(q.difficulty)) q.difficulty = 'choose';
  q.timerAuto = !!q.timerAuto;
  q.timerSeconds = _clampInt(q.timerSeconds, 5, 600, 30);
  if (!['session', 'game'].includes(q.tracking)) q.tracking = 'session';
  q.answerOnPhone = q.answerOnPhone !== false;

  const a = r.actions;
  if (!hasActionCards || !['digital', 'physical'].includes(a.cards)) a.cards = hasActionCards ? (a.cards === 'physical' ? 'physical' : 'digital') : 'physical';
  a.kinds = (a.kinds || []).filter(k => actionKinds.includes(k));
  if (!a.kinds.length) a.kinds = [...actionKinds];
  a.timerSeconds = _clampInt(a.timerSeconds, 5, 600, 90);

  const b = r.board;
  b.tileMix = normalizeTileMix(b.tileMix).mix;
  if (!['varied', 'first'].includes(b.deedEffects)) b.deedEffects = 'varied';
  b.noBackwards = !!b.noBackwards;

  const t = r.turns;
  t.exactFinish = !!t.exactFinish;
  if (!['order', 'random'].includes(t.whoStarts)) t.whoStarts = 'order';
  if (!['normal', 'fast'].includes(t.animation)) t.animation = 'normal';
  return r;
}

/**
 * Build the rules for a game: defaults → preset → changes, normalized.
 * @param {Object} config      CONFIG (with RULE_PRESETS and the edition merged)
 * @param {Object} stored      { preset, changes } as saved per edition (or null)
 * @param {Object} [opts]      { hasActionCards }
 */
function buildRules(config, stored, opts = {}) {
  const defaults = defaultRules(config, opts);
  const presetId = config.RULE_PRESETS?.[stored?.preset] ? stored.preset : 'family';
  const withPreset = mergeRules(defaults, config.RULE_PRESETS?.[presetId]?.changes || {});
  const rules = normalizeRules(mergeRules(withPreset, stored?.changes || {}), {
    hasActionCards: opts.hasActionCards, actionKinds: Object.keys(config.ACTION_KINDS || {}),
  });
  rules.preset = presetId;
  return rules;
}

/** The rules a preset gives before any personal change (for "N changed"). */
function presetBase(config, presetId, opts = {}) {
  return buildRules(config, { preset: presetId, changes: {} }, opts);
}

/** Finish bonus for the nth player to finish (1-based). */
function finishBonusFor(rules, config, order) {
  const choice = rules?.scoring?.finishBonus ?? 'standard';
  const list = choice === 'standard' ? (config.FINISH_BONUS || []) : (FINISH_BONUS_CHOICES[choice] || []);
  if (choice === 'standard') return list[order - 1] ?? 1;   // engine behaviour: at least 1
  return list[order - 1] ?? 0;
}

/** The finish bonus list shown in the panel / summary. */
function finishBonusList(rules, config) {
  const choice = rules?.scoring?.finishBonus ?? 'standard';
  return choice === 'standard' ? [...(config.FINISH_BONUS || [])] : [...(FINISH_BONUS_CHOICES[choice] || [])];
}

/** Landmark points by how the player got there: 'roll' | 'good' | 'bad'. */
function landmarkPoints(rules, how) {
  const s = rules?.scoring || {};
  return how === 'good' ? (s.landmarkGoodDeed ?? 0)
       : how === 'bad'  ? (s.landmarkBadDeed  ?? 0)
       : (s.landmarkRoll ?? 5);
}

/** The tile mix as fractions for generateBoard, or null for the edition default. */
function tileDistribution(rules) {
  const mix = rules?.board?.tileMix;
  if (!mix) return null;
  return Object.fromEntries(TILE_TYPES.map(t => [t, (mix[t] || 0) / 100]));
}

/**
 * How many tiles of each type a board gets — THE counting rule, used by
 * generateBoard and by the rules panel preview so they always agree.
 * @param {Object} dist           fractions per tile type (questions ignored)
 * @param {number} middleCount    spaces between start and finish
 * @param {number} landmarkCount  landmarks the edition has (caps landmark tiles)
 */
function tileCounts(dist, middleCount, landmarkCount = Infinity) {
  const counts = {};
  for (const [t, r] of Object.entries(dist || {})) {
    if (t !== 'question') counts[t] = Math.max(0, Math.round(r * middleCount));
  }
  if ('landmark' in counts) counts.landmark = Math.min(landmarkCount, counts.landmark);
  const special = Object.values(counts).reduce((s, c) => s + c, 0);
  counts.question = Math.max(0, middleCount - special);
  return counts;
}

/**
 * Prepare deed cards for a board under these rules:
 *   - noBackwards: drop backward effects; cards left with none are skipped
 *   - deedEffects 'first': keep only the card's first (remaining) effect
 */
function deedCardsForBoard(cards, rules) {
  const noBack = !!rules?.board?.noBackwards;
  const firstOnly = rules?.board?.deedEffects === 'first';
  const out = [];
  for (const card of cards || []) {
    let effects = card.effects?.length ? card.effects : [{ effect: card.effect, value: card.value ?? 0, landmark: card.landmark ?? null }];
    if (noBack) effects = effects.filter(e => !BACKWARD_EFFECTS.has(e.effect));
    if (!effects.length) continue;
    if (firstOnly) effects = [effects[0]];
    out.push({ ...card, effects, effect: effects[0].effect, value: effects[0].value, landmark: effects[0].landmark ?? null });
  }
  return out;
}

/** 1 for normal animation speed, 0.5 for fast. */
function animationFactor(rules) {
  return rules?.turns?.animation === 'fast' ? 0.5 : 1;
}

/** Short phrases for the setup screen summary line. */
function summarizeRules(rules, config) {
  const s = rules.scoring;
  const pts = config.GAME?.pointsName ?? 'pts';
  const bonus = finishBonusList(rules, config);
  const parts = [
    `Questions ${s.questionEasy}/${s.questionHard}`,
    rules.turns.exactFinish ? 'Exact finish' : 'Any roll finishes',
    s.landmarkRoll ? `Landmark ${s.landmarkRoll > 0 ? '+' : ''}${s.landmarkRoll} ${pts}` : 'Landmarks: info only',
    bonus.length ? `Finish bonus ${bonus.slice(0, 3).join('/')}${bonus.length > 3 ? '…' : ''}` : 'No finish bonus',
  ];
  if (rules.questions.difficulty !== 'choose') parts.push(`Always ${rules.questions.difficulty}`);
  if (rules.board.noBackwards) parts.push('No going backwards');
  if (rules.turns.animation === 'fast') parts.push('Fast');
  return parts;
}

/**
 * A preset entry for config.js RULE_PRESETS from the current rules: only the
 * values that differ from the plain defaults.
 */
function exportPreset(rules, config, opts = {}, { id = 'myPreset', label = 'My preset', description = '' } = {}) {
  const changes = diffRules(rules, defaultRules(config, opts));
  return `${id}: ${JSON.stringify({ label, description, changes }, null, 2)},`;
}

if (typeof module !== 'undefined') {
  module.exports = {
    TILE_TYPES, MAX_SPECIAL_PERCENT, TILE_MIX_PRESETS, FINISH_BONUS_CHOICES, BACKWARD_EFFECTS,
    defaultRules, mergeRules, diffRules, countChanges, normalizeTileMix, normalizeRules,
    buildRules, presetBase, finishBonusFor, finishBonusList, landmarkPoints, tileDistribution,
    tileCounts, deedCardsForBoard, animationFactor, summarizeRules, exportPreset,
  };
}
