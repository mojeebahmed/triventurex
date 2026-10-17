# Triventurex — Design Document

_Last updated: 2026-10-17_

> **For AI assistants / new contributors:** Start here for context, then read `CLAUDE.md` for the authoritative architecture reference and `README.md` for gameplay and setup instructions. `CHANGELOG.md` lists what changed; `IMPROVEMENT-PLAN.md` is the backlog.

---

## What is Triventurex?

**Triventurex** = Trivia + Adventure + X

A family/group board game engine where players roll dice, move along a path, and collect points through:
- **Quiz questions** — Easy (+1 pt) or Hard (+2 pt), chosen by the player
- **Action cards** — act it out / explain it / hum it; performer and guesser both earn points. In a network game the card is shown only on the performer's phone
- **Good/Bad deed cards** — Randomly assigned effects (move forward/back, score, skip turn, etc.)
- **Landmarks** — Visual stops with photos and descriptions; GM awards 5 pts

**Winner = most points when all players reach the finish.**

The engine is fully **edition-neutral** — swap a content folder and colour scheme to get a completely different game.

---

## Active Editions

| Edition | Points | Finish | Deed labels | Landmarks | Questions | Action cards |
|---|---|---|---|---|---|---|
| Swab Quest | Sawab | Al-Ka'ba, Mecca | Good Deed / Bad Deed | 20 mosques & Islamic sites | 432 | 26 |
| Football Quest | Goals | The Final | Good Play / Foul Play | 20 iconic stadiums & venues | 92 | 25 |

---

## Architecture

### Stack

- **Client:** Vanilla HTML + CSS + JavaScript — no framework, no build step. Plain `<script>` files, not ES modules, so `index.html` also works opened from disk
- **Server (V2):** Node.js + Express + Socket.IO
- **Content:** CSV files (loaded via `fetch()`) with generated JS fallbacks for offline/`file://` use (`npm run build:content`)
- **Tests:** Node's built-in test runner (`npm test`), no test framework

### Key files

`js/` is grouped by who loads a file: `shared/` (no page access at load; used by several of host page, phone page, server, tests), `host/` (index.html only), `player/` (player.html only).

| File | Responsibility |
|---|---|
| `js/shared/config.js` | Engine defaults: board sizes, space types, scoring, action card kinds, zoom, animation, paths |
| `js/shared/players.js` | Player model (`createPlayer`, `movePlayer`, `addScore`, `getSortedPlayers`) |
| `js/shared/turn.js` | Pure turn logic: next player, undo snapshots / restore, history rows (also used by server.js) |
| `js/shared/csv.js` | CSV parsing for questions, deeds, action cards (also used by the content tooling) |
| `js/shared/dice.js` | `renderDie(n, sizeClass)` — CSS dot-die; used on host + player screens |
| `js/shared/socket-client.js` | `TX_NET` singleton — shared Socket.IO layer; safe no-ops when offline |
| `js/shared/utils.js` | `esc()` — HTML escaping for anything a player can type |
| `js/host/game.js` | Shared game `state`; start / resume / reset a game; bootstrap (loaded last) |
| `js/host/turn-flow.js` | The turn pipeline, undo, GM controls |
| `js/host/net-host.js` | Host side of network play: lobby, state sync, socket events, private cards |
| `js/shared/board.js` | Board generation algorithm + DOM rendering |
| `js/host/ui.js` | Modals (question, deed, action, landmark), scoreboard, legend, timer, history |
| `js/host/setup.js`, `badge-picker.js`, `category-filter.js` | Setup screen pieces |
| `js/host/edition-loader.js` | Edition loading, config merge, edition picker, colours + branding |
| `js/host/storage.js`, `js/shared/viewport.js` | localStorage save/prefs; pan / zoom / board background |
| `display.html`, `js/display/display.js` | TV display: read-only second screen fed by the host (G16) |
| `js/player/player.js` | Phone screen logic: join, action box, session management |
| `game_editions/editions.js` | Edition registry — lists all available editions |
| `game_editions/<id>/config.js` | Edition config: name, colours, landmarks, background, space + score overrides |
| `game_editions/<id>/*.csv` | Source of truth for questions, deeds, action cards — edit these, then `npm run build:content` |
| `server.js` | Rooms, authoritative dice, host → phone relays; state-ownership rules at the top |
| `player.html` | Lightweight player screen (phones/tablets) |
| `scripts/` | Node-only dev tooling: content build + checker (not served) |
| `tools/path-designer.html` | Visual board path design tool — dev use only |
| `test/` | Automated tests (`npm test`) |

---

## Edition System

