/**
 * test/html-structure.test.js
 * Guards the page structure of index.html and player.html: every <div> is
 * closed, and every `.screen` is a top-level sibling. A missing </div> once
 * nested the game screen inside the setup screen, so the board never showed.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

/** Walk the <div> tags of an HTML file: depth at each `class="screen"` + final balance. */
function divStructure(file) {
  const html = fs.readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/<!--[\s\S]*?-->/g, '')          // comments
    .replace(/<script[\s\S]*?<\/script>/g, '') // inline scripts
    .replace(/<style[\s\S]*?<\/style>/g, '');  // inline styles
  let depth = 0;
  const screens = [];
  for (const m of html.matchAll(/<div\b([^>]*)>|<\/div>/g)) {
    if (m[0] === '</div>') { depth--; assert.ok(depth >= 0, `${file}: extra </div>`); continue; }
    const id = (m[1].match(/\bid="([^"]+)"/) || [])[1];
    if (/class="[^"]*\bscreen\b/.test(m[1])) screens.push({ id, depth });
    depth++;
  }
  return { screens, balance: depth };
}

describe('index.html structure', () => {
  const { screens, balance } = divStructure('index.html');

  it('every <div> is closed', () => assert.equal(balance, 0));

  it('setup, lobby, game and end screens are top-level siblings', () => {
    const ids = screens.map(s => s.id);
    for (const id of ['setup-screen', 'lobby-screen', 'game-screen', 'end-screen']) {
      assert.ok(ids.includes(id), `${id} missing`);
    }
    for (const s of screens) assert.equal(s.depth, 0, `${s.id} is nested ${s.depth} levels deep`);
  });
});

describe('player.html structure', () => {
  it('every <div> is closed', () => assert.equal(divStructure('player.html').balance, 0));
});

describe('academy.html structure', () => {
  it('every <div> is closed', () => assert.equal(divStructure('academy.html').balance, 0));

  it('loads only shared and academy scripts (it must work opened from disk, without the host page)', () => {
    const html = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', 'academy.html'), 'utf8');
    const scripts = [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);
    assert.ok(scripts.length > 0);
    for (const s of scripts) assert.match(s, /^(js\/shared\/|js\/academy\/|game_editions\/editions\.js$)/, s);
  });
});

// Phones: the setup screen and the Academy must be usable on a phone (2026-11)
describe('phone-friendly pages', () => {
  const read = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');

  for (const file of ['index.html', 'player.html', 'academy.html']) {
    it(`${file} has a mobile viewport`, () => {
      assert.match(read(file), /<meta name="viewport" content="width=device-width, initial-scale=1\.0/);
    });
  }

  it('the Academy fills the screen with dvh (phone browser bars must not hide the bottom)', () => {
    const css = read('css/academy.css');
    assert.match(css, /body\.academy\s*\{[^}]*height:\s*100vh;\s*height:\s*100dvh/);
  });

  it('the Academy has the phone filter sheet, its Show button, the More sheet and the backdrop', () => {
    const html = read('academy.html');
    for (const id of ['ac-filter', 'ac-filter-done', 'ac-more', 'ac-backdrop']) assert.match(html, new RegExp(`id="${id}"`), id);
  });

  it('only Print cards and Review move to More on a phone', () => {
    const modes = read('js/academy/modes.js');
    const desk = [...modes.matchAll(/id: '(\w+)'[^\n]*phone: false/g)].map(m => m[1]);
    assert.deepEqual(desk.sort(), ['print', 'review']);
  });
});

describe('setup screen on phones', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

  it('Questions and Boards move to More on a phone; New game and Rules stay', () => {
    assert.match(html, /class="setup-tab desk-tab" data-tab="questions"/);
    assert.match(html, /class="setup-tab desk-tab" data-tab="boards"/);
    assert.match(html, /class="setup-tab active" data-tab="new"/);
    assert.match(html, /class="setup-tab" data-tab="rules"/);
    assert.match(html, /onclick="openSetupMore\(\)"/);
  });

  it('More offers Questions, Boards and the Academy', () => {
    const more = html.slice(html.indexOf('id="setup-more"'), html.indexOf('id="setup-backdrop"'));
    for (const call of ["showSetupTab('questions')", "showSetupTab('boards')", 'openAcademy()']) assert.ok(more.includes(call), call);
  });

  it('the setup card fills a phone screen with dvh', () => {
    const css = fs.readFileSync(path.join(__dirname, '..', 'css/styles.css'), 'utf8');
    assert.match(css, /\.setup-container \{[^}]*height: 100vh; height: 100dvh;/);
  });
});

