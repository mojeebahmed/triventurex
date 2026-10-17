/**
 * board-picker.js
 * Step ③ on the setup screen: a thumbnail per board path for the chosen game
 * length, plus 🎲 Random (G8). Thumbnails are drawn from CONFIG.PATH_TEMPLATES,
 * so a new path gets one automatically. The choice is kept in the hidden
 * #path-select input ('random' or the template index) that startGame reads.
 */

const THUMB_CELL = 7;   // px per grid cell in a thumbnail
const THUMB_GAP  = 2;   // px between cells

/** Small SVG of a path template: one square per space, start + finish coloured. */
function boardThumbSvg(gameLength, template) {
  const { coords } = buildPathCoords(gameLength, template);
  const { minRow, minCol, rows, cols } = pathBounds(coords.map(([row, col]) => ({ row, col })));
  const step = THUMB_CELL + THUMB_GAP;
  const last = coords.length - 1;
  const cells = coords.map(([r, c], i) => {
    const cls = i === 0 ? 'thumb-start' : i === last ? 'thumb-finish' : 'thumb-space';
    return `<rect class="${cls}" x="${(c - minCol) * step}" y="${(r - minRow) * step}"
                  width="${THUMB_CELL}" height="${THUMB_CELL}" rx="1.5"/>`;
  }).join('');
  return `<svg class="board-thumb-svg" viewBox="0 0 ${cols * step - THUMB_GAP} ${rows * step - THUMB_GAP}"
               aria-hidden="true">${cells}</svg>`;
}

/** "A — L-shape winding" → "L-shape winding" (the letter is just an id). */
const _pathLabel = t => (t.name || '').split('—').pop().trim() || t.name || 'Path';

/**
 * Draw the board choices for a game length. Keeps the current choice if it
 * exists for this length, otherwise falls back to Random.
 */
function renderBoardPicker(gameLength, selected = document.getElementById('path-select')?.value) {
  const input  = document.getElementById('path-select');
  const picker = document.getElementById('board-picker');
  if (!input || !picker) return;
  const templates = CONFIG.PATH_TEMPLATES[gameLength] || [];
  const valid = selected === 'random' || (selected !== '' && templates[Number(selected)]);
  input.value = valid ? String(selected) : 'random';

  const card = (value, art, label, title) => `
    <button type="button" class="board-card ${input.value === value ? 'selected' : ''}"
            data-path="${value}" title="${esc(title)}" aria-pressed="${input.value === value}">
      <span class="board-card-art">${art}</span>
      <span class="board-card-name">${esc(label)}</span>
    </button>`;

  picker.innerHTML =
    card('random', '<span class="board-card-dice">🎲</span>', 'Random', 'A different path each game') +
    templates.map((t, i) => {
      const spaces = buildPathCoords(gameLength, t).coords.length;
      return card(String(i), boardThumbSvg(gameLength, t), (t.custom ? '✏️ ' : '') + _pathLabel(t),
                  `${t.name} · ${spaces} spaces${t.custom ? ' · your board' : ''}`);
    }).join('');
}

/** Click on a board card → remember the choice and redraw the selection. */
function initBoardPicker() {
  document.getElementById('board-picker')?.addEventListener('click', e => {
    const btn = e.target.closest('.board-card');
    if (!btn) return;
    const len = document.querySelector('input[name="gameLength"]:checked')?.value || 'medium';
    renderBoardPicker(len, btn.dataset.path);
  });
}

/** Kept for existing callers (edition switch, reset, restore). */
function populatePathSelector(gameLength) { renderBoardPicker(gameLength); }
