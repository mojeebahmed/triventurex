/**
 * test/help.test.js — the in-game help (js/shared/help.js): every topic, link
 * and icon exists, every word is known, and the markup renders safely.
 */
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { HELP, helpWords, helpHtml, rulesCardHtml } = require('../js/shared/help.js');
const { defaultRules } = require('../js/shared/rules.js');
const { ICONS } = require('../js/shared/icon-registry.js');

const ROOT = path.join(__dirname, '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
const WORDS = Object.keys(helpWords(null));

describe('help topics', () => {
  it('every topic has a title, an icon and a body; links point at topics', () => {
    for (const [id, t] of Object.entries(HELP)) {
      assert.ok(t.title && t.body, id);
      assert.ok(ICONS[t.icon], `${id}: unknown icon ${t.icon}`);
      for (const k of t.more || []) assert.ok(HELP[k], `${id}: links to unknown topic ${k}`);
    }
  });

  it('every {icon:name} exists and every {word} is known', () => {
    for (const [id, t] of Object.entries(HELP)) {
      for (const [, n] of t.body.matchAll(/\{icon:([A-Za-z0-9]+)\}/g)) assert.ok(ICONS[n], `${id}: unknown icon ${n}`);
      for (const [, w] of t.body.matchAll(/\{([a-z]+)\}/g)) assert.ok(WORDS.includes(w), `${id}: unknown word {${w}}`);
    }
  });

  it('every screen has its help: setup tabs, Academy modes, phone views', () => {
    for (const [, tab] of read('index.html').matchAll(/class="setup-tab[^"]*" data-tab="([a-z]+)"/g)) {
      assert.ok(HELP[`setup-${tab}`], `setup tab ${tab}`);
    }
    for (const [, mode] of read('js/academy/modes.js').matchAll(/registerMode\(\{\s*id: '([a-z]+)'/g)) {
      assert.ok(HELP[`academy-${mode}`], `Academy mode ${mode}`);
    }
    for (const t of ['lobby', 'game', 'game-cards', 'game-log', 'game-gm', 'phone-join', 'phone-lobby', 'phone-game', 'academy', 'how-to-play']) {
      assert.ok(HELP[t], t);
    }
  });

  it('every page has a ? button and loads help.js after icons.js', () => {
    for (const page of ['index.html', 'player.html', 'academy.html']) {
      const html = read(page);
      assert.match(html, /class="help-btn/, `${page}: no help button`);
      assert.match(html, /href="css\/help\.css"/, `${page}: help.css`);
      assert.ok(html.indexOf('src="js/shared/help.js"') > html.indexOf('src="js/shared/icons.js"'), `${page}: script order`);
    }
  });
});

describe('help markup', () => {
  const plain = n => `[${n}]`;

  it('paragraphs, headings, bullets, bold, icons and words', () => {
    const html = helpHtml('Hello **you**.\n\n## Spaces\n- {icon:tileSkip} **{skip}**\n- two', { ...helpWords(null), skip: 'Red Card' }, plain);
    assert.equal(html, '<p>Hello <strong>you</strong>.</p><section class="help-section"><h3>Spaces</h3><ul><li>[tileSkip] <strong>Red Card</strong></li><li>two</li></ul></section>');
  });

  it('each heading starts its own section box', () => {
    const html = helpHtml('Intro\n## A\ntext a\n## B\n- b', helpWords(null), plain);
    assert.equal(html, '<p>Intro</p><section class="help-section"><h3>A</h3><p>text a</p></section><section class="help-section"><h3>B</h3><ul><li>b</li></ul></section>');
  });

  it("uses the edition's words", () => {
    const w = helpWords({ GAME: { pointsName: 'Goals', finishLabel: 'The Final', editionName: 'Football Quest' },
                         SPACE_INFO: { good_deed: { label: 'Good Play' }, finish: { label: 'Finish!' } } });
    assert.equal(w.points, 'Goals');
    assert.equal(w.finish, 'The Final');
    assert.equal(w.good, 'Good Play');
    assert.equal(helpWords(null).points, 'points', "the engine's 'pts' reads as points");
  });

  it('escapes words and text (words can come from the network on phones)', () => {
    const html = helpHtml('<b>x</b> {points}', { ...helpWords(null), points: '<img onerror=x>' }, plain);
    assert.ok(!html.includes('<img') && !html.includes('<b>'), html);
  });

  it('leaves unknown {words} alone', () => {
    assert.equal(helpHtml('{nope}', helpWords(null), plain), '<p>{nope}</p>');
  });
});

describe('rules card', () => {
  const config = { SCORE_VALUES: { question_easy: 1, question_hard: 2, landmark: 3 }, TIMER: { question: 30, action: 90 } };
  const words = helpWords({ GAME: { pointsName: 'Goals', finishLabel: 'The Final', editionName: 'Football Quest' }, SPACE_INFO: { good_deed: { label: 'Good Play' } } });

  it("uses this game's points and the edition's words", () => {
    const html = rulesCardHtml({ rules: defaultRules(config), bonus: [10, 6, 3, 1], words, edition: { name: 'Football Quest' } });
    for (const s of ['Football Quest', 'The Final', 'Goals', 'Good Play', 'easy <b>+1</b> or hard <b>+2</b>', '1st <b>+10</b>', '<b>+3</b>', 'Roll the exact number']) {
      assert.ok(html.includes(s), s);
    }
  });

  it('follows the rules: always easy, no going backwards, no bonus', () => {
    const R = defaultRules(config);
    R.questions.difficulty = 'easy'; R.board.noBackwards = true; R.turns.exactFinish = false;
    const html = rulesCardHtml({ rules: R, bonus: [], words });
    assert.ok(html.includes('always easy <b>+1</b>'));
    assert.ok(html.includes('No going backwards'));
    assert.ok(html.includes('no bonus'));
    assert.ok(!html.includes('Roll the exact number'));
    assert.ok(!html.includes('move back'));
  });
});
