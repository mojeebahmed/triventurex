/**
 * test/icons.test.js
 * The icon system (js/shared/icon-registry.js + icons.js): engine code uses
 * icons only by name, every name exists, every name has its icon bundled, and
 * the bundled files are up to date. See "Icons" in CLAUDE.md.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');
const { glyphKey, findEmoji } = require('../js/shared/icons.js');
const { ICONS, BADGES, BADGE_COLORS } = require('../js/shared/icon-registry.js');

const ROOT = path.join(__dirname, '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');

/** The registry, icon data and icons.js loaded together, like a page does. */
function iconWorld() {
  const ctx = {};
  vm.createContext(ctx);
  for (const f of ['js/shared/icon-registry.js', 'js/shared/icons-data.js', 'js/shared/icons.js']) {
    vm.runInContext(read(f), ctx, { filename: f });
  }
  return ctx;
}

/** Engine files: the four pages and js/ (not the registry, the generated data or third-party code). */
function engineFiles() {
  const out = ['index.html', 'player.html', 'display.html', 'academy.html'];
  const walk = d => { for (const e of fs.readdirSync(path.join(ROOT, d), { withFileTypes: true })) {
    const p = `${d}/${e.name}`;
    if (e.isDirectory()) { if (e.name !== 'vendor') walk(p); }
    else if (p.endsWith('.js') && !/icon-registry\.js$|icons-data\.js$/.test(p)) out.push(p);
  } };
  walk('js');
  return out;
}

