/**
 * test/text-size.test.js
 * js/shared/text-size.js — the A− / A+ text size steps — and the iPhone
 * "Add to Home Screen" helpers in js/shared/academy.js.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const T = require('../js/shared/text-size.js');
const { iosBrowser, homeScreenSteps } = require('../js/shared/academy.js');

const ROOT = path.join(__dirname, '..');
const STEPS = [1, 1.15, 1.3, 1.5];

describe('text size steps', () => {
  it('steps come from CONFIG, sorted, always with 1', () => {
    assert.deepEqual(T.textSizeSteps({ TEXT_SIZE: { steps: [1.5, 1.2] } }), [1, 1.2, 1.5]);
    assert.deepEqual(T.textSizeSteps({}), [1]);
    assert.deepEqual(T.textSizeSteps({ TEXT_SIZE: { steps: [0, -1, 'x', 1.3] } }), [1, 1.3]);
  });

  it('the engine config has sensible steps', () => {
    const src = fs.readFileSync(path.join(ROOT, 'js/shared/config.js'), 'utf8');
    const m = src.match(/TEXT_SIZE:\s*{\s*steps:\s*\[([^\]]+)\]/);
    assert.ok(m, 'CONFIG.TEXT_SIZE.steps exists');
    const steps = m[1].split(',').map(Number);
    assert.equal(steps[0], 1);
    assert.ok(steps.every((n, i) => i === 0 || n > steps[i - 1]), 'ascending');
    assert.ok(Math.max(...steps) <= 2, 'not so big that a card no longer fits');
  });

  it('a saved value snaps to the nearest step; junk is 1', () => {
    assert.equal(T.nearestTextSize('1.3', STEPS), 1.3);
    assert.equal(T.nearestTextSize(1.4, STEPS), 1.3);
    assert.equal(T.nearestTextSize(9, STEPS), 1.5);
    assert.equal(T.nearestTextSize('abc', STEPS), 1);
    assert.equal(T.nearestTextSize(null, STEPS), 1);
    assert.equal(T.nearestTextSize(-2, STEPS), 1);
  });

  it('stepping up and down stops at the ends', () => {
    assert.equal(T.stepTextSize(1, 1, STEPS), 1.15);
    assert.equal(T.stepTextSize(1.3, -1, STEPS), 1.15);
    assert.equal(T.stepTextSize(1.5, 1, STEPS), 1.5);
    assert.equal(T.stepTextSize(1, -1, STEPS), 1);
  });

  it('label is a whole percentage', () => {
    assert.equal(T.textSizeLabel(1), '100%');
    assert.equal(T.textSizeLabel(1.15), '115%');
  });

  it('only the cards grow: the CSS zooms the cards, never the board or the page', () => {
    const css = fs.readFileSync(path.join(ROOT, 'css/styles.css'), 'utf8');
    const ac = fs.readFileSync(path.join(ROOT, 'css/academy.css'), 'utf8');
    const noComments = (css + ac).replace(/\/\*[\s\S]*?\*\//g, '');
    const rules = [...noComments.matchAll(/([^{}]+)\{([^}]*)\}/g)].filter(m => /zoom:[^;]*--text-scale/.test(m[2]));
    // the element each selector zooms = its last part (body.presenting #modal → #modal)
    const zoomed = rules.flatMap(m => m[1].split(',').map(s => s.trim().split(/\s+/).pop()));
    assert.ok(zoomed.includes('#modal'), 'the game card grows');
    assert.ok(zoomed.includes('.ac-flash-grid') && zoomed.includes('.ac-panel'), 'the Academy cards grow');
    for (const el of zoomed) assert.doesNotMatch(el, /^(html|body|:root|#board[\w-]*|#sidebar|#game-main|\.ac-sheet|\.ac-main|\.ac-top|\.ac-modes)$/, el);
  });

  it('every A− / A+ control on the pages has both buttons', () => {
    for (const page of ['index.html', 'academy.html']) {
      const html = fs.readFileSync(path.join(ROOT, page), 'utf8');
      assert.match(html, /data-text-size/, page);
      assert.match(html, /data-text-step="-1"/, page);
      assert.match(html, /data-text-step="1"/, page);
      assert.match(html, /js\/shared\/text-size\.js/, page);
    }
  });
});

describe('iPhone: Add to Home Screen', () => {
  const UA = {
    safari:  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
    chrome:  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.6778.73 Mobile/15E148 Safari/604.1',
    firefox: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/132.0 Mobile/15E148 Safari/605.1.15',
    edge:    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 EdgiOS/131.0.2903.68 Mobile/15E148 Safari/605.1.15',
    google:  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) GSA/343.0.695551749 Mobile/15E148 Safari/604.1',
    ipadDesk:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    mac:     'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    android: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
  };

  it('tells the iPhone browsers apart', () => {
    assert.equal(iosBrowser(UA.safari), 'safari');
    assert.equal(iosBrowser(UA.chrome), 'chrome');
    assert.equal(iosBrowser(UA.firefox), 'firefox');
    assert.equal(iosBrowser(UA.edge), 'edge');
    assert.equal(iosBrowser(UA.google), 'other');
    assert.equal(iosBrowser(UA.ipadDesk, 5), 'safari', 'an iPad asking for the desktop site');
  });

  it('is null off an iPhone / iPad', () => {
    assert.equal(iosBrowser(UA.mac, 0), null);
    assert.equal(iosBrowser(UA.ipadDesk, 0), null, 'a real Mac has no touch points');
    assert.equal(iosBrowser(UA.android), null);
    assert.equal(iosBrowser(), null);
  });

  it('gives steps for each browser, ending at Add to Home Screen', () => {
    for (const b of ['safari', 'chrome', 'firefox', 'edge', 'other']) {
      const steps = homeScreenSteps(b);
      assert.ok(steps.length >= 2, b);
      assert.ok(steps.some(s => /Add to Home Screen/.test(s)), b);
      for (const s of steps) assert.doesNotMatch(s, /[<>]/, 'plain text (the page escapes it)');
    }
    assert.match(homeScreenSteps('chrome')[0], /top right/);
    assert.match(homeScreenSteps('other')[0], /Safari/);
  });
});
