/**
 * display.js
 * TV display (G16) — display.html, opened as /display?game=ID on a second
 * screen. Read-only: it shows what the host sends (board, tokens, scores,
 * dice, timer and the open card with its secrets already removed) and the
 * lobby list from the server. Nothing here can change the game.
 */

let _gameId    = null;
let _editionId = null;
let _board     = null;
let _players   = [];
let _hopMs     = 400;

// The board fills the TV like the host's presentation mode (viewport.js asks)
function isPresenting() { return true; }

function showDisplayScreen(id) {
  document.querySelectorAll('.d-screen').forEach(s => s.classList.toggle('active', s.id === id));
}

function joinDisplay(id) {
  const gameId = String(id || '').replace(/\D/g, '').slice(0, 4);
  if (gameId.length !== 4) { document.getElementById('d-join-error').textContent = 'A Game ID has 4 digits.'; return; }
  _gameId = gameId;
  history.replaceState(null, '', `${location.pathname}?game=${gameId}`);   // a refresh comes back here
  TX_NET.joinDisplay(gameId);
}

// ── Edition ─────────────────────────────────────────────────────────────────────

/** Load an edition's config.js once and apply its labels, colours and background. */
async function _useEdition(editionId) {
  if (!editionId || editionId === _editionId) return;
  window.EDITION_CONFIG = null;
  await new Promise(resolve => {
    const el = document.createElement('script');
    el.src = `game_editions/${editionId}/config.js`;
    el.onload = el.onerror = resolve;
    document.head.appendChild(el);
  });
  mergeEditionConfig(CONFIG, window.EDITION_CONFIG);
  applyEditionColors(CONFIG);
  _editionId = editionId;
  const g = CONFIG.GAME || {};
  document.title = `📺 ${g.editionName || g.engineName || 'Triventurex'}`;
  document.getElementById('d-end-msg').textContent = g.endScreenMessage || '';
}

// ── Lobby ───────────────────────────────────────────────────────────────────────

function _chip(p) {
  return `<div class="d-chip"><div class="score-token" style="background:${esc(p.color)}">
            <div class="token-emoji">${esc(p.token || '●')}</div></div>${esc(p.name)}</div>`;
}

function _renderLobby(players) {
  document.getElementById('d-lobby-players').innerHTML = players.length
    ? players.map(_chip).join('')
    : '<div class="d-sub">Waiting for players…</div>';
  showDisplayScreen('d-lobby');
}

