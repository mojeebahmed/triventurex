# Changelog

All notable changes to Triventurex. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

IDs in brackets (B1, A2, C3, …) refer to items in [`IMPROVEMENT-PLAN.md`](IMPROVEMENT-PLAN.md), where each one is described in more detail.

## [Unreleased]

### Added
- Guided setup screen with *New game* and *Rules* tabs (G6); 🔁 Rematch and "New game setup" keep your choices (G7); board picker with thumbnails (G8).
- The board is fitted to the path, not the empty grid (G9); phones show the same rolling dice animation as the host (G10).
- Join by QR code (G11); per-game rules with presets and "Copy as preset" (G12).
- Phones show *"You're next"* and buzz on your turn (G18); leave the lobby from the phone (G21).
- 📺 Presentation mode for playing on a TV: full screen, big board and scoreboard, GM tools behind ⚙️ (G15).

### Fixed
- Refreshing a phone that was first opened from an earlier game's QR code showed the join page and joined as a new player. It now rejoins the same seat.
- The host scoreboard now shows ⚠️ next to a player whose phone is disconnected.

## [2.1.0] — 2026-10-17

A code review and hardening release. It fixes 18 bugs, restructures the host code, adds content tooling and digital action cards, and adds about 200 automated tests. Saved games and phone sessions from 2.0 keep working.

### Fixed

**Network turns**
- A roll tapped on a phone skipped the turn setup: Undo then restored the wrong turn, and the host's Roll button stayed active during the phone player's turn (B1).
- The server accepted rolls at any time, so a double-tap on a phone could start two turns at once (B2).
- After an "exact finish" overshoot, the next player's phone never got its dice (B3).
- After an extra-turn deed, the phone stayed stuck and the host's manual dice stayed disabled (B4).
- Refreshing the host while a space card was open left the turn stuck. Resuming now re-opens the card and the turn completes normally (B15).
- A phone roll ignored "skip next turn" (B16). Undoing a skipped turn now also restores the skip.
- Phones were never told when the game ended (B17).
- An extra turn could be given to a player who had just finished or was sitting out.

**Players and GM**
- Removing a player earlier in the turn order skipped someone's turn (B5).
- "Host left" was never shown when the host was also playing (B6).
- GM score / move / skip changes didn't reach phones and couldn't be undone (B7).
- The "deactivate player" feature was half-built: no button, and it was ignored by turn order (B8). It is now *Sit out / Rejoin*, see Added.
- The ⚠️ disconnected marker never cleared after a phone reconnected.
- A phone joining at the same moment as a host sync could be dropped from the game.
- A host who refreshed while also playing kept their own ⚠️ for the rest of the game.
- Phones kept showing "host left" after the host had simply refreshed and come back.
- The host's badge preview never updated while picking a badge.
- The GM player dropdown jumped back to the first player after every turn.

**Questions and content**
- "Already asked" question lists were shared between editions (B9).
- Question IDs depended on row order, so inserting a row scrambled the asked-question history (B10). Questions now have an `id` column.
- 10 Football Quest questions had commas without quotes, which shifted their columns, so the game could never ask them (B18). All 92 questions are now playable.
- The template's deed file used an old format with effect names the engine doesn't know.

**Board and scoring**
- On short Swab Quest boards (about 1 in 600), a deed could break its placement rule. For example, "move forward" could carry a player onto the finish, or "go to the next landmark" had none ahead. Found by the new board property test (T3).
- Finishing via a deed or a GM move gave no finish bonus or finish place (B12).
- Score labels were hard-coded ("+1", "Award 5") instead of using the configured values (B11).
- The landmark card always showed 🌍 and "Holy Site", even in Football Quest (B11).
- Points names were naively pluralised, e.g. "2 ptss" / "2 Goalss" (B11).

### Security
- Player names, tokens and colours sent from phones are now escaped wherever they are shown, and the server cleans them on join (B13). Previously a crafted name or colour could inject HTML.
- The server now serves only the game's client files. It used to serve the whole project folder, including `server.js`, docs and `node_modules` (B14).
- Every phone used to receive every other player's rejoin token, which could be used to take over their seat. Server-only fields are now never sent to clients (A3).
- Space cards and activity messages are only relayed from the host. Before, any phone could send fake ones to the others (A3).

