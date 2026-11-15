/**
 * text-size.js
 * The A− / A+ text size buttons: make the cards bigger for people who need
 * larger text, without touching the rest of the page.
 *
 * The size is a CSS variable, --text-scale, on <html>. Only the parts that should
 * grow use it, with CSS `zoom` (the whole card grows: text, spacing, buttons and
 * icons together, so it keeps its shape):
 *   game (index.html)    – the space card (#modal), css/styles.css
 *   Academy              – the question cards of every mode, css/academy.css
 * The board, player names, scoreboard, menus and tabs stay the same size.
 *
 * Steps in CONFIG.TEXT_SIZE.steps. Remembered per device and page in
 * localStorage `triventurex_text_size_<page>` (a preference, not a game rule —
 * it is not saved with the game).
 *
 * Top-level code does not touch the page (js/shared rule).
 */

const LS_TEXT_SIZE_PREFIX = 'triventurex_text_size_';

/** The sizes the buttons step through (sorted, always including 1). */
function textSizeSteps(config = (typeof CONFIG !== 'undefined' ? CONFIG : {})) {
  const steps = (config.TEXT_SIZE?.steps || [1]).filter(n => typeof n === 'number' && n > 0);
  return [...new Set([1, ...steps])].sort((a, b) => a - b);
}

/** The step nearest to `scale` (a saved value from an older list of steps still works). */
function nearestTextSize(scale, steps = textSizeSteps()) {
  const n = Number(scale);
  if (!Number.isFinite(n) || n <= 0) return 1;
  return steps.reduce((best, s) => (Math.abs(s - n) < Math.abs(best - n) ? s : best), steps[0]);
}

/** One step bigger (dir = 1) or smaller (dir = -1); stays at the ends. */
function stepTextSize(scale, dir, steps = textSizeSteps()) {
  const i = steps.indexOf(nearestTextSize(scale, steps));
  return steps[Math.max(0, Math.min(steps.length - 1, i + Math.sign(dir)))];
}

/** "130%" — for the label between the buttons. */
const textSizeLabel = scale => `${Math.round(scale * 100)}%`;

function loadTextSize(page) {
  try { return nearestTextSize(localStorage.getItem(LS_TEXT_SIZE_PREFIX + page) ?? 1); } catch { return 1; }
}

function saveTextSize(page, scale) {
  try {
    if (scale === 1) localStorage.removeItem(LS_TEXT_SIZE_PREFIX + page);
    else localStorage.setItem(LS_TEXT_SIZE_PREFIX + page, String(scale));
  } catch {}
}

/** The size on the page now (1 before startTextSize). */
function currentTextSize() {
  return nearestTextSize(document.documentElement.style.getPropertyValue('--text-scale') || 1);
}

/** Set the size on the page and update every A− / A+ control on it (call it
 *  again after drawing a new control, to show the size on it). */
function applyTextSize(scale) {
  const steps = textSizeSteps();
  const s = nearestTextSize(scale, steps);
  document.documentElement.style.setProperty('--text-scale', String(s));
  document.documentElement.classList.toggle('text-big', s > 1);
  document.querySelectorAll('[data-text-size]').forEach(box => {
    const label = box.querySelector('.text-size-value');
    if (label) label.textContent = textSizeLabel(s);
    const smaller = box.querySelector('[data-text-step="-1"]');
    const bigger = box.querySelector('[data-text-step="1"]');
    if (smaller) smaller.disabled = s <= steps[0];
    if (bigger) bigger.disabled = s >= steps[steps.length - 1];
  });
  return s;
}

/** The A− / A+ buttons (+ the size between them). Put them anywhere on the page;
 *  startTextSize() handles their clicks. */
function textSizeControlHtml(extraClass = '') {
  return `<span class="text-size ${extraClass}" data-text-size role="group" aria-label="Text size on the cards">
      <button type="button" data-text-step="-1" title="Smaller text on the cards" aria-label="Smaller text">${icon('textSmaller')}</button>
      <span class="text-size-value" aria-live="polite">100%</span>
      <button type="button" data-text-step="1" title="Bigger text on the cards" aria-label="Bigger text">${icon('textBigger')}</button>
    </span>`;
}

/**
 * Start the text size on a page: apply the saved size and handle every A− / A+
 * click (controls drawn later work too). `onChange(scale)` runs after a change,
 * e.g. to refit something.
 */
function startTextSize(page, onChange) {
  const scale = applyTextSize(loadTextSize(page));
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-text-step]');
    if (!btn || btn.disabled) return;
    const scale = applyTextSize(stepTextSize(currentTextSize(), Number(btn.dataset.textStep)));
    saveTextSize(page, scale);
    document.dispatchEvent(new CustomEvent('textsizechange', { detail: { scale } }));   // e.g. Flashcards refit
    onChange?.(scale);
  });
  return scale;
}

if (typeof module !== 'undefined') {
  module.exports = { textSizeSteps, nearestTextSize, stepTextSize, textSizeLabel };
}
