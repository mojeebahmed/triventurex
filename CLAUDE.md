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
- All configurable values in `js/shared/config.js` (engine) or `game_editions/<id>/config.js` (edition) — never hardcode

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
- `test/turn-flow.test.js` drives the real host turn pipeline (scripts loaded in index.html order, UI stubbed) — add a scenario here when changing turn behaviour
- `test/csv.test.js` — CSV parser + every edition's content (CSV must match the generated JS; valid answers/effects)
- `test/board.test.js` — property test: random boards for every template of every edition must keep all placement rules, and every landmark tile label must match where the player actually goes (raise `BOARDS_PER_TEMPLATE` locally to hunt rare cases)
- `test/action-cards.test.js` — drawing/showing action cards
- `test/turn.test.js`, `test/players.test.js`, `test/utils.test.js` — pure unit tests
- `test/server.test.js` starts the real server on a random port and drives it with `socket.io-client` (dev dependency) as host + phones
- `server.js` exports `{ server, io, rooms }` and only calls `listen()` when run directly — keep it that way
- Run `npm test` before merging any change (it takes ~3 s)

## Key files
`js/` is grouped by who loads a file (plus `js/vendor/` for third-party libraries):
- `js/shared/` — no page access at load time; used by more than one place (host page, phone page, server, tests). A change here can affect all of them. Rule: top-level code in `shared/` must not touch `document`/`window` (only inside functions)
- `js/host/` — host page (`index.html`) only
- `js/player/` — phone page (`player.html`) only

Host page scripts are plain `<script>` files (not ES modules — `index.html` must work from disk), loaded in the order index.html lists them; top-level declarations are shared between them and `js/host/game.js` is loaded last.

`js/shared/`:
- `js/shared/utils.js` — shared helpers for host + player pages (`esc()` HTML escaping); loaded first
- `js/shared/config.js` — engine settings (board, space types, zoom, animation, score, rules)
- `js/shared/players.js` — player model: `createPlayer`, `movePlayer`, `addScore`, `getSortedPlayers`
- `js/shared/turn.js` — pure turn logic (next player, snapshots, undo restore, history rows); unit-tested
- `js/shared/csv.js` — pure CSV parsing for questions/deeds; unit-tested
- `js/shared/dice.js` — `renderDie(n, sizeClass)` CSS dot-die used by host + player screens
- `js/shared/socket-client.js` — `TX_NET` singleton; safe no-ops when offline

`js/host/` (the controller was one 2000-line game.js before A4):
- `js/host/game.js` — shared `state`, start / resume / reset a game (`_startNewGame`, `_enterGameScreen`, `_restoreGame`), `refreshUI`, bootstrap
- `js/host/turn-flow.js` — the turn pipeline (`_beginTurn` → `_playRoll` → `_resolveSpace` → `_finishTurn`), undo, GM controls
- `js/host/net-host.js` — host side of network play: lobby, `_syncStateToServer`, all socket handlers
- `js/host/setup.js` — setup screen: local / host / join tabs, player rows, host player row
- `js/host/badge-picker.js` — one badge modal for setup rows and the host (`openBadgeModal(index | 'host')`)
- `js/host/category-filter.js` — 3-level question topic tree in Game Settings
- `js/host/edition-loader.js` — `loadEdition`, config merge, edition picker, colours + branding
- `js/host/storage.js` — saved game + remembered preferences (localStorage)
- `js/host/viewport.js` — pan / zoom / fit and the board background
- `js/host/board.js` — board generation (`generateBoard`) and rendering (`renderBoard`, `updateBoardTokens`)
- `js/host/ui.js` — modals (question, deed, action, landmark), timer, scoreboard, history panel, toast

Player page + server:
- `player.html` + `js/player/player.js` — phone screen (join, action box, session management)
- `server.js` — rooms, dice rolling, host → phone relays (ownership rules at the top)

