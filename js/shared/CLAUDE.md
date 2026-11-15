# js/shared — engine code used by several pages

Notes for Claude, loaded automatically when working in this folder. The project-wide rules are in the
root `CLAUDE.md`. Keep invariants for this area here; update them when one changes.

## Files
- `js/shared/utils.js` — shared helpers for host + player pages (`esc()` HTML escaping); loaded first
- `js/shared/icon-registry.js` — every icon the engine uses, by name (`ICONS`), plus `ICON_OVERRIDES` (engine icon swaps that keep the original) and the badge pickers' lists (`BADGES`, `BADGE_COLORS` — host and phones show the same); loaded before config.js on every page
- `js/shared/icons.js` + generated `js/shared/icons-data.js` — `icon(name)` / `iconText(name)`, `data-icon` placeholders, and the content-emoji swap (`startIcons()` at each page's start)
- `js/shared/config.js` — engine settings (board, space types, zoom, animation, score, rule presets, awards, presentation)
- `js/shared/rules.js` — per-game rules model (defaults → preset → changes), tile counts; pure, unit-tested
- `js/shared/players.js` — player model: `createPlayer`, `movePlayer`, `addScore`, `getSortedPlayers`
- `js/shared/turn.js` — pure turn logic (next player, snapshots, undo restore, history rows); unit-tested
- `js/shared/csv.js` — pure CSV parsing for questions/deeds; unit-tested
- `js/shared/dice.js` — `renderDie(n, sizeClass)` + `animateDieInto` — CSS dot-die and roll animation (host, phones, TV)
- `js/shared/socket-client.js` — `TX_NET` singleton; safe no-ops when offline
- `js/shared/board.js` — board generation (`generateBoard`) and rendering (`renderBoard`, `updateBoardTokens`) — host + TV display
- `js/shared/viewport.js` — pan / zoom / fit and the board background — host + TV display
- `js/shared/edition.js` — `mergeEditionConfig`, `applyEditionColors` — host + TV display
- `js/shared/stats.js` — end-screen stats + awards from the history (G13)
- `js/shared/questions.js` — question tree / filter / marked-questions report (G14 + G19), topic keys
- `js/shared/help.js` — the in-game help: all help text (`HELP` topics), `openHelp(topic)`, `startHelp(topicFn)` (? key, Esc, first-visit glow); shared by host, phone and Academy (+ `css/help.css`)
- `js/shared/marks.js` — 🚩 marked questions + reviewed ticks (localStorage), shared by the host page and the Academy
- `js/shared/academy.js` — Academy rounds (true/false, match pairs, places quiz, flashcard sets via `chunk`, double-sided `printSheets` with mirrored backs, `textSize` for fixed-size cards, review stats); pure, unit-tested
- `js/shared/path-design.js` — drawing board paths: cells, runs, checks, template export (G20)
- `js/shared/text-size.js` — A− / A+ text size for the cards (`--text-scale`, `startTextSize(page)`, `textSizeControlHtml()`); steps in `CONFIG.TEXT_SIZE`

## Architecture — V1 (don't revert)
- **Board generation**: `generateBoard()` in board.js — pre-picks deed effects → constraint-aware deed-to-slot assignment (`_assignDeedsToSlots`) → no consecutive same-type → resolved landmark names stored on each deed
- **SPACE_DISTRIBUTION**: defined in `js/shared/config.js` as engine default. Editions override via `SPACE_DISTRIBUTION` in their `config.js` — can be flat (all lengths) or keyed by `short`/`medium`/`long`. Questions always fill whatever space remains; no `question` key is needed in the distribution object.
- **Constraint-aware placement** (`_assignDeedsToSlots`):
  - `move_back N` → slot index ≥ N (not near start)
  - `move_forward N` → slot index ≤ poolLen-1-N (not near finish)
  - `move_to_prev_landmark N` → N landmarks exist before the slot
  - `move_to_next_landmark N` → N landmarks exist after the slot
  - Fallback: try alternative effect from card's effects array; then swap in an unused card from the deck that fits (`_replacementFromSpares`); least-bad slot only if nothing in the deck fits
  - All of this is checked by a randomized test (`test/board.test.js`, ~3,000 boards per run) — keep it green when touching board.js
- **Landmark deeds**: `move_to_prev_landmark` / `move_to_next_landmark` with `value=N` (N = 1 → nearest). Names resolved at board-gen time and stored as `resolvedLandmark` on each deed. `{landmark}` in deed text is filled by `fillLandmarkText()` (board.js) on the tile AND in the modal — never show raw text (the board property test checks it).
- **Variable deed effects**: each card has up to 3 effects in CSV; one chosen at board-gen time via `_pickActiveEffect()`
- **Space GPU layers**: `transform: translateZ(0)` on each space → crisp at any zoom level
- **fitBoardInView()** is SYNCHRONOUS (no rAF) — no board-jump bug
- **Board drawn to the path's bounding box** (`pathBounds` in board.js), not the template's full grid — so fit-to-view centres on the path. `_gridRows/_gridCols` are still saved for old saves but not used for drawing
- **#board-world** pinned to grid dimensions — no background-loading shift
- **Pure turn logic** lives in `js/shared/turn.js` (`nextTurnIndex`, `takeSnapshot`, `restoreFromSnapshot`, `indexAfterRemoval`, `makeHistoryEntry`) — no DOM; unit-tested in `test/turn.test.js`

## Architecture — V2 (don't revert)
- **Board under rules**: `generateBoard(len, template, { tileMix, deeds })`; counting is `tileCounts()` in rules.js — the panel preview uses the same function
- **End-screen stats + awards (G13)**: `js/shared/stats.js` (pure) — `gameStats(history, players)` and `gameAwards(stats, CONFIG.AWARDS)` from `state.history`. Each history entry carries `landedOn` (the space the ROLL landed on — `spaceType` is where the turn ended after deed moves) and `result` (`{ question }` set by `_noteQuestion` in ui.js, `{ action }` set in `_resolveSpace`). GM entries are ignored. Award titles/texts in `CONFIG.AWARDS` ({n}, {s}, {good}/{bad}/{landmark}, {points}); editions rename them via `AWARDS` in their config.js. Host end screen: `showEndScreen` → `endOfGameSummary` / `statLine` / `awardsHtml`; TV gets `display` kind `end` (`_displayEnd`)
- **CSS dice**: `renderDie(n, sizeClass)` + `animateDieInto(el, result)` in `js/shared/dice.js` — dot-based, no images; host and phones use the same rolling animation (phones: roller big in the action box, others in a strip above the activity feed; feed entry added after the animation)
- **Turn order**: `nextTurnIndex()` (turn.js) skips finished and sitting-out players (falls back to any unfinished player so the game never stalls)

## Effect types and related notes
- **In-game help**: one ? button per screen (host setup card, lobby card, board zoom + presentation controls; phone: floating bottom-right; Academy header) and the ? key. Each `## ` part of a topic is drawn as its own box (`.help-section`); following a *More help* link adds a Back button (and Backspace) to the page you came from. All text is in `HELP` in js/shared/help.js — one topic per setup tab, lobby, game (+ cards, game log, GM controls), phone view and Academy mode, plus a shared *How to play*; `more` links related topics. Text uses a small markup (`##`, `- `, `**bold**`), `{icon:name}` (registry names — no raw emoji) and the edition's words `{points} {finish} {question} {action} {good} {bad} {landmark} {skip} {edition}` (`helpWords(CONFIG)`; the phone passes words from the host's `edition` block). **When you add or change a screen, tab, mode or control, update its help topic**; test/help.test.js checks that every setup tab and Academy mode has a topic and every icon / word / link exists
- **What we learned today**: `learnedToday(history, questions)` in js/shared/stats.js — up to 3 questions asked this game (right answers first, then ones with a note) + the topics played; `learnedHtml` (ui.js) on the end screen, sent drawn to the TV with the `end` display kind
- **Text size (A− / A+)**: `js/shared/text-size.js` sets `--text-scale` on `<html>`; ONLY card containers use it, with CSS `zoom` (the whole card grows and keeps its shape): game `#modal` (styles.css; × `--present-scale` while presenting) and the Academy's card containers (academy.css) — never the board, sidebar, tabs, filter or printed cards (test/text-size.test.js checks which selectors zoom). Controls = any `[data-text-size]` with `[data-text-step="-1|1"]` buttons (one document click handler): game zoom bar + the open card's corner (`.modal-text-size`, outside `#modal-content`, so never sent to the TV — the open card covers the zoom bar); Academy top bar + More on phones. Saved per page and device: `triventurex_text_size_game` / `_academy` (a preference, not a rule — not saved with the game). Under `zoom`, % sizes resolve against the parent (a card still fits the board area) while px / vh scale — divide vh by the scale. A new card container that should grow → add it to the zoom rule; grids inside should drop columns (`auto-fill, minmax(max(<min>px, …))`) rather than squeeze
- **Icons** (developer guide):
  - **Engine code never types an emoji or icon symbol.** It asks for a NAME from `js/shared/icon-registry.js`: `icon('undo')` → HTML (Lucide line icon in the text colour, or a Fluent Emoji Flat image); `iconText('tileSkip')` → plain text for places that can't hold HTML (`<option>`, tile labels, phone/TV text, toasts' text) — line icons give ''. In HTML pages: `<i data-icon="undo"></i>`; for an `<option>`: `data-icon-text="easy"`. `showModal` buttons take `icon` / `iconAfter` names; `showToast(text, ms, iconName)`.
  - **Choose**: a Lucide line icon (`lucide:<name>`) for controls (buttons, tabs, links); an emoji (`emoji:<emoji>`) for game symbols (tiles, cards, awards, status). Name by purpose (`tvDisplay`, `awardQuizMaster`), not by look.
  - **Add an icon**: add a name + comment to the registry, use it, run `npm run build:icons` (bundles the Lucide SVG into `icons-data.js` / the emoji image into `images/emoji/`). `npm test` fails on raw emoji/icon symbols in engine code (comments are fine), on unknown names, and on out-of-date bundles.
  - **Editions** override names in ONE `ICONS` block in their config.js (`tileGoodDeed: '⚽'`, `awardExplorer: '🏟️'`) — lookup is edition → engine (`CONFIG.EDITION_ICONS`, set by `mergeEditionConfig(config, T, editionId)` in js/shared/edition.js; pass the edition id). Values: an emoji, `'<set>:<icon>'`, or `'file:icons/x.svg'` (a picture in the edition folder → `url:game_editions/<id>/…`; `iconText()` gives '' for it). Only names the engine uses are allowed — `check:content` reports unknown names, bad values, missing pictures, and warns about old-style `SPACE_INFO.*.icon` / `AWARDS.*.icon`. `build:icons` bundles line icons from the registry AND editions' ICONS (keyed by id, `lucide:undo-2`). The phone page has no edition loaded — the host sends the edition's icons with the state (see *Edition on phones*).
  - **Config fields** (`SPACE_INFO.*.icon`, `AWARDS.*.icon`, `ACTION_KINDS.*.icon`, `GAME.editionIcon`) hold a NAME or an emoji — render them with `icon()` / `iconText()`, never as raw text. Player badges are emoji data (`BADGES` + `BADGE_COLORS` in the registry, used by both the host's and the phone's picker); keep a badge in a `data-token` attribute, never read it back from `textContent` (the page shows it as an image).
  - **Overrides keep the original**: `ICONS` holds the original icon of every name; a different choice for the engine goes in `ICON_OVERRIDES` (same file, normally empty or a few lines). Lookup is edition `ICONS` block → `ICON_OVERRIDES` → `ICONS`. Back to the original = remove the override line; keep it for good = change `ICONS` and remove the line. Tests: an override must name an existing icon and differ from the original
  - **Trying other icons**: `tools/icon-picker.html` (open via the server: `/tools/icon-picker.html`) lists every name with its purpose (parsed from the registry's comments) and current icon, for the engine or one edition; overridden names show their original, with *Back to the original* / *Make it the original*. Search Lucide / Phosphor / Tabler or Fluent emoji, or draw an emoji from Twemoji / Noto / OpenMoji (needs the internet — Iconify API + jsDelivr). It changes no file: it produces the lines to apply — `ICON_OVERRIDES` add / remove, originals to change in `ICONS`, an edition's ICONS block, `scripts/icons.config.js` emoji-set overrides (+ any `npm i -D @iconify-json/<set>` needed); then `npm run build:icons`. Keep overrides few
  - **Content** (questions, deeds, edition labels) keeps plain emoji; `startIcons()` swaps them for the bundled images in the page (one MutationObserver). Opt out: `.no-icons`. The emoji SET is in `scripts/icons.config.js` (with the rare per-emoji override).
