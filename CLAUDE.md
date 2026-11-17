# Memory & Context Files
Personal context lives in `/Users/mojeebahmed/Claude/Claude Mojeeb/about me/`:
- `aboutme.md` — read at the start of a conversation (it is short).
- `memory.md` and `projects.md` — read only when a task needs project history or another project. Triventurex's own history is in `CHANGELOG.md`, git and the CLAUDE.md files.

Update memory.md when meaningful progress is made (a short line — details belong in CHANGELOG.md).
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
- **World Tour** — travel & geography, family-friendly (third edition; outline in `game_editions/world-tour/OUTLINE.md`)
- **Animal Safari** — animals & wild places, family-friendly (fourth edition; outline in `game_editions/animal-safari/OUTLINE.md`)
- **Prophets' Stories** — stories of the prophets for families (fifth edition; Ahmadiyya understanding, Qur'an refs with Bismillah = verse 1, no pictures of people, nobody acts a prophet; decisions in `game_editions/prophets-stories/OUTLINE.md`). Questions are being reviewed by a knowledgeable person in the 📚 Questions tab (🚩 marks + notes → 📋 Copy marked list → fix questions.csv by id); `REVIEW.md` (`node scripts/review-sheet.js prophets-stories`) is a printable alternative — regenerate it after changing questions.csv

## Run (V1 offline)
Open `index.html`. For images + CSV loading: `python3 -m http.server 8080`

## Run (V2 — live)
`node server.js` — serves everything and handles Socket.IO rooms.
- Host: `http://localhost:3000`
- Players: `http://<host-ip>:3000/player`

## Tests
`npm test` — Node's built-in test runner (`node:test`), files in `test/**/*.test.js`. Which test covers what: `test/CLAUDE.md`.
- `server.js` exports `{ server, io, rooms }` and only calls `listen()` when run directly — keep it that way
- Run `npm test` before merging any change (it takes ~5 s)

