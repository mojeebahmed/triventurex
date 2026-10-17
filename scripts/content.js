/**
 * scripts/content.js
 * Edition content toolkit (Node only — not served to browsers):
 *   - load an edition's CSV files + config
 *   - check them and report problems with row numbers
 *   - generate questions.js / deeds.js (the fallback used when index.html is
 *     opened from disk, where the browser can't fetch the CSV files)
 *
 * Parsing uses js/shared/csv.js — the exact code the game uses — so what the
 * checker accepts is what the game loads.
 *
 * Used by scripts/build-content.js (npm run build:content / check:content)
 * and test/csv.test.js.
 */

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { _csvSplit, _parseQuestionsCSV, _parseDeedsCSV, _parseActionsCSV } = require('../js/shared/csv.js');

const EDITIONS_DIR = path.join(__dirname, '..', 'game_editions');

const EFFECTS = new Set(['score_add', 'score_remove', 'move_forward', 'move_back',
  'move_to_prev_landmark', 'move_to_next_landmark', 'move_to_landmark', 'skip_turn',
  'extra_turn', 'all_players_gain', 'all_players_lose', 'protection']);
const LANDMARK_EFFECTS = new Set(['move_to_prev_landmark', 'move_to_next_landmark', 'move_to_landmark']);
const ACTION_KINDS = new Set(['act', 'explain', 'sound']); // keep in sync with CONFIG.ACTION_KINDS

/**
 * The general action cards every edition can mix in (game_editions/shared/).
 * Not an edition: no questions.csv, so listEditions() leaves it out.
 */
const SHARED_ID = 'shared';

/** Edition folders that have content CSVs (includes `template`). */
function listEditions() {
  return fs.readdirSync(EDITIONS_DIR)
    .filter(d => fs.existsSync(path.join(EDITIONS_DIR, d, 'questions.csv')))
    .sort();
}

/** Read an edition from disk: raw CSV text, parsed rows, and its config (for landmarks). */
function loadEdition(id) {
  const dir = path.join(EDITIONS_DIR, id);
  const read = f => (fs.existsSync(path.join(dir, f)) ? fs.readFileSync(path.join(dir, f), 'utf8') : null);
  let config = {};
  const configJs = read('config.js');
  if (configJs) {
    const ctx = { window: {} };
    vm.createContext(ctx);
    vm.runInContext(configJs, ctx, { filename: `${id}/config.js` });
    config = ctx.window.EDITION_CONFIG || {};
  }
  return { ...makeEdition({ id, config, questionsCsv: read('questions.csv'), deedsCsv: read('deeds.csv'),
                           actionsCsv: read('actions.csv') }), dir };
}

/** The shared folder as an edition-like object: only actions.csv, generated as GENERAL_ACTIONS_DATA. */
function loadSharedContent() {
  const dir = path.join(EDITIONS_DIR, SHARED_ID);
  const file = path.join(dir, 'actions.csv');
  const actionsCsv = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null;
  return { ...makeEdition({ id: SHARED_ID, actionsCsv }), dir, actionsGlobal: 'GENERAL_ACTIONS_DATA' };
}

/** Build an edition object from CSV text (also used by tests for made-up content). */
function makeEdition({ id = 'test', config = {}, questionsCsv = null, deedsCsv = null, actionsCsv = null }) {
  // Parser warnings (e.g. a missing id) are reported by checkEdition instead
  const quiet = fn => { const w = console.warn; console.warn = () => {}; try { return fn(); } finally { console.warn = w; } };
  return {
    id, config, questionsCsv, deedsCsv, actionsCsv,
    questions: questionsCsv ? quiet(() => _parseQuestionsCSV(questionsCsv)) : [],
    deeds:     deedsCsv     ? quiet(() => _parseDeedsCSV(deedsCsv))         : [],
    actions:   actionsCsv   ? _parseActionsCSV(actionsCsv)                  : [],
  };
}

/**
 * Raw CSV lines with their 1-based line number, header first.
 * Mirrors _parseCSV: blank lines are skipped.
 */
function csvLines(text) {
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n')
    .map((line, i) => ({ line: line.trim(), n: i + 1 }))
    .filter(l => l.line);
}

