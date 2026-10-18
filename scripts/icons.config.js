/**
 * scripts/icons.config.js — the emoji set the game draws with. Used by
 * scripts/build-icons.js (`npm run build:icons`).
 *
 * Which icon each NAME uses (line icons for controls, emoji for game symbols)
 * is in js/shared/icon-registry.js — that is where icons are added or changed.
 * This file only says how EMOJI are drawn: one set for the whole game, so the
 * engine's emoji and the editions' content emoji look alike.
 *
 * Overrides: keep them few. To draw one emoji from another set, install that
 * set (`npm i -D @iconify-json/<set>`) and add it here, e.g.
 *   overrides: { '🐊': 'twemoji' }
 * then run `npm run build:icons`. The icon credits are written automatically.
 */

module.exports = {
  emoji: {
    set: 'fluent-emoji-flat',     // Microsoft Fluent Emoji, Flat style (MIT)
    overrides: {},
  },
};
