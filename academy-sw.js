/**
 * academy-sw.js — the Triventurex Academy's service worker: install it like an
 * app and learn offline (GitHub Pages, or `node server.js`; not from disk).
 *
 * Registered by js/academy/academy.js with scope `./academy`, so it controls
 * ONLY the Academy page — never the game, phone or TV pages.
 *
 * - Install: saves the Academy's own files (ACADEMY_FILES — every script and
 *   stylesheet academy.html loads; test/academy-offline.test.js checks the list)
 *   every edition's config.js + questions.js (ids read from editions.js) and the
 *   emoji pictures (images/emoji/, list from js/shared/icons-data.js, ~600 KB).
 * - Code and questions (html / js / css / json): network first, so updates show
 *   as soon as there is a connection; the saved copy when offline.
 * - Pictures (emoji, place photos): saved the first time they are shown and then
 *   read from the saved copy. The page can save an edition's photos in one go
 *   (Save photos for offline, in More) — same cache, ACADEMY_CACHE.
 *
 * Changing how this file caches? Raise the version in ACADEMY_CACHE (and in
 * js/academy/academy.js) so old copies are cleared.
 */

const ACADEMY_CACHE = 'tx-academy-v1';

const ACADEMY_FILES = [
  'academy.html',
  'academy.webmanifest',
  'css/styles.css',
  'css/academy.css',
  'css/help.css',
  'game_editions/editions.js',
  'js/shared/utils.js',
  'js/shared/icon-registry.js',
  'js/shared/icons-data.js',
  'js/shared/icons.js',
  'js/shared/help.js',
  'js/shared/config.js',
  'js/shared/edition.js',
  'js/shared/questions.js',
  'js/shared/marks.js',
  'js/shared/academy.js',
  'js/academy/academy.js',
  'js/academy/modes.js',
  'images/academy/icon-192.png',
  'images/academy/apple-touch-icon.png',
];

/** The emoji pictures questions and labels are drawn with (js/shared/icons-data.js). */
// Loaded while this file first runs (the only time a worker may load new scripts); defines TX_ICON_DATA
try { importScripts('js/shared/icons-data.js'); } catch {}
function emojiFiles() {
  return typeof TX_ICON_DATA === 'undefined' ? [] : TX_ICON_DATA.emoji.map(code => `images/emoji/${code}.svg`);
}

/** Every edition's config + questions, from the ids in editions.js. */
async function editionFiles() {
  try {
    const text = await (await fetch('game_editions/editions.js', { cache: 'no-cache' })).text();
    const ids = [...text.matchAll(/\bid:\s*['"]([\w-]+)['"]/g)].map(m => m[1]);
    return ids.flatMap(id => [`game_editions/${id}/config.js`, `game_editions/${id}/questions.js`]);
  } catch { return []; }
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(ACADEMY_CACHE);
    const files = [...ACADEMY_FILES, ...await editionFiles(), ...emojiFiles()];
    // One by one: a missing file must not stop the rest from being saved
    await Promise.all(files.map(f => cache.add(new Request(f, { cache: 'no-cache' })).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith('tx-academy-') && key !== ACADEMY_CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

const isPicture = url => /\.(png|jpe?g|webp|gif|svg)$/i.test(url.pathname);

/** How long to wait for the network before using the saved copy (weak signal). */
const NETWORK_WAIT_MS = 4000;

/** Network first; the saved copy when offline or slow. The page itself matches any ?edition=. */
async function networkFirst(request) {
  const cache = await caches.open(ACADEMY_CACHE);
  const navigate = request.mode === 'navigate';
  const savedCopy = async () => (await cache.match(request, { ignoreSearch: navigate })) ||
    (navigate ? cache.match('academy.html', { ignoreSearch: true }) : undefined);
  const fetching = fetch(request).then(fresh => {
    if (fresh.ok) cache.put(request, fresh.clone());
    return fresh;
  });
  let timer;
  const slow = new Promise(resolve => { timer = setTimeout(resolve, NETWORK_WAIT_MS, 'slow'); });
  try {
    const first = await Promise.race([fetching, slow]);
    if (first !== 'slow') return first;
    return (await savedCopy()) || await fetching;   // slow: the saved copy now, the fresh one is still saved for next time
  } catch (err) {
    const saved = await savedCopy();
    if (saved) return saved;
    throw err;
  } finally { clearTimeout(timer); }
}

/** Saved copy first; fetched (and saved) the first time. */
async function cacheFirst(request) {
  const cache = await caches.open(ACADEMY_CACHE);
  const saved = await cache.match(request);
  if (saved) return saved;
  const fresh = await fetch(request);
  if (fresh.ok) cache.put(request, fresh.clone());
  return fresh;
}

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  event.respondWith(isPicture(url) ? cacheFirst(request) : networkFirst(request));
});
