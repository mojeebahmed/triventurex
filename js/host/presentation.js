/**
 * presentation.js
 * 📺 Presentation mode (G15): one button → full screen for a TV mirrored from
 * the laptop. The board fills the screen, the sidebar shows only what players
 * need (current player, dice, timer, scoreboard) drawn bigger, and the GM
 * tools (GM panel, game log, manual dice, timer buttons) wait behind a small
 * floating ⚙️. Works offline — it's only layout (body.presenting) + the
 * browser's Fullscreen API. Settings: CONFIG.PRESENTATION.
 */

let _cursorTimer = null;

const isPresenting = () => document.body.classList.contains('presenting');

function enterPresentation() {
  if (isPresenting()) return;
  document.body.style.setProperty('--present-scale', CONFIG.PRESENTATION?.scale ?? 1.35);
  document.body.classList.add('presenting');
  // Full screen when the browser allows it; without it the layout still works
  // (e.g. the browser is already full screen with F11).
  document.documentElement.requestFullscreen?.().catch(() => {});
  _wakeCursor();
  _refit();
}

function exitPresentation() {
  if (!isPresenting()) return;
  document.body.classList.remove('presenting', 'present-gm-open', 'present-idle');
  clearTimeout(_cursorTimer);
  _syncGMButton();
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  _refit();
}

const togglePresentation = () => (isPresenting() ? exitPresentation() : enterPresentation());

/** ⚙️ — show / hide the GM tools in the sidebar (they open expanded). */
function togglePresentGM() {
  const open = document.body.classList.toggle('present-gm-open');
  if (open) document.getElementById('gm-controls')?.classList.remove('hidden');
  _syncGMButton();
}

function _syncGMButton() {
  document.getElementById('present-gm-btn')
    ?.setAttribute('aria-pressed', String(document.body.classList.contains('present-gm-open')));
}

/** The viewport changed size: fit the board again once the layout has settled. */
function _refit() {
  if (document.getElementById('game-screen')?.classList.contains('active')) fitBoardInView();
}

/** Hide the mouse pointer on the TV after a while without moving. */
function _wakeCursor() {
  document.body.classList.remove('present-idle');
  clearTimeout(_cursorTimer);
  const ms = CONFIG.PRESENTATION?.cursorHideMs ?? 0;
  if (ms > 0 && isPresenting()) _cursorTimer = setTimeout(() => document.body.classList.add('present-idle'), ms);
}

function initPresentation() {
  // Esc in full screen is taken by the browser — leaving full screen we
  // entered also leaves presentation mode.
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && isPresenting()) exitPresentation();
    else _refit();
  });
  window.addEventListener('resize', () => { if (isPresenting()) _refit(); });
  document.addEventListener('mousemove', () => { if (isPresenting()) _wakeCursor(); });

  document.addEventListener('keydown', e => {
    if (!document.getElementById('game-screen')?.classList.contains('active')) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.target.closest?.('input, textarea, select')) return;
    const key = (CONFIG.PRESENTATION?.key ?? 'p').toLowerCase();
    if (e.key.toLowerCase() === key) { e.preventDefault(); togglePresentation(); }
    else if (e.key === 'Escape' && isPresenting()) exitPresentation();
  });
}
