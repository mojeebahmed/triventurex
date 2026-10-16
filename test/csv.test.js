/**
 * test/csv.test.js
 * Unit tests for js/csv.js, plus content checks on every edition's CSV files:
 * the CSV must parse to exactly what the generated questions.js holds, and
 * every row must be valid (catches unquoted commas shifting columns — see B18).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { _csvSplit, _parseCSV, _parseQuestionsCSV, _parseDeedsCSV } = require('../js/csv.js');

const EDITIONS_DIR = path.join(__dirname, '../game_editions');
const EDITIONS = fs.readdirSync(EDITIONS_DIR)
  .filter(d => fs.existsSync(path.join(EDITIONS_DIR, d, 'questions.csv')));
const EFFECTS = new Set(['score_add', 'score_remove', 'move_forward', 'move_back',
  'move_to_prev_landmark', 'move_to_next_landmark', 'move_to_landmark', 'skip_turn',
  'extra_turn', 'all_players_gain', 'all_players_lose', 'protection']);

const read = (ed, file) => fs.readFileSync(path.join(EDITIONS_DIR, ed, file), 'utf8');
const quiet = fn => { const w = console.warn; console.warn = () => {}; try { return fn(); } finally { console.warn = w; } };

describe('_csvSplit', () => {
  it('splits plain fields', () => assert.deepEqual(_csvSplit('a,b,c'), ['a', 'b', 'c']));
  it('keeps commas inside quotes', () => assert.deepEqual(_csvSplit('1,"Madrid, Spain",x'), ['1', 'Madrid, Spain', 'x']));
  it('unescapes doubled quotes', () => assert.deepEqual(_csvSplit('"say ""hi""",b'), ['say "hi"', 'b']));
  it('keeps empty fields', () => assert.deepEqual(_csvSplit('a,,c,'), ['a', '', 'c', '']));
});

describe('_parseCSV', () => {
  it('keys rows by normalised header and skips blank lines', () => {
    const rows = _parseCSV('Question,Sub Category\r\nQ1,X\n\nQ2,Y\n');
    assert.equal(rows.length, 2);
    assert.deepEqual({ ...rows[0] }, { question: 'Q1', sub_category: 'X' });
  });
});

describe('_parseQuestionsCSV', () => {
  const HDR = 'id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note\n';

  it('turns a multi answer number into a letter', () => {
    const [q] = _parseQuestionsCSV(HDR + '7,Q?,multi,2,A1,B1,C1,,hard,cat,sub,top,n\n');
    assert.equal(q.id, 7);
    assert.equal(q.answer, 'B');
    assert.deepEqual([...q.opts], ['A1', 'B1', 'C1']);
    assert.equal(q.diff, 'hard');
  });

  it('keeps an open answer as text with no options', () => {
    const [q] = _parseQuestionsCSV(HDR + '1,Q?,open,"Madrid, Spain",,,,,easy,c,,,\n');
    assert.equal(q.answer, 'Madrid, Spain');
    assert.equal(q.opts.length, 0);
  });

  it('falls back to row position when there is no id column', () => {
    const qs = quiet(() => _parseQuestionsCSV('question,type,answer\nQ1,open,A\nQ2,open,B\n'));
    assert.deepEqual(qs.map(q => q.id), [1, 2]);
  });
});

describe('_parseDeedsCSV', () => {
  it('collects up to 3 alternative effects', () => {
    const [d] = _parseDeedsCSV('type,text,effect,value,landmark,effect_2,value_2,landmark_2,effect_3,value_3,landmark_3,mood\n'
      + 'good,Helped,score_add,2,,move_forward,3,,,,,kind\n');
    assert.equal(d.effects.length, 2);
    assert.equal(d.effect, 'score_add');
    assert.equal(d.effects[1].value, 3);
  });
});

for (const ed of EDITIONS) {
  describe(`edition content: ${ed}`, () => {
    const questions = _parseQuestionsCSV(read(ed, 'questions.csv'));

    it('questions.csv parses to exactly what questions.js holds', () => {
      const jsFile = path.join(EDITIONS_DIR, ed, 'questions.js');
      if (!fs.existsSync(jsFile)) return;
      const ctx = { window: {} };
      vm.createContext(ctx);
      vm.runInContext(fs.readFileSync(jsFile, 'utf8'), ctx);
      const plain = x => JSON.parse(JSON.stringify(x));
      assert.deepEqual(plain(questions), plain(ctx.window.QUESTIONS_DATA),
        'CSV and generated JS differ — regenerate questions.js');
    });

    it('every question has a unique id, valid difficulty, and a valid answer', () => {
      const ids = new Set();
      for (const q of questions) {
        const where = `question id ${q.id}`;
        assert.ok(!ids.has(q.id), `${where}: duplicate id`); ids.add(q.id);
        assert.ok(['easy', 'hard'].includes(q.diff), `${where}: difficulty "${q.diff}" (unquoted comma?)`);
        if (q.opts.length) {
          assert.ok('ABCD'.slice(0, q.opts.length).includes(q.answer), `${where}: answer ${q.answer} not an option`);
        } else {
          assert.ok(q.answer && q.answer !== 'open' && q.answer !== 'multi', `${where}: open answer "${q.answer}"`);
        }
      }
    });

    it('every deed has a valid type, known effects and numeric values', () => {
      if (!fs.existsSync(path.join(EDITIONS_DIR, ed, 'deeds.csv'))) return;
      for (const d of _parseDeedsCSV(read(ed, 'deeds.csv'))) {
        assert.ok(['good', 'bad'].includes(d.type), `deed ${d.id}: type "${d.type}"`);
        for (const e of d.effects) {
          assert.ok(EFFECTS.has(e.effect), `deed ${d.id}: unknown effect "${e.effect}"`);
          assert.ok(Number.isFinite(e.value), `deed ${d.id}: value not a number`);
        }
      }
    });
  });
}
