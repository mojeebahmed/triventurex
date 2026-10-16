/**
 * game_editions/template/deeds.js
 * Good and Bad deed cards for this edition.
 *
 * HOW TO ADD DEED CARDS:
 *   Copy an entry, give it a unique `id`, and fill in the fields.
 *
 * Fields:
 *   id        – unique number (required)
 *   type      – "good" or "bad"
 *   text      – full card text read aloud to players
 *   effect    – what the card does (primary; see effects table below)
 *   value     – number of points or spaces (0 for landmark-targeting effects)
 *   landmark  – landmark name for move_to_landmark effect, otherwise null
 *               (must match exactly a `name` in config.js LANDMARKS array)
 *   effects   – (optional) array of { effect, value, landmark } for variable rewards;
 *               if present and length > 1, one is chosen randomly each game.
 *               In deeds.csv, use columns effect_2/value_2/landmark_2 and
 *               effect_3/value_3/landmark_3 for up to three alternatives.
 *   mood      – (optional) flavour tag, e.g. blessing, social, challenge,
 *               reflection, funny, risk — used for future filtering.
 *
 * Effects:
 *   score_add             – player gains `value` points
 *   score_remove          – player loses `value` points
 *   move_forward          – player moves forward `value` spaces
 *   move_back             – player moves back `value` spaces
 *   move_to_landmark      – player moves to the named landmark (backward; penalty)
 *   move_to_next_landmark – player advances to the next landmark ahead of them
 *   skip_turn             – player must skip their next turn
 *   extra_turn            – player gets an extra roll immediately
 *   all_players_gain      – every player gains `value` points
 *   all_players_lose      – every player loses `value` points
 *   protection            – player's next bad deed card is cancelled
 */

window.DEEDS_DATA = [

  // ── Good deeds ────────────────────────────────────────────────────────────

  {
    id: 1,
    type: "good",
    text: "Example good deed. You earn 2 points!",
    effect: "score_add",
    value: 2,
    landmark: null,
  },

  {
    id: 2,
    type: "good",
    text: "Another good deed. Move forward 2 spaces.",
    effect: "move_forward",
    value: 2,
    landmark: null,
  },

  // ── Bad deeds ─────────────────────────────────────────────────────────────

  {
    id: 101,
    type: "bad",
    text: "Example bad deed. Lose 2 points.",
    effect: "score_remove",
    value: 2,
    landmark: null,
  },

  {
    id: 102,
    type: "bad",
    text: "Another bad deed. Move back 1 space.",
    effect: "move_back",
    value: 1,
    landmark: null,
  },

  // {
  //   id: 103,
  //   type: "bad",
  //   text: "Go back to a landmark.",
  //   effect: "move_to_landmark",
  //   value: 0,
  //   landmark: "My Place",   // must match a name in config.js LANDMARKS
  // },

];
