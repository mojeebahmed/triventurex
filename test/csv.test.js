/**
 * test/csv.test.js
 * Unit tests for js/shared/csv.js and the content checker (scripts/content.js),
 * plus every edition in the repo: no content errors, and the generated
 * questions.js / deeds.js must match the CSVs.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { _csvSplit, _parseCSV, _parseQuestionsCSV, _parseDeedsCSV } = require('../js/shared/csv.js');

const { listEditions, loadEdition, makeEdition, checkEdition, generateEditionJs } = require('../scripts/content.js');

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

// ── Content checker (scripts/content.js) ─────────────────────────────────────

const QH = 'id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note\n';
const DH = 'type,text,effect,value,landmark,effect_2,value_2,landmark_2,effect_3,value_3,landmark_3,mood\n';
const check = parts => checkEdition(makeEdition(parts));
const messages = list => list.map(p => `${p.file}:${p.line} ${p.message}`).join('\n');

describe('content checker', () => {
  it('accepts valid content', () => {
    const r = check({ questionsCsv: QH + '1,Q?,multi,2,A,B,,,easy,c,s,t,\n2,Q2?,open,"Madrid, Spain",,,,,hard,c,s,t,\n',
                      deedsCsv: DH + 'good,Nice.,score_add,2,,,,,,,,kind\n' });
    assert.deepEqual(r.errors, []);
    assert.deepEqual(r.warnings, []);
  });

  it('catches the B18 broken row (unquoted commas that still give 13 columns)', () => {
    // Real row from football-quest before the fix
    const row = '35,If a match is 0–0 after 90 minutes in a knockout tie,what happens next?,open,Extra time (30 minutes),then a penalty shootout if still level,,,,,,,easy\n';
    const r = check({ questionsCsv: QH + row });
    assert.match(messages(r.errors), /questions\.csv:2 type "open" must be multi or open|difficulty "" must be easy or hard/);
  });

  it('reports a wrong column count with the line number', () => {
    const r = check({ questionsCsv: QH + '1,Q?,open,Madrid, Spain,,,,,easy,c,s,t,\n' });
    assert.match(messages(r.errors), /questions\.csv:2 14 columns, expected 13/);
  });

  it('reports duplicate and non-numeric ids', () => {
    const r = check({ questionsCsv: QH + '4,A?,open,a,,,,,easy,c,s,t,\n4,B?,open,b,,,,,easy,c,s,t,\nx,C?,open,c,,,,,easy,c,s,t,\n' });
    assert.match(messages(r.errors), /:3 duplicate id 4 \(also on line 2\)/);
    assert.match(messages(r.errors), /:4 id "x" must be a whole number/);
  });

  it('reports a multi answer that points at an empty option', () => {
    const r = check({ questionsCsv: QH + '1,Q?,multi,3,A,B,,,easy,c,s,t,\n' });
    assert.match(messages(r.errors), /answer 3 points at an empty option/);
  });

  it('warns about a question without a topic when others have one', () => {
    const r = check({ questionsCsv: QH + '1,A?,open,a,,,,,easy,c,s,t,\n2,B?,open,b,,,,,easy,c,s,,\n' });
    assert.equal(r.errors.length, 0);
    assert.match(messages(r.warnings), /questions\.csv:3 no topic/);
  });

  it('reports unknown deed effects and types', () => {
    const r = check({ deedsCsv: DH + 'great,Text.,sawab_add,2,,,,,,,,\n' });
    assert.match(messages(r.errors), /type "great" must be good or bad/);
    assert.match(messages(r.errors), /unknown effect "sawab_add"/);
  });

  it('checks landmark effects against config.js LANDMARKS', () => {
    const config = { LANDMARKS: [{ name: 'Old Mill' }, { name: 'Bridge' }] };
    const r = check({ config, deedsCsv: DH
      + 'bad,Go to the mill.,move_to_landmark,0,Old Mill,,,,,,,\n'
      + 'bad,Go to the tower.,move_to_landmark,0,Tower,,,,,,,\n'
      + 'good,Run to {landmark}!,move_to_next_landmark,5,,,,,,,,\n'
      + 'good,Visit {landmark}.,score_add,1,,,,,,,,\n' });
    assert.match(messages(r.errors), /deeds\.csv:3 landmark "Tower" is not in config\.js LANDMARKS/);
    assert.match(messages(r.warnings), /deeds\.csv:4 move_to_next_landmark 5, but the edition only has 2 landmarks/);
    assert.match(messages(r.warnings), /deeds\.csv:5 text uses \{landmark\}/);
    assert.doesNotMatch(messages(r.errors), /:2 /, 'the valid landmark row is fine');
  });

  it('reports relative landmark effects in an edition without landmarks', () => {
    const r = check({ deedsCsv: DH + 'good,Go.,move_to_next_landmark,1,,,,,,,,\n' });
    assert.match(messages(r.errors), /needs LANDMARKS in config\.js/);
  });
});

// ── Every edition in the repo ─────────────────────────────────────────────────

for (const id of listEditions()) {
  describe(`edition content: ${id}`, () => {
    const ed = loadEdition(id);

    it('passes the content checker (no errors)', () => {
      const { errors } = checkEdition(ed);
      assert.equal(errors.length, 0, '\n' + messages(errors));
    });

    it('generated questions.js / deeds.js are up to date (run: npm run build:content)', () => {
      for (const [file, text] of Object.entries(generateEditionJs(ed))) {
        const current = fs.readFileSync(path.join(ed.dir, file), 'utf8');
        assert.equal(current, text, `${id}/${file} is out of date — run: npm run build:content ${id}`);
      }
    });
  });
}
