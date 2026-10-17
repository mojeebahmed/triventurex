/**
 * test/board.test.js
 * Board generation (js/shared/board.js) — T3 property test: generate many
 * random boards for every path template of every edition and check that the
 * rules generateBoard promises always hold. Plus _resolveRelativeLandmark (T2).
 *
 * Loaded with the real edition config + deeds.csv, and the real ui.js
 * landmark resolution, so "tile label = where you actually go" is checked
 * against the code the game runs.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..');
const BOARDS_PER_TEMPLATE = 100;   // ~3,000 boards per run; raise locally to hunt rare bugs
// Every edition in the registry (game_editions/editions.js), so a new edition is tested automatically
const EDITIONS = (() => {
  const ctx = { window: {} };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'game_editions/editions.js'), 'utf8'), ctx);
  return ctx.window.TRIVENTUREX_EDITIONS.map(e => e.id);
})();
const ADJACENCY_RULED = new Set(['good_deed', 'bad_deed', 'action', 'landmark']);

/** Sandbox with config, board.js, ui.js and an edition's config + deeds loaded. */
function editionWorld(edition) {
  const ctx = { console, Math, document: { getElementById: () => null } };
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of ['js/shared/utils.js', 'js/shared/config.js', 'js/shared/csv.js', 'js/shared/rules.js',
                   'js/shared/board.js', 'js/shared/edition.js', 'js/host/edition-loader.js', 'js/host/ui.js']) {
    vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), ctx, { filename: f });
  }
  if (edition) {
    vm.runInContext(fs.readFileSync(path.join(ROOT, `game_editions/${edition}/config.js`), 'utf8'), ctx);
    vm.runInContext('_mergeEditionConfig()', ctx);
    ctx.__deeds = fs.readFileSync(path.join(ROOT, `game_editions/${edition}/deeds.csv`), 'utf8');
    vm.runInContext('window.DEEDS_DATA = _parseDeedsCSV(__deeds)', ctx);
  }
  return ctx;
}

/** Every rule generateBoard promises. Returns a list of violation messages. */
function boardViolations(ctx, b) {
  const out = [];
  const last = b.length - 1;

  // Path: ids in order, start/finish at the ends, contiguous, on the grid, no overlap
  if (b.some((s, i) => s.id !== i)) out.push('ids not 0..n-1');
  if (b[0].type !== 'start' || b[last].type !== 'finish') out.push('start/finish not at the ends');
  for (let i = 0; i < last; i++) {
    if (Math.abs(b[i + 1].row - b[i].row) + Math.abs(b[i + 1].col - b[i].col) !== 1) {
      out.push(`path jumps between ${i} and ${i + 1}`); break;
    }
  }
  if (new Set(b.map(s => `${s.row},${s.col}`)).size !== b.length) out.push('path overlaps itself');
  if (b.some(s => s.row < 0 || s.col < 0 || s.row >= b._gridRows || s.col >= b._gridCols)) out.push('space off the grid');

  // Layout: no two identical special spaces in a row; landmarks unique
  for (let i = 1; i < last - 1; i++) {
    if (ADJACENCY_RULED.has(b[i].type) && b[i].type === b[i + 1].type) out.push(`two ${b[i].type} in a row at ${i}`);
  }
  const lms = b.filter(s => s.type === 'landmark').map(s => s.name);
  if (new Set(lms).size !== lms.length) out.push('duplicate landmark');

  // Deeds: right card type, placement rules, label = actual target
  ctx._gameBoard = b; // what ui.js _resolveRelativeLandmark reads at runtime
  for (const s of b) {
    if (s.type !== 'good_deed' && s.type !== 'bad_deed') continue;
    if (!s.deed) { out.push(`deed space ${s.id} has no card`); continue; }
    if ((s.type === 'good_deed') !== (s.deed.type === 'good')) out.push(`deed type mismatch at ${s.id}`);
    if ((s.text || '').includes('{landmark}')) out.push(`deed tile ${s.id} shows a raw {landmark} placeholder`);
    const { effect, value } = s.deed;
    const n = Math.max(1, Math.round(value) || 1);
    if (effect === 'move_back' && s.id - n < 1) out.push(`move_back ${n} at ${s.id} reaches the start`);
    if (effect === 'move_forward' && s.id + n >= last) out.push(`move_forward ${n} at ${s.id} reaches the finish`);
    if (effect === 'move_to_next_landmark' || effect === 'move_to_prev_landmark') {
      const ahead  = b.filter(x => x.type === 'landmark' && x.id > s.id).length;
      const behind = b.filter(x => x.type === 'landmark' && x.id < s.id).length;
      if ((effect === 'move_to_next_landmark' ? ahead : behind) < n) out.push(`${effect} ${n} at ${s.id}: not enough landmarks`);
      const actual = ctx._resolveRelativeLandmark(effect, s.id, value)?.name ?? null;
      if (actual !== s.deed.resolvedLandmark) out.push(`${effect} at ${s.id}: tile says "${s.deed.resolvedLandmark}", player goes to "${actual}"`);
    }
  }
  return out;
}