Content:
- `game_editions/editions.js` — edition registry (loaded via `<script>` in index.html)
- `game_editions/<id>/config.js` — edition config (name, colours, landmarks, finish text, SPACE_INFO, SPACE_DISTRIBUTION)
- `game_editions/<id>/questions.csv` + `deeds.csv` — edit content here
- `game_editions/<id>/questions.js` + `deeds.js` — auto-generated from CSV

## Content workflow
Edit CSV → `npm run build:content` (checks the content, then regenerates questions.js / deeds.js / actions.js) → refresh browser.
- `npm run check:content` — check only; fails if a CSV has errors or a generated JS file is out of date. `npm test` includes the same checks
- The checker (`scripts/content.js`) reports `file:line message`: wrong column count (unquoted comma), bad/duplicate ids, type/difficulty, multi answer not pointing at a filled option, unknown deed effects, landmark effects vs config.js `LANDMARKS`; warnings for missing topics and `{landmark}` text without a landmark effect
- `questions.csv` first column is `id` — unique per edition, never reuse or renumber (asked-question tracking is stored by id). New question → next unused number
- Any field containing a comma MUST be wrapped in double quotes (`"Madrid, Spain"`)
- Never edit questions.js / deeds.js by hand — they're generated (the fallback for index.html opened from disk)
- Column + effect reference for authors: `game_editions/template/README.md`
- `scripts/` = Node-only dev tooling (not served); `tools/` = browser dev tools (served)

## Terminology
- **Edition** = interchangeable game content pack (was "theme" before 2026-06-01)
- `EDITION_CONFIG` — the `window` global set by each edition's `config.js`
- `CONFIG.COLORS` — CSS colour variables (was `CONFIG.THEME`); edition configs use a `COLORS` block. `GAME.editionName` / `GAME.editionIcon` (were `themeName` / `themeIcon`)
- No "theme" identifiers remain in code (2026-10-16) — use "edition" for content packs, "colors" for styling
- `TRIVENTUREX_EDITIONS` — the registry array in `game_editions/editions.js`
- localStorage key: `triventurex_edition` (saves last-used edition ID)

## Architecture — V1 (don't revert)
- **Edition loading**: `loadEdition()` in game.js; validates saved ID against registry before use; `_ENGINE_DEFAULTS` snapshot for clean edition switching; calls `_populateCategoryFilter()` after load
- **Board generation**: `generateBoard()` in board.js — pre-picks deed effects → constraint-aware deed-to-slot assignment (`_assignDeedsToSlots`) → no consecutive same-type → resolved landmark names stored on each deed
- **SPACE_DISTRIBUTION**: defined in `js/shared/config.js` as engine default. Editions override via `SPACE_DISTRIBUTION` in their `config.js` — can be flat (all lengths) or keyed by `short`/`medium`/`long`. Questions always fill whatever space remains; no `question` key is needed in the distribution object.
- **Constraint-aware placement** (`_assignDeedsToSlots`):
  - `move_back N` → slot index ≥ N (not near start)
  - `move_forward N` → slot index ≤ poolLen-1-N (not near finish)
  - `move_to_prev_landmark N` → N landmarks exist before the slot
  - `move_to_next_landmark N` → N landmarks exist after the slot
  - Fallback: try alternative effect from card's effects array; then swap in an unused card from the deck that fits (`_replacementFromSpares`); least-bad slot only if nothing in the deck fits
  - All of this is checked by a randomized test (`test/board.test.js`, ~3,000 boards per run) — keep it green when touching board.js
