/**
 * badge-picker.js
 * Badge picker modal (token emoji + colour) for setup-screen players and the host player.
 * One implementation for both — the "target" decides where the choice is stored.
 */

// What the open modal is editing: a local setup-row index (number), 'host',
// or a seat in a network lobby / running game: { playerId, where: 'lobby' | 'game' }
let _badgeModalTarget = null;

/**
 * Adapter for the current target, so the modal code doesn't care which it is.
 *   badge()   → { token, color } currently chosen
 *   set(p)    → store a partial change ({ token } or { color })
 *   typed()   → name typed in that row's input ('' if none)
 *   label()   → name for the modal title (typed name or a default)
 *   setupEl() → the badge element on the setup screen
 */
function _badgeTarget() {
  if (typeof _badgeModalTarget === 'object') {
    const { playerId, where } = _badgeModalTarget;
    const find = () => (where === 'game' ? state.players : _lobbyPlayers).find(p => p.id === playerId) || {};
    return {
      badge:   find,
      set:     patch => _setSeatBadge(playerId, where, patch),
      typed:   () => find().name || '',
      label:   () => find().name || 'Player',
      setupEl: () => null,
    };
  }
  if (_badgeModalTarget === 'host') {
    const typed = () => document.getElementById('host-player-name')?.value?.trim() || '';
    return {
      badge:   () => _hostPlayerState || CONFIG.PLAYERS.defaults[0],
      set:     patch => { _hostPlayerState = { ..._hostPlayerState, ...patch }; },
      typed,
      label:   () => typed() || 'Host',
      setupEl: () => document.getElementById('setup-badge-host'),
    };
  }
  const i = _badgeModalTarget;
  const typed = () => state.players[i]?.nameInput?.value?.trim() || '';
  return {
    badge:   () => state.players[i],
    set:     patch => Object.assign(state.players[i], patch),
    typed,
    label:   () => typed() || `Player ${i + 1}`,
    setupEl: () => document.getElementById(`setup-badge-${i}`),
  };
}

/** Open the picker for a local setup row (index), the host player ('host') or a seat ({ playerId, where }). */
function openBadgeModal(target) {
  _badgeModalTarget = target;
  const t = _badgeTarget();
  const p = t.badge();
  const tokens = CONFIG.PLAYERS.tokens;
  const colors = CONFIG.PLAYERS.colors;

  document.getElementById('badge-modal-title').textContent = t.label() + "'s Badge";
  _renderBadgePreview();

  document.getElementById('badge-modal-body').innerHTML = `
    <div class="picker-section">
      <span class="picker-label">Icon</span>
      <div class="picker-grid picker-tokens">
        ${tokens.map(tok =>
          `<div class="picker-token ${tok === p.token ? 'selected' : ''}" data-token="${esc(tok)}"
               onclick="selectBadgeToken('${tok}')">${tok}</div>`
        ).join('')}
      </div>
    </div>
    <div class="picker-section">
      <span class="picker-label">Colour</span>
      <div class="picker-grid picker-colors">
        ${colors.map(c =>
          `<div class="picker-color ${c === p.color ? 'selected' : ''}"
               style="background:${c}" data-color="${c}"
               onclick="selectBadgeColor('${c}')"></div>`
        ).join('')}
      </div>
    </div>`;

  document.getElementById('badge-modal-overlay').classList.remove('hidden');
}

function closeBadgeModal(e) {
  if (e && e.target !== document.getElementById('badge-modal-overlay')) return;
  document.getElementById('badge-modal-overlay').classList.add('hidden');
  _badgeModalTarget = null;
}

/** Large preview at the top of the modal: emoji + initials on the chosen colour. */
function _renderBadgePreview() {
  const preview = document.getElementById('badge-modal-preview');
  if (!preview || _badgeModalTarget === null) return;
  const t = _badgeTarget();
  const p = t.badge();
  preview.style.background = p.color;
  preview.innerHTML = `
    <div class="token-emoji">${esc(p.token)}</div>
    <div class="token-initial">${esc(t.typed().slice(0, 2).toUpperCase() || '?')}</div>`;
}

/** GM panel: change the badge of the player picked in the GM player list (any game). */
function gmChangeBadge() {
  const p = getGMSelectedPlayer();
  if (p) openBadgeModal({ playerId: p.id, where: 'game' });
}

/**
 * Store a badge change for a seat. In a game the host owns the players: change
 * them, redraw, save and sync (sync_state carries token + colour to the phones).
 * In the network lobby there's no game yet — the server keeps the list.
 */
function _setSeatBadge(playerId, where, patch) {
  // The host's own player: remember the new badge for next time too
  const hostId = where === 'game' ? state.hostPlayerId : _pendingNetworkSetup?.hostPlayer?.id;
  if (hostId != null && playerId === hostId) {
    _hostPlayerState = { ..._hostPlayerState, ...patch };
    const seat = (where === 'game' ? state.players : _lobbyPlayers).find(pl => pl.id === playerId);
    if (seat) _saveHostPlayerPref(seat.name, patch.color ?? seat.color, patch.token ?? seat.token);
  }
  if (where === 'game') {
    const p = state.players.find(pl => pl.id === playerId);
    if (!p) return;
    Object.assign(p, patch);
    updateBoardTokens(state.players);
    updateScoreboard(state.players);
    refreshUI();
    if (_isNetworkGame) _renderGMNetworkPlayers(state.players);
    saveGame();
    _syncStateToServer();
    return;
  }
  const p = _lobbyPlayers.find(pl => pl.id === playerId);
  if (p) Object.assign(p, patch);
  _renderLobbyPlayers(_lobbyPlayers);
  if (_networkGameId) TX_NET.updatePlayer(_networkGameId, playerId, patch);
}

function selectBadgeToken(token) {
  if (_badgeModalTarget === null) return;
  const t = _badgeTarget();
  t.set({ token });
  const badge = t.setupEl();
  if (badge) badge.querySelector('.token-emoji').textContent = token;
  document.getElementById('badge-modal-body')?.querySelectorAll('.picker-token')
    .forEach(el => el.classList.toggle('selected', el.dataset.token === token));   // emoji are drawn as images, so not textContent
  _renderBadgePreview();
}

function selectBadgeColor(color) {
  if (_badgeModalTarget === null) return;
  const t = _badgeTarget();
  t.set({ color });
  const badge = t.setupEl();
  if (badge) badge.style.background = color;
  document.getElementById('badge-modal-body')?.querySelectorAll('.picker-color')
    .forEach(el => el.classList.toggle('selected', el.dataset.color === color));
  _renderBadgePreview();
}
