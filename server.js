/**
 * server.js
 * Triventurex V2 — Express + Socket.IO game server.
 * Serves the client files, manages game rooms and rolls the dice.
 *
 * STATE OWNERSHIP
 *  - The HOST (js/host/game.js) owns all game state: positions, scores, turn order,
 *    finish order, sitting out. It pushes it here with `sync_state`; the
 *    server stores it only to answer late joiners / rejoins and to validate rolls.
 *  - The SERVER owns connection state: socketId, rejoinToken, `disconnected`,
 *    room membership, plus dice rolls. `sync_state` never overwrites these.
 *  - Server-only fields (SERVER_ONLY_FIELDS) are never sent to any client.
 */

const express   = require('express');
const http      = require('http');
const { Server } = require('socket.io');
const path      = require('path');
const os        = require('os');
const { indexAfterRemoval } = require('./js/shared/turn.js'); // shared with the host

const app    = express();
const server = http.createServer(app);
const io     = new Server(server);

const PORT = process.env.PORT || 3000;

// ── Static file serving ───────────────────────────────────────────────────────
// Allowlist: only the files the host and player pages need. Everything else in
// the project folder (server.js, docs, package.json, node_modules, test/) is
// NOT served.
const PUBLIC_DIRS = ['css', 'js', 'game_editions', 'images', 'tools'];
for (const dir of PUBLIC_DIRS) {
  app.use(`/${dir}`, express.static(path.join(__dirname, dir)));
}
app.get(['/', '/index.html'],      (req, res) => res.sendFile(path.join(__dirname, 'index.html')));
app.get(['/player', '/player.html'], (req, res) => res.sendFile(path.join(__dirname, 'player.html')));

// ── Room state ────────────────────────────────────────────────────────────────
// Map<gameId, RoomState>
const rooms = new Map();

/**
 * Generate a short game ID like TX-1A2B3C4D-XY9Z
 */
function generateGameId() {
  // 4-digit numeric code, unique among active rooms
  let id;
  do { id = String(Math.floor(1000 + Math.random() * 9000)); } while (rooms.has(id));
  return id;
}

/**
 * Roll a standard 6-sided die on the server.
 */
function rollDie() {
  return Math.floor(Math.random() * 6) + 1;
}

/**
 * Clean a player profile sent by a client: bounded name and token, and a
 * colour that must be a hex value (it ends up inside style="" attributes).
 * Clients also escape on render — this is the second layer.
 */
function cleanProfile({ name, token, color } = {}, fallbackName) {
  return {
    name:  String(name ?? '').trim().slice(0, 20) || fallbackName,
    // Array.from splits by code point so multi-code-point emoji aren't cut in half
    token: Array.from(String(token ?? '').trim()).slice(0, 8).join('') || '●',
    color: /^#[0-9a-f]{3,8}$/i.test(String(color ?? '')) ? color : '#4CAF50',
  };
}

// Fields that exist only on the server — stripped from everything sent out.
// rejoinToken in particular lets whoever holds it take over that player's seat.
const SERVER_ONLY_FIELDS = ['socketId', 'rejoinToken', 'awaitingHostSync'];

/** A player as clients may see it (no server-only fields). */
function publicPlayer(p) {
  const out = { ...p };
  for (const f of SERVER_ONLY_FIELDS) delete out[f];
  return out;
}
const publicPlayers = players => players.map(publicPlayer);

/** The state slice clients receive in state_update / rejoined. */
function publicState(room) {
  return {
    playerStates:       publicPlayers(room.players),
    currentPlayerIndex: room.currentPlayerIndex,
    turnPhase:          room.turnPhase,
    finishCount:        room.finishCount,
    phase:              room.phase,
  };
}

/** Take a player out of the room, keeping currentPlayerIndex on the same player. */
function removeFromRoom(room, idx) {
  const [removed] = room.players.splice(idx, 1);
  room.currentPlayerIndex = indexAfterRemoval(room.currentPlayerIndex, idx, room.players.length);
  return removed;
}

/**
 * Get the local network IP so players can connect.
 */
