/**
 * path-design.js
 * Drawing a board path (G20 — the ✏️ Boards tab; same idea as
 * tools/path-designer.html). A path is a template like CONFIG.PATH_TEMPLATES:
 * { name, start: [row, col], segments: [[dir, steps], …], gridRows, gridCols }.
 * Pure: no page access — unit-tested.
 */

const PD_STEP = { up: [-1, 0], down: [1, 0], left: [0, -1], right: [0, 1] };

/** Spaces per game length the built-in boards aim for (start + finish included). */
const PD_TARGET = { short: 22, medium: 42, long: 62 };
const PD_MIN_SPACES = 10;
const PD_GRID = { min: 6, max: 16 };

/** Every cell of the path in order: [{ r, c, dir }] (dir = how we got there; none for the start). */
function designCells(start, segments) {
  if (!start) return [];
  let [r, c] = start;
  const cells = [{ r, c, dir: null }];
  for (const [dir, steps] of segments || []) {
    const [dr, dc] = PD_STEP[dir] || [0, 0];
    for (let i = 0; i < steps; i++) { r += dr; c += dc; cells.push({ r, c, dir }); }
  }
  return cells;
}

/**
 * From the path's end towards a clicked cell, in a straight line (the longer
 * axis wins for a diagonal click). null when the click is on the end itself.
 */
function segmentTowards([er, ec], [r, c]) {
  const dr = r - er, dc = c - ec;
  if (!dr && !dc) return null;
  if (Math.abs(dr) >= Math.abs(dc)) return { dir: dr < 0 ? 'up' : 'down', steps: Math.abs(dr) };
  return { dir: dc < 0 ? 'left' : 'right', steps: Math.abs(dc) };
}

/**
 * Can this segment be added? It must stay on the grid and not run over the
 * path. Returns the cells it would add, or null.
 */
function segmentCells(design, { dir, steps }) {
  const cells = designCells(design.start, design.segments);
  if (!cells.length) return null;
  const used = new Set(cells.map(p => `${p.r},${p.c}`));
  let { r, c } = cells[cells.length - 1];
  const [dr, dc] = PD_STEP[dir];
  const added = [];
  for (let i = 0; i < steps; i++) {
    r += dr; c += dc;
    if (r < 0 || c < 0 || r >= design.gridRows || c >= design.gridCols || used.has(`${r},${c}`)) return null;
    added.push({ r, c, dir });
  }
  return added;
}

/** Add a segment (merged into the last one when it goes the same way). New segments array. */
function addSegment(segments, { dir, steps }) {
  const out = (segments || []).map(s => [...s]);
  const last = out[out.length - 1];
  if (last && last[0] === dir) last[1] += steps;
  else out.push([dir, steps]);
  return out;
}

/**
 * Cells where two parallel runs touch side by side (hard to follow on the
 * board). Corners are fine. Returns a Set of "r,c".
 */
function designCrowded(cells) {
  const axis = new Map(cells.map(p => [`${p.r},${p.c}`,
    !p.dir ? null : (p.dir === 'left' || p.dir === 'right') ? 'h' : 'v']));
  const out = new Set();
  for (const p of cells) {
    const a = axis.get(`${p.r},${p.c}`);
    if (!a) continue;
    const sides = a === 'h' ? [[p.r - 1, p.c], [p.r + 1, p.c]] : [[p.r, p.c - 1], [p.r, p.c + 1]];
    for (const [r, c] of sides) {
      if (axis.get(`${r},${c}`) === a) { out.add(`${p.r},${p.c}`); out.add(`${r},${c}`); }
    }
  }
  return out;
}

/**
 * What the designer says about a path: { spaces, target, crowded, errors, warnings }.
 * errors block saving; warnings don't.
 */
function designCheck(design, gameLength) {
  const cells = designCells(design.start, design.segments);
  const target = PD_TARGET[gameLength] ?? PD_TARGET.medium;
  const crowded = designCrowded(cells);
  const errors = [], warnings = [];
  if (!design.start) errors.push('Click a cell to place the start');
  else if (cells.length < PD_MIN_SPACES) errors.push(`At least ${PD_MIN_SPACES} spaces (now ${cells.length})`);
  if (!String(design.name || '').trim()) errors.push('Give the board a name');
  if (crowded.size) warnings.push('Some parallel rows touch — players may find the path hard to follow');
  if (cells.length && Math.abs(cells.length - target) > target * 0.25) {
    warnings.push(`${cells.length} spaces — the built-in ${gameLength} boards have about ${target}`);
  }
  return { spaces: cells.length, target, crowded, errors, warnings };
}

/** The design as a template (only what CONFIG.PATH_TEMPLATES needs). */
function designTemplate(design, defaultGrid = { rows: 12, cols: 12 }) {
  const t = { name: String(design.name || '').trim(), start: [...design.start], segments: design.segments.map(s => [...s]) };
  if (design.gridRows !== defaultGrid.rows) t.gridRows = design.gridRows;
  if (design.gridCols !== defaultGrid.cols) t.gridCols = design.gridCols;
  return t;
}

/** One line to paste into CONFIG.PATH_TEMPLATES[length] in config.js. */
function templateText(t) {
  const q = s => `'${String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;
  const grid = (t.gridRows ? `, gridRows: ${t.gridRows}` : '') + (t.gridCols ? `, gridCols: ${t.gridCols}` : '');
  return `{ name: ${q(t.name)}, start: [${t.start.join(',')}]${grid}, segments: [${t.segments.map(([d, n]) => `[${q(d)},${n}]`).join(',')}] },`;
}

if (typeof module !== 'undefined') {
  module.exports = { PD_TARGET, PD_MIN_SPACES, PD_GRID, designCells, segmentTowards, segmentCells,
                     addSegment, designCrowded, designCheck, designTemplate, templateText };
}
