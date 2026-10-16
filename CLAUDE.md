# Memory & Context Files
At the start of every conversation, read these files:
- /Users/mojeebahmed/Claude/Claude Mojeeb/about me/aboutme.md
- /Users/mojeebahmed/Claude/Claude Mojeeb/about me/memory.md
- /Users/mojeebahmed/Claude/Claude Mojeeb/about me/projects.md

Update memory.md whenever meaningful progress is made.
Save project files to this project's folder.

# About Me
- Name: Mojeeb Ahmed — private project, unrelated to Bauer Media

# Coding Standards
- Vanilla HTML + CSS + JS (no framework, no build step) for client
- V2 server: Node.js + Socket.IO + Express — keep client code vanilla
- All configurable values in `js/config.js` (engine) or `game_editions/<id>/config.js` (edition) — never hardcode

# Project: Triventurex

## Name
**Triventurex** = Trivia + Adventure + X. Game editions are interchangeable — same engine, different content.

## Active editions
- **Swab Quest** — Islamic/Ahmadiyya (first edition)
- **Football Quest** — football trivia (second edition)

## Run (V1 offline)
Open `index.html`. For images + CSV loading: `python3 -m http.server 8080`

## Run (V2 — live)
`node server.js` — serves everything and handles Socket.IO rooms.
- Host: `http://localhost:3000`
- Players: `http://<host-ip>:3000/player`

## Tests
`npm test` — Node's built-in test runner (`node:test`), files in `test/**/*.test.js`.
- `test/server.test.js` starts the real server on a random port and drives it with `socket.io-client` (dev dependency) as host + phones
- `server.js` exports `{ server, io, rooms }` and only calls `listen()` when run directly — keep it that way
- Run `npm test` before merging any change to `server.js`

## Key files
- `js/config.js` — engine settings (board, space types, zoom, animation, score, rules)
- `js/board.js` — board generation (`generateBoard`) and rendering (`buildBoard`, `updateBoardTokens`)
- `js/utils.js` — shared helpers for host + player pages (`esc()` HTML escaping); loaded first
- `js/dice.js` — `renderDie(n, sizeClass)` CSS dot-die used by host + player screens
- `js/socket-client.js` — `TX_NET` singleton; safe no-ops when offline
- `js/game.js` — main controller; handles both local and network game modes
- `js/ui.js` — modal flow (question, deed, action), timer, scoreboard, toast, category filter
- `js/players.js` — player setup row rendering, badge picker
- `js/player.js` — player screen logic (join, action box, session management)
- `game_editions/editions.js` — edition registry (loaded via `<script>` in index.html)
- `game_editions/<id>/config.js` — edition config (name, colours, landmarks, finish text, SPACE_INFO, SPACE_DISTRIBUTION)
- `game_editions/<id>/questions.csv` + `deeds.csv` — edit content here
- `game_editions/<id>/questions.js` + `deeds.js` — auto-generated from CSV
- `server.js` — room management, dice rolling, event relay
- `player.html` — lightweight player screen

## Content workflow
Edit CSV → ask Claude "regenerate the JS files" → refresh browser.
- `questions.csv` first column is `id` — unique per edition, never reuse or renumber (asked-question tracking is stored by id). New question → next unused number.
- Any field containing a comma MUST be wrapped in double quotes (`"Madrid, Spain"`). Unquoted commas silently shift columns — this broke 10 Football Quest questions before 2026-10-16.
- Regenerate JS with the game's own parser (`_parseQuestionsCSV` in game.js) so CSV and JS can't drift.

## Terminology
- **Edition** = interchangeable game content pack (was "theme" before 2026-06-01)
- `EDITION_CONFIG` — the `window` global set by each edition's `config.js`
- `TRIVENTUREX_EDITIONS` — the registry array in `game_editions/editions.js`
- localStorage key: `triventurex_edition` (saves last-used edition ID)

## Architecture — V1 (don't revert)
- **Edition loading**: `loadTheme()` in game.js; validates saved ID against registry before use; `_ENGINE_DEFAULTS` snapshot for clean edition switching; calls `_populateCategoryFilter()` after load
- **Board generation**: `generateBoard()` in board.js — pre-picks deed effects → constraint-aware deed-to-slot assignment (`_assignDeedsToSlots`) → no consecutive same-type → resolved landmark names stored on each deed
- **SPACE_DISTRIBUTION**: defined in `js/config.js` as engine default. Editions override via `SPACE_DISTRIBUTION` in their `config.js` — can be flat (all lengths) or keyed by `short`/`medium`/`long`. Questions always fill whatever space remains; no `question` key is needed in the distribution object.
- **Constraint-aware placement** (`_assignDeedsToSlots`):
  - `move_back N` → slot index ≥ N (not near start)
  - `move_forward N` → slot index ≤ poolLen-1-N (not near finish)
  - `move_to_prev_landmark N` → N landmarks exist before the slot
  - `move_to_next_landmark N` → N landmarks exist after the slot
  - Fallback: try alternative effect from card's effects array; then use least-bad slot
