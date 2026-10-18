#!/usr/bin/env node
/**
 * scripts/build-icons.js — bundle the icons the game uses (offline-ready).
 *
 *   npm run build:icons    write js/shared/icons-data.js with the line icons named
 *                          in js/shared/icon-registry.js, and images/emoji/<code
 *                          points>.svg for every emoji the game uses (registry,
 *                          badges, pages, edition content)
 *   npm run check:icons    check only: fails if a file is missing or out of date
 *
 * Names: js/shared/icon-registry.js. Emoji set: scripts/icons.config.js. Icon data comes from the @iconify-json/*
 * dev dependencies (pinned in package.json); nothing is fetched at run time.
 * Emoji without an image in the set keep the device's own emoji (listed as
 * "no image" below — fine for text symbols, worth a look for real emoji).
 */

const fs = require('node:fs');
const path = require('node:path');
const { findEmoji, glyphKey } = require('../js/shared/icons.js');
const config = require('./icons.config.js');
const { ICONS, BADGES, PHONE_BADGES } = require('../js/shared/icon-registry.js');
const { listEditions, loadEdition } = require('./content.js');

/** Every icon id used: the engine registry plus each edition's ICONS block. */
function iconIds() {
  const ids = new Set(Object.values(ICONS));
  for (const id of listEditions()) {
    for (const v of Object.values(loadEdition(id).config.ICONS || {})) ids.add(String(v).trim());
  }
  return [...ids];
}

const ROOT = path.join(__dirname, '..');
const EMOJI_DIR = path.join(ROOT, 'images', 'emoji');
const DATA_FILE = path.join(ROOT, 'js', 'shared', 'icons-data.js');
const checkOnly = process.argv.includes('--check');

// ── Icon sets ───────────────────────────────────────────────────────────────────

const _sets = {};
function iconSet(prefix) {
  if (_sets[prefix]) return _sets[prefix];
  let icons, info, chars = {};
  try {
    icons = require(`@iconify-json/${prefix}/icons.json`);
    info  = require(`@iconify-json/${prefix}/info.json`);
    try { chars = require(`@iconify-json/${prefix}/chars.json`); } catch {}
  } catch {
    throw new Error(`Icon set "${prefix}" is not installed — run: npm i -D @iconify-json/${prefix}`);
  }
  return (_sets[prefix] = { prefix, icons, info, chars });
}

/** An icon's SVG; `id` is 'name' in `defaultSet` or 'set:name'. */
function svgFor(id, defaultSet) {
  const [prefix, name] = id.includes(':') ? id.split(':') : [defaultSet, id];
  const set = iconSet(prefix);
  let icon = set.icons.icons[name];
  const alias = set.icons.aliases?.[name];
  if (!icon && alias) icon = set.icons.icons[alias.parent];
  if (!icon) throw new Error(`No icon "${name}" in ${prefix}`);
  const w = icon.width ?? set.icons.width ?? 16, h = icon.height ?? set.icons.height ?? 16;
  return { prefix, svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}">${icon.body}</svg>` };
}

/** The set's icon name for an emoji (via its chars table), or null. */
function emojiName(set, glyph) {
  const k = glyphKey(glyph);
  return set.chars[k] || set.chars[`${k}-fe0f`] ||
    set.chars[[...glyph].map(c => c.codePointAt(0).toString(16)).join('-')] || null;
}

// ── Emoji used in the game ──────────────────────────────────────────────────────

function sourceFiles() {
  const out = [];
  const walk = (dir, ok) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) { if (!['vendor', 'node_modules', 'images'].includes(e.name)) walk(p, ok); }
      else if (ok(e.name)) out.push(p);
    }
  };
  for (const f of fs.readdirSync(ROOT)) if (f.endsWith('.html')) out.push(path.join(ROOT, f));
  walk(path.join(ROOT, 'js'), n => n.endsWith('.js') && n !== 'icons-data.js');
  walk(path.join(ROOT, 'game_editions'), n => n.endsWith('.js') || n.endsWith('.csv'));
  return out;
}

function usedEmoji() {
  const found = new Map();                       // glyphKey → glyph
  for (const v of Object.values(ICONS)) if (v.startsWith('emoji:')) found.set(glyphKey(v.slice(6)), v.slice(6));
  for (const b of [...BADGES, ...PHONE_BADGES]) found.set(glyphKey(b), b);
  for (const f of sourceFiles()) {
    for (const { glyph } of findEmoji(fs.readFileSync(f, 'utf8'))) found.set(glyphKey(glyph), glyph);
  }
  return found;
}

