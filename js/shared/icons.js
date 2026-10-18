/**
 * icons.js — draw icons from the sets bundled with the game, so they look the
 * same on every device (host, phones, TV, Academy).
 *
 * Engine code asks for icons BY NAME (js/shared/icon-registry.js); the active
 * edition can override any name in its config.js ICONS block (merged into
 * CONFIG.EDITION_ICONS by js/shared/edition.js), so lookup is edition → engine:
 *   icon('undo')            → HTML: an inline line icon (Lucide) in the text colour,
 *                             or an emoji image (Fluent Emoji Flat)
 *   iconText('tileSkip')    → plain text for places that cannot hold HTML;
 *                             '' for line icons
 *   <i data-icon="undo"></i> in the HTML pages, filled in by startIcons()
 * `icon()` / `iconText()` also accept an emoji itself — editions and saved
 * player badges hold emoji, not names.
 *
 * Content (questions, deed texts, edition labels) keeps plain emoji. After
 * startIcons(), one MutationObserver swaps emoji in the page for the bundled
 * images, so content looks the same as the engine's icons. Text-only places
 * (<option>, <title>, inputs) keep the device's own emoji.
 *
 * The icon data (emoji files that exist, line-icon SVGs) is generated into
 * js/shared/icons-data.js by `npm run build:icons`. Top-level code here does not
 * touch the page; the pure helpers are unit-tested in test/icons.test.js.
 */

const EMOJI_DIR = 'images/emoji/';