- **Landmark deeds**: `move_to_prev_landmark` / `move_to_next_landmark` with `value=N` (N = 1 → nearest). Names resolved at board-gen time and stored as `resolvedLandmark` on each deed. `{landmark}` in deed text is substituted at modal render time.
- **Variable deed effects**: each card has up to 3 effects in CSV; one chosen at board-gen time via `_pickActiveEffect()`
- **Exact finish**: `CONFIG.RULES.exactFinish` — player must roll exact number to land on finish; overshooting doesn't move. Toggle in Game Settings (select: on/off). Default: on.
- **Question tracking**: per-edition, per-difficulty localStorage keys (`triventurex_asked_<editionId>_<diff>`). Two modes: `session` (remember across games, default) or `game` (reset each game). When all questions in a difficulty are exhausted, auto-recycles. Questions filtered by selected categories.
- **Question topics (3-level filter)**: questions have `cat > subcat > topic` hierarchy. Game Settings shows a collapsible tree — checking a cat/subcat toggles all children; parent shows indeterminate state when partial. Saved per edition to localStorage as an array of selected topic strings (`triventurex_cats_<editionId>`). `getSelectedTopics()` in game.js returns a Set of topic strings; `_availablePool()` in ui.js filters by `q.topic`. Questions with empty topic always pass through (backwards compat with editions that only have `cat`).
- **Edition-neutral engine**: `player.score`, `addScore()`, `SCORE_VALUES`; editions provide `pointsName`, `finishLabel`, `finishCelebration`, `finishButtonLabel`, `endScreenMessage`
- **Score values**: every point label and award reads `CONFIG.SCORE_VALUES` / `CONFIG.FINISH_BONUS` — never hardcode numbers in UI text. Editions may override either in their `config.js` (reset on edition switch via `_ENGINE_DEFAULTS`)
- **Finish bonus**: `_recordFinish(player)` in game.js — called after every movement (roll, deed effect, GM move); idempotent
- **Deed/question labels**: `CONFIG.SPACE_INFO[type].label` drives all modal titles and history icons — editions override via `SPACE_INFO` in config.js (e.g. Football Quest: "Good Play" / "Foul Play")
- **Space GPU layers**: `transform: translateZ(0)` on each space → crisp at any zoom level
- **fitBoardInView()** is SYNCHRONOUS (no rAF) — no board-jump bug
- **#board-world** pinned to grid dimensions — no background-loading shift
- **Modal** is `position:absolute` inside `#board-viewport` — sidebar always accessible
- **Modal accent colour**: `--modal-accent` CSS var set per space type; coloured border + tinted icon area
- **saveGame() AFTER endTurn()** — `turnPhase` always 'roll' in saved state
- **On resume with turnPhase==='resolving'** → re-opens space modal
- **Badge picker modal**: clicking player badge on setup screen opens a fixed overlay modal; shows live preview with emoji + initials; width = 80% of setup container
- **Setup screen**: resume prompt is a slim single-line bar; Game Settings is a collapsible `<details>` section with rows: Board Layout, Exact Finish, Question Tracking, Question Categories
- **Host player**: separate from local player list; stored in `triventurex_host_player` localStorage; GM-only toggle disables (not hides) the player input