/** Source without comments (// …, /* … *\/, <!-- … -->) — icons may be named in comments. */
function code(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')
    .split('\n').map(l => l.replace(/(^|[^:'"`\\])\/\/.*$/, '$1')).join('\n');
}

describe('finding emoji', () => {
  it('glyphKey: code points without the FE0F variation selector', () => {
    assert.equal(glyphKey('⚙️'), '2699');
    assert.equal(glyphKey('🦁'), '1f981');
    assert.equal(glyphKey('👨‍👩‍👧'), '1f468-200d-1f469-200d-1f467');
  });

  it('finds emoji, flags and ZWJ sequences; leaves ©, ®, ™ and digits as text', () => {
    assert.deepEqual(findEmoji('Go 🦁 and 🇸🇪! © ® ™ 42').map(e => e.glyph), ['🦁', '🇸🇪']);
    assert.deepEqual(findEmoji('A family 👨‍👩‍👧').map(e => e.glyph), ['👨‍👩‍👧']);
  });
});

describe('icons by name', () => {
  const w = iconWorld();

  it('icon(): a line icon is an inline SVG, an emoji is the bundled image', () => {
    assert.match(w.icon('boardUndo'), /^<span class="tx-icon" aria-hidden="true"><svg /);
    assert.match(w.icon('tileQuestion'), /<img class="tx-emoji" src="images\/emoji\/2753\.svg" alt="❓"/);
  });

  it('icon() and iconText() also take an emoji (editions and badges hold emoji)', () => {
    assert.match(w.icon('🦁'), /images\/emoji\/1f981\.svg/);
    assert.equal(w.iconText('🦁'), '🦁');
  });

  it('iconText(): the emoji for emoji names, nothing for line icons and unknown names', () => {
    assert.equal(w.iconText('tileSkip'), ICONS.tileSkip.slice(6));
    assert.equal(w.iconText('boardUndo'), '');
    assert.equal(w.iconText('noSuchIcon'), '');
    assert.equal(w.icon('noSuchIcon'), '');
  });
});

describe('edition icons at run time', () => {
  const { editionIcons } = require('../js/shared/edition.js');

  it('editionIcons: bare emoji → emoji:, file: → the edition folder, set icons unchanged', () => {
    assert.deepEqual(editionIcons({ tileGoodDeed: '⚽', tileBadDeed: 'emoji:🟥', trophy: 'file:icons/cup.svg', rulesScoring: 'lucide:trophy' }, 'football-quest'), {
      tileGoodDeed: 'emoji:⚽', tileBadDeed: 'emoji:🟥', trophy: 'url:game_editions/football-quest/icons/cup.svg', rulesScoring: 'lucide:trophy' });
  });

  it("the edition's ICONS win over the engine; other names stay the engine's", () => {
    const w = iconWorld();
    vm.runInContext(`var CONFIG = { EDITION_ICONS: ${JSON.stringify(editionIcons({ tileGoodDeed: '⚽', trophy: 'file:icons/cup.svg', rulesScoring: 'lucide:trophy' }, 'fq'))} };`, w);
    assert.equal(w.iconText('tileGoodDeed'), '⚽');
    assert.match(w.icon('tileGoodDeed'), /images\/emoji\/26bd\.svg/);
    assert.match(w.icon('trophy'), /<img class="tx-emoji tx-picture" src="game_editions\/fq\/icons\/cup\.svg"/);
    assert.equal(w.iconText('trophy'), '', 'a picture has no text form');
    assert.match(w.icon('rulesScoring'), /<svg /);
    assert.equal(w.iconText('tileBadDeed'), ICONS.tileBadDeed.slice(6), 'not overridden: engine default');
  });
});

describe('the registry', () => {
  const data = vm.runInContext('TX_ICON_DATA', iconWorld());   // a const is not a property of the sandbox

  it('every entry is "<set>:<icon>"', () => {
    for (const [name, v] of Object.entries(ICONS)) assert.match(v, /^[a-z0-9-]+:.+$/, name);
  });

  it('every line icon is bundled, and every emoji has its image (keycaps excepted)', () => {
    for (const [name, v] of Object.entries(ICONS)) {
      if (v.startsWith('emoji:')) {
        const g = v.slice(6);
        if (/⃣/.test(g)) continue;                       // keycaps: no image in the set, device emoji
        assert.ok(data.emoji.includes(glyphKey(g)), `${name}: no image for ${g}`);
      } else {
        assert.ok(data.ui[v], `${name}: line icon ${v} not bundled (npm run build:icons)`);
      }
    }
    for (const b of BADGES) assert.ok(data.emoji.includes(glyphKey(b)), `badge ${b}`);
  });

  it('host and phones offer the same badges and colours', () => {
    assert.equal(new Set(BADGES).size, BADGES.length, 'no duplicate badges');
    assert.equal(new Set(BADGE_COLORS).size, BADGE_COLORS.length, 'no duplicate colours');
    for (const c of BADGE_COLORS) assert.match(c, /^#[0-9A-F]{6}$/, c);   // the server only accepts hex colours
    const player = fs.readFileSync(path.join(ROOT, 'js/player/player.js'), 'utf8');
    assert.match(player, /const TOKENS = BADGES;/);
    assert.match(player, /const COLORS = BADGE_COLORS;/);
    assert.match(fs.readFileSync(path.join(ROOT, 'js/shared/config.js'), 'utf8'), /colors: BADGE_COLORS/);
  });

  it('engine code has no raw emoji or icon symbols — use icon(name) / iconText(name)', () => {
    const bad = [];
    for (const f of engineFiles()) {
      code(read(f)).split('\n').forEach((line, i) => {
        const glyphs = [...findEmoji(line).map(e => e.glyph), ...(line.match(/[⌂✕←→↑↓↺]/g) || [])];
        if (glyphs.length) bad.push(`${f}:${i + 1} ${glyphs.join(' ')}`);
      });
    }
    assert.deepEqual(bad, [], 'Add a name to js/shared/icon-registry.js and use it:\n' + bad.join('\n'));
  });

  it('every icon name used in the code exists', () => {
    const used = new Map();
    for (const f of engineFiles()) {
      const src = code(read(f));
      for (const re of [/\bicon(?:Text)?\('([A-Za-z0-9]+)'\)/g, /data-icon(?:-text)?="([A-Za-z0-9]+)"/g,
                        /\bicon: '([A-Za-z0-9]+)'/g, /_addActivity\('([A-Za-z0-9]+)'/g]) {
        for (const m of src.matchAll(re)) used.set(m[1], f);
      }
    }
    const missing = [...used].filter(([n]) => !ICONS[n]).map(([n, f]) => `${n} (${f})`);
    assert.deepEqual(missing, [], 'Unknown icon names — add them to js/shared/icon-registry.js');
  });
});

describe('bundled icons', () => {
  it('images and icons-data.js are up to date (run: npm run build:icons)', () => {
    let out = '';
    try { out = execFileSync('node', ['scripts/build-icons.js', '--check'], { cwd: ROOT, encoding: 'utf8' }); }
    catch (e) { assert.fail(e.stdout + e.stderr); }
    assert.match(out, /✓ icons/);
    assert.ok(fs.existsSync(path.join(ROOT, 'images/emoji/LICENSE.txt')));
  });

  for (const page of ['index.html', 'player.html', 'display.html', 'academy.html']) {
    it(`${page} loads icon-registry.js, icons-data.js and icons.js, in that order`, () => {
      const html = read(page);
      const at = f => html.indexOf(`src="js/shared/${f}"`);
      assert.ok(at('icon-registry.js') > 0 && at('icon-registry.js') < at('icons-data.js') && at('icons-data.js') < at('icons.js'), page);
    });
  }
});
