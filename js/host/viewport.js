/**
 * viewport.js
 * Board viewport: pan, zoom, fit-to-screen and the board background image.
 */

/**
 * Apply BOARD_BACKGROUND config to #board-bg (inside #board-world).
 *
 * Loads the image to read its natural dimensions, then sizes #board-bg to
 * match the image's exact aspect ratio while being large enough to fill the
 * viewport at minimum zoom — so any image size and shape works correctly.
 *
 * Blur affects only this element, leaving board spaces above it crisp.
 */
// Keep a reference to the active probe so we can cancel stale loads.
// ── Board background ────────────────────────────────────────────────────────────

let _bgProbe = null;

function _applyBoardBackground() {
  const bg  = document.getElementById('board-bg');
  const cfg = CONFIG.BOARD_BACKGROUND;
  if (!bg) return;

  // Cancel any previous pending load to avoid race conditions
  if (_bgProbe) { _bgProbe.onload = null; _bgProbe.onerror = null; _bgProbe = null; }

  if (!cfg?.image) {
    bg.style.display = 'none';
    _bgBounds = null;
    return;
  }

  const op   = cfg.overlayOpacity ?? 0.65;
  const pos  = cfg.position || 'center';
  const blur = cfg.blur || 0;

  const probe = new Image();
  _bgProbe = probe;
  probe.onload = () => {
    if (probe !== _bgProbe) return; // superseded by a newer call
    _bgProbe = null;
    const vp  = document.getElementById('board-viewport');
    const vpW = vp?.offsetWidth  || 1440;
    const vpH = vp?.offsetHeight || 900;

    // Use the current fit scale (view.scale set by fitBoardInView).
    // Sizing based on fit scale means the image appears roughly viewport-sized
    // at the default zoom — you see most of the image, not a tiny crop.
    // A safety factor of 1.5 gives panning room without making the image
    // look zoomed in at the default view.
    const fitScale = view.scale || 1.0;
    const neededW  = (vpW / fitScale) * 1.5;
    const neededH  = (vpH / fitScale) * 1.5;

    // Match the image's own aspect ratio exactly
    const aspect = probe.naturalWidth / probe.naturalHeight;
    let bgW = Math.max(neededW, neededH * aspect);
    let bgH = bgW / aspect;
    if (bgH < neededH) { bgH = neededH; bgW = bgH * aspect; }

    const boardEl = document.getElementById('board');
    const boardW  = boardEl ? boardEl.offsetWidth  : bW;
    const boardH  = boardEl ? boardEl.offsetHeight : bH;

    // Position using absolute px centred on the board grid.
    // % values would be relative to #board-world which has no explicit size
    // until fitBoardInView pins it — using px avoids any reflow-based jump.
    const bgLeft = Math.round((boardW - bgW) / 2);
    const bgTop  = Math.round((boardH - bgH) / 2);
    bg.style.width   = Math.round(bgW) + 'px';
    bg.style.height  = Math.round(bgH) + 'px';
    bg.style.left    = bgLeft + 'px';
    bg.style.top     = bgTop  + 'px';
    bg.style.display = 'block';

    // Store bounds so _clampView can keep the bg filling the viewport
    _bgBounds = { left: bgLeft, top: bgTop, width: bgW, height: bgH };

    // Gradient tint over the image — both set as background layers
    bg.style.backgroundImage = [
      `linear-gradient(150deg,` +
        `rgba(200,230,201,${op}) 0%,` +
        `rgba(178,223,219,${op}) 50%,` +
        `rgba(197,202,233,${op}) 100%)`,
      `url('${cfg.image}')`,
    ].join(', ');
    bg.style.backgroundSize     = `cover, cover`;
    bg.style.backgroundPosition = `center, ${pos}`;
    bg.style.filter = blur > 0 ? `blur(${blur}px)` : '';
  };

  probe.onerror = () => {
    if (probe !== _bgProbe) return;
    _bgProbe = null;
    console.warn(`BOARD_BACKGROUND: could not load image "${cfg.image}"`);
    bg.style.display = 'none';
    _bgBounds = null;
  };

  probe.src = cfg.image;
}

// ── Pan + zoom ──────────────────────────────────────────────────────────────────

const view = { x: 0, y: 0, scale: 1 };

// Both limits are driven by CONFIG.ZOOM (see config.js).
// SCALE_MIN is recalculated in fitBoardInView() after the board renders.
let SCALE_MIN = 0.2;

let SCALE_MAX = CONFIG.ZOOM?.maxScale ?? 2.0;

// Background bounds in board-world coordinates — set when bg loads.
// Used to clamp panning so the background always covers the viewport.
let _bgBounds = null; // { left, top, width, height }

/** Clamp view.x / view.y so the background image always fills the viewport. */
function _clampView() {
  if (!_bgBounds) return;
  const vp = document.getElementById('board-viewport');
  if (!vp) return;
  const vpW = vp.offsetWidth;
  const vpH = vp.offsetHeight;
  const { left: bL, top: bT, width: bW, height: bH } = _bgBounds;
  const s = view.scale;
  // bg edge positions in viewport space: view.x + bL*s (left), view.x + (bL+bW)*s (right)
  // For bg to cover the viewport: left_vp ≤ 0 AND right_vp ≥ vpW
  view.x = Math.min(-(bL * s), Math.max(vpW - (bL + bW) * s, view.x));
  view.y = Math.min(-(bT * s), Math.max(vpH - (bT + bH) * s, view.y));
}

