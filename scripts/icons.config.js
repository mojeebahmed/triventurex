/**
 * scripts/icons.config.js — which icons the game draws. Used by
 * scripts/build-icons.js (`npm run build:icons`).
 *
 * Two kinds of icon:
 *   • Emoji in content (tiles, cards, awards, badges, edition icons, question
 *     text) are drawn with ONE emoji set, so they look the same on every device.
 *   • A glyph at the start or end of a CONTROL's label (a <button>, tab or
 *     summary) is drawn as a line icon in the control's own colour — the table
 *     below says which. Plain symbols like + and − only count when they stand
 *     alone or are followed by a space ("+ Add", "−"), so "+1" and "+30s" stay text.
 *
 * Overrides: keep them few. To take one icon from another set, install that
 * set (`npm i -D @iconify-json/<set>`) and write '<set>:<icon name>' — e.g.
 *   emoji.overrides: { '🐊': 'twemoji' }          (same emoji, other set)
 *   controls: { '🎨': 'ph:palette-bold' }          (one control from Phosphor)
 * then run `npm run build:icons`. The icon credits are written automatically.
 */

module.exports = {
  emoji: {
    set: 'fluent-emoji-flat',     // Microsoft Fluent Emoji, Flat style (MIT)
    overrides: {},
  },

  // Control glyph → line icon ('<name>' = Lucide, ISC; '<set>:<name>' = another installed set)
  controls: {
    // setup tabs, rules side tabs
    '🎲': 'dices',          '⚙️': 'settings',        '📚': 'library-big',    '✏️': 'pencil',
    '🏆': 'trophy',         '❓': 'circle-help',      '🎬': 'clapperboard',   '🗺️': 'map',
    '⏱️': 'timer',          '🏷️': 'tags',
    // actions
    '▶': 'play',            '↩': 'undo-2',           '↺': 'rotate-ccw',      '📋': 'clipboard-copy',
    '💾': 'save',           '✨': 'sparkles',        '➕': 'plus',           '+': 'plus',
    '−': 'minus',           '✕': 'x',                '🎨': 'palette',        '🔁': 'repeat',
    '📺': 'tv',             '📱': 'smartphone',      '🎮': 'monitor',        '⌂': 'house',
    '📜': 'scroll-text',    '🚩': 'flag',            '🔎': 'search',         '🔍': 'search',
    '🖨️': 'printer',        '⏭️': 'skip-forward',    '⏸️': 'pause',          '🔀': 'shuffle',
    '🔄': 'refresh-cw',     '←': 'arrow-left',       '→': 'arrow-right',     '👁': 'eye',
    '🙈': 'eye-off',        '✅': 'check',           '❌': 'x',              '🎓': 'graduation-cap',
    // Academy modes
    '🃏': 'layers',         '🧩': 'puzzle',          '✔️': 'circle-check',   '⚡': 'zap',
    '🧭': 'compass',
  },
};