// ── Build ───────────────────────────────────────────────────────────────────────

const strip = s => s.replace(/️/g, '');
const overrides = Object.fromEntries(Object.entries(config.emoji.overrides || {}).map(([g, v]) => [glyphKey(g), v]));

const files = {};                                // file name → svg
const noImage = [];
const usedSets = new Set();
for (const [key, glyph] of usedEmoji()) {
  const prefix = overrides[key] || config.emoji.set;
  const set = iconSet(prefix);
  const name = emojiName(set, glyph);
  if (!name) { noImage.push(glyph); continue; }
  files[`${key}.svg`] = svgFor(`${prefix}:${name}`).svg;
  usedSets.add(prefix);
}

const ui = {};                                   // icon id ('lucide:undo-2') → SVG, for every line / set icon in use
for (const id of iconIds().sort()) {
  if (id.startsWith('emoji:') || id.startsWith('file:') || !/^[a-z0-9-]+:/.test(id)) continue;   // emoji and pictures are files
  const { prefix, svg } = svgFor(id, 'lucide');
  ui[id] = svg.replace('<svg ', '<svg aria-hidden="true" focusable="false" ');
  usedSets.add(prefix);
}

const credits = [...usedSets].sort().map(p => {
  const i = iconSet(p).info;
  return `${i.name} — ${i.author?.name ?? ''} — ${i.license?.title ?? ''} (${i.license?.url ?? i.author?.url ?? ''})`;
});

const data = [
  '/**',
  ' * js/shared/icons-data.js — AUTO-GENERATED by `npm run build:icons` from',
  ' * js/shared/icon-registry.js + scripts/icons.config.js. Do not edit; change those and rebuild.',
  ' *',
  ' * Icon sets and licences:',
  ...credits.map(c => ` *   ${c}`),
  ' */',
  '',
  'const TX_ICON_DATA = {',
  `  // emoji with an image in images/emoji/ (file = code points, no FE0F)`,
  `  emoji: ${JSON.stringify(Object.keys(files).map(f => f.replace('.svg', '')).sort())},`,
  `  // icon id → line icon SVG (used by the names in js/shared/icon-registry.js and editions' ICONS)`,
  '  ui: {',
  ...Object.entries(ui).map(([k, v]) => `    ${JSON.stringify(k)}: ${JSON.stringify(v)},`),
  '  },',
  '};',
  '',
].join('\n');

const licence = [
  'Emoji images in this folder come from icon sets bundled with Triventurex (see scripts/icons.config.js):',
  '',
  ...credits.map(c => `- ${c}`),
  '',
  'Microsoft Fluent Emoji — MIT License — Copyright (c) Microsoft Corporation.',
  'Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated',
  'documentation files (the "Software"), to deal in the Software without restriction, including without limitation',
  'the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to',
  'permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright',
  'notice and this permission notice shall be included in all copies or substantial portions of the Software.',
  'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.',
  '',
].join('\n');

// ── Write or check ──────────────────────────────────────────────────────────────

let problems = 0;
const want = new Map([[DATA_FILE, data], [path.join(EMOJI_DIR, 'LICENSE.txt'), licence],
  ...Object.entries(files).map(([f, svg]) => [path.join(EMOJI_DIR, f), svg])]);
const existing = fs.existsSync(EMOJI_DIR) ? fs.readdirSync(EMOJI_DIR).filter(f => f.endsWith('.svg')) : [];
const stale = existing.filter(f => !files[f]);

if (!checkOnly) fs.mkdirSync(EMOJI_DIR, { recursive: true });
for (const [file, text] of want) {
  const cur = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null;
  if (cur === text) continue;
  if (checkOnly) { console.log(`OUT OF DATE  ${path.relative(ROOT, file)}`); problems++; }
  else fs.writeFileSync(file, text);
}
for (const f of stale) {
  if (checkOnly) { console.log(`UNUSED  images/emoji/${f}`); problems++; }
  else fs.unlinkSync(path.join(EMOJI_DIR, f));
}

console.log(`${problems ? '✗' : '✓'} icons — ${Object.keys(files).length} emoji images, ${Object.keys(ui).length} line icons` +
  (noImage.length ? ` · no image (device emoji): ${noImage.join(' ')}` : ''));
if (checkOnly && problems) console.log('Run: npm run build:icons');
process.exit(problems ? 1 : 0);
