#!/usr/bin/env node
/**
 * scripts/commons-image.js
 * Find a freely licensed photo on Wikimedia Commons, save it as a landmark /
 * background image for an edition, and record its credit.
 *
 *   node scripts/commons-image.js search "Eiffel Tower" [--json]
 *       lists good candidates (landscape, big enough, free licence);
 *       --json prints title + a 500px preview URL for each, to build a contact sheet
 *   node scripts/commons-image.js get <edition> <slug> "File:Name.jpg" [--bg]
 *       downloads it, crops/resizes it and writes
 *         game_editions/<edition>/images/landmarks/<slug>.jpg   (800x600)
 *         game_editions/<edition>/images/backgrounds/<slug>.jpg (--bg, 1920x1080)
 *       and adds/updates its row in game_editions/<edition>/CREDITS.md
 *
 * Needs macOS `sips` (resize/crop) and Node 18+ (fetch). Dev tooling only.
 * Only licences that allow reuse are offered: CC0, public domain, CC BY, CC BY-SA.
 */

const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const EDITIONS_DIR = path.join(__dirname, '..', 'game_editions');
const API = 'https://commons.wikimedia.org/w/api.php';
const UA = 'TriventurexDevTool/1.0 (private family trivia game; contact: mojeeb.ahmed@gmail.com)';
const FREE = /^(CC0|Public domain|PD|CC BY(-SA)?( \d(\.\d)?)?|CC BY(-SA)? \d(\.\d)?( \w+)?)/i;

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getJson(params) {
  const url = `${API}?${new URLSearchParams({ format: 'json', formatversion: '2', ...params })}`;
  for (let attempt = 0; attempt < 5; attempt++) {
    const res = await fetch(url, { headers: { 'User-Agent': UA } });
    if (res.status === 429 || res.status >= 500) { await sleep(2000 * (attempt + 1)); continue; }
    if (!res.ok) throw new Error(`Commons API ${res.status}`);
    return res.json();
  }
  throw new Error('Commons API: too many retries');
}

const stripHtml = s => String(s ?? '').replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&quot;/g, '"')
  .replace(/&#0?39;/g, "'").replace(/\s+/g, ' ').trim();

/** imageinfo for pages (search results or titles) at a 1280px thumbnail. */
function toCandidate(page) {
  const ii = page.imageinfo?.[0];
  if (!ii) return null;
  const m = ii.extmetadata ?? {};
  return {
    title: page.title,
    width: ii.width, height: ii.height, mime: ii.mime,
    thumb: ii.thumburl, page: ii.descriptionurl,
    licence: stripHtml(m.LicenseShortName?.value),
    licenceUrl: stripHtml(m.LicenseUrl?.value),
    artist: stripHtml(m.Artist?.value) || stripHtml(m.Credit?.value) || 'Unknown',
    description: stripHtml(m.ImageDescription?.value).slice(0, 120),
  };
}
const INFO = { prop: 'imageinfo', iiprop: 'url|size|mime|extmetadata', iiurlwidth: '1280' };

async function search(query, limit = 40) {
  const data = await getJson({ action: 'query', generator: 'search', gsrnamespace: '6', gsrlimit: String(limit),
                               gsrsearch: `${query} filetype:bitmap`, ...INFO });
  return (data.query?.pages ?? []).sort((a, b) => a.index - b.index).map(toCandidate).filter(Boolean);
}

const usable = c => /^image\/(jpeg|png|tiff)$/.test(c.mime) && c.width >= 1600 && c.height >= 900 && FREE.test(c.licence) &&
                    c.width / c.height >= 1.2 && c.width / c.height <= 2.0;

async function cmdSearch(query, asJson) {
  const found = (await search(query)).filter(usable).slice(0, asJson ? 12 : 8);
  if (asJson) {
    return console.log(JSON.stringify(found.map(c => ({ title: c.title, size: `${c.width}x${c.height}`, licence: c.licence,
      preview: c.thumb.replace(/\/\d+px-/, '/500px-') })), null, 1));
  }
  if (!found.length) return console.log('No usable candidates — try another query.');
  found.forEach((c, i) => console.log(`${i + 1}. ${c.title}  ${c.width}x${c.height}  ${c.licence}\n     ${c.artist.slice(0, 60)} — ${c.description}`));
}

async function download(url, file) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const res = await fetch(url, { headers: { 'User-Agent': UA } });
    if (res.status === 429 || res.status >= 500) { await sleep(3000 * (attempt + 1)); continue; }
    if (!res.ok) throw new Error(`download ${res.status}: ${url}`);
    fs.writeFileSync(file, Buffer.from(await res.arrayBuffer()));
    return;
  }
  throw new Error('download: too many retries');
}