function getLocalIP() {
  const ifaces = os.networkInterfaces();
  for (const name of Object.keys(ifaces)) {
    for (const iface of ifaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return 'localhost';
}

// ── Socket.IO events ──────────────────────────────────────────────────────────

io.on('connection', (socket) => {
  console.log(`[connect]    socket=${socket.id}`);

  // ── host_game ──────────────────────────────────────────────────────────────
  socket.on('host_game', ({ editionId, gameLength, pathIndex, hostPlayer, isGMOnly }) => {
    const gameId = generateGameId();
    console.log(`[host_game]  socket=${socket.id} gameId=${gameId} edition=${editionId} length=${gameLength} gmOnly=${isGMOnly}`);

    const players = [];
    if (!isGMOnly && hostPlayer) {
      players.push({
        id:                   hostPlayer.id ?? 0,
        socketId:             socket.id,
        ...cleanProfile(hostPlayer, 'Host'),
        position:             0,
        score:                0,
        finished:             false,
        skipNextTurn:         false,
        hasExtraTurn:         false,
        protectedFromBadDeed: false,
        finishOrder:          null,
        inactive:             false,
        disconnected:         false,
      });
    }

    const room = {
      gameId,
      hostSocketId: socket.id,
      hostPlayerId: players[0]?.id ?? null,   // host's own player entry (if playing)
      isGMOnly,
      editionId,
      gameLength,
      pathIndex,
      phase:               'lobby',
      players,
      currentPlayerIndex:  0,
      turnPhase:           'roll',
      finishCount:         0,
      history:             [],
    };

    rooms.set(gameId, room);
    socket.join(gameId);
    socket.emit('hosted', { gameId });
    console.log(`[host_game]  room created gameId=${gameId} players=${players.length}`);
  });

  // ── join_game ──────────────────────────────────────────────────────────────
  socket.on('join_game', ({ gameId, playerName, token, color }) => {
    console.log(`[join_game]  socket=${socket.id} gameId=${gameId} name=${playerName}`);

    const room = rooms.get(gameId);
    if (!room) {
      socket.emit('error', { message: `Game "${gameId}" not found.` });
      return;
    }

    // Assign next available id
    const existingIds = room.players.map(p => p.id);
    let playerId = 0;
    while (existingIds.includes(playerId)) playerId++;

    const player = {
      id:                   playerId,
      socketId:             socket.id,
      ...cleanProfile({ name: playerName, token, color }, `Player ${playerId + 1}`),
      position:             0,
      score:                0,
      finished:             false,
      skipNextTurn:         false,
      hasExtraTurn:         false,
      protectedFromBadDeed: false,
      finishOrder:          null,
      inactive:             false,
      disconnected:         false,
    };

    const rejoinToken = Math.random().toString(36).slice(2, 10);
    player.rejoinToken = rejoinToken;
    // Until a host sync includes this player, a sync with an older player list
    // must not drop them (they joined after the host built that list)
    player.awaitingHostSync = true;

    room.players.push(player);
    socket.join(gameId);
    socket.data.gameId   = gameId;
    socket.data.playerId = playerId;

    socket.emit('joined', {
      gameId,
      playerId,
      phase:       room.phase,
      players:     publicPlayers(room.players),
      rejoinToken,                              // only ever sent to its owner
    });

    io.to(gameId).emit('player_joined', {
      player:  publicPlayer(player),
      players: publicPlayers(room.players),
    });

    // If game already started, send current state immediately
    if (room.phase === 'playing') socket.emit('state_update', publicState(room));

    console.log(`[join_game]  playerId=${playerId} joined gameId=${gameId} total=${room.players.length}`);
  });

  // ── start_game ─────────────────────────────────────────────────────────────
  socket.on('start_game', ({ gameId }) => {
    console.log(`[start_game] socket=${socket.id} gameId=${gameId}`);

    const room = rooms.get(gameId);
    if (!room) { socket.emit('error', { message: 'Game not found.' }); return; }
    if (socket.id !== room.hostSocketId) { socket.emit('error', { message: 'Only the host can start.' }); return; }

    room.phase = 'playing';
    io.to(gameId).emit('game_started', { players: publicPlayers(room.players) });
    console.log(`[start_game] gameId=${gameId} started with ${room.players.length} players`);
  });

  // ── roll ───────────────────────────────────────────────────────────────────
  socket.on('roll', ({ gameId }) => {
    console.log(`[roll]       socket=${socket.id} gameId=${gameId}`);

    const room = rooms.get(gameId);
    if (!room) { socket.emit('error', { message: 'Game not found.' }); return; }

    // Accept from host OR the current player's socket
    const currentPlayer = room.players[room.currentPlayerIndex];
    const isHost        = socket.id === room.hostSocketId;
    const isCurrent     = currentPlayer && socket.id === currentPlayer.socketId;

    if (!isHost && !isCurrent) {
      socket.emit('error', { message: 'Not your turn.' });
      return;
    }

    // A phone may only roll at the start of a turn — blocks double-taps and
    // late rolls from starting a second, concurrent turn. The host is the
    // game authority and has already checked its own turnPhase, so it is
    // always allowed (also avoids a stuck host if this flag is ever stale).
    if (!isHost && room.turnPhase !== 'roll') {
      socket.emit('error', { message: 'Turn already in progress.' });
      return;
    }
    // Host's next sync_state (end of turn / undo) sets this back to 'roll'
    room.turnPhase = 'resolving';

    const roll = rollDie();
    console.log(`[roll]       gameId=${gameId} result=${roll} player=${currentPlayer?.name}`);
    io.to(gameId).emit('roll_result', { roll, playerId: currentPlayer?.id });
  });

  // ── manual_roll — host sets a specific dice value (physical dice play) ────────
  // Broadcasts roll_result only to player screens (not back to host) so the host
  // can process the roll locally without waiting and without double-processing.
  socket.on('manual_roll', ({ gameId, roll }) => {
    const room = rooms.get(gameId);
    if (!room) { socket.emit('error', { message: 'Game not found.' }); return; }
    if (socket.id !== room.hostSocketId) { socket.emit('error', { message: 'Only the host can set a manual roll.' }); return; }
    const n = Math.min(6, Math.max(1, parseInt(roll, 10) || 1));
    room.turnPhase = 'resolving'; // phones can't roll while the host resolves this turn
    const currentPlayer = room.players[room.currentPlayerIndex];
    console.log(`[manual_roll] gameId=${gameId} result=${n} player=${currentPlayer?.name}`);
    socket.to(gameId).emit('roll_result', { roll: n, playerId: currentPlayer?.id });
  });

  // ── sync_state ─────────────────────────────────────────────────────────────
  socket.on('sync_state', ({ gameId, playerStates, currentPlayerIndex, turnPhase, finishCount, phase }) => {
    console.log(`[sync_state] socket=${socket.id} gameId=${gameId} turnPhase=${turnPhase}`);

    const room = rooms.get(gameId);
    if (!room) return;
    if (socket.id !== room.hostSocketId) return; // only host can sync

    if (playerStates) {
      // Game fields come from the host; connection fields stay the server's
      const hostIds = new Set(playerStates.map(ps => ps.id));
      const synced = playerStates.map(ps => {
        const existing = room.players.find(rp => rp.id === ps.id);
        return {
          ...ps,
          socketId:         existing?.socketId    ?? null,
          rejoinToken:      existing?.rejoinToken ?? null,
          disconnected:     existing?.disconnected ?? false,
          awaitingHostSync: false,
        };
      });
      // Joined after the host built this list — keep them; the host's
      // player_joined handler will include them in its next sync
      const unseen = room.players.filter(rp => rp.awaitingHostSync && !hostIds.has(rp.id));
      room.players = [...synced, ...unseen];
    }
    if (currentPlayerIndex !== undefined) room.currentPlayerIndex = currentPlayerIndex;
    if (turnPhase)                        room.turnPhase          = turnPhase;
    if (finishCount !== undefined)        room.finishCount        = finishCount;
    if (phase)                            room.phase              = phase;

    // Broadcast the merged state to all clients EXCEPT the host
    socket.to(gameId).emit('state_update', publicState(room));
  });

  // ── remove_player ──────────────────────────────────────────────────────────
  socket.on('remove_player', ({ gameId, playerId }) => {
    console.log(`[remove]     socket=${socket.id} gameId=${gameId} playerId=${playerId}`);

    const room = rooms.get(gameId);
    if (!room) return;
    if (socket.id !== room.hostSocketId) return;

    const idx = room.players.findIndex(p => p.id === playerId);
    if (idx !== -1) {
      const removed = removeFromRoom(room, idx);
      // Tell everyone (incl. the removed phone), then stop sending that phone
      // room broadcasts. No state_update here — the host owns turn order and
      // syncs the result itself (see player_removed in game.js).
      io.to(gameId).emit('player_removed', { playerId });
      io.sockets.sockets.get(removed.socketId)?.leave(gameId);
    }
  });

  // ── rejoin_game ────────────────────────────────────────────────────────────
  socket.on('rejoin_game', ({ gameId, playerId, rejoinToken }) => {
    const room = rooms.get(gameId);
    if (!room) { socket.emit('rejoin_failed', { msg: 'Game not found or expired.' }); return; }

    const player = room.players.find(p => p.id === playerId && p.rejoinToken === rejoinToken);
    if (!player) { socket.emit('rejoin_failed', { msg: 'Invalid session.' }); return; }

    // Update socket ID
    player.socketId      = socket.id;
    player.disconnected  = false;
    socket.join(gameId);
    socket.data.gameId   = gameId;
    socket.data.playerId = playerId;

    socket.emit('rejoined', {
      gameId,
      playerId,
      players: publicPlayers(room.players),
      ...publicState(room),
    });

    // Notify others that player reconnected
    socket.to(gameId).emit('player_reconnected', { playerId, playerName: player.name });
    console.log(`[rejoin]     playerId=${playerId} rejoined gameId=${gameId}`);
  });

  // ── host_rejoin ────────────────────────────────────────────────────────────
  socket.on('host_rejoin', ({ gameId }) => {
    const room = rooms.get(gameId);
    if (!room) { socket.emit('rejoin_failed', { msg: 'Game session expired.' }); return; }
    room.hostSocketId = socket.id;
    socket.join(gameId);
    socket.data.gameId  = gameId;
    socket.data.isHost  = true;

    // A playing host is also a player — reconnect that entry too
    const hostPlayer = room.players.find(p => p.id === room.hostPlayerId);
    if (hostPlayer) {
      hostPlayer.socketId     = socket.id;
      hostPlayer.disconnected = false;
      socket.to(gameId).emit('player_reconnected', { playerId: hostPlayer.id, playerName: hostPlayer.name });
    }
    socket.emit('host_rejoined', { gameId, players: publicPlayers(room.players), phase: room.phase });
    console.log(`[host_rejoin] host rejoined gameId=${gameId}`);
  });

  // ── leave_game — player voluntarily leaves ────────────────────────────────
  socket.on('leave_game', ({ gameId }) => {
    const room = rooms.get(gameId || socket.data.gameId);
    if (!room) return;
    const idx = room.players.findIndex(p => p.socketId === socket.id);
    const player = room.players[idx];
    if (player) {
      removeFromRoom(room, idx);
      socket.leave(room.gameId);
      io.to(room.gameId).emit('player_removed', { playerId: player.id, players: publicPlayers(room.players) });
      console.log(`[leave_game] ${player.name} left ${room.gameId}`);
    }
  });

  // ── Host → players relays (turn outcome, space card) ──────────────────────
  // Only the host may send these — otherwise any phone could fake a card or
  // an activity-feed entry on everyone else's screen.
  const fromHost = gameId => rooms.get(gameId)?.hostSocketId === socket.id;

  socket.on('turn_result', ({ gameId, ...data }) => {
    if (fromHost(gameId)) socket.to(gameId).emit('turn_result', data);
  });

  socket.on('space_card', ({ gameId, ...cardData }) => {
    if (fromHost(gameId)) socket.to(gameId).emit('space_card', cardData);
  });

  socket.on('space_card_done', ({ gameId }) => {
    if (fromHost(gameId)) socket.to(gameId).emit('space_card_done');
  });

  // ── disconnect ─────────────────────────────────────────────────────────────
  socket.on('disconnect', () => {
    console.log(`[disconnect] socket=${socket.id}`);

    for (const [gameId, room] of rooms.entries()) {
      // Check host first — a playing host is ALSO in room.players, so the
      // player branch alone would hide the host_left notification.
      const isHost = room.hostSocketId === socket.id;
      if (isHost) {
        console.log(`[disconnect] HOST disconnected gameId=${gameId}`);
        io.to(gameId).emit('host_left', { msg: 'The host has left the game.' });
      }

      const player = room.players.find(p => p.socketId === socket.id);
      if (player) {
        player.disconnected = true;
        console.log(`[disconnect] player=${player.name} gameId=${gameId}`);
        io.to(gameId).emit('player_disconnected', {
          playerId:   player.id,
          playerName: player.name,
        });
      }

      if (isHost || player) break;
    }
  });
});

// ── Start server ──────────────────────────────────────────────────────────────
// Only listen when run directly (`node server.js`). Tests require() this file
// and start it themselves on a random port.
module.exports = { server, io, rooms };

if (require.main === module) server.listen(PORT, () => {
  const localIP = getLocalIP();
  console.log('');
  console.log('  ╔══════════════════════════════════════════════╗');
  console.log('  ║           Triventurex V2 Server              ║');
  console.log('  ╚══════════════════════════════════════════════╝');
  console.log('');
  console.log(`  Host (this device):   http://localhost:${PORT}`);
  console.log(`  Players (same Wi-Fi): http://${localIP}:${PORT}/player.html`);
  console.log('');
  console.log('  1. Open the Host URL above in your browser to set up a game.');
  console.log('  2. Players open the Player URL on their phones (same Wi-Fi).');
  console.log('  3. Enter the Game ID shown on the host screen to join.');
  console.log('');
});
