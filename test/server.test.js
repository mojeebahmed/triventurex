/**
 * test/server.test.js
 * Integration tests for server.js — real Socket.IO server on a random port,
 * real socket.io-client connections acting as host and phones.
 *
 * Run: npm test
 */

const { describe, it, before, after, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { io: Client } = require('socket.io-client');

let server, io, rooms, url;
const clients = [];
let _origLog;

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Resolve with the next `event` payload, or reject after `ms`. */
function once(socket, event, ms = 1000) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`timeout waiting for '${event}'`)), ms);
    socket.once(event, data => { clearTimeout(t); resolve(data); });
  });
}

/** Record every `event` payload into an array (for "exactly N" / "none" checks). */
function collect(socket, event) {
  const seen = [];
  socket.on(event, data => seen.push(data));
  return seen;
}

/** Let the server process fire-and-forget events that have no reply. */
const settle = (ms = 80) => new Promise(r => setTimeout(r, ms));

async function connect() {
  const s = Client(url, { forceNew: true, transports: ['websocket'] });
  clients.push(s);
  await once(s, 'connect');
  return s;
}

/**
 * Create a room with `phones` joined players. Optionally the host also plays
 * (as player id 0) and the game is started.
 */
async function setupGame({ phones = 2, hostPlays = false, start = true } = {}) {
  const host = await connect();
  host.emit('host_game', {
    themeId: 'test', gameLength: 'short', pathIndex: 'random',
    isGMOnly: !hostPlays,
    hostPlayer: hostPlays ? { id: 0, name: 'Host', token: 'H', color: '#000' } : null,
  });
  const { gameId } = await once(host, 'hosted');

  const players = [];
  for (let i = 0; i < phones; i++) {
    const socket = await connect();
    socket.emit('join_game', { gameId, playerName: `P${i}` });
    const joined = await once(socket, 'joined');
    players.push({ socket, id: joined.playerId, token: joined.rejoinToken });
  }

  if (start) {
    host.emit('start_game', { gameId });
    await once(host, 'game_started');
  }
  return { host, gameId, players, room: rooms.get(gameId) };
}