### How editions are loaded

1. `game_editions/editions.js` (loaded via `<script>` in `index.html`) sets `window.TRIVENTUREX_EDITIONS`
2. On `DOMContentLoaded`, `game.js` reads the last-used edition from localStorage (`triventurex_edition`)
3. `loadEdition()` (edition-loader.js) dynamically injects the edition's `config.js`, `questions.js`, `deeds.js` and `actions.js`, then fetches the CSV files, which replace the JS copies when served over HTTP
4. `config.js` sets `window.EDITION_CONFIG` → merged into `CONFIG` via `_mergeEditionConfig()`
5. `_ENGINE_DEFAULTS` snapshot allows `_resetToEngineDefaults()` before an edition switch

### What an edition defines

- `GAME` — name, icon, subtitle, pointsName, finish labels, celebration text
- `LANDMARKS` — array of `{ name, image, description }` objects (image path relative to `index.html`)
- `BOARD_BACKGROUND` — image, overlay opacity, blur
- `SPACE_DISTRIBUTION` — ratios per space type, optionally keyed by `short/medium/long`
- `SPACE_INFO` — icon, label, colour overrides (e.g. Football Quest: "Good Play" / "Foul Play")
- `COLORS` — CSS custom properties (`--green`, `--gold`, `--bg`, etc.)
- `SCORE_VALUES`, `FINISH_BONUS` — optional point overrides (every point label in the game reads these)

---

## Board Generation

The board is built fresh each game from the active edition's content. Steps in order:

1. **Count** spaces per type from `SPACE_DISTRIBUTION` ratios; questions fill the remainder
2. **Pre-pick deed effects** — `_pickActiveEffect()` selects one effect from each card's `effects[]` array (variable rewards per game)
3. **Constraint-aware pool assignment** (`_assignDeedsToSlots`):
   - `move_back N` → placed at slot ≥ N (not near start)
   - `move_forward N` → placed at slot ≤ poolLen-1-N (not near finish)
   - `move_to_prev_landmark N` → N landmarks must exist before the slot
   - `move_to_next_landmark N` → N landmarks must exist after the slot
   - Fallback: try another effect on the same card; then swap in an unused card from the deck that fits; least-bad slot only if nothing in the deck fits
4. **Shuffle and de-duplicate** — no two consecutive spaces of the same constrained type
5. **Resolve landmark names** — `resolvedLandmark` stored on each deed at gen time; `{landmark}` in deed text substituted at modal render time
6. **Assemble + add direction arrows**

These rules are checked by a randomized test (`test/board.test.js`): ~3,000 boards per run across every path template of every edition, including that each landmark tile's label matches where the player actually goes. It found a rare rule break on short boards (fixed in 2.1).

The board path is determined by a `PATH_TEMPLATES` entry (`{ name, start, segments, gridRows?, gridCols? }`). Any path length works — `BOARD_SIZES` in config.js is informational only.

---

## Gameplay Rules

| Rule | Default | Configurable? |
|---|---|---|
| Exact finish | On — must roll exact number; overshooting = no move | Yes, in Game Settings |
| Question tracking | Session — asked questions skipped until pool exhausted, then resets | Yes, in Game Settings |
| Question topics | All selected | Yes, 3-level filter in Game Settings |
| Undo | Mid-turn: cancels only the current turn. Between turns: undoes the last turn or GM change | — |
| Sit out | GM can mark a player as sitting out: skipped in turn order, keeps place and score | GM controls |
| Finish bonus | By finishing order (10 / 7 / 5 / …), however the player reached the finish (roll, deed, GM move) | Per edition (`FINISH_BONUS`) |

### Question topic filter (3 levels)

Questions have `category > subcategory > topic`. Game Settings shows a collapsible tree — checking/unchecking a parent toggles all children. Parent shows an indeterminate (−) state when partially selected. At least one topic must always remain checked. Selections saved per edition to `triventurex_cats_<editionId>`.

---

## Landmark Info

Each landmark can have a `description` field in the edition's `config.js`. Descriptions appear:
1. In the **landing modal** — shown to the GM when a player lands on the space
2. In the **info popup** — shown to anyone who clicks a landmark space on the board at any time

The info popup shows the landmark photo, name, and description in a full-screen overlay.

---

## V2 — Local Network Multiplayer

### Architecture

```
Node.js + Express + Socket.IO server (server.js)
    ├── serves an allowlist of client files (not server code, docs or tests)
    ├── manages game rooms  Map<gameId, RoomState> — cleaned up when finished or abandoned
    ├── rolls the dice (authoritative)
    └── relays events host → phones (all, or ONE phone for private cards)

Host browser (index.html)          Player browsers (player.html)
  full board view                    single action box (fixed height)
  GM controls panel                  own badge + score
  all V1 functionality               others' scores
  Roll button on host-player turn    dice → rolled → card → activity modes
```

