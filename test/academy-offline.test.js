/**
 * test/academy-offline.test.js
 * The Academy as an app (install + offline): academy-sw.js saves every file
 * academy.html needs, the cache name matches the page's, the manifest and its
 * icons are valid, and the worker finds every edition in editions.js.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
const sw = read('academy-sw.js');
const html = read('academy.html');

/** ACADEMY_FILES from academy-sw.js. */
const academyFiles = () => {
  const list = sw.match(/const ACADEMY_FILES = (\[[\s\S]*?\]);/);
  assert.ok(list, 'ACADEMY_FILES not found');
  return vm.runInNewContext(list[1]);
};

describe('academy-sw.js', () => {
  it('saves every script and stylesheet academy.html loads', () => {
    const files = academyFiles();
    const needed = [...html.matchAll(/<script src="([^"]+)"/g), ...html.matchAll(/<link rel="stylesheet" href="([^"]+)"/g)].map(m => m[1]);
    assert.ok(needed.length > 10);
    for (const f of needed) assert.ok(files.includes(f), `${f} is loaded by academy.html but not saved for offline (add it to ACADEMY_FILES)`);
  });

  it('every saved file exists', () => {
    for (const f of academyFiles()) assert.ok(fs.existsSync(path.join(ROOT, f)), `${f} missing`);
  });

  it('uses the same cache name as the page (Save photos for offline)', () => {
    const inSw = sw.match(/const ACADEMY_CACHE = '([^']+)'/)[1];
    const inPage = read('js/academy/academy.js').match(/const ACADEMY_CACHE = '([^']+)'/)[1];
    assert.equal(inSw, inPage);
  });

  it('finds every edition in editions.js (their config + questions are saved)', () => {
    const ctx = { window: {} };
    vm.runInNewContext(read('game_editions/editions.js'), ctx);
    const ids = Array.from(ctx.window.TRIVENTUREX_EDITIONS, e => e.id);   // Array.from: out of the vm realm
    const found = [...read('game_editions/editions.js').matchAll(/\bid:\s*['"]([\w-]+)['"]/g)].map(m => m[1]);
    assert.deepEqual(found, ids);
    for (const id of ids) {
      assert.ok(fs.existsSync(path.join(ROOT, `game_editions/${id}/config.js`)));
      assert.ok(fs.existsSync(path.join(ROOT, `game_editions/${id}/questions.js`)));
    }
  });

  it('is registered for the Academy page only (scope ./academy)', () => {
    assert.match(read('js/academy/academy.js'), /register\('academy-sw\.js', \{ scope: '\.\/academy' \}\)/);
  });
});

describe('academy.webmanifest', () => {
  const manifest = JSON.parse(read('academy.webmanifest'));

  it('is linked from academy.html', () => assert.match(html, /<link rel="manifest" href="academy\.webmanifest">/));

  it('starts the Academy, standalone, with a name', () => {
    assert.equal(manifest.start_url, 'academy.html');
    assert.equal(manifest.display, 'standalone');
    assert.ok(manifest.name && manifest.short_name);
  });

  it('has 192 and 512 px icons that exist', () => {
    const sizes = manifest.icons.map(i => i.sizes);
    assert.ok(sizes.includes('192x192') && sizes.includes('512x512'));
    for (const i of manifest.icons) assert.ok(fs.existsSync(path.join(ROOT, i.src)), `${i.src} missing`);
  });
});