### Added
- **Digital action cards** (C3): `actions.csv` per edition with three kinds: *act* (mime), *explain* (without the key words) and *sound* (hum / make sounds). Cards are drawn without repeats. In a network game the card appears **only on the performer's phone**. Otherwise it is hidden on the host screen behind a show/hide toggle. Editions without action cards keep the physical-deck prompt. Ships with draft cards: Swab Quest 26, Football Quest 25.
- **Sit out / Rejoin** in GM controls (B8): the player is skipped in turn order but keeps their place and score.
- GM changes appear in the move history ("⚙️ GM") and can be undone (B7).
- A toast when someone finishes via a deed or GM move, e.g. "🏁 Sara finished 2nd!" (B12).
- **Content tooling** (C1, C2):
  - `npm run build:content` checks each edition's CSV files and regenerates the JS copies (replaces regenerating them by hand).
  - `npm run check:content` reports problems as `file:line message`: unquoted commas, bad or duplicate ids, invalid answers, unknown deed effects, and landmark effects that don't match the edition's landmarks.
- The template is now a working starter edition, with `questions.csv`, `deeds.csv`, `actions.csv` and a `README.md` column and effect reference.
- Editions can override `SCORE_VALUES` and `FINISH_BONUS` in their `config.js` (B11).
- **Room clean-up** on the server (A5): a game closes when the host clicks *Play again* or cancels the lobby, 5 minutes after it ends, or 30 minutes after the host leaves without coming back. Phones now see whether the host *disconnected* or *ended the game*.
- **Automated tests** (`npm test`, Node's built-in runner; T1–T5): about 200 tests covering the server, the host turn flow end to end, board generation (a randomized test over ~3,000 boards per run), pure turn logic, players, CSV parsing, and every edition's content.

### Changed
- **Undo during a turn** now cancels only that turn, back to before the roll. Previously it also undid the previous turn.
- One turn pipeline (A2): every turn, including skipped turns and exact-finish blocks, now ends in one place that always records history, updates phones, saves and syncs.
- State ownership (A3): the host owns all game state, and the server owns connection state (sockets, rejoin tokens, connected/disconnected) plus the dice. The rules are documented at the top of `server.js`.
- `game.js` (about 2,000 lines) was split into focused files (A4), grouped as `js/shared/`, `js/host/` and `js/player/` by which page loads them. They are still plain scripts, so opening `index.html` from disk keeps working.
- "theme" was renamed to "edition" throughout the code (A1). `CONFIG.THEME` became `CONFIG.COLORS`, and `themeName`/`themeIcon` became `editionName`/`editionIcon`. Edition configs use a `COLORS` block.
- The generated `deeds.js` now has one card per line, like `questions.js`.
- The `/player` URL now works (before, only `/player.html` did).
- README, design document, CLAUDE.md and the template guide were updated to match.

### Removed
- The unused server-side `set_player_active` event. Sitting out is now handled by the host.
- The duplicate copy of the dice renderer in the phone code (A8).

## [2.0.0] — 2026-06

### Added
- Local network multiplayer (V2): Node.js + Express + Socket.IO server; players join on phones with a 4-digit Game ID and roll from their phone; token-based rejoin after refresh or screen-off; GM controls; manual dice for physical-dice play.
- Exact finish rule, no-repeat question tracking, relative landmark deeds, constraint-aware board generation, per-edition space distribution (2026-06-01).
- 3-level question topic filter (category > subcategory > topic); 432 Swab Quest questions (2026-06-01).
- Landmark descriptions and info popup; 20 landmarks per edition (2026-06-03).

### Changed
- "Themes" renamed to "editions": `themes/` → `game_editions/`, `THEME_CONFIG` → `EDITION_CONFIG` (2026-06-01).

## [1.0.0] — 2026-05

### Added
- Single-device game (V1): edition-neutral engine with Swab Quest and Football Quest; board generation, questions, deed cards, action space, landmarks; pan/zoom; save/resume; GM controls, game log and undo.