**Ownership model:**
- The **host** owns all game state — positions, scores, turn order, finish order, sitting out — and pushes it with `sync_state`; the server forwards it to phones as `state_update`.
- The **server** owns connection state — which socket belongs to whom, rejoin tokens, connected/disconnected, room membership — and the dice. A host sync never overwrites these, and server-only fields never leave the server.

### Critical V2 invariants

- **One turn pipeline** — every turn ends in `_finishTurn()` (finish bonus → history → phone update → game over? → next player → save → sync); never end a turn any other way
- **`state.turn`** — the turn in progress; every async step checks it is still current, so undo / player removal cancel everything in flight
- **Server-only fields** (`socketId`, `rejoinToken`) are stripped from everything sent to clients; a phone gets its own rejoin token once, when it joins
- **`state_update` must not override `rolled-mode` or `card-mode`** — prevents clearing a result the player is actively reading
- **`turn_result` before `space_card_done`** — activity feed updates before card clears
- **Private cards** — `private_card` goes from the host to ONE phone only (used for action cards)
- **Room lifecycle** — closed when the host clicks Play again / cancels the lobby, 5 min after the game ends, or 30 min after the host disconnects without coming back

### Session persistence

- **Identity** (`triventurex_player_identity`): name, token, colour — pre-fills on next join
- **Session** (`triventurex_game_session`): `{ gameId, playerId, rejoinToken }` — auto-rejoin on any reconnect
- **Host** (`tx_net_game`): gameId — re-registers host socket after browser refresh

### Action box modes (player screen)

`dice-mode` → (tap roll) → `rolled-mode` → (space_card) → `card-mode` → (space_card_done) → `activity-mode` → (next turn) → `dice-mode`

---

## State & Persistence (localStorage keys)

| Key | Contents |
|---|---|
| `triventurex_save` | Full game state for resume on refresh (V1 / host) |
| `triventurex_player_prefs` | Player names, colours, tokens (local game) |
| `triventurex_host_player` | Host player name/colour/token (network host) |
| `triventurex_game_settings` | Last game length, path choice, exact finish, question tracking |
| `triventurex_edition` | Last active edition ID |
| `triventurex_asked_<editionId>_<diff>` | Asked question IDs per edition and difficulty (`easy` / `hard`) |
| `triventurex_asked_<editionId>_actions` | Used action card IDs per edition |
| `triventurex_cats_<editionId>` | Selected question topic names per edition |
| `triventurex_player_identity` | Player name/token/colour on player device (V2) |
| `triventurex_game_session` | Rejoin token + game/player IDs on player device (V2) |
| `tx_net_game` | Host's active network game ID for host-rejoin after refresh (V2) |

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Winner by score, not first to finish | More strategic throughout the game |
| Player chooses question difficulty | Agency; risk/reward balance |
| Variable deed effects (random per game) | Same cards, different outcomes — replayability |
| Constraint-aware deed placement | No `move_back` near start; no `move_forward` near finish — never an unfair result |
| Relative landmark deeds (`move_to_prev/next_landmark`) | Board-position-independent; works on any path layout |
| Exact finish rule | Landing exactly on finish is a skill element; configurable off |
| No-repeat question tracking | Prevents the same questions dominating repeated games |
| Edition-neutral engine | Engine code never changes when adding a new edition |
| `SPACE_INFO.label` drives all modal titles | Football Quest shows "Foul Play", Swab Quest shows "Bad Deed" — zero engine coupling |
| Modal inside `#board-viewport` | Sidebar stays accessible during questions |
| Synchronous `fitBoardInView` (no rAF) | Eliminates "board jumps" visual glitch |
| One end-of-turn path (`_finishTurn`) | Every earlier network bug was a turn path that skipped a step (sync, save, history) |
| Host owns game state, server owns connections | One source of truth each; the server never computes game state |
| Plain scripts, not ES modules | Browsers block modules on `file://`; the offline mode must keep working |
| CSV + generated JS, checked by a script | Editors use spreadsheets; the checker catches unquoted commas, bad ids, unknown effects with file:line |
| Action card shown only on the performer's phone | Keeps the card secret without anyone looking away; host-screen fallback hides it behind a toggle |
| 4-digit numeric Game ID | Easy to type on a phone without looking |
| Token-based rejoin (not socket ID) | socketId changes on every reconnect; token persists across sessions — and is never shown to other players |
| `translateZ(0)` on each `.space` | Each space in its own GPU layer → crisp at any zoom level |

