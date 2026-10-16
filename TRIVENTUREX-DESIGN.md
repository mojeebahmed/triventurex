# Triventurex — Design Document

_Last updated: 2026-06-03_

> **For AI assistants / new contributors:** Start here for context, then read `CLAUDE.md` for the authoritative architecture reference and `README.md` for gameplay and setup instructions.

---

## What is Triventurex?

**Triventurex** = Trivia + Adventure + X

A family/group board game engine where players roll dice, move along a path, and collect points through:
- **Quiz questions** — Easy (+1 pt) or Hard (+2 pt), chosen by the player
- **Action cards** — Charade-style performance; performer and guesser both earn points
- **Good/Bad deed cards** — Randomly assigned effects (move forward/back, score, skip turn, etc.)
- **Landmarks** — Visual stops with photos and descriptions; GM awards 5 pts

**Winner = most points when all players reach the finish.**

The engine is fully **edition-neutral** — swap a content folder and colour scheme to get a completely different game.

---

## Active Editions

| Edition | Points | Finish | Deed labels | Landmarks | Questions |
|---|---|---|---|---|---|
| Swab Quest | Sawab | Al-Ka'ba, Mecca | Good Deed / Bad Deed | 20 mosques & Islamic sites | 432 |
| Football Quest | Goals | The Final | Good Play / Foul Play | 20 iconic stadiums & venues | 92 |

---

## Architecture

### Stack

- **Client:** Vanilla HTML + CSS + JavaScript — no framework, no build step
- **Server (V2):** Node.js + Express + Socket.IO
- **Content:** CSV files (loaded via `fetch()`) with JS fallbacks for offline/`file://` use

### Key files

| File | Responsibility |
|---|---|
| `js/config.js` | Engine defaults: board sizes, space types, scoring, zoom, animation, paths |
| `js/board.js` | Board generation algorithm + DOM rendering |
| `js/players.js` | Player state helpers (`createPlayer`, `movePlayer`, `addScore`) |
| `js/dice.js` | `renderDie(n, sizeClass)` — CSS dot-die; no images; used on host + player screens |
| `js/ui.js` | Modals, scoreboard, legend, timer, deed display, landmark info popup, history |
| `js/game.js` | Main controller: state, turns, pan/zoom, localStorage, edition loading, setup screen |
| `js/socket-client.js` | `TX_NET` singleton — shared Socket.IO layer; safe no-ops when offline |
| `js/player.js` | Player screen logic: join, action box, session management |
| `game_editions/editions.js` | Edition registry — lists all available editions |
| `game_editions/<id>/config.js` | Edition config: name, colours, landmarks, background, space overrides |
| `game_editions/<id>/questions.csv` | Source of truth for questions — edit this; regenerate JS after |
| `game_editions/<id>/deeds.csv` | Source of truth for deed cards — edit this; regenerate JS after |
| `server.js` | Node.js + Socket.IO room management; event relay; authoritative dice roll |
| `player.html` | Lightweight player screen (phones/tablets) |
| `tools/path-designer.html` | Visual board path design tool — dev use only |

---

## Edition System

### How editions are loaded

1. `game_editions/editions.js` (loaded via `<script>` in `index.html`) sets `window.TRIVENTUREX_EDITIONS`
2. On `DOMContentLoaded`, `game.js` reads the last-used edition from localStorage (`triventurex_edition`)
3. `loadEdition()` dynamically injects the edition's `config.js`, `questions.js`, and `deeds.js`
4. `config.js` sets `window.EDITION_CONFIG` → merged into `CONFIG` via `_mergeEditionConfig()`
5. `_ENGINE_DEFAULTS` snapshot allows `_resetToEngineDefaults()` before an edition switch

### What an edition defines

