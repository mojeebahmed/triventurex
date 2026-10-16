/**
 * test/utils.test.js
 * Unit tests for js/utils.js (browser script — loaded into a vm context).
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ctx = {};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/utils.js'), 'utf8'), ctx);
const { esc } = ctx;

describe('esc()', () => {
  it('escapes HTML tags', () => {
    assert.equal(esc('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;');
  });

  it('escapes quotes so values cannot break out of an attribute', () => {
    assert.equal(esc(`red" onmouseover="x`), 'red&quot; onmouseover=&quot;x');
    assert.equal(esc(`'`), '&#39;');
  });

  it('escapes & first (no double-escaping of its own output)', () => {
    assert.equal(esc('Tom & Jerry <3'), 'Tom &amp; Jerry &lt;3');
  });

  it('leaves normal names and emoji unchanged', () => {
    assert.equal(esc('Ali 🚀'), 'Ali 🚀');
    assert.equal(esc('#1565C0'), '#1565C0');
  });

  it('turns null/undefined into an empty string', () => {
    assert.equal(esc(null), '');
    assert.equal(esc(undefined), '');
    assert.equal(esc(0), '0');
  });
});
