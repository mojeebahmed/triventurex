/**
 * icons.js — draw emoji and control icons from the sets bundled with the game,
 * so they look the same on every device (host, phones, TV, Academy).
 *
 *   • Emoji anywhere in the page → <img class="tx-emoji"> from images/emoji/
 *     (Fluent Emoji Flat; see scripts/icons.config.js).
 *   • A glyph at the start or end of a control's label (button, tab, summary)
 *     that is in the control table → an inline line icon (Lucide) that takes
 *     the control's text colour.
 *
 * Content keeps plain emoji everywhere (CSVs, config.js, JS strings); startIcons()
 * swaps them in the page as it changes, through one MutationObserver. Text-only
 * places (<option>, <title>, inputs, textarea) keep the device's own emoji.
 *
 * The icon data (which emoji files exist, the control SVGs) is generated into
 * js/shared/icons-data.js by `npm run build:icons`. Top-level code here does
 * not touch the page; the pure helpers are unit-tested in test/icons.test.js.
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

/**
 * A control label's leading / trailing glyph, if it is in the control table
 * (`keys` = Set of glyphKey()s). A glyph only counts when a space or the end
 * of the text follows (leading) or a space or the start precedes it (trailing),
 * so "+1" and "+30s" stay text. → { lead: { glyph, end } | null, trail: { glyph, start } | null }
 */
function controlGlyphs(text, keys, { first = true, last = true } = {}) {
  const t = String(text);
  const res = { lead: null, trail: null };
  const probe = s => {                        // the longest table glyph at the start of s
    for (const len of [3, 2, 1]) {
      const g = [...s].slice(0, len).join('');
      if (g && keys.has(glyphKey(g))) return g;
    }
    return null;
  };
  if (first) {
    const lead = t.length - t.trimStart().length;
    const g = probe(t.slice(lead));
    if (g) {
      const end = lead + g.length;
      if (end === t.length || /\s/.test(t[end])) res.lead = { glyph: g, end };
    }
  }
  if (last) {
    const body = t.trimEnd();
    const chars = [...body];
    for (const len of [3, 2, 1]) {
      const g = chars.slice(-len).join('');
      if (!g || !keys.has(glyphKey(g))) continue;
      const start = body.length - g.length;
      if ((start === 0 || /\s/.test(body[start - 1])) && (!res.lead || start >= res.lead.end)) res.trail = { glyph: g, start };
      break;
    }
  }
  return res;
}

// ── In the page ─────────────────────────────────────────────────────────────────

const CONTROL_SEL = 'button, summary, [role="tab"], .btn, .link-btn';
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'TITLE', 'NOSCRIPT', 'svg', 'SVG']);
let _iconData = null, _controlKeys = null, _emojiKeys = null;

function _iconsReady() {
  if (_iconData) return true;
  if (typeof TX_ICON_DATA === 'undefined') return false;
  _iconData = TX_ICON_DATA;
  _controlKeys = new Set(Object.keys(_iconData.controls));
  _emojiKeys = new Set(_iconData.emoji);
  return true;
}

function _emojiImg(doc, glyph) {
  const img = doc.createElement('img');
  img.className = 'tx-emoji';
  img.src = EMOJI_DIR + glyphKey(glyph) + '.svg';
  img.alt = glyph;                 // copy / paste and screen readers keep the emoji
  img.draggable = false;
  img.decoding = 'async';
  return img;
}

function _controlIcon(doc, glyph) {
  const span = doc.createElement('span');
  span.className = 'tx-icon';
  span.setAttribute('aria-hidden', 'true');
  span.innerHTML = _iconData.controls[glyphKey(glyph)];
  return span;
}

/** Replace the emoji in one text node with images (and control glyphs with icons). */
function _enhanceText(node) {
  const text = node.nodeValue;
  if (!text || !/[^\x00-\x7F]|[+]/.test(text)) return;
  const parent = node.parentNode;
  if (!parent || SKIP_TAGS.has(parent.nodeName) || parent.closest?.('[contenteditable], .no-icons')) return;
  const doc = node.ownerDocument;

  // Control glyph? Only on the control's first / last piece of text
  let lead = null, trail = null;
  const control = parent.closest?.(CONTROL_SEL);
  if (control && !parent.closest('[data-content]')) {
    const texts = [];
    const w = doc.createTreeWalker(control, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) if (n.nodeValue.trim()) texts.push(n);
    ({ lead, trail } = controlGlyphs(text, _controlKeys, { first: texts[0] === node, last: texts.at(-1) === node }));
  }

  const parts = [];
  let pos = 0;
  const pushText = (from, to) => { if (to > from) parts.push(doc.createTextNode(text.slice(from, to))); };
  const emojiIn = (from, to) => {
    let p = from;
    for (const e of findEmoji(text.slice(from, to))) {
      const at = from + e.index;
      if (!_emojiKeys.has(glyphKey(e.glyph))) continue;          // no image for it: keep the device's emoji
      pushText(p, at);
      parts.push(_emojiImg(doc, e.glyph));
      p = at + e.glyph.length;
    }
    pushText(p, to);
  };
  if (lead) { pushText(0, lead.end - lead.glyph.length); parts.push(_controlIcon(doc, lead.glyph)); pos = lead.end; }
  const end = trail ? trail.start : text.length;
  emojiIn(pos, end);
  if (trail) { parts.push(_controlIcon(doc, trail.glyph)); pushText(trail.start + trail.glyph.length, text.length); }

  const changed = parts.length !== 1 || parts[0].nodeType !== 3 || parts[0].nodeValue !== text;
  if (!changed) return;
  const frag = doc.createDocumentFragment();
  parts.forEach(p => frag.appendChild(p));
  parent.replaceChild(frag, node);
  // an icon-only control still needs a name for screen readers
  if (control && !control.textContent.trim() && !control.getAttribute('aria-label') && !control.title) {
    control.setAttribute('aria-label', (lead || trail).glyph);
  }
}

/** Replace emoji / control glyphs in an element and everything inside it. */
function enhanceIcons(root) {
  if (!_iconsReady() || !root) return;
  if (root.nodeType === 3) { _enhanceText(root); return; }
  if (root.nodeType !== 1 || SKIP_TAGS.has(root.nodeName)) return;
  const texts = [];
  const w = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) texts.push(n);
  texts.forEach(_enhanceText);
}

/** Start drawing icons on this page: the current content, and everything added later. */
function startIcons(doc = typeof document !== 'undefined' ? document : null) {
  if (!doc?.body || typeof MutationObserver === 'undefined' || !_iconsReady() || doc.__txIcons) return;
  doc.__txIcons = true;
  enhanceIcons(doc.body);
  new MutationObserver(records => {
    for (const r of records) {
      if (r.type === 'characterData') enhanceIcons(r.target);
      else r.addedNodes.forEach(n => enhanceIcons(n));
    }
  }).observe(doc.body, { childList: true, subtree: true, characterData: true });
}

if (typeof module !== 'undefined') module.exports = { glyphKey, findEmoji, controlGlyphs, EMOJI_RE };
