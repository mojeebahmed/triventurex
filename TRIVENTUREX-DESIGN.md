# Triventurex — Design Document

_Last updated: 2026-10-17 (version 2.2.0)_

> **For AI assistants / new contributors:** Start here for context, then read `CLAUDE.md` for the authoritative architecture reference and `README.md` for gameplay and setup instructions. `CHANGELOG.md` lists what changed in each release.

---

## What is Triventurex?

**Triventurex** = Trivia + Adventure + X

A family/group board game engine where players roll dice, move along a path, and collect points through:
- **Quiz questions** — Easy (+1 pt) or Hard (+2 pt) by default, chosen by the player; in a network game answered on the player's phone
- **Action cards** — act it out / explain it / hum it; performer and guesser both earn points. In a network game the card is shown only on the performer's phone
- **Good/Bad deed cards** — Randomly assigned effects (move forward/back, score, skip turn, etc.)
- **Landmarks** — Visual stops with photos and descriptions; points set by the rules (+5 by default when landing by a roll)

**Winner = most points when all players reach the finish.** The end screen adds per-player stats and fun awards.

The engine is fully **edition-neutral** — swap a content folder and colour scheme to get a completely different game.

---

## Active Editions

| Edition | Points | Finish | Deed labels | Landmarks | Questions | Action cards |
|---|---|---|---|---|---|---|
| Swab Quest | Sawab | Al-Ka'ba, Mecca | Good Deed / Bad Deed | 20 mosques & Islamic sites | 432 | 26 |
| Football Quest | Goals | The Final | Good Play / Foul Play | 20 iconic stadiums & venues | 92 | 25 |
| World Tour | Stamps | Home Again | Smooth Travels / Travel Trouble | 26 world wonders | 220 | 25 |
| Animal Safari | Paw Prints | Safari Lodge | Wildlife Hero / Safari Mishap | 26 wild places & reserves | 220 | 25 |
| Prophets' Stories (in review) | Noor | Al-Ka'ba, Mecca | Good Deed / Lesson to Learn | 24 blessed places | 221 | 25 |

Every edition also gets 40 general action cards from `game_editions/shared/actions.csv`.

---

## Architecture

### Stack

- **Client:** Vanilla HTML + CSS + JavaScript — no framework, no build step. Plain `<script>` files, not ES modules, so `index.html` also works opened from disk
- **Server (V2):** Node.js + Express + Socket.IO
- **Content:** CSV files (loaded via `fetch()`) with generated JS fallbacks for offline/`file://` use (`npm run build:content`)
- **Tests:** Node's built-in test runner (`npm test`, ~390 tests), no test framework; one third-party client library, vendored: `js/vendor/qrcode.js` (MIT)

### Pages