// Emoji: flags, keycaps, or a pictograph with optional variation/skin-tone and ZWJ parts
const EMOJI_RE = /(?:\p{Regional_Indicator}{2})|(?:[#*0-9]️?⃣)|(?:\p{Extended_Pictographic}(?:️|[\u{1F3FB}-\u{1F3FF}])?(?:‍\p{Extended_Pictographic}(?:️|[\u{1F3FB}-\u{1F3FF}])?)*)/gu;
// Text symbols that look like pictographs but must stay text unless followed by FE0F
const TEXT_ONLY = new Set(['©', '®', '™', '↔', '↕', '‼', '⁉', '#', '*', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']);

/** File key of an emoji: its code points in hex, without the FE0F variation selector. */
function glyphKey(g) {
  return [...String(g).replace(/️/g, '')].map(c => c.codePointAt(0).toString(16)).join('-');
}

/** Emoji in a string → [{ index, glyph }] (text-style symbols like © are skipped). */
function findEmoji(text) {
  const out = [];
  for (const m of String(text).matchAll(EMOJI_RE)) {
    if (TEXT_ONLY.has(m[0])) continue;
    out.push({ index: m.index, glyph: m[0] });
  }
  return out;
}

/** Is `s` exactly one emoji? */
const isEmoji = s => { const e = findEmoji(s); return e.length === 1 && e[0].index === 0 && e[0].glyph === String(s); };

// ── By name ─────────────────────────────────────────────────────────────────────

/**
 * The entry for a name: the edition's override first, then the engine's
 * registry. Entries: 'emoji:🎲', 'lucide:undo-2' (any '<set>:<icon>'), or
 * 'url:<path>' (an edition's own picture). null for unknown names.
 */
function iconEntry(name) {
  const ed = typeof CONFIG !== 'undefined' ? CONFIG.EDITION_ICONS : null;
  return (ed && ed[name]) || (typeof ICONS !== 'undefined' && ICONS[name]) || null;
}

/** Plain text for an icon name or an emoji: the emoji, or '' for line icons, pictures and unknown names. */
function iconText(nameOrEmoji) {
  const e = iconEntry(nameOrEmoji);
  if (e) return e.startsWith('emoji:') ? e.slice(6) : '';
  return isEmoji(nameOrEmoji) ? String(nameOrEmoji) : '';
}

const _escAttr = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function _iconsData() { return typeof TX_ICON_DATA !== 'undefined' ? TX_ICON_DATA : null; }

/** An emoji as HTML: the bundled image when there is one, otherwise the emoji itself. */
function emojiHtml(glyph) {
  const data = _iconsData();
  if (!data || !data.emoji.includes(glyphKey(glyph))) return _escAttr(glyph);
  return `<img class="tx-emoji" src="${EMOJI_DIR}${glyphKey(glyph)}.svg" alt="${_escAttr(glyph)}" draggable="false" decoding="async">`;
}

/**
 * HTML for an icon name (or an emoji). Line icons are decorative
 * (aria-hidden) — the control's own text names it. Unknown names give ''.
 */
function icon(nameOrEmoji) {
  const e = iconEntry(nameOrEmoji);
  if (!e) return isEmoji(nameOrEmoji) ? emojiHtml(nameOrEmoji) : '';
  return entryHtml(e);
}

/** HTML for a registry entry ('emoji:🎲', 'lucide:undo-2', 'url:<path>'); '' if it can't be drawn. */
function entryHtml(e) {
  e = String(e || '');
  if (e.startsWith('emoji:')) return emojiHtml(e.slice(6));
  if (e.startsWith('url:')) return `<img class="tx-emoji tx-picture" src="${_escAttr(e.slice(4))}" alt="" draggable="false" decoding="async">`;
  const svg = _iconsData()?.ui?.[e];            // line icons are bundled by id ('lucide:undo-2')
  return svg ? `<span class="tx-icon" aria-hidden="true">${svg}</span>` : '';
}

// ── In the page ─────────────────────────────────────────────────────────────────

const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'TITLE', 'NOSCRIPT', 'svg', 'SVG']);

/** Replace the emoji in one text node with the bundled images. */
function _emojiInText(node) {
  const text = node.nodeValue;
  if (!text || !/[^\x00-\x7F]/.test(text)) return;
  const parent = node.parentNode;
  if (!parent || SKIP_TAGS.has(parent.nodeName) || parent.closest?.('[contenteditable], .no-icons')) return;
  const data = _iconsData();
  const found = findEmoji(text).filter(e => data.emoji.includes(glyphKey(e.glyph)));
  if (!found.length) return;
  const doc = node.ownerDocument;
  const frag = doc.createDocumentFragment();
  let p = 0;
  for (const e of found) {
    if (e.index > p) frag.appendChild(doc.createTextNode(text.slice(p, e.index)));
    const tmp = doc.createElement('span');
    tmp.innerHTML = emojiHtml(e.glyph);
    frag.appendChild(tmp.firstChild);
    p = e.index + e.glyph.length;
  }
  if (p < text.length) frag.appendChild(doc.createTextNode(text.slice(p)));
  parent.replaceChild(frag, node);
}

/**
 * Fill <i data-icon="name"></i> placeholders, put an emoji in front of text-only
 * labels (<option data-icon-text="easy">Easy</option>), and swap emoji in an
 * element and everything inside it.
 */
function enhanceIcons(root) {
  if (!_iconsData() || !root) return;
  if (root.nodeType === 3) { _emojiInText(root); return; }
  if (root.nodeType !== 1 || SKIP_TAGS.has(root.nodeName)) return;
  const slots = [...(root.matches?.('[data-icon]') ? [root] : []), ...root.querySelectorAll('[data-icon]')];
  for (const el of slots) {
    if (el.dataset.iconDone === el.dataset.icon) continue;
    el.dataset.iconDone = el.dataset.icon;
    el.innerHTML = icon(el.dataset.icon);
  }
  const labels = [...(root.matches?.('[data-icon-text]') ? [root] : []), ...root.querySelectorAll('[data-icon-text]')];
  for (const el of labels) {
    if (el.dataset.iconDone === el.dataset.iconText) continue;
    if (el.dataset.label === undefined) el.dataset.label = el.textContent.trim();
    el.dataset.iconDone = el.dataset.iconText;
    const t = iconText(el.dataset.iconText);
    el.textContent = (t ? t + ' ' : '') + el.dataset.label;
  }
  const texts = [];
  const w = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) texts.push(n);
  texts.forEach(_emojiInText);
}

/** Start drawing icons on this page: the current content, and everything added later. */
function startIcons(doc = typeof document !== 'undefined' ? document : null) {
  if (!doc?.body || typeof MutationObserver === 'undefined' || !_iconsData() || doc.__txIcons) return;
  doc.__txIcons = true;
  enhanceIcons(doc.body);
  new MutationObserver(records => {
    for (const r of records) {
      if (r.type === 'characterData') enhanceIcons(r.target);
      else if (r.type === 'attributes') enhanceIcons(r.target);
      else r.addedNodes.forEach(n => enhanceIcons(n));
    }
  }).observe(doc.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['data-icon'] });
}

if (typeof module !== 'undefined') module.exports = { glyphKey, findEmoji, isEmoji, iconEntry, iconText, icon, entryHtml, EMOJI_RE };