---

## Scoring

| Event | Points |
|---|---|
| Easy question correct | +1 |
| Hard question correct | +2 |
| Action performed | +1 (performer) |
| Action guessed correctly | +1 (guesser) |
| Landmark (GM awards) | +5 |
| Finish bonus (1st) | +10 |

Values come from `CONFIG.SCORE_VALUES` / `CONFIG.FINISH_BONUS` (finish bonus by order: 10, 7, 5, 4, 3, 2, 1, 1); editions can override them. Deed card score effects are defined per edition in `deeds.csv`.

---

## Adding a New Edition

1. Copy `game_editions/template/` to `game_editions/<your-id>/`
2. Edit `config.js` — fill in `GAME`, `LANDMARKS`, `COLORS`, `SPACE_INFO`
3. Edit `questions.csv`, `deeds.csv` and (optionally) `actions.csv` — columns: `game_editions/template/README.md`
4. Run `npm run build:content <your-id>` — checks the content (file:line messages) and produces `questions.js`, `deeds.js`, `actions.js`
5. Add your edition to `game_editions/editions.js`
6. Done — the edition picker appears automatically on the setup screen

---

## Tools

### Path Designer (`tools/path-designer.html`)

A visual drag-and-click tool for designing new board path templates. It needs to be served (it loads `js/shared/config.js`): with `node server.js` running, open `http://localhost:3000/tools/path-designer.html` (or use `python3 -m http.server 8080`).

Features:
- Click to set start, click to extend path segment by segment
- Violation detection (highlights cells that are too close to adjacent path runs)
- Space counter vs. short/medium/long targets
- Generates JSON in the exact `PATH_TEMPLATES` format — copy and paste into `js/shared/config.js`
- Load dropdown shows all existing templates live from `CONFIG.PATH_TEMPLATES`

### Content tooling (`scripts/`)

- `npm run build:content [edition]` — checks every edition's CSV files and regenerates the JS copies
- `npm run check:content` — check only; also fails if a generated file is out of date (`npm test` runs the same checks)

---

## Future Possibilities

The planned gameplay work (endgame pacing, score balance, answering questions on the phone, automatic landmark points, …) is tracked as *Phase 5* in `IMPROVEMENT-PLAN.md`.

### Near-term
- **Sound effects** — dice roll, correct answer, finish fanfare, deed card reveal
- **More Swab Quest questions** — currently 432; target 600+ across all topics
- **Football Quest subcategories/topics** — currently flat; could add `Clubs / International / History` structure

### Medium-term
- **New editions** — Science Quest, History Quest, Geography Quest — same engine, different content
- **Mobile layout improvements** — board tiles larger on phones; better touch handling
- **Timed questions** — countdown per question with score penalty for running out
- **Team mode** — two teams share a token; questions alternate between team members

### Longer-term
- **Online multiplayer** — beyond local Wi-Fi (requires hosted server + authentication)
- **Question editor UI** — add/edit questions in-browser without editing CSV files
- **Admin dashboard** — view all active V2 rooms; room stats (rooms already clean themselves up since 2.1)

---

## Development History

| Phase | Date | What was built |
|---|---|---|
| V1 initial | 2026-05 | Core engine: board generation, modals, scoring, pan/zoom, save/resume |
| V2 network | 2026-05-18 | Local network multiplayer: Socket.IO, player screens, rejoin, GM controls |
| Gameplay improvements | 2026-06-01 | Exact finish, no-repeat questions, relative landmark deeds, constraint-aware board gen, SPACE_DISTRIBUTION per edition/length, host player separation |
| Theme → Edition rename | 2026-06-01 | `themes/` → `game_editions/`, `THEME_CONFIG` → `EDITION_CONFIG`, localStorage key updated |
| 3-level question topics | 2026-06-01 | `cat > subcat > topic` hierarchy; collapsible filter tree in Game Settings; 432 Swab Quest questions |
| Landmark descriptions | 2026-06-03 | `description` field on landmarks; landing modal shows it; click-to-info popup on board tiles |
| More landmarks | 2026-06-03 | Swab Quest: 6 → 20 landmarks; Football Quest: 6 → 20 stadiums/venues |
| Code review & hardening (2.1) | 2026-10-16/17 | 18 bugs fixed; one turn pipeline; host/server state ownership; `game.js` split into `js/shared/host/player`; content build + checker; digital action cards; ~200 automated tests — details in `CHANGELOG.md` |