- **Landmark deeds**: `move_to_prev_landmark` / `move_to_next_landmark` with `value=N` (N = 1 → nearest). Names resolved at board-gen time and stored as `resolvedLandmark` on each deed. `{landmark}` in deed text is substituted at modal render time.
- **Variable deed effects**: each card has up to 3 effects in CSV; one chosen at board-gen time via `_pickActiveEffect()`
- **Exact finish**: `CONFIG.RULES.exactFinish` — player must roll exact number to land on finish; overshooting doesn't move. Toggle in Game Settings (select: on/off). Default: on.
- **Question tracking**: per-edition, per-difficulty localStorage keys (`triventurex_asked_<editionId>_<diff>`). Two modes: `session` (remember across games, default) or `game` (reset each game). When all questions in a difficulty are exhausted, auto-recycles. Questions filtered by selected categories.
- **Topic tree rows**: the checkbox + name (`.tree-check` label) toggle the selection; the rest of a row (count, arrow, empty space) expands/collapses. Each row shows its question count
- **Question topics (3-level filter)**: questions have `cat > subcat > topic` hierarchy. Game Settings shows a collapsible tree — checking a cat/subcat toggles all children; parent shows indeterminate state when partial. Saved per edition to localStorage as an array of selected topic strings (`triventurex_cats_<editionId>`). `getSelectedTopics()` in game.js returns a Set of topic strings; `_availablePool()` in ui.js filters by `q.topic`. Questions with empty topic always pass through (backwards compat with editions that only have `cat`).
- **Edition-neutral engine**: `player.score`, `addScore()`, `SCORE_VALUES`; editions provide `pointsName`, `finishLabel`, `finishCelebration`, `finishButtonLabel`, `endScreenMessage`
- **Score values**: every point label and award reads `CONFIG.SCORE_VALUES` / `CONFIG.FINISH_BONUS` — never hardcode numbers in UI text. Editions may override either in their `config.js` (reset on edition switch via `_ENGINE_DEFAULTS`)
- **Finish bonus**: `_recordFinish(player)` in game.js — called after every movement (roll, deed effect, GM move); idempotent
- **Deed/question labels**: `CONFIG.SPACE_INFO[type].label` drives all modal titles and history icons — editions override via `SPACE_INFO` in config.js (e.g. Football Quest: "Good Play" / "Foul Play")
- **Space GPU layers**: `transform: translateZ(0)` on each space → crisp at any zoom level
- **fitBoardInView()** is SYNCHRONOUS (no rAF) — no board-jump bug
- **Board drawn to the path's bounding box** (`pathBounds` in board.js), not the template's full grid — so fit-to-view centres on the path. `_gridRows/_gridCols` are still saved for old saves but not used for drawing
- **#board-world** pinned to grid dimensions — no background-loading shift
- **Modal** is `position:absolute` inside `#board-viewport` — sidebar always accessible
- **Modal accent colour**: `--modal-accent` CSS var set per space type; coloured border + tinted icon area
- **Turn pipeline (A2)**: every turn = `_beginTurn` → `_playRoll` → `_resolveSpace` → `_finishTurn`; skipped turns (`_skipTurn`) and exact-finish blocks also end in `_finishTurn`, the ONLY end-of-turn path (finish bonus → history → turn_result/space_card_done → game over? → extra turn or `endTurn` → save → sync). Never end a turn any other way
- **`state.turn`**: the turn in progress (`{ token, playerId, roll, posBefore, scoreBefore, snapshot, awaitingRoll }`) or `null`. Plain data, saved with the game; on resume a saved `state.turn` re-opens the space modal via `_resolveSpace`
- **Stale continuations**: every async step / modal callback captures `token` and checks `_isStale(token)`; undo and player removal clear `state.turn`, which cancels everything in flight
- **Pure turn logic** lives in `js/shared/turn.js` (`nextTurnIndex`, `takeSnapshot`, `restoreFromSnapshot`, `indexAfterRemoval`, `makeHistoryEntry`) — no DOM; unit-tested in `test/turn.test.js`
- **Badge picker modal**: clicking player badge on setup screen opens a fixed overlay modal; shows live preview with emoji + initials; width = 80% of setup container
- **Setup screen (G6/G7)**: two tabs — *🎲 New game* and *⚙️ Rules*. New game = accordion wizard (`js/host/setup-flow.js`): steps ① Edition → ② Game length → ③ Board → ④ Players, one open at a time, each collapsed heading shows the current choice (`updateSetupValues`), a choice opens the next step (`onSetupChoice`). Fixed-height card: header + tabs at the top, footer (whole setup summary + Start) at the bottom, only the tab content scrolls (in the Rules tab only the right-hand settings pane) (Enter in a name field also starts). First visit opens step ①; later visits start fully collapsed with last time's choices. Mode (*On this screen* / *On phones*) lives inside ④ Players; in phone mode Start reads *Open lobby*. Players are chips. CSS counter numbers the visible steps
- **Board picker (G8)**: `js/host/board-picker.js` draws a thumbnail per `PATH_TEMPLATES` entry for the chosen length (+ 🎲 Random); the choice lives in hidden `#path-select` ('random' or index). Changing length resets it to Random
- **Host player**: separate from local player list; stored in `triventurex_host_player` localStorage; GM-only toggle disables (not hides) the player input

