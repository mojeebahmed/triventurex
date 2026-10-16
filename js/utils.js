/**
 * utils.js
 * Small helpers shared by the host page (index.html) and the player page
 * (player.html). Load before any other game script.
 */

/**
 * Escape a value for safe insertion into HTML — both element content and
 * quoted attribute values (e.g. style="background:${esc(color)}").
 * Use for anything a player can type or a phone can send: names, tokens, colours.
 * NOT needed for textContent (showToast, button labels, modal titles).
 */
function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
