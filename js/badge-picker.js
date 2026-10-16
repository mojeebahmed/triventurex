/**
 * badge-picker.js
 * Badge picker modal (token emoji + colour) for setup-screen players and the host player.
 */

// openHostBadgeModal reuses the badge modal but saves to host prefs
function openHostBadgeModal() {
  const name = document.getElementById('host-player-name')?.value?.trim() || 'Host';
  _badgeModalIndex = 'host';

  const p = _hostPlayerState || CONFIG.PLAYERS.defaults[0];
  const tokens = CONFIG.PLAYERS.tokens;
  const colors = CONFIG.PLAYERS.colors;

  document.getElementById('badge-modal-title').textContent = name + "'s Badge";
  _renderHostBadgePreview(p);

  document.getElementById('badge-modal-body').innerHTML = `
    <div class="picker-section">
      <span class="picker-label">Icon</span>
      <div class="picker-grid picker-tokens">
        ${tokens.map(t =>
          `<div class="picker-token ${t === p.token ? 'selected' : ''}"
               onclick="selectHostToken('${t}')">${t}</div>`
        ).join('')}
      </div>
    </div>
    <div class="picker-section">
      <span class="picker-label">Colour</span>
      <div class="picker-grid picker-colors">
        ${colors.map(c =>
          `<div class="picker-color ${c === p.color ? 'selected' : ''}"
               style="background:${c}" data-color="${c}"
               onclick="selectHostColor('${c}')"></div>`
        ).join('')}
      </div>
    </div>`;

  document.getElementById('badge-modal-overlay').classList.remove('hidden');
}

function _renderHostBadgePreview(p) {
  const previewEl = document.getElementById('badge-preview');
  if (!previewEl) return;
  const name = document.getElementById('host-player-name')?.value?.trim() || 'Host';
  previewEl.style.background = p.color;
  const emojiEl = previewEl.querySelector('.token-emoji');
  const initEl  = previewEl.querySelector('.token-initial');
  if (emojiEl) emojiEl.textContent = p.token;
  if (initEl)  initEl.textContent  = name.slice(0, 2).toUpperCase();
}

function selectHostToken(token) {
  _hostPlayerState = { ..._hostPlayerState, token };
  document.querySelectorAll('#badge-modal-body .picker-token').forEach(el => {
    el.classList.toggle('selected', el.textContent === token);
  });
  const badgeEl = document.getElementById('setup-badge-host');
  if (badgeEl) badgeEl.querySelector('.token-emoji').textContent = token;
  _renderHostBadgePreview(_hostPlayerState);
}

function selectHostColor(color) {
  _hostPlayerState = { ..._hostPlayerState, color };
  document.querySelectorAll('#badge-modal-body .picker-color').forEach(el => {
    el.classList.toggle('selected', el.dataset.color === color);
  });
  const badgeEl = document.getElementById('setup-badge-host');
  if (badgeEl) { badgeEl.style.background = color; }
  _renderHostBadgePreview(_hostPlayerState);
}

let _badgeModalIndex = null;

function openBadgeModal(index) {
  _badgeModalIndex = index;
  const p      = state.players[index];
  const tokens = CONFIG.PLAYERS.tokens;
  const colors = CONFIG.PLAYERS.colors;

  document.getElementById('badge-modal-title').textContent =
    (p.nameInput?.value?.trim() || `Player ${index + 1}`) + "'s Badge";

  _renderBadgePreview(p);

  document.getElementById('badge-modal-body').innerHTML = `
    <div class="picker-section">
      <span class="picker-label">Icon</span>
      <div class="picker-grid picker-tokens">
        ${tokens.map(t =>
          `<div class="picker-token ${t === p.token ? 'selected' : ''}"
               onclick="selectPlayerToken(${index},'${t}')">${t}</div>`
        ).join('')}
      </div>
    </div>
    <div class="picker-section">
      <span class="picker-label">Colour</span>
      <div class="picker-grid picker-colors">
        ${colors.map(c =>
          `<div class="picker-color ${c === p.color ? 'selected' : ''}"
               style="background:${c}" data-color="${c}"
               onclick="selectPlayerColor(${index},'${c}')"></div>`
        ).join('')}
      </div>
    </div>`;

  document.getElementById('badge-modal-overlay').classList.remove('hidden');
}

function closeBadgeModal(e) {
  if (e && e.target !== document.getElementById('badge-modal-overlay')) return;
  document.getElementById('badge-modal-overlay').classList.add('hidden');
  _badgeModalIndex = null;
}

function _renderBadgePreview(p) {
  const name    = p.nameInput?.value?.trim() || '';
  const initials = name.slice(0, 2).toUpperCase() || '?';
  const preview  = document.getElementById('badge-modal-preview');
  if (!preview) return;
  preview.style.background = p.color;
  preview.innerHTML = `
    <div class="token-emoji">${esc(p.token)}</div>
    <div class="token-initial">${esc(initials)}</div>`;
}

function selectPlayerToken(index, token) {
  if (!state.players[index]) return;
  state.players[index].token = token;
  const badge = document.getElementById(`setup-badge-${index}`);
  if (badge) badge.querySelector('.token-emoji').textContent = token;
  document.getElementById('badge-modal-body')?.querySelectorAll('.picker-token')
    .forEach(el => el.classList.toggle('selected', el.textContent === token));
  _renderBadgePreview(state.players[index]);
}

function selectPlayerColor(index, color) {
  if (!state.players[index]) return;
  state.players[index].color = color;
  const badge = document.getElementById(`setup-badge-${index}`);
  if (badge) badge.style.background = color;
  document.getElementById('badge-modal-body')?.querySelectorAll('.picker-color')
    .forEach(el => el.classList.toggle('selected', el.dataset.color === color));
  _renderBadgePreview(state.players[index]);
}

// ── Start Game ────────────────────────────────────────────────────────────────