| Page | Who | What |
|---|---|---|
| `index.html` | Host (laptop) | Setup screen (tabs: 🎲 New game · ⚙️ Rules · 📚 Questions · ✏️ Boards), lobby, game screen with GM controls, end screen. Works offline (single device) or as the network host |
| `player.html` (`/player`) | Phones | Join (QR or Game ID), lobby, one action box: roll, answer, private cards, activity feed |
| `display.html` (`/display?game=ID`) | TV / second screen | Read-only: lobby QR, board, tokens, scoreboard, dice, timer, open card, final scores and awards |
| `academy.html` (`/academy`) | Anyone, before playing | 🎓 Triventurex Academy — one edition at a time: Explore, Flashcards, Quiz, Match, True or false, Speed round, Places, Print cards, Review. Works from disk (loads the edition's config.js + questions.js as scripts) |

### Key files

`js/` is grouped by who loads a file: `shared/` (no page access at load; used by several of host page, phone page, TV page, server, tests), `host/` (index.html only), `player/` (player.html only), `display/` (display.html only), `vendor/` (third-party, don't edit).

| File | Responsibility |
|---|---|
| `js/shared/config.js` | Engine defaults: board sizes, space types, scoring, rule presets, action card kinds, awards, zoom, animation, presentation mode, paths |
| `js/shared/rules.js` | Per-game rules model: defaults → preset → changes; normalising, tile counts, finish bonus, landmark points (pure) |
| `js/shared/players.js` | Player model (`createPlayer`, `movePlayer`, `addScore`, `getSortedPlayers`) |
| `js/shared/turn.js` | Pure turn logic: next player, undo snapshots / restore, history rows (also used by server.js and the phone) |
| `js/shared/board.js` | Board generation algorithm + DOM rendering (host + TV) |
| `js/shared/viewport.js` | Pan / zoom / fit-to-screen and the board background (host + TV) |
| `js/shared/edition.js` | Edition config merge + colours as CSS variables (host + TV) |
| `js/shared/stats.js` | End-screen stats and awards from the game history (pure) |
| `js/shared/questions.js` | Question tree / search / marked-questions report / topic keys (pure) |
| `js/shared/icon-registry.js` | Every engine icon by name (`lucide:…` for controls, `emoji:…` for game symbols) and the badge lists |
| `js/shared/icons.js`, `icons-data.js` | `icon(name)` / `iconText(name)`, `data-icon` placeholders, content emoji drawn as bundled Fluent Emoji Flat images — built by `npm run build:icons` |
| `js/shared/marks.js` | 🚩 marked questions + reviewed ticks in localStorage (host + Academy share them) |
| `js/shared/academy.js` | Academy rounds: true/false items, match pairs, places quiz, flashcard sets, double-sided print sheets, text size for fixed cards, review stats (pure, tested) |
| `js/academy/academy.js`, `modes.js` | Academy page: edition loading, shared filter, mode switching; the nine modes |
| `js/shared/path-design.js` | Drawing board paths for the ✏️ Boards tab (pure) |
| `js/shared/csv.js` | CSV parsing for questions, deeds, action cards (also used by the content tooling) |
| `js/shared/dice.js` | `renderDie(n, sizeClass)` + `animateDieInto` — CSS dot-die and roll animation; host, phones, TV |
| `js/shared/socket-client.js` | `TX_NET` singleton — shared Socket.IO layer; safe no-ops when offline |
| `js/shared/utils.js` | `esc()` — HTML escaping for anything a player can type |
| `js/host/game.js` | Shared game `state`; start / resume / rematch / reset a game; bootstrap (loaded last) |
| `js/host/turn-flow.js` | The turn pipeline, undo, GM controls |
| `js/host/net-host.js` | Host side of network play: lobby, QR, state sync, socket events, private cards, phone prompts, players without a phone, TV display feed |
| `js/host/ui.js` | Modals (question, deed, action, landmark), scoreboard, legend, timer, history, end screen |
| `js/host/setup.js`, `setup-flow.js`, `board-picker.js`, `badge-picker.js`, `category-filter.js` | Setup screen: player rows, the step-by-step New game tab, board thumbnails, badge picker, topic tree |
| `js/host/rules-panel.js` | ⚙️ Rules tab; `gameRules()` — the only way host code reads rules |
| `js/host/question-explorer.js` | 📚 Questions tab + 🚩 report on question cards |
| `js/host/board-designer.js` | ✏️ Boards tab: draw, save, play a board |
| `js/host/presentation.js` | 📺 Presentation mode (full screen on one screen) |
| `js/host/edition-loader.js` | Edition loading, edition picker, branding |
| `js/host/storage.js` | localStorage: saved game, preferences, custom boards, marked questions |
| `js/player/player.js` | Phone screen logic: join, action box, answering, session management |
| `js/display/display.js` | TV display logic |
| `game_editions/editions.js` | Edition registry — lists all available editions |
| `game_editions/<id>/config.js` | Edition config: name, colours, landmarks, background, space / score / award overrides |
| `game_editions/<id>/*.csv` | Source of truth for questions, deeds, action cards — edit these, then `npm run build:content` |
| `game_editions/shared/actions.csv` | General action cards mixed into every edition (`GENERAL_ACTIONS_DATA`; ids become `g<n>` in the deck) |
| `game_editions/IDEAS.md` | Ideas for new editions, content targets, how an edition is built |
| `server.js` | Rooms, authoritative dice, relays (host → phones, phone → host, host → TV); state-ownership rules at the top |
| `scripts/` | Node-only dev tooling: content build + checker, `commons-image.js` for Wikimedia Commons photos, `review-sheet.js` for a printable question review (not served) |
| `tools/path-designer.html` | Older standalone path designer (the ✏️ Boards tab replaces it) |
| `test/` | Automated tests (`npm test`) |

---

## Edition System

### How editions are loaded

1. `game_editions/editions.js` (loaded via `<script>` in `index.html`) sets `window.TRIVENTUREX_EDITIONS`
2. On `DOMContentLoaded`, `game.js` reads the last-used edition from localStorage (`triventurex_edition`)
3. `loadEdition()` (edition-loader.js) dynamically injects the edition's `config.js`, `questions.js`, `deeds.js` and `actions.js`, then fetches the CSV files, which replace the JS copies when served over HTTP
4. `config.js` sets `window.EDITION_CONFIG` → merged into `CONFIG` via `mergeEditionConfig()` (js/shared/edition.js — the TV display uses the same function)
5. `_ENGINE_DEFAULTS` snapshot allows `_resetToEngineDefaults()` before an edition switch

### What an edition defines

- `GAME` — name, icon, subtitle, pointsName, finish labels, celebration text
- `LANDMARKS` — array of `{ name, image, description }` objects (image path relative to `index.html`)
- `BOARD_BACKGROUND` — image, overlay opacity, blur
- `SPACE_DISTRIBUTION` — ratios per space type, optionally keyed by `short/medium/long` (the template has Swab Quest's mix as the standard)
- `SPACE_INFO` — label and colour overrides (e.g. Football Quest: "Good Play" / "Foul Play")
- `ICONS` — the icons the edition changes, by engine name (`tileGoodDeed: '⚽'`); emoji, `'<set>:<icon>'` or `'file:icons/x.svg'` in the edition folder
- `COLORS` — CSS custom properties (`--green`, `--gold`, `--bg`, etc.)
- `SCORE_VALUES`, `FINISH_BONUS` — optional point overrides (the defaults for the rules)
- `AWARDS` — optional new names for end-screen awards (Football Quest: "Football brain", "Groundhopper", …)

---

## Board Generation

The board is built fresh each game from the active edition's content and the game's rules. Steps in order:

1. **Count** spaces per type (`tileCounts` in rules.js) from the rules' tile mix, or the edition's `SPACE_DISTRIBUTION`; questions fill the remainder; landmarks capped by the edition's landmark count
2. **Pre-pick deed effects** — `_pickActiveEffect()` selects one effect from each card's `effects[]` array (variable rewards per game; rules can force the first effect or leave out backward effects)
3. **Constraint-aware pool assignment** (`_assignDeedsToSlots`):
   - `move_back N` → placed at slot ≥ N (not near start)
   - `move_forward N` → placed at slot ≤ poolLen-1-N (not near finish)
   - `move_to_prev_landmark N` → N landmarks must exist before the slot
   - `move_to_next_landmark N` → N landmarks must exist after the slot
   - Fallback: try another effect on the same card; then swap in an unused card from the deck that fits; least-bad slot only if nothing in the deck fits
4. **Shuffle and de-duplicate** — no two consecutive spaces of the same constrained type
5. **Resolve landmark names** — `resolvedLandmark` stored on each deed at gen time; `{landmark}` in deed text is filled by `fillLandmarkText()` on the board tile and in the card modal (the target, or "a <landmark label>" such as "a wonder" when the game's effect isn't a landmark move)
6. **Assemble + add direction arrows**

These rules are checked by a randomized test (`test/board.test.js`): ~3,000 boards per run across every path template of every edition, including rule variants and that each landmark tile's label matches where the player actually goes.

The board path is a `PATH_TEMPLATES` entry (`{ name, start, segments, gridRows?, gridCols? }`), chosen in the board picker (or 🎲 Random). Any path length works — `BOARD_SIZES` in config.js is only used for the rules panel's tile preview. Boards drawn in the ✏️ Boards tab are saved in the browser and added after the built-in templates (so built-in indexes never change). The board is drawn only as big as the path's bounding box, and fit-to-screen leaves room for the legend.

---

## Gameplay Rules

Every rule has a default in code (engine or edition). The **⚙️ Rules** tab changes them per edition: a **preset** (*Family*, *Kids*, *Quiz night* — `CONFIG.RULE_PRESETS`) plus the player's own changes. A game copies its rules at the start and keeps them (also after a resume). **📋 Copy as preset** exports the current rules as a new `RULE_PRESETS` entry.

| Section | Rules (default) |
|---|---|
| Scoring | Question points easy/hard (1/2) · action performer/guesser (1/1) · finish bonus Standard 10/7/5… / Small 5/3/2/1 / Off · landmark points by roll (+5), via good deed (0), via bad deed (0) · negative scores (off) |
| Questions | Difficulty: player chooses / always easy / always hard · timer auto-start (off) + seconds (30) · avoid repeats: across games / per game · players answer on their phone (on) · topics |
| Action cards | Digital or physical deck (a digital card can always be swapped) · add the general cards (on) · kinds: act / explain / sound · timer (90 s) |
| Board | Tile mix per type (0 removes it; presets; special tiles capped at 70%) · deed effects varied / first · no going backwards |
| Turn & pace | Exact finish (on) · who starts: first / random · animation speed: normal / fast |

Other rules: **Undo** (mid-turn: cancels only the current turn; between turns: undoes the last turn or GM change) · **Sit out** (GM: skipped in turn order, keeps place and score) · **Finish bonus** is given however the player reaches the finish (roll, deed, GM move).

### Question topic filter (3 levels)

Questions have `category > subcategory > topic`. The Rules tab's *Topics* section shows a collapsible tree with question counts — the checkbox/name toggles, the rest of the row expands. Checking/unchecking a parent toggles all children; a parent shows an indeterminate (−) state when partially selected. At least one topic must always remain checked. Saved per edition to `triventurex_cats_<editionId>`.

---

## Landmark Info

Each landmark can have a `description` field in the edition's `config.js`. Descriptions appear:
1. In the **landing modal** — shown when a player lands on the space
2. In the **info popup** — shown to anyone who clicks a landmark space on the board at any time

Arriving at a landmark via a deed shows a toast with the points the rules give for it.

---

## Playing on a big screen

Two ways, for different setups:

| | 📺 Presentation mode | 📺 TV display |
|---|---|---|
| Setup | One screen: laptop mirrored to a TV | Two screens: the laptop keeps the controls, the TV shows the game |
| How | 📺 next to the zoom buttons, or **P** | *📺 Open TV display* in the lobby / GM controls → `/display?game=ID` |
| Needs the server | No (works offline) | Yes |
| What it is | The host page, full screen, bigger, GM tools behind ⚙️ | A separate read-only page fed by the host |
| Secrets | GM must not open them on the shared screen | Never sent: card HTML is stripped of `[data-secret]` (unrevealed answer, action card), `[data-host-only]`, hidden elements and buttons before it leaves the host |

---

## V2 — Local Network Multiplayer

### Architecture

```
Node.js + Express + Socket.IO server (server.js)
    ├── serves an allowlist of client files (not server code, docs or tests)
    ├── manages game rooms  Map<gameId, RoomState> — cleaned up when finished or abandoned
    ├── rolls the dice (authoritative)
    ├── relays host → phones (all, or ONE phone for private cards)
    ├── relays phone → host (card_choice: a tapped answer / difficulty)
    └── relays host → TV displays (and replays the latest state to a late TV)

Host browser (index.html)          Player browsers (player.html)       TV (display.html)
  full board view                    single action box (fixed height)   board, tokens, scores
  GM controls panel                  own badge + score                  dice, timer, open card
  all V1 functionality               others' scores, "You're next"      lobby QR, final awards
  rolls for itself + no-phone seats  dice → rolled → card → activity    read-only
```

**Ownership model:**
- The **host** owns all game state — positions, scores, turn order, finish order, sitting out, badges in a running game — and pushes it with `sync_state`; the server forwards it to phones as `state_update`.
- The **server** owns connection state — which socket belongs to whom, rejoin tokens, connected/disconnected, whether a seat has no phone (`noPhone`), room membership — and the dice. A host sync never overwrites these, and server-only fields never leave the server.

### Critical V2 invariants

- **One turn pipeline** — every turn ends in `_finishTurn()` (finish bonus → history → phone update → game over? → next player → save → sync); never end a turn any other way
- **`state.turn`** — the turn in progress; every async step checks it is still current, so undo / player removal cancel everything in flight
- **Server-only fields** (`socketId`, `rejoinToken`, `awaitingHostSync`) are stripped from everything sent to clients; a phone gets its own rejoin token once, when it joins. Rejoining needs a real token, so seats without one (host's own player, players without a phone) can't be taken over
- **`state_update` must not override `rolled-mode` or `card-mode`** — prevents clearing a result the player is actively reading
- **`turn_result` before `space_card_done`** — activity feed updates before card clears
- **Private cards** — `private_card` goes from the host to ONE phone only (action cards, questions, results). With `choices` it's a prompt: the phone answers with `card_choice`, which reaches the host only, with the player id taken from the socket; the host accepts only the prompt it is waiting for
- **TX_NET forwards only listed events** — a new server → page event must be added to the list in socket-client.js (a test checks it)
- **Room lifecycle** — closed when the host clicks *New game setup* on the end screen / leaves the lobby, 5 min after the game ends, or 30 min after the host disconnects without coming back

### Session persistence

- **Identity** (`triventurex_player_identity`): name, token, colour — pre-fills on next join (and adopts a badge the host gave this phone)
- **Session** (`triventurex_game_session`): `{ gameId, playerId, rejoinToken }` — auto-rejoin on any reconnect. A `?game=` link (QR) is read once and removed from the address, so a refresh rejoins instead of re-applying an old link
- **Host** (`tx_net_game`): gameId — re-registers host socket after browser refresh

### Action box modes (player screen)

`dice-mode` → (tap roll) → `rolled-mode` → (space_card) → `card-mode` → (space_card_done) → `activity-mode` → (next turn) → `dice-mode`

---

## State & Persistence (localStorage keys)

| Key | Contents |
|---|---|
| `triventurex_save` | Full game state for resume on refresh (incl. the turn in progress and the game's rules) |
| `triventurex_player_prefs` | Player names, colours, tokens (local game) |
| `triventurex_host_player` | Host player name/colour/token (network host) |
| `triventurex_game_settings` | Last game length, board choice, number of players |
| `triventurex_edition` | Last active edition ID |
| `triventurex_rules_<editionId>` | Rules per edition: `{ preset, changes }` (only what differs from the preset) |
| `triventurex_asked_<editionId>_<diff>` | Asked question IDs per edition and difficulty (`easy` / `hard`) |
| `triventurex_asked_<editionId>_actions` | Used action card IDs per edition (general cards are `g<n>`) |
| `triventurex_cats_<editionId>` | Selected question topics per edition, as "cat › subcat › topic" keys (older saves: plain topic names) |
| `triventurex_marked_<editionId>` | Questions marked wrong / unclear: `{ [id]: { note, at } }` (game + Academy) |
| `triventurex_reviewed_<editionId>` | Academy 🔍 Review: questions ticked as reviewed `{ [id]: at }` |
| `triventurex_academy_edition` | Last edition opened in the Academy |
| `triventurex_custom_boards` | Boards from the ✏️ Boards tab: `{ short, medium, long }` (all editions) |
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
| Rules = defaults → preset → changes | Stored as only the changes, so a new default in code reaches settings nobody touched; presets are plain data anyone can add |
| Modal inside `#board-viewport` | Sidebar stays accessible during questions |
| `#board-viewport` never scrolls (`overflow: clip`) | Pan/zoom are transforms; focusing a text box in a card must not shift the board |
| Synchronous `fitBoardInView` (no rAF) | Eliminates "board jumps" visual glitch |
| One end-of-turn path (`_finishTurn`) | Every earlier network bug was a turn path that skipped a step (sync, save, history) |
| Host owns game state, server owns connections | One source of truth each; the server never computes game state |
| Plain scripts, not ES modules | Browsers block modules on `file://`; the offline mode must keep working |
| CSV + generated JS, checked by a script | Editors use spreadsheets; the checker catches unquoted commas, bad ids, unknown effects with file:line |
| Action card shown only on the performer's phone | Keeps the card secret without anyone looking away; host-screen fallback hides it behind a toggle |
| Answers checked on the host, never sent early | The phone only gets the options; the host scores the tap — a phone can't cheat by reading the payload |
| TV display fed by the host, secrets stripped | One page per role; anything marked `data-secret` can't reach a shared screen by accident |
| Players without a phone are normal server seats | The same game flow for everyone; a network game can run with zero phones, so the TV display works for every game |
| History entries record where the roll landed and the result | End-screen stats stay right even when a deed moves the player afterwards |
| Custom boards appended after built-in ones | Built-in board indexes (saved settings, rematch) never change |
| 4-digit numeric Game ID | Easy to type on a phone without looking |
| Token-based rejoin (not socket ID) | socketId changes on every reconnect; token persists across sessions — and is never shown to other players |
| `translateZ(0)` on each `.space` | Each space in its own GPU layer → crisp at any zoom level |

**Decided against (2026-10):** endgame pacing rules (the GM can move a player or set the dice when an endgame drags) and streaks / wagers / a final round (keep the game simple). The finish bonus and landmark points became settings in the Rules tab instead.

---

## Scoring

Defaults (all of them are rules — see *Gameplay Rules*):

| Event | Points |
|---|---|
| Easy question correct | +1 |
| Hard question correct | +2 |
| Action performed | +1 (performer) |
| Action guessed correctly | +1 (guesser) |
| Landmark, landing by a roll | +3 (deed arrivals 0 by default) |
| Finish bonus | 10, 7, 5, 4, 3, 2, 1, 1 by finishing order |

Defaults come from `CONFIG.SCORE_VALUES` / `CONFIG.FINISH_BONUS`; editions can override them. Deed card score effects are defined per edition in `deeds.csv`.

---

## Adding a New Edition

Check the idea against the content targets in `game_editions/IDEAS.md` first (20+ landmarks, 50+ deeds, 25+ actions, 200+ questions; overlap with other editions is fine up to about 10% of the questions). That file also describes the five steps we follow: outline → images → questions → deeds and actions → check and play.

1. Copy `game_editions/template/` to `game_editions/<your-id>/`
2. Edit `config.js` — fill in `GAME`, `LANDMARKS`, `COLORS`, `SPACE_INFO` (optionally `AWARDS`). Landmark photos: `scripts/commons-image.js` (credits go in `CREDITS.md`)
3. Edit `questions.csv`, `deeds.csv` and (optionally) `actions.csv` — columns: `game_editions/template/README.md`
4. Run `npm run build:content <your-id>` — checks the content (file:line messages) and produces `questions.js`, `deeds.js`, `actions.js`
5. Add your edition to `game_editions/editions.js`
6. Done — the edition picker appears automatically on the setup screen

---

## Tools

### ✏️ Boards tab (board designer)

Built into the setup screen: click a start cell, then cells in a straight line to add runs; live thumbnail, space count vs. the usual size, warning when parallel rows touch. Save to *My boards* (appears in the board picker), play straight away, or **📋 Copy as template** for `CONFIG.PATH_TEMPLATES`.

### 📚 Questions tab

Browse every question by category › subcategory › topic, search, filter by difficulty, show answers, and mark questions as wrong / unclear with a note (also possible with 🚩 on a question card in play). **📋 Copy marked list** gives a text list to fix `questions.csv`.

### 🎓 Triventurex Academy (`academy.html`)

A learning page next to the game, one edition at a time (switching edition reloads the page with `?edition=<id>`; the mode is the `#hash`). One filter (topic tree, difficulty, search) feeds every question mode. The rounds are built by `js/shared/academy.js` (pure); the page is `js/academy/`. 🚩 marks and reviewer ticks live in `js/shared/marks.js`, so a mark made in the Academy shows in the game's 📚 Questions tab in the same browser. Opened from disk the page works the same — the edition's `config.js` and `questions.js` are loaded as plain scripts.

### Path Designer (`tools/path-designer.html`)

The older standalone version of the ✏️ Boards tab. It needs to be served (it loads `js/shared/config.js`): with `node server.js` running, open `http://localhost:3000/tools/path-designer.html`.

### Content tooling (`scripts/`)

- `npm run build:content [edition]` — checks every edition's CSV files and regenerates the JS copies
- `npm run check:content` — check only; also fails if a generated file is out of date (`npm test` runs the same checks)

---

## Future Possibilities

### Near-term
- **Sound effects** — dice roll, correct answer, finish fanfare, deed card reveal
- **Steal** — when the active player answers wrong on their phone, others can answer for points
- **Content review** — the draft action cards (both editions) and the Football Quest notes flagged in 2.1 (truncated notes; possible factual errors in #66, #70, #73, #86) — use the 📚 Questions tab to mark and export them
- **More Swab Quest questions** — currently 432; target 600+ across all topics
- **Football Quest subcategories/topics** — currently flat; could add `Clubs / International / History` structure

### Medium-term
- **New editions** — same engine, different content. Ideas, sizing and the build process: `game_editions/IDEAS.md` (World Tour and Animal Safari are done)
- **Team mode** — two teams share a token; questions alternate between team members
- **Timer penalty** — losing points when the question timer runs out
- **Mobile layout improvements** — board tiles larger on phones; better touch handling

### Longer-term
- **Online multiplayer** — beyond local Wi-Fi (requires hosted server + authentication)
- **Question editor UI** — edit questions in the browser (today the Questions tab marks them for fixing in the CSV)
- **Admin dashboard** — view all active V2 rooms; room stats

---

## Development History

| Phase | Date | What was built |
|---|---|---|
| V1 initial | 2026-05 | Core engine: board generation, modals, scoring, pan/zoom, save/resume |
| V2 network | 2026-05-18 | Local network multiplayer: Socket.IO, player screens, rejoin, GM controls |
| Gameplay improvements | 2026-06-01 | Exact finish, no-repeat questions, relative landmark deeds, constraint-aware board gen, SPACE_DISTRIBUTION per edition/length, host player separation |
| Theme → Edition rename | 2026-06-01 | `themes/` → `game_editions/`, `THEME_CONFIG` → `EDITION_CONFIG`, localStorage key updated |
| 3-level question topics | 2026-06-01 | `cat > subcat > topic` hierarchy; collapsible filter tree; 432 Swab Quest questions |
| Landmark descriptions | 2026-06-03 | `description` field on landmarks; landing modal shows it; click-to-info popup on board tiles |
| More landmarks | 2026-06-03 | Swab Quest: 6 → 20 landmarks; Football Quest: 6 → 20 stadiums/venues |
| Code review & hardening (2.1) | 2026-10-16/17 | 18 bugs fixed; one turn pipeline; host/server state ownership; `game.js` split into `js/shared/host/player`; content build + checker; digital action cards; ~200 automated tests |
| Gameplay & play experience (2.2) | 2026-10-17 | Setup screen with tabs, rules panel + presets, board picker, QR join, answering on phones, players without a phone, presentation mode, TV display, end-screen stats + awards, question explorer + reporting, board designer; ~310 tests — details in `CHANGELOG.md` |
| World Tour, Animal Safari + shared actions (unreleased) | 2026-10-17/18 | World Tour and Animal Safari editions (220 questions each); Prophets' Stories (in review); topic filter keyed by full path; World Tour edition (220 questions, 56 deeds, 26 wonders with Commons photos); 40 general action cards for every edition; landmark points 3; Rules tab action bar; `scripts/commons-image.js`; board test covers every registered edition |
