/**
 * game_editions/template/deeds.js
 * AUTO-GENERATED from deeds.csv by `npm run build:content` — do not edit directly.
 *
 * 4 deed cards  (2 good / 2 bad)
 */

window.DEEDS_DATA = [
  {"id": 1, "type": "good", "text": "Example good deed — you helped a friend.", "effects": [{"effect": "score_add", "value": 2}, {"effect": "move_forward", "value": 2}], "effect": "score_add", "value": 2, "mood": "social"},
  {"id": 2, "type": "good", "text": "Example good deed with a choice of rewards — one is picked each game.", "effects": [{"effect": "move_forward", "value": 3}, {"effect": "score_add", "value": 2}, {"effect": "protection", "value": 1}], "effect": "move_forward", "value": 3, "mood": "blessing"},
  {"id": 3, "type": "bad", "text": "Example bad deed — you forgot your homework.", "effects": [{"effect": "score_remove", "value": 1}, {"effect": "move_back", "value": 2}], "effect": "score_remove", "value": 1, "mood": "reflection"},
  {"id": 4, "type": "bad", "text": "Example bad deed — you were late, so you sit out a turn.", "effects": [{"effect": "skip_turn", "value": 0}, {"effect": "score_remove", "value": 2}], "effect": "skip_turn", "value": 0, "mood": "risk"},
];
