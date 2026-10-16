/**
 * badge-picker.js
 * Badge picker modal (token emoji + colour) for setup-screen players and the host player.
 * One implementation for both — the "target" decides where the choice is stored.
 */

// What the open modal is editing: a local setup-row index (number) or 'host'
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

/** Open the picker for a local setup row (index) or the host player ('host'). */
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
          `<div class="picker-token ${tok === p.token ? 'selected' : ''}"
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

function selectBadgeToken(token) {
  if (_badgeModalTarget === null) return;
  const t = _badgeTarget();
  t.set({ token });
  const badge = t.setupEl();
  if (badge) badge.querySelector('.token-emoji').textContent = token;
  document.getElementById('badge-modal-body')?.querySelectorAll('.picker-token')
    .forEach(el => el.classList.toggle('selected', el.textContent === token));
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
