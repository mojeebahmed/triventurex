/**
 * test/socket-events.test.js
 * TX_NET (js/shared/socket-client.js) only forwards the socket events in its
 * `events` list. A handler for an event missing from that list never runs —
 * silently. Every TX_NET.on('…') in the host and phone code must be listed.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');

describe('TX_NET event list', () => {
  const client = read('js/shared/socket-client.js');
  const listed = new Set([...client.match(/const events = \[([\s\S]*?)\];/)[1].matchAll(/'([a-z_]+)'/g)].map(m => m[1]));

  it('forwards every event the host and phone pages listen for', () => {
    const files = ['js/player/player.js', ...fs.readdirSync(path.join(ROOT, 'js/host')).map(f => `js/host/${f}`)];
    const missing = [];
    for (const f of files) {
      for (const [, ev] of read(f).matchAll(/TX_NET\.on\('([a-z_]+)'/g)) {
        if (!listed.has(ev)) missing.push(`${f}: ${ev}`);
      }
    }
    assert.deepEqual(missing, []);
  });
});