for (const edition of EDITIONS) {
  describe(`generateBoard — ${edition} (property test)`, () => {
    const ctx = editionWorld(edition);
    const templates = vm.runInContext('CONFIG.PATH_TEMPLATES', ctx);

    for (const len of ['short', 'medium', 'long']) {
      for (const template of templates[len]) {
        it(`${len} / ${template.name}: ${BOARDS_PER_TEMPLATE} random boards keep every rule`, () => {
          ctx.__len = len; ctx.__t = template;
          const seen = new Map(); // violation → count (report distinct problems, not 100 copies)
          for (let k = 0; k < BOARDS_PER_TEMPLATE; k++) {
            for (const v of boardViolations(ctx, vm.runInContext('generateBoard(__len, __t)', ctx))) {
              const key = v.replace(/\d+/g, 'N');
              seen.set(key, (seen.get(key) || 0) + 1);
            }
          }
          assert.equal(seen.size, 0, [...seen].map(([v, c]) => `${c}× ${v}`).join('\n'));
        });
      }
    }
  });
}

// ── Rules variants (G12) ─────────────────────────────────────────────────────

const VARIANTS = {
  'questions only':      { board: { tileMix: { action: 0, good_deed: 0, bad_deed: 0, landmark: 0, skip: 0 } } },
  'more action':         { board: { tileMix: { action: 20, good_deed: 15, bad_deed: 10, landmark: 8, skip: 0 } } },
  'max special tiles':   { board: { tileMix: { action: 14, good_deed: 14, bad_deed: 14, landmark: 14, skip: 14 } } },
  'no going backwards':  { board: { noBackwards: true } },
  'first effect only':   { board: { deedEffects: 'first' } },
};

for (const edition of EDITIONS) {
  describe(`generateBoard under rules — ${edition}`, () => {
    const ctx = editionWorld(edition);
    for (const [name, changes] of Object.entries(VARIANTS)) {
      it(`${name}: every rule still holds, tile counts match the panel preview`, () => {
        ctx.__changes = changes;
        const rules = vm.runInContext('buildRules(CONFIG, { changes: __changes })', ctx);
        ctx.__rules = rules;
        const opts = vm.runInContext('({ tileMix: tileDistribution(__rules), deeds: deedCardsForBoard(window.DEEDS_DATA, __rules) })', ctx);
        ctx.__opts = opts;
        const originals = new Map(vm.runInContext('window.DEEDS_DATA', ctx).map(d => [d.id, d]));
        for (const len of ['short', 'medium', 'long']) {
          for (let k = 0; k < 40; k++) {
            ctx.__len = len;
            const b = vm.runInContext('generateBoard(__len, undefined, __opts)', ctx);
            const problems = boardViolations(ctx, b);
            assert.deepEqual(problems, [], `${len}: ${problems.join('; ')}`);

            // Tile counts: what the panel previews (tileCounts) is the most a type gets;
            // the adjacency rule may turn a few special tiles into questions.
            const middle = b.length - 2;
            const dist = opts.tileMix ?? vm.runInContext(`editionTileDistribution('${len}')`, ctx);
            const expected = ctx.tileCounts(dist, middle, vm.runInContext('CONFIG.LANDMARKS.length', ctx));
            const actual = {};
            for (const s of b.slice(1, -1)) actual[s.type] = (actual[s.type] || 0) + 1;
            for (const t of vm.runInContext("TILE_TYPES", ctx)) {
              assert.ok((actual[t] || 0) <= (expected[t] || 0), `${len}: ${t} ${actual[t]} > preview ${expected[t]}`);
            }

            const deeds = b.filter(s => s.deed).map(s => s.deed);
            if (name === 'questions only') assert.ok(b.slice(1, -1).every(s => s.type === 'question'));
            if (name === 'no going backwards') {
              for (const d of deeds) assert.ok(!vm.runInContext("BACKWARD_EFFECTS", ctx).has(d.effect), `backward effect ${d.effect}`);
            }
            if (name === 'first effect only') {
              for (const d of deeds) assert.equal(d.effect, originals.get(d.id).effects[0].effect);
            }
          }
        }
      });
    }
  });
}