## Where the details live
Each area has its own CLAUDE.md, loaded automatically when you work in that folder — read the one for the area you are about to change before changing it:
- `js/shared/CLAUDE.md` — board generation and placement rules, turn logic, stats, help, icons (developer guide), dice
- `js/host/CLAUDE.md` — host page: turn pipeline, setup screen, rules tab, modals, GM controls, undo, phone answering / private cards / badges (host side), presentation, board designer
- `js/player/CLAUDE.md` — phone page: action box modes, rejoin, join by QR, edition on phones
- `js/display/CLAUDE.md` — TV display
- `js/academy/CLAUDE.md` — Triventurex Academy, its phone layout and offline app
- `game_editions/CLAUDE.md` — content workflow, CSV rules, effect types, action cards
- `test/CLAUDE.md` — what each test file checks
- `question-validator/CLAUDE.md` — the **Question Validator**, a separate Python project (AI-assisted fact-checking of
  the editions' questions; phases 1–2 done, next steps listed there). The game rules in this file do not apply to it

## Key files
`js/` is grouped by who loads a file (plus `js/vendor/` for third-party libraries):
- `js/shared/` — no page access at load time; used by more than one place (host page, phone page, server, tests). A change here can affect all of them. Rule: top-level code in `shared/` must not touch `document`/`window` (only inside functions)
- `js/host/` — host page (`index.html`) only
- `js/player/` — phone page (`player.html`) only
- `js/display/` — TV display page (`display.html`) only
- `js/academy/` — Triventurex Academy page (`academy.html`) only

Host page scripts are plain `<script>` files (not ES modules — `index.html` must work from disk), loaded in the order index.html lists them; top-level declarations are shared between them and `js/host/game.js` is loaded last.
- `server.js` — rooms, dice rolling, relays host → phones / phone → host / host → TV (ownership rules at the top)
- `js/vendor/qrcode.js` — qrcode-generator (MIT, Kazuhiko Arase) — third-party, don't edit
- `tools/icon-picker.html` — try other icons for the engine or an edition, copy the list of changes (see *Icons* in `js/shared/CLAUDE.md`); `tools/path-designer.html` — older standalone board-path designer

## Rules for every change
- Player-supplied values go through `esc()` when inserted as HTML (see *Escaping* below)
- Never hardcode configurable values, point numbers or edition words — `CONFIG` / edition config / `gameRules()`
- No raw emoji or icon symbols in engine code — icon NAMES via `icon()` / `iconText()` (`js/shared/CLAUDE.md` → Icons)
- Host code reads rules only via `gameRules()`; a turn ends only through `_finishTurn` (`js/host/CLAUDE.md`)
- New server → page event: add it to socket-client.js's `events` list; new top-level client folder: add it to `PUBLIC_DIRS`
- New or changed screen, tab, mode or control: update its help topic in js/shared/help.js
- Content: edit the CSV, never the generated JS; never renumber question ids (`game_editions/CLAUDE.md`)

## Terminology
- **Edition** = interchangeable game content pack (was "theme" before 2026-06-01)
- `EDITION_CONFIG` — the `window` global set by each edition's `config.js`
- `CONFIG.COLORS` — CSS colour variables (was `CONFIG.THEME`); edition configs use a `COLORS` block. `GAME.editionName` / `GAME.editionIcon` (were `themeName` / `themeIcon`)
- No "theme" identifiers remain in code (2026-10-16) — use "edition" for content packs, "colors" for styling
- `TRIVENTUREX_EDITIONS` — the registry array in `game_editions/editions.js`
- localStorage key: `triventurex_edition` (saves last-used edition ID)

## Architecture — engine-wide (don't revert)
- **Edition-neutral engine**: `player.score`, `addScore()`, `SCORE_VALUES`; editions provide `pointsName`, `finishLabel`, `finishCelebration`, `finishButtonLabel`, `endScreenMessage`
- **Score values**: every point label and award reads `CONFIG.SCORE_VALUES` / `CONFIG.FINISH_BONUS` — never hardcode numbers in UI text. Editions may override either in their `config.js` (reset on edition switch via `_ENGINE_DEFAULTS`)

## Architecture — server & network (don't revert)
- **Escaping**: any player-supplied value (name, token, colour) inserted via innerHTML/template MUST go through `esc()`. Not needed for `textContent` (toasts, button labels, modal titles). Server also cleans profiles on join (`cleanProfile`: name ≤20, token ≤8 code points, hex-only colour)
- **Static files**: server.js serves an allowlist only (`/`, `/player`, `/display`, `/academy`, `css/ js/ game_editions/ images/ tools/`). New top-level client folder → add it to `PUBLIC_DIRS`
- **Authority**: Host (`game.js`) runs all game logic; server relays state via `sync_state` → `state_update`
- **Dice**: server rolls (authoritative); player taps → `roll` event → server generates → broadcasts `roll_result`
- **Game ID**: 4-digit numeric, unique among active rooms; easy to type on a phone
- **State ownership (A3)**: HOST owns game state (positions, scores, turn order, finish order, sitting out) and pushes it with `sync_state`. SERVER owns connection state (`socketId`, `rejoinToken`, `disconnected`, room membership) + dice; `sync_state` never overwrites these. Rules are written at the top of server.js
- **Server-only fields never leave the server**: `SERVER_ONLY_FIELDS` (`socketId`, `rejoinToken`, `awaitingHostSync`) are stripped by `publicPlayer(s)()` / `publicState()` from every emit. A player's own `rejoinToken` is only sent once, in its `joined` reply
- **Late joiners survive syncs**: a joiner is `awaitingHostSync` until a host sync includes them; a sync with an older list keeps them. The host's `player_joined` handler adds them + syncs. A player the host has synced before and then leaves out IS dropped (host authority)
- **Rejoin needs a real token**: `rejoin_game` only matches a non-empty string token — seats without one (host's own player, no-phone players) can't be taken over
- **TX_NET events**: socket-client.js forwards only the events in its `events` list — a new server → page event must be added there (`test/socket-events.test.js` checks it)
- **Room lifecycle (A5)**: rooms are deleted immediately on `close_room` (host's end-screen "New game setup" / lobby Back — phones get `host_left` "ended the game"), `ROOM_TTL.endedMs` (5 min) after `phase: 'ended'`, or `ROOM_TTL.hostGoneMs` (30 min) after the host disconnects. `host_rejoin` cancels the countdown and sends `host_back` (phone hides its "host left" overlay). TTLs in `ROOM_TTL` at the top of server.js (env overrides)
- **Host → phone relays** (`turn_result`, `space_card`, `space_card_done`) are accepted from the host socket only
- **remove_player** on the server only changes membership (+ removed socket leaves the room); it sends no `state_update` — the host's `player_removed` handler syncs the result

## Current state
- Version 2.2.0 (2026-10-17) — see `CHANGELOG.md` for what changed in each release (2.1 = code review & hardening, 2.2 = gameplay & play experience). The work-item IDs in commits and the changelog (B1…, A2…, C3…, T1…, G6…) come from the 2026-10 plan: B = bug, A = architecture, C = content, T = tests, G = gameplay
- 5 editions: Swab Quest (432 questions, 52 deed cards, 26 action cards, 20 landmarks) + Football Quest (92 questions, 52 deed cards, 25 action cards, 20 stadium landmarks) + World Tour (220 questions, 56 deed cards, 25 action cards, 26 wonders) + Animal Safari (220 questions, 56 deed cards, 25 action cards, 26 reserves). + Prophets' Stories (221 questions, 56 deed cards, 25 action cards, 24 places; in review). The last three use Wikimedia Commons photos — credits in each edition's `CREDITS.md`
- Plus 40 general action cards (`game_editions/shared/`) mixed into every edition
- All Islamic/football text in respective `game_editions/<id>/config.js` — engine is fully edition-neutral
- Four pages: host (`index.html`), phones (`player.html`), TV (`display.html`), 🎓 Academy (`academy.html`) — setup, game and Academy also have phone layouts; the Academy installs as an offline app (2026-11)
- ~500 tests (`npm test`)

## Workflow (how Mojeeb works on this project)
- `main` stays playable. One branch per item or small group of related items (e.g. `feat/g16-second-screen`, `fix/phone-refresh-rejoin`)
- Each branch: change → `npm test` → check in a browser (offline AND network with ≥1 phone when it touches play) → Mojeeb tests → merge `--ff-only` to `main`
- Push to GitHub only when Mojeeb asks
- After pulling server changes: restart `node server.js` and reload host + phone pages
- When an invariant changes, update the CLAUDE.md that covers it (this file for project-wide rules and the server; otherwise the folder's own CLAUDE.md)

## Next work / ideas
- **Content**: more questions for every edition over time (Swab Quest 432; World Tour, Animal Safari, Prophets' Stories ~220 each). **Football Quest needs a revisit**: it was the first content and has only 92 questions with a flat, inconsistent category / subcategory / topic structure — rework its questions and categories like the newer editions (see game_editions/IDEAS.md → Improving existing editions)
- **Question tags — suggestions** (Mojeeb, 2026-11-17): the `tags` column, shared tag list and tag filters are built (see `game_editions/CLAUDE.md` → Tags; first tags added by hand). Next: the Question Validator suggests tags from what a question is about, a person accepts them; more tags by hand where they clearly help
- **First-game walkthrough**: a short guided tour in the first game (Roll Dice, the card, scoreboard, GM controls), one step at a time
- **Celebrate moments**: a short confetti / fanfare for a landmark, a finish, a hard question answered right
- **Kids mode on the phone**: bigger buttons, pictures before words, a *Read it to me* button
- **Fun facts on the TV between turns**: a landmark fact or question note while the next player rolls
- Sound effects — and with them **read aloud** in the Academy (Web Speech) for children who can't read yet
- Academy **progress tracking**: profiles, stars per topic, spaced repetition across days (see IDEAS.md)
- **Cross-edition question mode**: on a question space the player picks an edition and topic, then gets a question from it
- *Steal*: others answer when the active player gets a phone question wrong
- Content review: draft action cards (both editions); Football Quest notes flagged in 2.1 (truncated notes) — mark them in the 📚 Questions tab. Factual errors in #66, #70, #73, #86 were fixed on 2026-11-15
- Team mode; more editions; online multiplayer
- Decided against (2026-10): endgame pacing rules, streaks / wagers / final round
