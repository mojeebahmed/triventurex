# Changelog

All notable changes to Triventurex. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

IDs in brackets (B1, A2, C3, T1, G6, …) are the work-item IDs used in branch names and commit messages, so `git log --grep=G16` finds the work for an item. B = bug, A = architecture, C = content pipeline, T = tests, G = gameplay.

## [Unreleased]

### Added
- **One icon style everywhere**: emoji are drawn with Microsoft **Fluent Emoji Flat** and buttons / tabs with **Lucide** line icons, bundled with the game (works offline), so the host, phones, TV and Academy look the same on every device. Content keeps writing plain emoji; `npm run build:icons` bundles what is used (`scripts/icons.config.js` for the few overrides).
- **🎓 Triventurex Academy** (`academy.html`, `/academy`; 🎓 Academy in the 📚 Questions tab): learn one edition's questions before playing — 📚 Explore, 🃏 Flashcards, ✏️ Quiz, 🧩 Match, ✔️ True or false, ⚡ Speed round, 🗺️ Places (with *Where am I?*), 🖨️ Print cards and 🔍 Review (reviewer ticks, progress and a copyable report). One filter (topics, difficulty, search) for every mode. Works opened from disk and from the server, on laptops and phones. 🚩 marks are shared with the game. Flashcards come in sets of 8 (4 × 2) or 9 (3 × 3) cards; every mode uses the same white question cards in the edition's colours; print cards are double-sided (answers mirrored on the back page) or fold-over, all the same size.
- **Prophets' Stories** edition 📖 (in review): the stories of the prophets from Hadhrat Adam (as) to the Holy Prophet Muhammad (sa) and the Promised Messiah (as), collecting *Noor*, finishing at Al-Ka'ba. Ahmadiyya understanding; every question cites its source (Qur'an with Bismillah as verse 1, hadith or books). 221 questions in 8 eras (category = era, subcategory = prophet, topic = story / miracles & signs / prayers & lessons), 56 deed cards (*Good Deed* / *Lesson to Learn*), 25 action cards (nobody acts a prophet) and 24 blessed places (photos of places only).
- `scripts/review-sheet.js`: a printable review sheet (REVIEW.md) of an edition's questions, answers and sources.
- **Animal Safari** edition 🦁: an expedition through the world's wild places collecting *Paw Prints*. 220 questions (mammals, birds, reptiles/frogs/bugs, habitats, animal superpowers, a little "under the sea"), 56 deed cards (*Wildlife Hero* / *Safari Mishap*), 25 action cards and 26 reserves with photos from Wikimedia Commons (credits in `game_editions/animal-safari/CREDITS.md`).
- **World Tour** edition 🌍: a trip around the world collecting *Stamps*. 220 questions (capitals, flags & languages, wonders & nature, culture, a little food), 56 deed cards (*Smooth Travels* / *Travel Trouble*), 25 action cards and 26 wonders with photos from Wikimedia Commons (credits in `game_editions/world-tour/CREDITS.md`) on a 1635 world-map board.
- `scripts/commons-image.js`: finds free-licence photos on Wikimedia Commons, crops/resizes them for an edition and records the credit.
- **General action cards** (C4): 40 everyday cards in `game_editions/shared/actions.csv` (act / explain / sound) that are mixed into every edition's deck. ⚙️ Rules → Action cards → *Add general cards* (on by default). An edition without its own `actions.csv` now gets digital action cards too.
- `game_editions/IDEAS.md`: ideas for new editions, the content target per edition, and how an edition is built.

### Fixed
- ⚙️ Rules → Topics: a topic that appears under several categories (World Tour's "Europe", Animal Safari's "Africa") could not be switched off in one branch only. The selection is now kept per full path (category › subcategory › topic); saved selections carry over.
- Deed tiles on the board showed a raw `{landmark}` placeholder; the tile and the card now both show the landmark (or "a wonder" / "a stadium" / … when this game's effect isn't a landmark move).

### Changed
- **Phones look like the edition**: the host sends the edition's icons and tile names with the game state, so a phone shows ⚽ *Good Play* in Football Quest instead of the engine's ✅ *Good Deed*.
- **Same badge picker on phones**: phones offer the same 72 badges and 36 colours as the host's picker (was 16 badges, 12 colours).
- **Edition icons in one place**: each edition sets the icons it changes in an `ICONS` block in its `config.js` (edition → engine lookup), instead of `icon` fields scattered over `SPACE_INFO` and `AWARDS`. Values can be an emoji, any installed Iconify set's icon, or the edition's own picture (`file:icons/x.svg`). `check:content` validates the block. All five editions moved over; nothing looks different.
- **Icons by name**: the engine's ~450 hard-coded emoji and symbols are now named icons in `js/shared/icon-registry.js`, used through `icon()` / `iconText()` / `data-icon`. A test keeps raw icons out of engine code and checks every name exists. No visible change. Badge lists live in the registry (the phone and host no longer keep separate copies).
- Marked questions moved from js/host/storage.js to js/shared/marks.js (shared with the Academy).
- Landing on a landmark now gives **3** points by default (was 5): easy 1 · hard 2 · landmark 3. Applies to every edition; games saved earlier keep their rules.
- New editions start from Swab Quest's board mix (the template's `SPACE_DISTRIBUTION`: 10% action / good / bad deeds, 8% landmarks, 5% skips; long boards 12% action). World Tour uses it too.
- `test/board.test.js` now tests every edition in `game_editions/editions.js` instead of a fixed list.
- ⚙️ Rules tab: the header is a one-line action bar (preset, "✎ N changed", ↺ Reset, 📋 Copy) like the Questions and Boards tabs. The "Rules for …" line is gone (the edition is in the setup header) and the preset's description is its tooltip.