/** Player states as the host sends them — no server-only fields. */
function hostView(room) {
  return room.players.map(({ socketId, rejoinToken, ...rest }) => rest);
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

before(async () => {
  _origLog = console.log;
  console.log = () => {};              // server logs every event — keep output clean
  ({ server, io, rooms } = require('../server.js'));
  await new Promise(r => server.listen(0, r));
  url = `http://localhost:${server.address().port}`;
});

afterEach(() => {
  while (clients.length) clients.pop().disconnect();
});

after(async () => {
  io.close();
  await new Promise(r => server.close(r));
  console.log = _origLog;
});

// ── Hosting & joining ─────────────────────────────────────────────────────────

describe('hosting and joining', () => {
  it('creates a 4-digit numeric game ID', async () => {
    const { gameId } = await setupGame({ phones: 0, start: false });
    assert.match(gameId, /^\d{4}$/);
  });

  it('rejects joining an unknown game', async () => {
    const s = await connect();
    s.emit('join_game', { gameId: '0000', playerName: 'X' });
    const err = await once(s, 'error');
    assert.match(err.message, /not found/);
  });

  it('gives each joining player a unique id and a rejoin token', async () => {
    const { players } = await setupGame({ phones: 3, start: false });
    assert.deepEqual(players.map(p => p.id), [0, 1, 2]);
    for (const p of players) assert.ok(p.token);
  });

  it('only lets the host start the game', async () => {
    const { gameId, players, room } = await setupGame({ phones: 2, start: false });
    players[0].socket.emit('start_game', { gameId });
    const err = await once(players[0].socket, 'error');
    assert.match(err.message, /Only the host/);
    assert.equal(room.phase, 'lobby');
  });

  it('sends current state immediately to a mid-game joiner', async () => {
    const { gameId } = await setupGame({ phones: 2 });
    const late = await connect();
    const update = once(late, 'state_update');
    late.emit('join_game', { gameId, playerName: 'Late' });
    const state = await update;
    assert.equal(state.playerStates.length, 3);
  });
});

// ── Rolling (B2) ──────────────────────────────────────────────────────────────

describe('rolling', () => {
  it("rejects a roll from a player whose turn it isn't", async () => {
    const { gameId, players } = await setupGame({ phones: 2 });
    players[1].socket.emit('roll', { gameId });
    const err = await once(players[1].socket, 'error');
    assert.match(err.message, /Not your turn/);
  });

  it('accepts only one roll when a phone double-taps', async () => {
    const { host, gameId, players, room } = await setupGame({ phones: 2 });
    const hostRolls = collect(host, 'roll_result');
    const rejected  = once(players[0].socket, 'error');

    players[0].socket.emit('roll', { gameId });
    players[0].socket.emit('roll', { gameId });

    assert.match((await rejected).message, /Turn already in progress/);
    await settle();
    assert.equal(hostRolls.length, 1);
    assert.ok(hostRolls[0].roll >= 1 && hostRolls[0].roll <= 6);
    assert.equal(room.turnPhase, 'resolving');
  });

  it('lets the phone roll again once the host syncs the end of the turn', async () => {
    const { host, gameId, players } = await setupGame({ phones: 2 });
    players[0].socket.emit('roll', { gameId });
    await once(host, 'roll_result');

    host.emit('sync_state', { gameId, turnPhase: 'roll', currentPlayerIndex: 0 });
    await settle();

    const next = once(host, 'roll_result');
    players[0].socket.emit('roll', { gameId });
    await next;
  });

  it('always accepts a roll from the host, even mid-turn', async () => {
    const { host, gameId, room } = await setupGame({ phones: 2 });
    room.turnPhase = 'resolving';
    const result = once(host, 'roll_result');
    host.emit('roll', { gameId });
    await result;
  });

  it('manual_roll: host only, clamped 1–6, sent to phones but not back to host', async () => {
    const { host, gameId, players, room } = await setupGame({ phones: 2 });

    players[0].socket.emit('manual_roll', { gameId, roll: 3 });
    assert.match((await once(players[0].socket, 'error')).message, /Only the host/);

    const hostRolls  = collect(host, 'roll_result');
    const phoneRoll  = once(players[1].socket, 'roll_result');
    host.emit('manual_roll', { gameId, roll: 9 });
    assert.equal((await phoneRoll).roll, 6);
    await settle();
    assert.equal(hostRolls.length, 0);
    assert.equal(room.turnPhase, 'resolving');
  });
});

// ── sync_state ────────────────────────────────────────────────────────────────

describe('sync_state', () => {
  it('preserves server-only rejoinToken and socketId', async () => {
    const { host, gameId, players, room } = await setupGame({ phones: 2 });
    host.emit('sync_state', { gameId, playerStates: hostView(room), turnPhase: 'roll' });
    await settle();

    for (const p of players) {
      const rp = room.players.find(x => x.id === p.id);
      assert.equal(rp.rejoinToken, p.token);
      assert.equal(rp.socketId, p.socket.id);
    }
  });

  it('is ignored when sent by a non-host', async () => {
    const { gameId, players, room } = await setupGame({ phones: 2 });
    players[0].socket.emit('sync_state', { gameId, currentPlayerIndex: 1 });
    await settle();
    assert.equal(room.currentPlayerIndex, 0);
  });

  it('broadcasts state_update to phones but not back to the host', async () => {
    const { host, gameId, players, room } = await setupGame({ phones: 2 });
    const hostUpdates = collect(host, 'state_update');
    const phoneUpdate = once(players[1].socket, 'state_update');
    host.emit('sync_state', { gameId, playerStates: hostView(room), currentPlayerIndex: 1 });
    assert.equal((await phoneUpdate).currentPlayerIndex, 1);
    await settle();
    assert.equal(hostUpdates.length, 0);
  });
});

// ── Removing / leaving (B5) ───────────────────────────────────────────────────

describe('removing players', () => {
  async function threePlayersOnTurnOf(index) {
    const game = await setupGame({ phones: 3 });
    game.host.emit('sync_state', { gameId: game.gameId, currentPlayerIndex: index });
    await settle();
    return game;
  }

  it('keeps the turn on the same player when an earlier player is removed', async () => {
    const { host, gameId, players, room } = await threePlayersOnTurnOf(2);
    const update = once(players[2].socket, 'state_update');
    host.emit('remove_player', { gameId, playerId: players[0].id });
    const state = await update;
    assert.equal(state.playerStates[state.currentPlayerIndex].id, players[2].id);
    assert.equal(room.players[room.currentPlayerIndex].id, players[2].id);
  });

  it('does not move the turn when a later player is removed', async () => {
    const { host, gameId, players, room } = await threePlayersOnTurnOf(0);
    host.emit('remove_player', { gameId, playerId: players[2].id });
    await settle();
    assert.equal(room.players[room.currentPlayerIndex].id, players[0].id);
  });

  it('wraps to the first player when the current last player is removed', async () => {
    const { host, gameId, players, room } = await threePlayersOnTurnOf(2);
    host.emit('remove_player', { gameId, playerId: players[2].id });
    await settle();
    assert.equal(room.currentPlayerIndex, 0);
    assert.equal(room.players.length, 2);
  });

  it('keeps the turn on the same player when an earlier player leaves', async () => {
    const { host, gameId, players, room } = await threePlayersOnTurnOf(2);
    const removed = once(host, 'player_removed');
    players[0].socket.emit('leave_game', { gameId });
    assert.equal((await removed).playerId, players[0].id);
    assert.equal(room.players[room.currentPlayerIndex].id, players[2].id);
  });

  it('ignores remove_player from a non-host', async () => {
    const { gameId, players, room } = await setupGame({ phones: 2 });
    players[0].socket.emit('remove_player', { gameId, playerId: players[1].id });
    await settle();
    assert.equal(room.players.length, 2);
  });
});

// ── Rejoining ─────────────────────────────────────────────────────────────────

describe('rejoining', () => {
  it('re-registers a player with a valid rejoin token', async () => {
    const { gameId, players, room } = await setupGame({ phones: 2 });
    const { id, token } = players[0];
    players[0].socket.disconnect();
    await settle();
    assert.equal(room.players.find(p => p.id === id).disconnected, true);

    const fresh = await connect();
    fresh.emit('rejoin_game', { gameId, playerId: id, rejoinToken: token });
    const data = await once(fresh, 'rejoined');
    assert.equal(data.playerId, id);

    const rp = room.players.find(p => p.id === id);
    assert.equal(rp.socketId, fresh.id);
    assert.equal(rp.disconnected, false);
  });

  it('rejects a rejoin with the wrong token', async () => {
    const { gameId, players } = await setupGame({ phones: 1 });
    const fresh = await connect();
    fresh.emit('rejoin_game', { gameId, playerId: players[0].id, rejoinToken: 'wrong' });
    await once(fresh, 'rejoin_failed');
  });

  it('lets a refreshed host take control again', async () => {
    const { host, gameId, room } = await setupGame({ phones: 2 });
    host.disconnect();
    const newHost = await connect();
    newHost.emit('host_rejoin', { gameId });
    await once(newHost, 'host_rejoined');

    newHost.emit('sync_state', { gameId, currentPlayerIndex: 1 });
    await settle();
    assert.equal(room.currentPlayerIndex, 1);
  });
});

// ── Static files (B14) ────────────────────────────────────────────────────────

/** GET a raw path (no URL normalisation, so ../ reaches the server as sent). */
function rawGet(pathname) {
  return new Promise((resolve, reject) => {
    require('node:http').get(`${url}${pathname}`, { path: pathname }, res => {
      let body = '';
      res.on('data', c => { body += c; });
      res.on('end', () => resolve({ status: res.statusCode, body }));
    }).on('error', reject);
  });
}

describe('static files', () => {
  for (const p of ['/', '/index.html', '/player', '/player.html', '/js/game.js', '/js/utils.js',
                   '/css/styles.css', '/game_editions/editions.js',
                   '/game_editions/swab-quest/questions.csv', '/images/game-length-short.png']) {
    it(`serves ${p}`, async () => {
      assert.equal((await rawGet(p)).status, 200);
    });
  }

  for (const p of ['/server.js', '/package.json', '/CLAUDE.md', '/IMPROVEMENT-PLAN.md',
                   '/test/server.test.js', '/node_modules/express/package.json']) {
    it(`does not serve ${p}`, async () => {
      assert.equal((await rawGet(p)).status, 404);
    });
  }

  for (const p of ['/js/../server.js', '/css/..%2fserver.js', '/game_editions/../package.json']) {
    it(`blocks path traversal ${p}`, async () => {
      const { status, body } = await rawGet(p);
      assert.notEqual(status, 200);
      assert.doesNotMatch(body, /require\(|"dependencies"/);
    });
  }
});

// ── Player profile cleaning (B13) ─────────────────────────────────────────────

describe('player profile cleaning', () => {
  async function joinWith(profile) {
    const { gameId } = await setupGame({ phones: 0, start: false });
    const s = await connect();
    s.emit('join_game', { gameId, ...profile });
    return (await once(s, 'joined')).players.at(-1);
  }

  it('rejects a colour that is not a hex value', async () => {
    const p = await joinWith({ playerName: 'X', color: 'red" onmouseover="alert(1)' });
    assert.equal(p.color, '#4CAF50');
  });

  it('keeps a valid hex colour', async () => {
    assert.equal((await joinWith({ playerName: 'X', color: '#1565C0' })).color, '#1565C0');
  });

  it('limits name length and trims whitespace', async () => {
    const p = await joinWith({ playerName: `   ${'A'.repeat(50)}   ` });
    assert.equal(p.name, 'A'.repeat(20));
  });

  it('falls back to a default name when empty', async () => {
    assert.equal((await joinWith({ playerName: '   ' })).name, 'Player 1');
  });

  it('limits token length without splitting an emoji', async () => {
    assert.equal((await joinWith({ playerName: 'X', token: '🛡️' })).token, '🛡️');
    assert.equal(Array.from((await joinWith({ playerName: 'X', token: 'x'.repeat(100) })).token).length, 8);
  });

  it('cleans the host player profile too', async () => {
    const host = await connect();
    host.emit('host_game', { themeId: 't', isGMOnly: false,
      hostPlayer: { id: 0, name: 'H', token: 'H', color: 'javascript:alert(1)' } });
    const { gameId } = await once(host, 'hosted');
    assert.equal(rooms.get(gameId).players[0].color, '#4CAF50');
  });
});

// ── Disconnects (B6) ──────────────────────────────────────────────────────────

describe('disconnects', () => {
  it('tells the host when a phone disconnects', async () => {
    const { host, players } = await setupGame({ phones: 2 });
    const notice = once(host, 'player_disconnected');
    players[1].socket.disconnect();
    assert.equal((await notice).playerId, players[1].id);
  });

  it('sends host_left when a GM-only host disconnects', async () => {
    const { host, players } = await setupGame({ phones: 1 });
    const notice = once(players[0].socket, 'host_left');
    host.disconnect();
    await notice;
  });

  it('sends host_left when a host who is also playing disconnects', async () => {
    const { host, players } = await setupGame({ phones: 1, hostPlays: true });
    const notice = once(players[0].socket, 'host_left');
    host.disconnect();
    await notice;
  });
});