## Architecture — V2 (don't revert)
- **Escaping**: any player-supplied value (name, token, colour) inserted via innerHTML/template MUST go through `esc()`. Not needed for `textContent` (toasts, button labels, modal titles). Server also cleans profiles on join (`cleanProfile`: name ≤20, token ≤8 code points, hex-only colour)
- **Static files**: server.js serves an allowlist only (`/`, `/player`, `css/ js/ game_editions/ images/ tools/`). New top-level client folder → add it to `PUBLIC_DIRS`
- **Offline fallback**: `index.html` dynamically loads `/socket.io/socket.io.js`; `onerror` leaves V1 untouched
- **Authority**: Host (`game.js`) runs all game logic; server relays state via `sync_state` → `state_update`
- **Dice**: server rolls (authoritative); player taps → `roll` event → server generates → broadcasts `roll_result`
- **Game ID**: 4-digit numeric, unique among active rooms; easy to type on a phone
- **State ownership (A3)**: HOST owns game state (positions, scores, turn order, finish order, sitting out) and pushes it with `sync_state`. SERVER owns connection state (`socketId`, `rejoinToken`, `disconnected`, room membership) + dice; `sync_state` never overwrites these. Rules are written at the top of server.js
- **Server-only fields never leave the server**: `SERVER_ONLY_FIELDS` (`socketId`, `rejoinToken`, `awaitingHostSync`) are stripped by `publicPlayer(s)()` / `publicState()` from every emit. A player's own `rejoinToken` is only sent once, in its `joined` reply
- **Late joiners survive syncs**: a joiner is `awaitingHostSync` until a host sync includes them; a sync with an older list keeps them. The host's `player_joined` handler adds them + syncs. A player the host has synced before and then leaves out IS dropped (host authority)
- **Rematch / back to setup (G7)**: end screen *🔁 Rematch* = same players, length, board choice and rules, new board (`rematch()` in game.js; network: same room — server cancels the room expiry when a synced game is `playing` again). *New game setup* returns with last choices (`_restoreGameSettings`), all steps collapsed
- **Per-game rules (G12)**: `js/shared/rules.js` (pure) builds rules as defaults (engine CONFIG + edition) → preset (`CONFIG.RULE_PRESETS`) → the player's changes. Stored per edition as `triventurex_rules_<editionId>` = `{ preset, changes }` (only what differs from the preset). Copied into `state.rules` at game start and saved with the game. Host code reads rules ONLY via `gameRules()` (rules-panel.js) — never `CONFIG.SCORE_VALUES` / `FINISH_BONUS` / `TIMER` / `RULES` directly; those are only the defaults
- **Rules tab**: `js/host/rules-panel.js`, side tabs from `_rulesSchema()` sections (+ 🏷️ Topics, static DOM); every change is saved immediately (`_commitRules`), no Done/Cancel — *Reset to preset* undoes. New setting = add it to `defaultRules` + `normalizeRules` (rules.js), one schema line, then read it via `gameRules()`. "📋 Copy as preset" produces a `RULE_PRESETS` entry to paste into config.js
- **Board under rules**: `generateBoard(len, template, { tileMix, deeds })`; counting is `tileCounts()` in rules.js — the panel preview uses the same function
- **Join by QR (G11)**: server's `hosted` reply carries `joinUrls` (every LAN IPv4 → `http://ip:port/player?game=ID`; the host page on localhost can't see these). Lobby shows a QR (`js/vendor/qrcode.js`, MIT, Kazuhiko Arase — third-party, don't edit), the address and the Game ID; GM panel has *📱 Show join code* for latecomers. `player.html?game=ID` pre-fills the Game ID and wins over an old saved session for another game
- **Private cards (C3)**: `private_card` (host-only) is forwarded by the server to ONE player's socket. `_sendPrivateCard(player, card)` in net-host.js sends it unless offline, the host's own player (`state.hostPlayerId`) or disconnected — then the host modal hides the card behind a show/hide toggle instead. Generic `{ title, text, rule, note }` payload — reuse it for other per-player secrets
- **Action cards (C3)**: optional `actions.csv` per edition (`id, text, kind, note`; kinds in `CONFIG.ACTION_KINDS`: act / explain / sound). Drawn without repeats (`_drawActionCard`, tracked like questions under the `actions` key); the drawn card is stored on `state.turn.actionCard` so a resumed turn shows the same card. No actions.csv → physical-deck prompt
- **Room lifecycle (A5)**: rooms are deleted immediately on `close_room` (host's "Play again" / lobby Cancel — phones get `host_left` "ended the game"), `ROOM_TTL.endedMs` (5 min) after `phase: 'ended'`, or `ROOM_TTL.hostGoneMs` (30 min) after the host disconnects. `host_rejoin` cancels the countdown and sends `host_back` (phone hides its "host left" overlay). TTLs in `ROOM_TTL` at the top of server.js (env overrides)
- **Host → phone relays** (`turn_result`, `space_card`, `space_card_done`) are accepted from the host socket only
- **remove_player** on the server only changes membership (+ removed socket leaves the room); it sends no `state_update` — the host's `player_removed` handler syncs the result
- **Token-based rejoin**: each player gets a `rejoinToken` on join; saved to `triventurex_game_session`; used to re-register the socket on any reconnect (page refresh OR phone screen wake)
- **Mid-session reconnect**: `connect` handler in player.js checks `_myId` + `_gameId`; if set, loads session and calls `rejoinGame()` automatically — no page refresh needed
- **Host rejoin**: `tx_net_game` localStorage key saves the host's gameId; on refresh, `_pendingHostRejoin` triggers `host_rejoin` event to re-register host socket
- **Action box**: fixed-height area on player screen; modes = `dice` | `rolled` | `card` | `activity`
- **Mode transitions**: `dice` → (tap roll) → `rolled` → (space_card) → `card` → (space_card_done) → `activity`
- **state_update must NOT override rolled/card mode**: `renderGameView()` skips mode change when box is in `rolled-mode` or `card-mode` during a resolving turn
- **turn_result before space_card_done**: `_finishTurn()` emits `turn_result` first so activity feed updates before card clears
- **CSS dice**: `renderDie(n, sizeClass)` + `animateDieInto(el, result)` in `js/shared/dice.js` — dot-based, no images; host and phones use the same rolling animation (phones: roller big in the action box, others in a strip above the activity feed; feed entry added after the animation)
- **GM controls**: adjust score, move player, skip turn, remove player, sit out / rejoin (`player.inactive`, host-owned, synced via `sync_state`); network players section shows connected/disconnected state
- **GM actions in history**: `_gmAction()` — between turns a GM change gets its own undoable `spaceType:'gm'` history entry; during a turn it folds into that turn
- **Turn order**: `nextTurnIndex()` (turn.js) skips finished and sitting-out players (falls back to any unfinished player so the game never stalls)
- **Undo**: mid-turn → cancels only the turn in progress (restores `state.turn.snapshot`); between turns → pops the last history entry. Restores by player id (`restoreFromSnapshot`): joined players kept, removed stay removed, `inactive`/`disconnected` keep live values
- **Manual dice**: `handleManualRoll(n)` on host → `_beginTurn` + `_playRoll(n)` locally; network also sends `manual_roll` so phones see the value (server broadcasts to players only) — no waiting on the server

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