function _renderJoinInfo(gameId, joinUrls) {
  const url = joinUrls?.[0] || `${location.origin}/player?game=${gameId}`;
  const qr = qrcode(0, 'M');
  qr.addData(url);
  qr.make();
  document.getElementById('d-qr').innerHTML = qr.createSvgTag({ cellSize: 6, margin: 2, scalable: true });
  document.getElementById('d-url').textContent = url.replace(/^https?:\/\//, '').replace(/\?.*$/, '');
  document.getElementById('d-gameid').textContent = gameId;
}

// ── Game ────────────────────────────────────────────────────────────────────────

async function _onGame({ editionId, board, hopMs }) {
  await _useEdition(editionId);
  _board = board;
  _hopMs = hopMs ?? _hopMs;
  _players = [];
  showDisplayScreen('d-game');
  renderBoard(_board, []);
  fitBoardInView();
}

/** Players + turn. The host sends one per token hop, so a move shows step by step. */
function _onLive({ players, currentPlayerIndex, turnPhase, phase }) {
  if (!_board) return;
  const before = new Map(_players.map(p => [p.id, p.position]));
  const moved  = players.find(p => before.has(p.id) && before.get(p.id) !== p.position);
  _players = players;

  updateBoardTokens(players, moved ? moved.id : null);
  const current = players[currentPlayerIndex] || players[0];
  highlightSpace((moved || current)?.position ?? 0);

  if (current) {
    const tok = document.getElementById('d-current-token');
    tok.style.backgroundColor = current.color;
    tok.innerHTML = `<div class="token-emoji">${esc(current.token || '●')}</div>
                     <div class="token-initial">${esc((current.name || '?').slice(0, 2).toUpperCase())}</div>`;
    document.getElementById('d-current-name').textContent = current.name;
    document.getElementById('d-current-phase').textContent = turnPhase === 'roll' ? 'Roll the dice' : 'Playing their turn…';
  }

  const pts = CONFIG.GAME?.pointsName ?? 'pts';
  document.getElementById('d-scoreboard').innerHTML = getSortedPlayers(players).map(p => `
    <div class="score-row ${p.id === current?.id ? 'is-current' : ''}">
      <div class="score-token" style="background:${esc(p.color)}">
        <div class="token-emoji">${esc(p.token || '●')}</div>
        <div class="token-initial">${esc((p.name || '?').slice(0, 2).toUpperCase())}</div>
      </div>
      <div class="score-name">${esc(p.name)}</div>
      <div>
        <div class="score-points">${p.score} ${esc(pts)}</div>
        <div class="score-position">Space ${p.position}${p.finished ? ' ✅' : ''}${p.inactive ? ' 💤' : ''}</div>
      </div>
    </div>`).join('');

  if (phase === 'ended') _showEnd(players);
  else if (document.getElementById('d-end').classList.contains('active')) showDisplayScreen('d-game');
}

function _showEnd(players) {
  const pts = CONFIG.GAME?.pointsName ?? 'pts';
  const medals = ['🥇', '🥈', '🥉'];
  document.getElementById('d-podium').innerHTML = getSortedPlayers(players).map((p, i) => `
    <div class="d-chip"><span class="d-place">${medals[i] ?? i + 1}</span>
      <div class="score-token" style="background:${esc(p.color)}"><div class="token-emoji">${esc(p.token || '●')}</div></div>
      ${esc(p.name)}<span class="d-pts">${p.score} ${esc(pts)}</span></div>`).join('');
  showDisplayScreen('d-end');
}

/** The host's open card (secrets already removed by the host), or null. */
function _onCard(card) {
  const overlay = document.getElementById('modal-overlay');
  if (!card) { overlay.classList.add('hidden'); return; }
  if (card.accent) document.documentElement.style.setProperty('--modal-accent', card.accent);
  document.getElementById('modal-icon').textContent  = card.icon || '';
  document.getElementById('modal-title').textContent = card.title || '';
  document.getElementById('modal-content').innerHTML = card.content || '';
  overlay.classList.remove('hidden');
}

let _rollSeq = 0;
async function _onRoll({ roll, playerId }) {
  const seq = ++_rollSeq;
  const p = _players.find(pl => pl.id === playerId);
  const overlay = document.getElementById('dice-overlay');
  document.getElementById('dice-overlay-num').textContent = '';
  document.getElementById('dice-overlay-name').textContent = p?.name || '';
  document.getElementById('dice-overlay-name').style.color = p?.color || '';
  overlay.classList.add('visible');
  await animateDieInto(document.getElementById('dice-overlay-face'), roll, { sizeClass: 'die-xl' });
  if (seq !== _rollSeq) return;
  document.getElementById('dice-overlay-num').textContent = roll;
  document.getElementById('d-roll-die').innerHTML = renderDie(roll, 'die-md');
  document.getElementById('d-roll-text').textContent = `${p?.name || 'Someone'} rolled ${roll}`;
  setTimeout(() => { if (seq === _rollSeq) overlay.classList.remove('visible'); }, 1100);
}

function _onTimer({ remaining, duration, running }) {
  const panel = document.getElementById('d-timer');
  panel.classList.toggle('idle', !running && remaining === duration);
  const pct = duration > 0 ? remaining / duration : 0;
  const mins = Math.floor(remaining / 60), secs = remaining % 60;
  document.getElementById('d-timer-time').textContent = mins > 0 ? `${mins}:${String(secs).padStart(2, '0')}` : `${remaining}s`;
  const bar = document.getElementById('timer-bar');
  bar.style.width = (pct * 100) + '%';
  bar.style.background = pct > 0.5 ? '#43A047' : pct > 0.25 ? '#FF9800' : '#E53935';
}

function _message(text) {
  document.getElementById('d-msg-text').textContent = text || '';
  document.getElementById('d-msg').classList.toggle('visible', !!text);
}

// ── Socket ──────────────────────────────────────────────────────────────────────

TX_NET.on('connect', () => { if (_gameId) TX_NET.joinDisplay(_gameId); });   // also after a reconnect

TX_NET.on('display_joined', async ({ gameId, joinUrls, editionId, phase }) => {
  _message('');
  _renderJoinInfo(gameId, joinUrls);
  await _useEdition(editionId);
  if (phase === 'lobby') showDisplayScreen('d-lobby');
});

TX_NET.on('display_failed', ({ msg } = {}) => {
  showDisplayScreen('d-join');
  document.getElementById('d-join-error').textContent = msg || 'Game not found.';
});

// One at a time, in order: 'game' loads the edition first, the 'live' right
// behind it must wait for the board
let _queue = Promise.resolve();
TX_NET.on('display', msg => { _queue = _queue.then(() => _onDisplay(msg)).catch(e => console.error(e)); });

async function _onDisplay({ kind, data } = {}) {
  switch (kind) {
    case 'lobby':  _renderLobby(data.players || []); break;
    case 'game':   await _onGame(data); break;
    case 'live':   _onLive(data); break;
    case 'card':   _onCard(data); break;
    case 'roll':   _onRoll(data); break;          // not awaited: the card may follow
    case 'timer':  _onTimer(data); break;
    case 'host':   _message(data.gone ? 'The host disconnected — waiting for them to come back…' : ''); break;
    case 'closed': _message('The game has ended. Thanks for playing!'); break;
  }
}

window.addEventListener('resize', () => { if (_board) fitBoardInView(); });

// Start: ?game=ID from the host's "Open TV display" link, otherwise ask
(() => {
  const id = new URLSearchParams(location.search).get('game');
  if (!TX_NET.connect()) { _message('Open this page from the game server (node server.js).'); return; }
  if (id) joinDisplay(id); else showDisplayScreen('d-join');
})();
