/**
 * test/questions.test.js
 * js/shared/questions.js — question explorer tree / filter and the marked
 * questions report (G14 + G19).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { questionTree, filterQuestions, answerLabel, markedReport, topicKey, selectedTopicKeys, checkLabel, checkedCount } = require('../js/shared/questions.js');

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
  it('by check (Question Validator): checked / not checked', () => {
    const withCheck = Q.map(q => (q.id === 2 ? { ...q, check: { status: 'confirmed', sources: [] } } : q));
    const got = c => filterQuestions(withCheck, { checked: c }).map(q => q.id);
    assert.deepEqual(got('yes'), [2]);
    assert.deepEqual(got('no'), [1, 3, 4]);
    assert.deepEqual(got('all'), [1, 2, 3, 4]);
    assert.equal(checkedCount(withCheck), 1);
    assert.equal(checkLabel(withCheck[1]), 'Confirmed by a reviewer');
    assert.equal(checkLabel(Q[0]), '');
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

describe('tags', () => {
  const { tagCounts, toggleTag, knownTags } = require('../js/shared/questions.js');
  const Q = [
    { id: 1, q: 'Longest river?', opts: [], answer: 'Nile', diff: 'easy', cat: 'Geo', tags: ['records', 'water'] },
    { id: 2, q: 'Biggest cat?', opts: [], answer: 'Tiger', diff: 'hard', cat: 'Animals', tags: ['records'] },
    { id: 3, q: 'Capital of Peru?', opts: [], answer: 'Lima', diff: 'easy', cat: 'Geo' },
  ];

  it('filters by tags: a question needs every chosen tag; no tags = everything', () => {
    assert.deepEqual(filterQuestions(Q, { tags: ['records'] }).map(q => q.id), [1, 2]);
    assert.deepEqual(filterQuestions(Q, { tags: ['records', 'water'] }).map(q => q.id), [1]);
    assert.deepEqual(filterQuestions(Q, { tags: [] }).map(q => q.id), [1, 2, 3]);
    assert.deepEqual(filterQuestions(Q, { tags: ['records'], diff: 'easy' }).map(q => q.id), [1]);
  });
  it('search finds tag words too', () => {
    assert.deepEqual(filterQuestions(Q, { text: 'water' }).map(q => q.id), [1]);
  });
  it('counts tags, most used first; toggles and drops unknown tags', () => {
    assert.deepEqual(tagCounts(Q), [{ tag: 'records', count: 2 }, { tag: 'water', count: 1 }]);
    assert.deepEqual(tagCounts([]), []);
    assert.deepEqual(toggleTag(['a'], 'b'), ['a', 'b']);
    assert.deepEqual(toggleTag(['a', 'b'], 'a'), ['b']);
    assert.deepEqual(knownTags(['water', 'gone'], Q), ['water']);
  });
});

describe('question HTML (tags, About this answer)', () => {
  // Page helpers: stub icon() and use the real esc()
  if (typeof global.esc !== 'function') {
    require('node:vm').runInThisContext(require('node:fs').readFileSync(require('node:path').join(__dirname, '../js/shared/utils.js'), 'utf8'));
  }
  global.icon ??= name => `[${name}]`;
  const { tagFilterHtml, questionTagsHtml, questionInfoHtml } = require('../js/shared/questions.js');
  const q = { id: 7, q: 'Longest river?', opts: [], answer: 'Nile', diff: 'easy', cat: 'Geo', subcat: '', topic: '', note: 'It flows north.',
    tags: ['water', '<b>x'],
    check: { status: 'verified', on: '2026-11-16', how: 'Checked', asOf: '', quote: 'Nile <script>',
      sources: [{ name: 'Good <i>site</i>', url: 'https://example.org/nile' }, { name: 'Bad', url: 'javascript:alert(1)' }] } };

  it('tag chips escape the tag and mark the chosen ones', () => {
    const html = tagFilterHtml([{ tag: 'water', count: 2 }, { tag: '<b>x', count: 1 }], ['water'], [{ tag: 'water', count: 2 }]);
    assert.match(html, /class="tag-chip on" data-tag="water" aria-pressed="true"/);
    assert.match(html, /&lt;b&gt;x <small>0<\/small>/);
    assert.match(html, /disabled/);          // nothing left with that tag
    assert.doesNotMatch(html, /<b>x/);
    assert.equal(tagFilterHtml([], []), '');
    assert.doesNotMatch(questionTagsHtml(q), /<b>x/);
    assert.equal(questionTagsHtml({ id: 1 }), '');
  });
  it('About this answer: escapes web text, links only http(s), says when not checked', () => {
    const html = questionInfoHtml(q);
    assert.match(html, /href="https:\/\/example.org\/nile"/);
    assert.doesNotMatch(html, /javascript:/);
    assert.doesNotMatch(html, /<script>|<i>site/);
    assert.match(html, /It flows north\./);
    assert.match(html, /Geo/);
    const plain = questionInfoHtml({ ...q, check: undefined });
    assert.match(plain, /Not checked against sources yet/);
    assert.equal(questionInfoHtml(null), '');
  });
});

describe('several branches and any / all tags', () => {
  const { togglePath, pathChosen, pathOpen, pathsLabel, tagChipCounts, tagModeHtml } = require('../js/shared/questions.js');
  const ids = opts => filterQuestions(Q, opts).map(q => q.id);
  const T = [
    { id: 1, cat: 'Geo', tags: ['records', 'water'] },
    { id: 2, cat: 'Animals', tags: ['records'] },
    { id: 3, cat: 'Geo', tags: ['food'] },
    { id: 4, cat: 'Geo' },
  ];
  const tids = opts => filterQuestions(T, opts).map(q => q.id);

  it('a question in ANY chosen branch matches; no branch = all; `path` still works', () => {
    assert.deepEqual(ids({ paths: [['Geo', 'Africa'], ['history']] }), [2, 3]);
    assert.deepEqual(ids({ paths: [['Geo', 'Europe', 'Capitals'], ['Geo', 'Africa', 'Rivers']] }), [1, 2, 4]);
    assert.deepEqual(ids({ paths: [] }), [1, 2, 3, 4]);
    assert.deepEqual(ids({ path: ['history'] }), [3]);
  });
  it('choosing a branch replaces the ones it contains or sits in; again = take it back; [] = all', () => {
    let p = togglePath([], ['Geo']);
    assert.deepEqual(p, [['Geo']]);
    p = togglePath(p, ['Geo', 'Europe']);                       // narrows down
    assert.deepEqual(p, [['Geo', 'Europe']]);
    p = togglePath(p, ['history']);
    assert.deepEqual(p, [['Geo', 'Europe'], ['history']]);
    assert.ok(pathChosen(p, ['history']) && !pathChosen(p, ['Geo']));
    assert.ok(pathOpen(p, ['Geo']) && pathOpen(p, ['Geo', 'Europe']) && !pathOpen(p, ['Geo', 'Africa']));
    assert.deepEqual(togglePath(p, ['Geo']), [['history'], ['Geo']]);   // widens again
    assert.deepEqual(togglePath(p, ['history']), [['Geo', 'Europe']]);
    assert.deepEqual(togglePath(p, []), []);
    assert.equal(pathsLabel(p), 'Geo › Europe + history');
    assert.equal(pathsLabel([], undefined, 'All'), 'All');
    assert.equal(pathsLabel([['']]), 'Other');
  });
  it("tags: 'any' = at least one chosen tag, 'all' = every one (the default)", () => {
    assert.deepEqual(tids({ tags: ['water', 'food'], tagMode: 'any' }), [1, 3]);
    assert.deepEqual(tids({ tags: ['water', 'food'], tagMode: 'all' }), []);
    assert.deepEqual(tids({ tags: ['water', 'food'] }), []);
    assert.deepEqual(tids({ tags: ['records'], tagMode: 'any', paths: [['Geo']] }), [1]);
  });
  it("chip counts: 'any' counts from the other filters, 'all' from what is left", () => {
    const f = { tags: ['water'], paths: [['Geo']] };
    assert.deepEqual(tagChipCounts(T, f, 'any'), [{ tag: 'food', count: 1 }, { tag: 'records', count: 1 }, { tag: 'water', count: 1 }]);
    assert.deepEqual(tagChipCounts(T, f, 'all'), [{ tag: 'records', count: 1 }, { tag: 'water', count: 1 }]);
  });
  it('the Any / All switch shows once two tags are chosen', () => {
    global.icon ??= name => `[${name}]`;
    if (typeof global.esc !== 'function') {
      require('node:vm').runInThisContext(require('node:fs').readFileSync(require('node:path').join(__dirname, '../js/shared/utils.js'), 'utf8'));
    }
    const { tagFilterHtml } = require('../js/shared/questions.js');
    const all = [{ tag: 'a', count: 1 }, { tag: 'b', count: 1 }];
    assert.doesNotMatch(tagFilterHtml(all, ['a'], null, 'any'), /data-tag-mode/);
    assert.match(tagFilterHtml(all, ['a', 'b'], null, 'any'), /data-tag-mode="any" aria-pressed="true"/);
    assert.doesNotMatch(tagFilterHtml(all, ['a', 'b']), /data-tag-mode/);   // no switch asked for
    assert.match(tagModeHtml('all'), /data-tag-mode="all" aria-pressed="true"/);
  });
});