describe('pathBounds (G9: the board is drawn only as big as its path)', () => {
  const ctx = editionWorld('football-quest');
  const templates = vm.runInContext('CONFIG.PATH_TEMPLATES', ctx);

  for (const len of ['short', 'medium', 'long']) {
    it(`${len}: every template's drawn grid is tight around the path`, () => {
      for (const template of templates[len]) {
        ctx.__len = len; ctx.__t = template;
        const b = vm.runInContext('generateBoard(__len, __t)', ctx);
        const { minRow, minCol, rows, cols } = ctx.pathBounds(b);
        const name = template.name;
        // every space inside the box …
        assert.ok(b.every(s => s.row >= minRow && s.row < minRow + rows &&
                               s.col >= minCol && s.col < minCol + cols), `${name}: space outside`);
        // … and the path touches all four edges (no empty border rows/columns)
        assert.ok(b.some(s => s.row === minRow) && b.some(s => s.row === minRow + rows - 1), `${name}: empty row`);
        assert.ok(b.some(s => s.col === minCol) && b.some(s => s.col === minCol + cols - 1), `${name}: empty column`);
      }
    });
  }
});

describe('_assignDeedsToSlots fallback', () => {
  const ctx = editionWorld(null);
  const card = (id, effects) => ({ id, type: 'good', text: `card ${id}`, effects,
                                   effect: effects[0].effect, value: effects[0].value });

  it('swaps in an unused card when a drawn card fits no free slot (short-board bug)', () => {
    // 10 middle spaces, the only good slot is 1 away from the finish:
    // move_forward 3 cannot go there; the spare score_add card can.
    const drawn = [card(1, [{ effect: 'move_forward', value: 3 }])];
    const spares = [card(2, [{ effect: 'score_add', value: 2 }])];
    ctx.__args = [drawn, [8], [], 10, spares];
    const assigned = vm.runInContext('_assignDeedsToSlots(...__args)', ctx);
    assert.equal(assigned.get(8).id, 2);
    assert.equal(assigned.get(8).effect, 'score_add');
    assert.equal(spares.length, 0, 'the spare card is used up');
  });

  it('prefers another effect on the same card over a spare card', () => {
    const drawn = [card(1, [{ effect: 'move_forward', value: 3 }, { effect: 'score_add', value: 1 }])];
    const spares = [card(2, [{ effect: 'score_add', value: 2 }])];
    ctx.__args = [drawn, [8], [], 10, spares];
    const assigned = vm.runInContext('_assignDeedsToSlots(...__args)', ctx);
    assert.equal(assigned.get(8).id, 1);
    assert.equal(assigned.get(8).effect, 'score_add');
    assert.equal(spares.length, 1);
  });

  it('only breaks a rule when no card in the deck fits (last resort)', () => {
    const drawn = [card(1, [{ effect: 'move_forward', value: 3 }])];
    ctx.__args = [drawn, [8], [], 10, []];
    const assigned = vm.runInContext('_assignDeedsToSlots(...__args)', ctx);
    assert.equal(assigned.get(8).effect, 'move_forward');
  });
});

describe('_resolveRelativeLandmark (T2)', () => {
  const ctx = editionWorld(null);
  ctx._gameBoard = [
    { id: 0, type: 'start' }, { id: 1, type: 'landmark', name: 'A' }, { id: 2, type: 'question' },
    { id: 3, type: 'landmark', name: 'B' }, { id: 4, type: 'question' }, { id: 5, type: 'landmark', name: 'C' },
    { id: 6, type: 'finish' },
  ];
  const r = (effect, pos, n) => ctx._resolveRelativeLandmark(effect, pos, n)?.name ?? null;

  it('finds the nth landmark ahead', () => {
    assert.equal(r('move_to_next_landmark', 2, 1), 'B');
    assert.equal(r('move_to_next_landmark', 2, 2), 'C');
  });

  it('finds the nth landmark behind', () => {
    assert.equal(r('move_to_prev_landmark', 4, 1), 'B');
    assert.equal(r('move_to_prev_landmark', 4, 2), 'A');
  });

  it('falls back to the furthest landmark when there are fewer than n', () => {
    assert.equal(r('move_to_next_landmark', 2, 5), 'C');
    assert.equal(r('move_to_prev_landmark', 4, 5), 'A');
  });

  it('returns null when there is no landmark in that direction', () => {
    assert.equal(r('move_to_next_landmark', 5, 1), null);
    assert.equal(r('move_to_prev_landmark', 1, 1), null);
  });
});

describe('fillLandmarkText', () => {
  it('fills {landmark} with the target, or "a <landmark label>" in the edition\'s words', () => {
    const ctx = editionWorld('world-tour');
    assert.equal(ctx.fillLandmarkText('Off to {landmark}!', 'Petra — Jordan'), 'Off to Petra — Jordan!');
    assert.equal(ctx.fillLandmarkText('Back to {landmark}.', null), 'Back to a wonder.');
    assert.equal(ctx.fillLandmarkText('No placeholder', null), 'No placeholder');
  });
});
