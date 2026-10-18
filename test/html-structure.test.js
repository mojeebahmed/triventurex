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