let _isPanning = false, _panOrigin = { x: 0, y: 0 }, _lastTouchDist = null;

function _applyView() {
  _clampView(); // keep view within bg image bounds (no-op if bg not loaded yet)
  const world = document.getElementById('board-world');
  if (world) world.style.transform = `translate(${view.x}px,${view.y}px) scale(${view.scale})`;
}

function _updateZoomLabel() {
  const lbl = document.getElementById('zoom-label');
  if (lbl) lbl.textContent = Math.round(view.scale * 100) + '%';
}

function _zoomAt(cx, cy, factor) {
  const ns = Math.min(Math.max(SCALE_MAX, SCALE_MIN), Math.max(SCALE_MIN, view.scale * factor));
  const r  = ns / view.scale;
  view.x = cx - r * (cx - view.x);
  view.y = cy - r * (cy - view.y);
  view.scale = ns;
  _applyView(); _updateZoomLabel();
}

function fitBoardInView() {
  const vp    = document.getElementById('board-viewport');
  const board = document.getElementById('board');
  if (!vp || !board) return;

  // Calling offsetWidth/Height forces a synchronous reflow so we get accurate
  // measurements right now — no requestAnimationFrame needed.
  // This also means the transform is applied before the first paint, eliminating
  // the visible jump from position (0,0) to the centred fit position.
  const pad = 32;
  const bW  = board.offsetWidth;
  const bH  = board.offsetHeight;
  if (!bW || !bH) return;

  const fitScale = Math.min(
    (vp.offsetWidth  - pad * 2) / bW,
    (vp.offsetHeight - pad * 2) / bH,
    isPresenting() ? (CONFIG.PRESENTATION?.maxFitScale ?? 1.0) : 1.0   // TV: let the board fill the screen
  );

  view.scale = fitScale;
  view.x = (vp.offsetWidth  - bW * fitScale) / 2;
  view.y = (vp.offsetHeight - bH * fitScale) / 2;

  // Pin board-world to the board grid size so #board-bg loading never causes
  // a reflow that shifts the board.
  const boardWorld = document.getElementById('board-world');
  if (boardWorld) { boardWorld.style.width = bW + 'px'; boardWorld.style.height = bH + 'px'; }

  // Minimum zoom: a configurable fraction below the fit scale
  SCALE_MIN = Math.max(0.15, fitScale * (CONFIG.ZOOM?.outFactor ?? 0.65));

  _applyView();
  _updateZoomLabel();

  // Reveal the board now that transform is already applied.
  if (boardWorld) boardWorld.style.opacity = '1';

  // Apply background with the correct fit scale now that view.scale is set.
  _applyBoardBackground();
}

function initPanZoom() {
  const vp = document.getElementById('board-viewport');

  vp.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = vp.getBoundingClientRect();
    _zoomAt(e.clientX - rect.left, e.clientY - rect.top, e.deltaY < 0 ? 1.12 : 1/1.12);
  }, { passive: false });

  vp.addEventListener('mousedown', e => {
    if (e.button !== 0) return;
    _isPanning = true;
    _panOrigin = { x: e.clientX - view.x, y: e.clientY - view.y };
    vp.classList.add('panning');
  });
  window.addEventListener('mousemove', e => {
    if (!_isPanning) return;
    view.x = e.clientX - _panOrigin.x;
    view.y = e.clientY - _panOrigin.y;
    _applyView();
  });
  window.addEventListener('mouseup', () => {
    _isPanning = false;
    document.getElementById('board-viewport')?.classList.remove('panning');
  });

  vp.addEventListener('touchstart', e => {
    if (e.touches.length === 1) {
      _isPanning = true;
      _panOrigin = { x: e.touches[0].clientX - view.x, y: e.touches[0].clientY - view.y };
    }
    if (e.touches.length === 2) _lastTouchDist = _touchDist(e.touches);
  }, { passive: true });

  vp.addEventListener('touchmove', e => {
    e.preventDefault();
    if (e.touches.length === 1 && _isPanning) {
      view.x = e.touches[0].clientX - _panOrigin.x;
      view.y = e.touches[0].clientY - _panOrigin.y;
      _applyView();
    }
    if (e.touches.length === 2 && _lastTouchDist) {
      const dist = _touchDist(e.touches);
      const rect = vp.getBoundingClientRect();
      const cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
      const cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;
      _zoomAt(cx, cy, dist / _lastTouchDist);
      _lastTouchDist = dist;
    }
  }, { passive: false });

  vp.addEventListener('touchend', () => { _isPanning = false; _lastTouchDist = null; });
}

function _touchDist(t) {
  return Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
}

function zoomIn()    { const vp = document.getElementById('board-viewport'); _zoomAt(vp.offsetWidth/2, vp.offsetHeight/2, 1.2); }

function zoomOut()   { const vp = document.getElementById('board-viewport'); _zoomAt(vp.offsetWidth/2, vp.offsetHeight/2, 1/1.2); }

function zoomReset() { fitBoardInView(); }