/** Crop to the target aspect (centred) and resize to exactly w×h as JPEG. */
function fit(src, dest, w, h, quality) {
  const dims = execFileSync('sips', ['-g', 'pixelWidth', '-g', 'pixelHeight', src]).toString();
  const sw = +dims.match(/pixelWidth: (\d+)/)[1], sh = +dims.match(/pixelHeight: (\d+)/)[1];
  fs.copyFileSync(src, dest);
  if (sw / sh > w / h) execFileSync('sips', ['--resampleHeight', String(h), dest], { stdio: 'ignore' });
  else execFileSync('sips', ['--resampleWidth', String(w), dest], { stdio: 'ignore' });
  execFileSync('sips', ['--cropToHeightWidth', String(h), String(w), '-s', 'format', 'jpeg',
                        '-s', 'formatOptions', String(quality), dest], { stdio: 'ignore' });
}

function writeCredit(edition, row) {
  const file = path.join(EDITIONS_DIR, edition, 'CREDITS.md');
  const header = `# Image credits — ${edition}\n\nPhotos from [Wikimedia Commons](https://commons.wikimedia.org). Images were cropped and resized.\n\n` +
                 '| File | Title | Author | Licence | Source |\n|---|---|---|---|---|\n';
  const lines = fs.existsSync(file) ? fs.readFileSync(file, 'utf8').split('\n') : header.split('\n');
  const cell = s => s.replace(/\|/g, '/');
  const licence = row.licenceUrl ? `[${row.licence}](${row.licenceUrl})` : row.licence;
  const mine = `| ${row.file} | ${cell(row.title.replace(/^File:/, ''))} | ${cell(row.artist)} | ${licence} | [Commons](${row.page}) |`;
  const i = lines.findIndex(l => l.startsWith(`| ${row.file} |`));
  if (i >= 0) lines[i] = mine;
  else { while (lines.length && !lines.at(-1)) lines.pop(); lines.push(mine, ''); }
  // keep the table rows sorted by file name
  const head = lines.filter(l => !l.startsWith('| ') || l.startsWith('| File ') || l.startsWith('|---'));
  const rows = lines.filter(l => l.startsWith('| ') && !l.startsWith('| File ')).sort();
  const at = head.findIndex(l => l.startsWith('|---')) + 1;
  fs.writeFileSync(file, [...head.slice(0, at), ...rows, ...head.slice(at)].join('\n').replace(/\n*$/, '\n'));
}

async function cmdGet(edition, slug, title, isBg) {
  const data = await getJson({ action: 'query', titles: title, ...INFO });
  const cand = toCandidate(data.query?.pages?.[0] ?? {});
  if (!cand) throw new Error(`Not found on Commons: ${title}`);
  if (!FREE.test(cand.licence)) throw new Error(`Licence "${cand.licence}" is not on the allowed list`);

  const kind = isBg ? 'backgrounds' : 'landmarks';
  const dir = path.join(EDITIONS_DIR, edition, 'images', kind);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = path.join(require('node:os').tmpdir(), `commons-${process.pid}.jpg`);
  await download(cand.thumb, tmp);
  const dest = path.join(dir, `${slug}.jpg`);
  isBg ? fit(tmp, dest, 1920, 1080, 50) : fit(tmp, dest, 800, 600, 72);
  fs.unlinkSync(tmp);

  writeCredit(edition, { file: `images/${kind}/${slug}.jpg`, ...cand });
  console.log(`✓ ${edition}/images/${kind}/${slug}.jpg  (${Math.round(fs.statSync(dest).size / 1024)} KB)  ${cand.licence} — ${cand.artist.slice(0, 50)}`);
}

(async () => {
  const [cmd, ...args] = process.argv.slice(2);
  const flags = args.filter(a => a.startsWith('--')), rest = args.filter(a => !a.startsWith('--'));
  if (cmd === 'search' && rest[0]) return cmdSearch(rest.join(' '), flags.includes('--json'));
  if (cmd === 'get' && rest.length === 3) return cmdGet(rest[0], rest[1], rest[2], flags.includes('--bg'));
  console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0].replace(/^[/ *]+/gm, ''));
  process.exit(1);
})().catch(e => { console.error(`✗ ${e.message}`); process.exit(1); });
