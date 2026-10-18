/**
 * test/icons.test.js
 * js/shared/icons.js (finding emoji and control glyphs) and the bundled icons:
 * every emoji the game uses has its image, the generated data is up to date,
 * and every page loads the icon scripts in the right order.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { glyphKey, findEmoji, controlGlyphs } = require('../js/shared/icons.js');

const ROOT = path.join(__dirname, '..');
const keys = (...g) => new Set(g.map(glyphKey));

describe('finding emoji', () => {
  it('glyphKey: code points without the FE0F variation selector', () => {
    assert.equal(glyphKey('⚙️'), '2699');
    assert.equal(glyphKey('⚙'), '2699');
    assert.equal(glyphKey('🦁'), '1f981');
    assert.equal(glyphKey('👨‍👩‍👧'), '1f468-200d-1f469-200d-1f467');
  });

  it('finds emoji, flags and ZWJ sequences; leaves ©, ®, ™ and digits as text', () => {
    assert.deepEqual(findEmoji('Go 🦁 and 🇸🇪! © ® ™ 42').map(e => e.glyph), ['🦁', '🇸🇪']);
    assert.deepEqual(findEmoji('⚙️ Rules').map(e => [e.index, e.glyph]), [[0, '⚙️']]);
    assert.deepEqual(findEmoji('A family 👨‍👩‍👧').map(e => e.glyph), ['👨‍👩‍👧']);
  });
});

describe('control glyphs', () => {
  const K = keys('↩', '▶', '+', '−', '⚙️', '📋');

  it('a leading glyph followed by a space, or alone', () => {
    assert.equal(controlGlyphs('↩ Undo', K).lead.glyph, '↩');
    assert.equal(controlGlyphs('⚙️ Rules', K).lead.glyph, '⚙️');
    assert.equal(controlGlyphs('+', K).lead.glyph, '+');
    assert.equal(controlGlyphs('  📋 Copy', K).lead.end, 4);
  });

  it('a trailing glyph after a space', () => {
    assert.equal(controlGlyphs('Start Game ▶', K).trail.glyph, '▶');
    assert.equal(controlGlyphs('Start Game▶', K).trail, null);
  });

  it('"+1", "−2" and "+30s" stay text', () => {
    for (const t of ['+1', '−2', '+30s', 'A+B']) {
      const r = controlGlyphs(t, K);
      assert.equal(r.lead, null, t);
      assert.equal(r.trail, null, t);
    }
  });

  it('only the first / last piece of a control counts', () => {
    assert.equal(controlGlyphs('↩ Undo', K, { first: false }).lead, null);
    assert.equal(controlGlyphs('Go ▶', K, { last: false }).trail, null);
  });

  it('glyphs that are not in the table are left for the emoji pass', () => {
    assert.deepEqual(controlGlyphs('🎉 Alhamdulillah!', K), { lead: null, trail: null });
  });
});

describe('bundled icons', () => {
  it('images and icons-data.js are up to date (run: npm run build:icons)', () => {
    let out = '';
    try { out = execFileSync('node', ['scripts/build-icons.js', '--check'], { cwd: ROOT, encoding: 'utf8' }); }
    catch (e) { assert.fail(e.stdout + e.stderr); }
    assert.match(out, /✓ icons/);
  });

  it('every control icon in the config exists, and the emoji folder has its licence', () => {
    const cfg = require('../scripts/icons.config.js');
    const data = fs.readFileSync(path.join(ROOT, 'js/shared/icons-data.js'), 'utf8');
    for (const g of Object.keys(cfg.controls)) assert.ok(data.includes(`"${glyphKey(g)}"`), `control ${g}`);
    assert.ok(fs.existsSync(path.join(ROOT, 'images/emoji/LICENSE.txt')));
  });

  for (const page of ['index.html', 'player.html', 'display.html', 'academy.html']) {
    it(`${page} loads icons-data.js before icons.js`, () => {
      const html = fs.readFileSync(path.join(ROOT, page), 'utf8');
      const a = html.indexOf('src="js/shared/icons-data.js"'), b = html.indexOf('src="js/shared/icons.js"');
      assert.ok(a > 0 && b > a, page);
    });
  }
});