describe('game screen on phones', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  const css = fs.readFileSync(path.join(__dirname, '..', 'css/styles.css'), 'utf8');

  it('the zoom bar has the legend button (phones hide the legend behind it)', () => {
    assert.match(html, /class="zoom-legend-btn" onclick="toggleLegend\(\)"/);
  });

  it('upright phones put the sidebar under the board (#game-main becomes a column)', () => {
    assert.match(html, /<div id="game-main"/);
    assert.match(css, /@media \(max-width: 720px\) and \(orientation: portrait\) \{\s*#game-main \{ flex-direction: column; \}/);
  });

  it('ui.js and the CSS use the same phone width / height', () => {
    const ui = fs.readFileSync(path.join(__dirname, '..', 'js/host/ui.js'), 'utf8');
    const q = ui.match(/const PHONE_GAME_QUERY = '([^']+)'/)[1];
    assert.ok(css.includes(`@media ${q} {`), `css has no @media ${q}`);
  });
});

describe('space cards never hide their buttons', () => {
  const css = fs.readFileSync(path.join(__dirname, '..', 'css/styles.css'), 'utf8');
  const rule = sel => (css.match(new RegExp(`\\n${sel} \\{([^}]*)\\}`)) || [])[1] || '';

  it('the card is a column no taller than the board area', () => {
    assert.match(rule('#modal'), /display: flex; flex-direction: column;/);
    assert.match(rule('#modal'), /max-height: calc\(100% - 24px\)/);
  });

  it('header, title and content scroll together; the buttons stay at the bottom', () => {
    assert.match(rule('#modal-body'), /overflow-y: auto/);
    assert.match(css, /#modal-actions \{ flex: none; \}/);
    for (const page of ['index.html', 'display.html']) {
      const html = fs.readFileSync(path.join(__dirname, '..', page), 'utf8');
      assert.match(html, /<div id="modal-body">\s*<div id="modal-icon"><\/div>\s*<h2 id="modal-title"><\/h2>\s*<div id="modal-content"><\/div>\s*<\/div>/, page);
    }
  });

  it('a finger or the wheel on a card scrolls the card, not the board', () => {
    const vp = fs.readFileSync(path.join(__dirname, '..', 'js/shared/viewport.js'), 'utf8');
    assert.match(vp, /const _onBoard = e => !e\.target\.closest\?\.\('#modal,/);
    for (const ev of ['wheel', 'mousedown', 'touchstart', 'touchmove']) {
      const handler = vp.slice(vp.indexOf(`addEventListener('${ev}'`)).slice(0, 220);
      assert.match(handler, /_onBoard\(e\)/, `${ev} must ignore cards`);
    }
  });
});

describe('last turn line on phones', () => {
  const css = fs.readFileSync(path.join(__dirname, '..', 'css/styles.css'), 'utf8');
  const ui = fs.readFileSync(path.join(__dirname, '..', 'js/host/ui.js'), 'utf8');

  it('is one line across the board (fitTurnRecap shrinks a long one)', () => {
    const phone = css.slice(css.indexOf('/* Last turn: one line across the board'));
    assert.match(phone.slice(0, 400), /left: 6px; right: 6px; transform: none;[\s\S]*white-space: nowrap/);
    assert.match(ui, /function renderTurnRecap[\s\S]*?fitTurnRecap\(\);/);
    assert.match(ui, /const refit = \(\) => \{[\s\S]*?fitTurnRecap\(\);/);   // again when the phone turns
  });
});