/**
 * Check an edition's content. Returns { errors, warnings }, each a list of
 * { file, line, message }. Errors break the game (wrong/missing data);
 * warnings are probably-unintended but still playable.
 */
function checkEdition(ed) {
  const errors = [], warnings = [];
  const err  = (file, line, message) => errors.push({ file, line, message });
  const warn = (file, line, message) => warnings.push({ file, line, message });

  // Column count per row — the classic "comma inside a field without quotes"
  for (const [file, text] of [['questions.csv', ed.questionsCsv], ['deeds.csv', ed.deedsCsv],
                               ['actions.csv', ed.actionsCsv]]) {
    if (!text) continue;
    const [header, ...rows] = csvLines(text);
    const width = _csvSplit(header.line).length;
    for (const r of rows) {
      const cols = _csvSplit(r.line).length;
      if (cols !== width) {
        err(file, r.n, `${cols} columns, expected ${width} — a comma inside a field needs "double quotes"`);
      }
    }
  }

  // Questions — row order matches the parser (blank lines skipped, header first)
  if (ed.questionsCsv) {
    const rows = csvLines(ed.questionsCsv).slice(1);
    const raw = rows.map(r => Object.fromEntries(
      _csvSplit(csvLines(ed.questionsCsv)[0].line).map((h, i) =>
        [h.trim().toLowerCase().replace(/\s+/g, '_'), (_csvSplit(r.line)[i] ?? '').trim()])));
    const seen = new Map();
    const usesTopics = raw.some(r => r.topic);
    raw.forEach((r, i) => {
      const n = rows[i].n;
      const f = 'questions.csv';
      if (!r.question) err(f, n, 'question text is empty');
      if (!/^\d+$/.test(r.id || '')) err(f, n, `id "${r.id || ''}" must be a whole number`);
      else if (seen.has(r.id)) err(f, n, `duplicate id ${r.id} (also on line ${seen.get(r.id)})`);
      else seen.set(r.id, n);
      if (!['multi', 'open'].includes(r.type)) err(f, n, `type "${r.type}" must be multi or open`);
      if (!['easy', 'hard'].includes(r.difficulty)) err(f, n, `difficulty "${r.difficulty}" must be easy or hard`);
      if (r.type === 'multi') {
        const opts = [r.opt_a, r.opt_b, r.opt_c, r.opt_d];
        const filled = opts.filter(Boolean).length;
        const a = Number(r.answer);
        if (filled < 2) err(f, n, 'multi question needs at least 2 options');
        if (!Number.isInteger(a) || a < 1 || a > 4) err(f, n, `answer "${r.answer}" must be 1-4 (the option number)`);
        else if (!opts[a - 1]) err(f, n, `answer ${a} points at an empty option`);
      }
      if (r.type === 'open' && !r.answer) err(f, n, 'open question has no answer');
      if (usesTopics && !r.topic) warn(f, n, 'no topic — the question is always asked, whatever the topic filter');
    });
  }

  // Deeds
  if (ed.deedsCsv) {
    const lines = csvLines(ed.deedsCsv).slice(1);
    const landmarks = (ed.config.LANDMARKS || []).map(l => l.name);
    ed.deeds.forEach((d, i) => {
      const n = lines[i]?.n;
      const f = 'deeds.csv';
      if (!['good', 'bad'].includes(d.type)) err(f, n, `type "${d.type}" must be good or bad`);
      if (!d.effects.length) err(f, n, 'no effect');
      for (const e of d.effects) {
        if (!EFFECTS.has(e.effect)) { err(f, n, `unknown effect "${e.effect}"`); continue; }
        if (e.effect === 'move_to_landmark' && !landmarks.includes(e.landmark)) {
          err(f, n, `landmark "${e.landmark ?? ''}" is not in config.js LANDMARKS`);
        }
        if ((e.effect === 'move_to_prev_landmark' || e.effect === 'move_to_next_landmark')) {
          if (!landmarks.length) err(f, n, `${e.effect} needs LANDMARKS in config.js (there are none)`);
          else if (e.value > landmarks.length) warn(f, n, `${e.effect} ${e.value}, but the edition only has ${landmarks.length} landmarks`);
        }
      }
      if (d.text.includes('{landmark}') && !d.effects.some(e => LANDMARK_EFFECTS.has(e.effect))) {
        warn(f, n, 'text uses {landmark} but no effect moves to a landmark — it will read "a landmark"');
      }
    });
  }

  // Action cards
  if (ed.actionsCsv) {
    const lines = csvLines(ed.actionsCsv).slice(1);
    const rows  = lines.map(l => _csvSplit(l.line));
    const header = _csvSplit(csvLines(ed.actionsCsv)[0].line).map(h => h.trim().toLowerCase());
    const col = name => header.indexOf(name);
    const seen = new Map();
    rows.forEach((cells, i) => {
      const n = lines[i].n, f = 'actions.csv';
      const id   = (cells[col('id')]   ?? '').trim();
      const text = (cells[col('text')] ?? '').trim();
      const kind = (cells[col('kind')] ?? '').trim();
      if (!text) err(f, n, 'card text is empty');
      if (!/^\d+$/.test(id)) err(f, n, `id "${id}" must be a whole number`);
      else if (seen.has(id)) err(f, n, `duplicate id ${id} (also on line ${seen.get(id)})`);
      else seen.set(id, n);
      if (!ACTION_KINDS.has(kind)) err(f, n, `kind "${kind}" must be one of: ${[...ACTION_KINDS].join(', ')}`);
    });
  }

  return { errors, warnings };
}

