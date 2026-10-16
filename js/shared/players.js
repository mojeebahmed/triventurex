/**
 * players.js
 * Player state creation and mutation helpers.
 * All functions are pure (return the mutated player) — game.js owns the state.
 */

/**
 * Create a new player object.
 * @param {number} id
 * @param {string} name
 * @param {string} color  CSS colour string
 * @returns {Object}
 */
function createPlayer(id, name, color, token) {
  const defaults = CONFIG.PLAYERS?.defaults;
  return {
    id,
    name,
    color,
    token: token || defaults?.[id % (defaults?.length || 1)]?.token || '●',
    position:             0,
    score:                0,
    finished:             false,
    finishOrder:          null,
    skipNextTurn:         false,
    protectedFromBadDeed: false,  // set by 'protection' deed; clears after absorbing one bad deed
    hasExtraTurn:         false,  // set by 'extra_turn' deed; grants one additional roll
  };
}

/**
 * Move a player forward (or backward with negative steps).
 * Clamps position to [0, spaces.length - 1] and sets finished flag.
 * @param {Object} player
 * @param {Array<Object>} spaces
 * @param {number} steps
 * @returns {Object} the same player (mutated)
 */
function movePlayer(player, spaces, steps) {
  const maxPos = spaces.length - 1;
  player.position = Math.max(0, Math.min(player.position + steps, maxPos));
  if (player.position >= maxPos && !player.finished) {
    player.finished = true;
  }
  return player;
}

/**
 * Move a player to an absolute position on the board.
 * @param {Object} player
 * @param {Array<Object>} spaces
 * @param {number} position
 * @returns {Object}
 */
function movePlayerToPosition(player, spaces, position) {
  const maxPos = spaces.length - 1;
  player.position = Math.max(0, Math.min(position, maxPos));
  if (player.position >= maxPos && !player.finished) {
    player.finished = true;
  }
  return player;
}

/**
 * Add (or remove) score points. Points cannot go below 0.
 * Fires window._onScoreChange(player, amount) if defined — used by game.js
 * to trigger the score flyout animation without coupling to the DOM here.
 * Also fires window._onScoreChange for any caller that hooks into it.
 * @param {Object} player
 * @param {number} amount  positive to add, negative to subtract
 * @returns {Object}
 */
function addScore(player, amount) {
  player.score = Math.max(0, player.score + amount);
  if (amount !== 0 && typeof window._onScoreChange === 'function') {
    window._onScoreChange(player, amount);
  }
  return player;
}

/**
 * Return a copy of the players array sorted by score (desc),
 * with finish order as a tiebreaker.
 * @param {Array<Object>} players
 * @returns {Array<Object>}
 */
function getSortedPlayers(players) {
  return [...players].sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    if (a.finishOrder && b.finishOrder) return a.finishOrder - b.finishOrder;
    if (a.finishOrder) return -1;
    if (b.finishOrder) return 1;
    return 0;
  });
}