## [2.2.0] — 2026-10-17

A gameplay and play-experience release. The setup screen is rebuilt around tabs, every rule can be changed per game, phones do more (scan to join, answer questions), people without a phone can play, and the game can be shown on a TV. About 310 automated tests. Saved games, phone sessions and settings from 2.1 keep working.

### Added

**Setup screen**
- New setup screen with tabs: **🎲 New game**, **⚙️ Rules**, **📚 Questions**, **✏️ Boards** (G6). *New game* is a step-by-step flow (① Edition → ② Game length → ③ Board → ④ Players): one step open at a time, collapsed steps show the current choice, and a footer always shows the whole setup next to **Start**. The card has a fixed height; only the tab content scrolls. *On this screen* / *On phones* moved into ④ Players, and players are shown as chips.
- The setup remembers your last choices and opens fully collapsed, so a repeat game is usually just **Start** (G7).
- **Board picker** with a thumbnail of every board path for the chosen length, plus 🎲 Random (G8).
- **⚙️ Rules** per game (G12), remembered per edition and kept with a saved game. *Family*, *Kids* and *Quiz night* presets; "N changed" summary; **↺ Reset to preset**; **📋 Copy as preset** turns the current rules into a `RULE_PRESETS` entry. Settings:
  - Scoring: question points, action points, finish bonus (Standard 10/7/5… · Small 5/3/2/1 · Off), landmark points for landing by a roll / arriving via a good deed / via a bad deed (each can be positive, negative or 0), negative scores on/off
  - Questions: difficulty (player chooses · always easy · always hard), timer auto-start and seconds, avoid repeats, players answer on their phone, topics
  - Action cards: digital or physical (a digital card can always be swapped for a physical one in play), allowed kinds, timer
  - Board: tile mix in % per tile type (0 removes it; presets Balanced / More questions / More action / Questions only; live tile counts; special tiles capped at 70%), deed effects varied or first, no going backwards
  - Turn & pace: exact finish, who starts, animation speed
- **📚 Questions** tab (G19): browse every question by category › subcategory › topic with counts, search, filter by difficulty, show answers, and mark a question as wrong / unclear with a note. **📋 Copy marked list** gives a text list to fix `questions.csv`.
- **✏️ Boards** tab (G20): draw your own board path on a grid (click a start, then cells in a straight line), see a thumbnail and the space count, save it to *My boards* (it appears in the board picker, marked ✏️), play it straight away, or **📋 Copy as template** for `CONFIG.PATH_TEMPLATES`.

