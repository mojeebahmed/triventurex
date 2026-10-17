#!/usr/bin/env node
/**
 * scripts/build-content.js
 * Check every edition's CSV content and regenerate questions.js / deeds.js /
 * actions.js, plus the general action cards in game_editions/shared/.
 *
 *   npm run build:content            check, then write the JS files
 *   npm run build:content swab-quest only that edition (or `shared`)
 *   npm run check:content            check only; also fails if a JS file is
 *                                    out of date (CSV edited, not rebuilt)
 *
 * Nothing is written for an edition that has errors.
 */

const fs = require('node:fs');
const path = require('node:path');
const { SHARED_ID, listEditions, loadEdition, loadSharedContent, checkEdition, generateEditionJs } = require('./content.js');

const args      = process.argv.slice(2);
const checkOnly = args.includes('--check');
const only      = args.filter(a => !a.startsWith('--'));
const editions  = only.length ? only : [...listEditions(), SHARED_ID];

let failed = false;

for (const id of editions) {
  if (id !== SHARED_ID && !listEditions().includes(id)) {
    console.log(`✗ ${id}: no game_editions/${id}/questions.csv`);
    failed = true;
    continue;
  }
  const ed = id === SHARED_ID ? loadSharedContent() : loadEdition(id);
  const { errors, warnings } = checkEdition(ed);

  const counts = id === SHARED_ID ? `${ed.actions.length} general action cards`
    : `${ed.questions.length} questions, ${ed.deeds.length} deeds, ${ed.actions.length} action cards`;
  console.log(`${errors.length ? '✗' : '✓'} ${id} — ${counts}` +
              (errors.length ? `, ${errors.length} error(s)` : '') +
              (warnings.length ? `, ${warnings.length} warning(s)` : ''));
  for (const e of errors)   console.log(`    ERROR    ${e.file}:${e.line}  ${e.message}`);
  for (const w of warnings) console.log(`    warning  ${w.file}:${w.line}  ${w.message}`);
  if (errors.length) { failed = true; continue; }

  for (const [file, text] of Object.entries(generateEditionJs(ed))) {
    const target  = path.join(ed.dir, file);
    const current = fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : null;
    if (current === text) continue;
    if (checkOnly) {
      console.log(`    OUT OF DATE  ${file} — run: npm run build:content ${id}`);
      failed = true;
    } else {
      fs.writeFileSync(target, text);
      console.log(`    wrote ${file}`);
    }
  }
}

process.exit(failed ? 1 : 0);
