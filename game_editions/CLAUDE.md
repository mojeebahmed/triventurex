# game_editions — content and edition configs

Notes for Claude, loaded automatically when working in this folder. The project-wide rules are in the
root `CLAUDE.md`. Keep invariants for this area here; update them when one changes.

## Files
- `game_editions/editions.js` — edition registry (loaded via `<script>` in index.html)
- `game_editions/<id>/config.js` — edition config (name, colours, landmarks, finish text, SPACE_INFO, SPACE_DISTRIBUTION)
- `game_editions/<id>/questions.csv` + `deeds.csv` + `actions.csv` — edit content here
- `game_editions/<id>/questions.js` + `deeds.js` + `actions.js` — generated from CSV (`npm run build:content`)
- `game_editions/shared/actions.csv` (+ generated `actions.js`, `GENERAL_ACTIONS_DATA`) — general action cards for every edition (C4)
- `game_editions/IDEAS.md` — ideas for new editions, content targets, and how we build one

## Content workflow
Edit CSV → `npm run build:content` (checks the content, then regenerates questions.js / deeds.js / actions.js) → refresh browser.
- `npm run check:content` — check only; fails if a CSV has errors or a generated JS file is out of date. `npm test` includes the same checks
- The checker (`scripts/content.js`) reports `file:line message`: wrong column count (unquoted comma), bad/duplicate ids, type/difficulty, multi answer not pointing at a filled option, unknown deed effects, landmark effects vs config.js `LANDMARKS`; warnings for missing topics and `{landmark}` text without a landmark effect
- `questions.csv` first column is `id` — unique per edition, never reuse or renumber (asked-question tracking is stored by id). New question → next unused number
- Any field containing a comma MUST be wrapped in double quotes (`"Madrid, Spain"`)
- Never edit questions.js / deeds.js by hand — they're generated (the fallback for index.html opened from disk)
- Column + effect reference for authors: `game_editions/template/README.md`
- `scripts/` = Node-only dev tooling (not served); `tools/` = browser dev tools (served). `scripts/commons-image.js` finds, crops and credits Wikimedia Commons photos for an edition (see `game_editions/IDEAS.md`); `scripts/review-sheet.js <edition>` writes a printable REVIEW.md of its questions

## Architecture — V2 (don't revert)
- **General action cards (C4)**: `game_editions/shared/actions.csv` → `window.GENERAL_ACTIONS_DATA` (index.html script + CSV fetch in `_loadEditionCSV`). `_actionDeck(general)` in ui.js mixes them into the edition's deck with ids `g<id>` so tracking never clashes with edition ids. Rule `actions.general` (default on). Digital cards are possible when the edition OR the shared file has cards (`_hasActionCards`). `shared/` has no questions.csv, so `listEditions()` skips it; `build:content` / `check:content` handle it as `shared`
- **Action cards (C3)**: optional `actions.csv` per edition (`id, text, kind, note`; kinds in `CONFIG.ACTION_KINDS`: act / explain / sound). Drawn without repeats (`_drawActionCard`, tracked like questions under the `actions` key); the drawn card is stored on `state.turn.actionCard` so a resumed turn shows the same card. No actions.csv → physical-deck prompt
- **Check columns (2026-11-17)**: the Question Validator's `corrected` / `ready` exports add `checked, checked_on, check_how, sources, source_links, source_quote, as_of, check_hash` at the end of questions.csv (`CHECK_COLUMNS` in question-validator/qv/domain/question.py). `_parseQuestionsCSV` puts them on `q.check` only when `checked` is filled (`_questionCheck` in csv.js; `sources` / `source_links` split on ` | `, matched by position). The checker errors on an unknown `checked` value and **warns when `check_hash` ≠ `checkHash(row)`** (the question was changed after it was checked). `checkHash` (scripts/content.js) must stay equal to `check_hash` in the validator — a validator test runs node to compare. Shown by `checkBadgeHtml` / `checkDetailsHtml` (js/shared/questions.js; source names and quotes come from web pages → always `esc()`, links only http(s)). The validator ignores these columns in its content hash, so re-importing an exported file keeps every result

## Effect types and related notes
`score_add`, `score_remove`, `move_forward`, `move_back`, `move_to_prev_landmark`, `move_to_next_landmark`, `skip_turn`, `extra_turn`, `all_players_gain`, `all_players_lose`, `protection`
(The old named `move_to_landmark` effect and the `landmark` CSV columns were removed on 2026-10-19 — use the next / previous landmark effects.)