**Playing**
- **🔁 Rematch** on the end screen: same players and rules, new board; in a network game the phones stay in the room (G7).
- **End-screen stats and awards** (G13): questions right, actions guessed, average roll and spaces travelled per player, and fun awards (Quiz master, Star performer, Do-gooder, Trouble magnet, Explorer, Big moment, Lucky roller, Unluckiest roller, Patience award). Ties share an award. Editions can rename awards (`AWARDS`); Football Quest has its own names.
- **🚩 Report this question** on the host's question card, with a note — goes into the same list as the 📚 Questions tab (G14).
- **📺 Presentation mode** for a TV mirrored from the laptop (G15): 📺 button or **P**, full screen, the board fills the screen, bigger sidebar and cards, GM tools behind a small ⚙️, the pointer hides when idle. Works offline. Settings in `CONFIG.PRESENTATION`.
- Arriving at a landmark via a deed shows a toast with the points the rules give for it (G12).

**Phones and network games**
- **Join by QR code** (G11): the lobby shows a QR code, the join address and the Game ID; scanning fills in the Game ID. *GM controls → 📱 Show join code* for latecomers.
- **Answer questions on the phone** (G3): the player taps Easy / Hard and then A / B / C; the host scores multiple choice automatically and both screens show the right answer. Open questions are shown on the phone and judged by the GM. The answer never reaches the phone before it's answered, and the GM can still judge on the host. Rule: *Players answer on their phone* (on).
- Phones roll with the same animation as the host; other phones see a small rolling die (G10).
- *"You're next — get ready!"* on the next player's phone, and a buzz when your turn starts (G18).
- **← Leave** in the phone lobby, to change name or badge and join again (G21).
- **Players without a phone** (G17): add them by name in the lobby or in GM controls; they play on the host screen. A network game can run with no phones at all.
- **Badges**: the host can change any player's badge (including their own) in the lobby, and the GM during a game (*GM controls → 🎨*); phones pick up the change and remember it (G17).
- **📺 TV display** (G16): a read-only second screen at `/display?game=ID` (*📺 Open TV display* in the lobby or GM controls). It shows the lobby QR code and players, then the board with hopping tokens, the current player, dice, timer, scoreboard, the open card and the final scores with awards. A TV that opens late or refreshes catches up at once.

### Changed
- The board is drawn only as big as its path, so fit-to-screen centres it (G9); fit-to-screen also leaves room for the legend.
- Landmark points are given automatically by the rules; the award button on the landmark card is gone (G12).
- History entries record where the roll landed and how a question / action went, so end-screen stats stay right after a deed moves the player (G13).
- `board.js` and `viewport.js` moved to `js/shared/`, and the edition config merge + colours to `js/shared/edition.js`, so the TV page can use them (G16).
- New pure, tested modules: `js/shared/rules.js`, `stats.js`, `questions.js`, `path-design.js`.
- Undo keeps badge changes and who has no phone (they aren't game moves).
- The host scoreboard shows ⚠️ next to a player whose phone is disconnected (before, only the GM panel did).
- The improvement plan used for 2.1 and 2.2 is finished and removed; open ideas are in the README roadmap.

### Fixed
- The board legend showed on the end screen, and covered the start space (and its tokens) on most boards.
- The board area could be scrolled by the browser, e.g. when a text box in a card got focus.

### Security
- A phone could take over the host's own player by rejoining without a token. Rejoining now needs the seat's real token, so seats without one (the host's player, players without a phone) can't be taken.
- A phone's answer (`card_choice`) reaches only the host, with the player id taken from the connection, never from the message; the host accepts only the question it asked that player.
- TV display messages are accepted only from the host and never sent to phones. Card content is stripped of anything secret (unrevealed answers, action cards, GM-only notes) before it leaves the host.

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
