/**
 * game_editions/template/deeds.js
 * AUTO-GENERATED from deeds.csv by `npm run build:content` — do not edit directly.
 *
 * 4 deed cards  (2 good / 2 bad)
 */

window.DEEDS_DATA = [
  {"id": 1, "type": "good", "text": "Example good deed — you helped a friend.", "effects": [{"effect": "score_add", "value": 2, "landmark": null}, {"effect": "move_forward", "value": 2, "landmark": null}], "effect": "score_add", "value": 2, "landmark": null, "mood": "social"},
  {"id": 2, "type": "good", "text": "Example good deed with a choice of rewards — one is picked each game.", "effects": [{"effect": "move_forward", "value": 3, "landmark": null}, {"effect": "score_add", "value": 2, "landmark": null}, {"effect": "protection", "value": 1, "landmark": null}], "effect": "move_forward", "value": 3, "landmark": null, "mood": "blessing"},
  {"id": 3, "type": "bad", "text": "Example bad deed — you forgot your homework.", "effects": [{"effect": "score_remove", "value": 1, "landmark": null}, {"effect": "move_back", "value": 2, "landmark": null}], "effect": "score_remove", "value": 1, "landmark": null, "mood": "reflection"},
  {"id": 4, "type": "bad", "text": "Example bad deed — you were late, so you sit out a turn.", "effects": [{"effect": "skip_turn", "value": 0, "landmark": null}, {"effect": "score_remove", "value": 2, "landmark": null}], "effect": "skip_turn", "value": 0, "landmark": null, "mood": "risk"},
];