- `GAME` — name, icon, subtitle, pointsName, finish labels, celebration text
- `LANDMARKS` — array of `{ name, image, description }` objects (image path relative to `index.html`)
- `BOARD_BACKGROUND` — image, overlay opacity, blur
- `SPACE_DISTRIBUTION` — ratios per space type, optionally keyed by `short/medium/long`
- `SPACE_INFO` — icon, label, colour overrides (e.g. Football Quest: "Good Play" / "Foul Play")
- `COLORS` — CSS custom properties (`--green`, `--gold`, `--bg`, etc.)

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
   - Fallback: try alternative effect; then use least-bad slot
4. **Shuffle and de-duplicate** — no two consecutive spaces of the same constrained type
5. **Resolve landmark names** — `resolvedLandmark` stored on each deed at gen time; `{landmark}` in deed text substituted at modal render time
6. **Assemble + add direction arrows**

The board path is determined by a `PATH_TEMPLATES` entry (`{ name, start, segments, gridRows?, gridCols? }`). Any path length works — `BOARD_SIZES` in config.js is informational only.

---

## Gameplay Rules

| Rule | Default | Configurable? |
|---|---|---|
| Exact finish | On — must roll exact number; overshooting = no move | Yes, in Game Settings |
| Question tracking | Session — asked questions skipped until pool exhausted, then resets | Yes, in Game Settings |
| Question topics | All selected | Yes, 3-level filter in Game Settings |

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
    ├── serves all static files
    ├── manages game rooms  Map<gameId, RoomState>
    └── relays events between host and player clients

Host browser (index.html)          Player browsers (player.html)
  full board view                    single action box (fixed height)
  GM controls panel                  own badge + score
  all V1 functionality               others' scores
  Roll button on host-player turn    dice → rolled → card → activity modes
```

**Authority model:** Host (`game.js`) runs all game logic. Server relays state via `sync_state` → `state_update`. Server rolls the dice (authoritative).

### Critical V2 invariants

- **`sync_state` must preserve server-only fields** — `rejoinToken` and `socketId` are server-managed; `playerStates` from host must not overwrite them
- **`state_update` must not override `rolled-mode` or `card-mode`** — prevents clearing a result the player is actively reading
- **`turn_result` before `space_card_done`** — activity feed updates before card clears
- **`_turnToken`** — incremented on each roll and undo; async continuations check token before proceeding

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
| `triventurex_asked_<editionId>_<diff>` | Asked question IDs per edition and difficulty |
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
| `saveGame()` after `endTurn()` | Prevents double-award on page-refresh mid-action |
| Host runs all logic; server relays | Server is a thin relay — all game logic stays in `game.js` |
| 4-digit numeric Game ID | Easy to type on a phone without looking |
| Token-based rejoin (not socket ID) | socketId changes on every reconnect; token persists across sessions |
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

Deed card score effects are defined per edition in `deeds.csv`.

---

## Adding a New Edition

1. Copy `game_editions/template/` to `game_editions/<your-id>/`
2. Edit `config.js` — fill in `GAME`, `LANDMARKS`, `COLORS`, `SPACE_INFO`
3. Edit `questions.csv` and `deeds.csv` — add your content
4. Ask Claude to "regenerate the JS files" to produce `questions.js` and `deeds.js`
5. Add your edition to `game_editions/editions.js`
6. Done — the edition picker appears automatically on the setup screen

---

## Tools

### Path Designer (`tools/path-designer.html`)

A visual drag-and-click tool for designing new board path templates. Open it in a browser served from the project root (requires a local server so it can load `js/config.js`):

```bash
python3 -m http.server 8080
# then open http://localhost:8080/tools/path-designer.html
```

Features:
- Click to set start, click to extend path segment by segment
- Violation detection (highlights cells that are too close to adjacent path runs)
- Space counter vs. short/medium/long targets
- Generates JSON in the exact `PATH_TEMPLATES` format — copy and paste into `js/config.js`
- Load dropdown shows all existing templates live from `CONFIG.PATH_TEMPLATES`

---

## Future Possibilities

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
- **Admin dashboard** — view all active V2 rooms; room stats; room shutdown

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