## Architecture — V2 (don't revert)
- **Escaping**: any player-supplied value (name, token, colour) inserted via innerHTML/template MUST go through `esc()`. Not needed for `textContent` (toasts, button labels, modal titles). Server also cleans profiles on join (`cleanProfile`: name ≤20, token ≤8 code points, hex-only colour)
- **Static files**: server.js serves an allowlist only (`/`, `/player`, `css/ js/ game_editions/ images/ tools/`). New top-level client folder → add it to `PUBLIC_DIRS`
- **Offline fallback**: `index.html` dynamically loads `/socket.io/socket.io.js`; `onerror` leaves V1 untouched
- **Authority**: Host (`game.js`) runs all game logic; server relays state via `sync_state` → `state_update`
- **Dice**: server rolls (authoritative); player taps → `roll` event → server generates → broadcasts `roll_result`
- **Game ID**: 4-digit numeric, unique among active rooms; easy to type on a phone
- **sync_state MUST preserve server-only fields**: `rejoinToken` and `socketId` come from the server's existing `room.players` — never overwrite them with the host's `playerStates`
- **Token-based rejoin**: each player gets a `rejoinToken` on join; saved to `triventurex_game_session`; used to re-register the socket on any reconnect (page refresh OR phone screen wake)
- **Mid-session reconnect**: `connect` handler in player.js checks `_myId` + `_gameId`; if set, loads session and calls `rejoinGame()` automatically — no page refresh needed
- **Host rejoin**: `tx_net_game` localStorage key saves the host's gameId; on refresh, `_pendingHostRejoin` triggers `host_rejoin` event to re-register host socket
- **Action box**: fixed-height area on player screen; modes = `dice` | `rolled` | `card` | `activity`
- **Mode transitions**: `dice` → (tap roll) → `rolled` → (space_card) → `card` → (space_card_done) → `activity`
- **state_update must NOT override rolled/card mode**: `renderGameView()` skips mode change when box is in `rolled-mode` or `card-mode` during a resolving turn
- **turn_result before space_card_done**: `afterSpaceResolved()` emits `turn_result` first so activity feed updates before card clears
- **CSS dice**: `renderDie(n, sizeClass)` in dice.js — dot-based, no images; also duplicated inline in player.html for standalone use
- **GM controls**: adjust score, move player, skip turn, remove player, sit out / rejoin (`player.inactive`, host-owned, synced via `sync_state`); network players section shows connected/disconnected state
- **GM actions in history**: `_gmAction()` — between turns a GM change gets its own undoable `spaceType:'gm'` history entry; during a turn it folds into that turn
- **Turn order**: `_nextTurnIndex()` skips finished and sitting-out players (falls back to any unfinished player so the game never stalls)
- **Undo restores by player id**: players who joined/left since the snapshot are kept/stay removed; `inactive`/`disconnected` keep live values
- **Manual dice**: `handleManualRoll(n)` on host; offline → `_processRoll(n)` direct; network → `TX_NET.manualRoll()` sends `manual_roll` to server which broadcasts `roll_result` to players only, host processes locally — no `_awaitingRoll`, cannot get stuck
- **Turn cancellation token**: `_turnToken` (int) incremented on each roll and on undo; `_processRoll` captures `myToken = _turnToken` at start; all async continuations check `_turnToken !== myToken` before proceeding — prevents stale turns running after undo
- **Skip turn network sync**: skip takes a snapshot, adds a history entry (`roll:0`, `spaceType:'skip'`), calls `_syncStateToServer()` + `emitTurnResult` so player screens update; skips are undoable
- **afterSpaceResolved guard**: bails out early if `!state._pendingHistory` — prevents double-fire if undo cleared the pending turn while a modal was open

## Current state
- V1 complete + V2 complete
- 2 editions: Swab Quest (432 questions, 52 deed cards, 20 landmarks) + Football Quest (92 questions, 52 deed cards, 20 stadium landmarks)
- All Islamic/football text in respective `game_editions/<id>/config.js` — engine is fully edition-neutral
- Recent improvements (2026-06-01):
  - Exact finish rule (configurable, default on)
  - No-repeat question tracking (per-edition, per-difficulty, session or per-game)
  - Relative landmark deeds (`move_to_prev/next_landmark` with value=N)
  - Landmark names shown on board tiles and in deed cards
  - Constraint-aware board generation (no move_back near start, no move_forward near finish)
  - SPACE_DISTRIBUTION configurable per edition and per game length
  - 3-level question topic filter in Game Settings (cat > subcat > topic, collapsible tree)
  - Renamed "theme" → "edition" throughout (files, variables, localStorage keys)
  - `themes/` folder renamed to `game_editions/`; `theme.js` → `config.js` in each edition
  - Host player setup separated from local player list
- Recent improvements (2026-06-03):
  - Landmark `description` field: shown in landing modal + clickable info popup (`showLandmarkInfo` in ui.js)
  - Swab Quest expanded to 20 landmarks (mosques & Islamic sites worldwide)
  - Football Quest expanded to 20 landmarks (iconic stadiums & venues)
  - `path-designer.html` moved to `tools/` subfolder (dev tool)
  - Design document rewritten as `TRIVENTUREX-DESIGN.md`

## Effect types
`score_add`, `score_remove`, `move_forward`, `move_back`, `move_to_prev_landmark`, `move_to_next_landmark`, `skip_turn`, `extra_turn`, `all_players_gain`, `all_players_lose`, `protection`

Note: `move_to_landmark` (named, absolute) is still handled in ui.js for backwards compatibility but no longer used in any edition's deed CSV.

## Next work
- Sound effects
- V3: more editions
