# test — the test suite

Notes for Claude, loaded automatically when working in this folder. The project-wide rules are in the
root `CLAUDE.md`. Keep invariants for this area here; update them when one changes.

## Tests
`npm test` — Node's built-in test runner (`node:test`), files in `test/**/*.test.js`.
- `test/turn-flow.test.js` drives the real host turn pipeline (scripts loaded in index.html order, UI stubbed) — add a scenario here when changing turn behaviour
- `test/csv.test.js` — CSV parser + every edition's content (CSV must match the generated JS; valid answers/effects)
- `test/board.test.js` — property test: random boards for every template of every edition in `editions.js` must keep all placement rules, and every landmark tile label must match where the player actually goes (raise `BOARDS_PER_TEMPLATE` locally to hunt rare cases)
- `test/action-cards.test.js` — drawing/showing action cards
- `test/ui-rules.test.js` — the space modals follow the game's rules (points, timer, difficulty, answering on the phone)
- `test/rules.test.js`, `test/stats.test.js`, `test/questions.test.js`, `test/path-design.test.js`, `test/turn.test.js`, `test/players.test.js`, `test/utils.test.js`, `test/dice.test.js` — pure unit tests
- `test/html-structure.test.js` — every `<div>` in index.html / player.html / academy.html is closed, the host screens are top-level (a missing `</div>` once hid the board), and academy.html loads only shared + academy scripts
- `test/icons.test.js` — icons: `icon()` / `iconText()`, edition → `ICON_OVERRIDES` → `ICONS` lookup, valid registry, host and phones offer the same badges + colours, no raw emoji/icon symbols in engine code, every icon name used exists, bundles up to date, every page loads the icon scripts in order
- `test/help.test.js` — the in-game help: a topic for every setup tab, Academy mode and phone view; every icon, word and link exists; markup renders safely
- `test/academy.test.js` — Academy rounds (js/shared/academy.js) + every edition gives each mode content
- `test/academy-offline.test.js` — the Academy as an app: academy-sw.js saves every file academy.html loads, same cache name as the page, every edition found, manifest + icons valid
- `test/socket-events.test.js` — every `TX_NET.on('…')` event is in socket-client.js's forward list
- `test/server.test.js` starts the real server on a random port and drives it with `socket.io-client` (dev dependency) as host + phones