// ── Generated JS ──────────────────────────────────────────────────────────────

/**
 * JSON with a space after ':' and ',' — the format the existing generated
 * files use, so regenerating unchanged content produces no diff.
 */
function spacedJson(v) {
  if (Array.isArray(v)) return `[${v.map(spacedJson).join(', ')}]`;
  if (v && typeof v === 'object') {
    return `{${Object.entries(v).map(([k, x]) => `${JSON.stringify(k)}: ${spacedJson(x)}`).join(', ')}}`;
  }
  return JSON.stringify(v);
}

function generatedFile({ id, file, source, summary, globalName, items }) {
  return [
    '/**',
    ` * game_editions/${id}/${file}`,
    ` * AUTO-GENERATED from ${source} by \`npm run build:content\` — do not edit directly.`,
    ' *',
    ` * ${summary}`,
    ' */',
    '',
    `window.${globalName} = [`,
    ...items.map(x => `  ${spacedJson(x)},`),
    '];',
    '',
  ].join('\n');
}

/** The questions.js / deeds.js text this edition's CSVs should produce. */
function generateEditionJs(ed) {
  const out = {};
  if (ed.questionsCsv) {
    const easy = ed.questions.filter(q => q.diff === 'easy').length;
    out['questions.js'] = generatedFile({
      id: ed.id, file: 'questions.js', source: 'questions.csv', globalName: 'QUESTIONS_DATA',
      summary: `${ed.questions.length} questions  (${easy} easy / ${ed.questions.length - easy} hard)`,
      items: ed.questions,
    });
  }
  if (ed.deedsCsv) {
    const good = ed.deeds.filter(d => d.type === 'good').length;
    out['deeds.js'] = generatedFile({
      id: ed.id, file: 'deeds.js', source: 'deeds.csv', globalName: 'DEEDS_DATA',
      summary: `${ed.deeds.length} deed cards  (${good} good / ${ed.deeds.length - good} bad)`,
      items: ed.deeds,
    });
  }
  if (ed.actionsCsv) {
    const kinds = [...ACTION_KINDS].map(k => `${ed.actions.filter(a => a.kind === k).length} ${k}`).join(' / ');
    out['actions.js'] = generatedFile({
      id: ed.id, file: 'actions.js', source: 'actions.csv', globalName: ed.actionsGlobal ?? 'ACTIONS_DATA',
      summary: `${ed.actions.length} action cards  (${kinds})`,
      items: ed.actions,
    });
  }
  return out;
}

module.exports = { EDITIONS_DIR, EFFECTS, SHARED_ID, listEditions, loadEdition, loadSharedContent, makeEdition,
                   checkEdition, generateEditionJs };
