# Triventurex — Improvement Plan

_Created: 2026-10-16 · Source: code review of V1 + V2 (commit 214b538)_

Work top to bottom. Each item has an ID; reference it in branch names and commit messages (e.g. `fix/B1-phone-roll-turn-setup`).
Tick the box when merged to `main`. Line numbers refer to commit 214b538 and will drift.

**Phases**
1. Bugs (B) — correctness first
2. Architecture (A) — structure, after bugs are fixed and the behaviour is known-good
3. Content pipeline (C)
4. Tests (T)
5. Gameplay (G) — last; to be expanded with Mojeeb's own ideas

---

## Phase 1 — Bugs

### 1a. Turn flow (network) — highest priority

- [x] **B1 — Phone-initiated rolls skip turn setup**
  - **Where:** `js/host/game.js` `TX_NET.on('roll_result')` (~L1033), `handleRoll()` (~L1273), `handleManualRoll()` (~L1235)
  - **Problem:** Only host-initiated rolls take `_preRollSnapshot`, set `turnPhase='resolving'`, bump `_turnToken`. Phone rolls go straight to `_processRoll()`. Undo then restores a stale snapshot; host Roll button stays enabled mid-turn; resume-reopen-modal never fires.
  - **Fix:** Extract `_beginTurn()` (snapshot + token + `turnPhase='resolving'` + disable roll/manual dice). Call it from `handleRoll`, `handleManualRoll`, and from `roll_result` when the roll was not host-initiated (i.e. when `!_awaitingRoll`).
  - **Verify:** Phone rolls → host Roll button disabled during turn → Undo restores the state from before *that* roll.

- [x] **B2 — Server accepts rolls at any time**
  - **Where:** `server.js` `roll` handler (~L191)
  - **Problem:** No `room.turnPhase` check; a second roll request would start a second concurrent turn.
  - **Fix:** Reject if `room.turnPhase !== 'roll'`; set `room.turnPhase = 'resolving'` when a roll is generated (host's next `sync_state` returns it to `'roll'`). Also guard on the host: ignore `roll_result` while `state.turnPhase === 'resolving'` and not `_awaitingRoll`.
  - **Depends on:** B1 (host must sync `'resolving'`/`'roll'` reliably).

- [x] **B3 — Exact-finish block never syncs to phones**
  - **Where:** `js/host/game.js` `_processRoll()` blocked branch (~L1366)
  - **Problem:** No `_syncStateToServer()` → next phone player can't roll. Also `saveGame()` runs before `endTurn()` (violates the "save after endTurn" invariant).
  - **Fix:** Route through the same end-of-turn path as `afterSpaceResolved` (see A2); minimal fix = `endTurn(); saveGame(); _syncStateToServer();`.

- [x] **B4 — Extra turn leaves phones stuck (likely)**
  - **Where:** `js/host/game.js` `afterSpaceResolved()` extra-turn branch (~L1460)
  - **Problem:** Returns without `saveGame()` / `_syncStateToServer()`; manual dice stay disabled (only `roll-btn` re-enabled).
  - **Fix:** Call `refreshUI()`, `saveGame()`, `_syncStateToServer()` before returning.
  - **Verify:** Land on an `extra_turn` deed from a phone → phone returns to dice mode.

- [x] **B15 — Host refresh mid-turn leaves the turn stuck** _(found while fixing B1)_
  - **Where:** `js/host/game.js` `saveGame()`, `_restoreGame()`, `host_rejoined` handler
  - **Problem:** `_pendingHistory` was null after restore, so `afterSpaceResolved()` bailed and the turn never ended; undo snapshot lost; finish-space modal not reopened. Also `host_rejoin` was only sent on socket `connect`, which has usually already fired before Resume is clicked.
  - **Fix:** Save a serialisable `pendingTurn` (roll, posBefore, scoreBefore, snapshot); restore it via `_beginTurn()`; rejoin immediately if already connected; host syncs state after `host_rejoined`.

- [x] **B16 — Phone roll ignored "skip next turn"** _(found while fixing B1)_
  - **Fix:** `roll_result` from a phone routes to `_handleSkippedTurn()`. The skip snapshot is now taken before the flag is cleared, so undo re-arms the skip.

- [x] **B17 — Phones never told the game ended**
  - **Where:** `state.phase` never became `'ended'`.
  - **Fix:** `_endGame()` sets `phase='ended'` and syncs; used by `afterSpaceResolved()` and `endTurn()`.

- [x] **B5 — Removing a player can skip a turn**
  - **Where:** `server.js` `remove_player` / `leave_game`; `js/host/game.js` `player_removed` handler (~L1046)
  - **Problem:** If the removed player's index < `currentPlayerIndex`, the index isn't decremented.
  - **Fix:** `if (idx < currentPlayerIndex) currentPlayerIndex--; else if (currentPlayerIndex >= length) currentPlayerIndex = 0;` in both places (or only on host once A3 makes the server a relay).

- [x] **B6 — `host_left` never fires when host is also a player**
  - **Where:** `server.js` `disconnect` (~L374)
  - **Fix:** Check `room.hostSocketId === socket.id` before the player match / `break`.

- [x] **B7 — GM score/move changes not synced or undoable**
  - **Where:** `js/host/game.js` `gmAdjustScore`, `gmMovePlayer`, `gmSkipTurn` (~L1497)
  - **Fix:** Call `_syncStateToServer()` after each. Decide whether GM actions go into history (recommended: yes, as a `gm` entry with snapshot, so they're undoable and visible in the log).

- [x] **B8 — Active/inactive player feature not wired**
  - **Where:** `TX_NET.setPlayerActive` exists, no UI calls it; `endTurn()` ignores `inactive`
  - **Fix:** Add toggle button in `_renderGMNetworkPlayers`; make `endTurn()` skip `inactive` (and maybe `disconnected`) players. Or remove the feature and the CLAUDE.md claim — decide first.

### 1b. Question tracking

- [x] **B9 — Asked-question keys shared across editions**
  - **Where:** `js/host/ui.js` `_askedKey()` (~L206)
  - **Problem:** `window._activeThemeId` is always undefined (`let` doesn't attach to `window`) → all editions write `triventurex_asked_default_*`.
  - **Fix:** Expose the active edition id properly (e.g. `window.getActiveEditionId()` or pass it in). Optionally clear the old `triventurex_asked_default_*` keys once.

- [x] **B10 — Question IDs are row positions**
  - **Where:** `js/host/game.js` `_parseQuestionsCSV()` (~L1832)
  - **Problem:** Inserting/deleting a CSV row reshuffles IDs and corrupts asked-tracking.
  - **Fix:** Add an `id` column to `questions.csv` (both editions + template); parser uses it, falls back to row index only if missing. Pairs well with C2 (validator checks uniqueness).

- [x] **B18 — 10 Football Quest questions broken by unquoted commas** _(found while fixing B10)_
  - **Problem:** ids 35, 40, 54, 57, 62, 66, 70, 73, 82, 86 had commas in question/answer text without CSV quotes → columns shifted, no valid difficulty, so they were never asked (and showed garbage if they had been).
  - **Fix:** Re-quoted the fields (wording unchanged), filled the lost category/difficulty, regenerated `questions.js`. Swab Quest and both deed files checked clean.
  - **Follow-up for content owner:** truncated notes and suspected factual errors listed in the batch-3 hand-off; C2 validator should catch this class of error automatically.

### 1c. Engine/edition leaks & finish logic

- [x] **B11 — Edition text and score values hardcoded in engine**
  - **Where:** `js/host/ui.js` landmark modal (~L131: "Holy Site", literal `5`), action modal (~L104 "+1"), question choice (~L271 "+1"), guesser modal (~L593 "+1"); stale comment in `js/shared/config.js` `SCORE_VALUES`
  - **Fix:** Use `CONFIG.SCORE_VALUES.*` everywhere; move landmark fallback title to `CONFIG.GAME` (edition-overridable).

- [x] **B12 — Finishing via deed/GM move gives no bonus or finish order**
  - **Where:** bonus only awarded in `_processRoll()` (~L1389)
  - **Fix:** Move finish-order/bonus into a single `_checkFinish(player)` called after any movement (roll, deed, GM).
  - **Done as:** `_recordFinish(player)`; deed/GM finishes show a toast; a GM move that finishes the last player ends the game. B11 also: landmark/action modal icons from `SPACE_INFO`, editions can override `SCORE_VALUES` / `FINISH_BONUS`, removed "ptss" pluralisation.

### 1d. Security (LAN-scale)

- [x] **B13 — Player names rendered via `innerHTML`**
  - **Where:** `js/host/ui.js` scoreboard/end screen, `js/host/game.js` lobby + GM list, `js/player/player.js` other-players list
  - **Fix:** Add `esc()` helper; escape names everywhere they're interpolated. Server: trim/limit name length.

- [x] **B14 — Whole project folder served statically**
  - **Where:** `server.js` `express.static(__dirname)`
  - **Fix:** Short term: serve only an allowlist (`index.html`, `player.html`, `css/`, `js/`, `game_editions/`, `images/`). Long term: `public/` folder (A6).

---

## Phase 2 — Architecture

- [x] **A1 — Finish the theme → edition rename in code** (`loadTheme`, `_activeThemeId`, `themeId`, `CONFIG.THEME`, `onThemePicked`, server `themeId`). Mechanical; do first so later refactors use final names.
- [x] **A2 — Single turn pipeline.** `beginTurn() → move → resolveSpace() → finishTurn()`, where `finishTurn` *always* does history → finish check → extra-turn/endTurn → save → sync. Replaces scattered `_pendingHistory` / `_awaitingRoll` / early returns. Absorbs B1, B3, B4, B12.
- [x] **A3 — Decide state ownership.** _Done as: host owns game state, server owns connection state (rules at top of server.js); server-only fields stripped from all emits (rejoin tokens were broadcast to every phone); `disconnected` no longer overwritten by host syncs (⚠️ never cleared after reconnect); late joiners survive older host syncs; host-only relays; playing host's player entry reconnects on host_rejoin; remove_player sends no server-computed state._ Original: Recommended: host is sole authority; server is a relay + roll generator + room registry. Server forwards GM actions (`remove_player`, `set_player_active`) to the host instead of mutating `room.players` itself. Also: host-only checks on `turn_result` / `space_card` relays.
- [x] **A4 — Split `game.js` (~2000 lines)** _Done as: 10 plain-script files (no ES modules — file:// must keep working); verbatim move verified line-for-line; one badge picker (also fixes host preview never updating); `_enterGameScreen` / `_startNewGame` replace 3 copies; tests: turn-flow (18), csv + edition content._ Original: into `setup.js`, `badge-picker.js` (dedupe host + local), `net-host.js`, `viewport.js` (pan/zoom/background), `content-loader.js` (CSV + edition loading), `turn.js`. Consider native ES modules (`<script type="module">`, no build step).
- [x] **A5 — Room lifecycle on server.** Delete rooms on game end, and after host absent > N minutes. _Done as: close_room (host Play again / lobby Cancel) closes immediately; 5 min after game end; 30 min after host disconnect (cancelled by host_rejoin, which now sends host_back so phones drop the "host left" overlay); ROOM_TTL in server.js._
- [x] **A6 — `public/` folder** for client files (completes B14). _Closed without change (2026-10-17): the B14 static-file allowlist already keeps server/docs/tests private; moving all client files was churn for no gain._
- [x] **A7 — `TX_NET.on` supports multiple handlers** per event. _Closed without change (2026-10-17): nothing needs multiple handlers per event today; revisit if a feature does._
- [x] **A8 — Remove duplicate `renderDie`** inline copy in `player.html` (load `js/shared/dice.js` instead). _Copy was actually in js/player/player.js (identical); removed, player.html loads dice.js._

## Phase 3 — Content pipeline

- [x] **C1 — Replace "ask Claude to regenerate JS"** _Done as: `npm run build:content [edition]` (scripts/build-content.js) using the game's own parser; generated JS kept (needed for file://)._ with `npm run build:content` (Node script), or drop generated `questions.js`/`deeds.js` entirely if file:// support is no longer needed.
- [x] **C2 — Content validator** _Done as: `npm run check:content` + in `npm test` (scripts/content.js) with file:line messages; template CSVs fixed (old deeds format with `sawab_add`) and documented in template/README.md._ `npm run validate`: multi-choice answer 1–4 and option non-empty; known effect names; numeric values; unique question IDs; topics non-empty; landmark count vs. `move_to_*_landmark N` values.
- [x] **C3 — Digital action cards** _Done as: actions.csv per edition (act / explain / sound), drawn without repeats, sent only to the performer's phone (private_card) or hidden behind a show/hide toggle on the host; draft cards for Swab Quest (26) and Football Quest (25) to review._ using `game_editions/template/action-cards-template.csv`; show privately on performer's phone.

## Phase 4 — Tests

- [x] **T1 — `node:test` setup.** `npm test` runs `test/**/*.test.js`. `server.js` exports `{ server, io, rooms }` and only listens when run directly. Client-side unit tests still need pure functions loadable in Node (after A2 / A4).
- [x] **T2 — Unit tests:** _Done as: test/players.test.js (createPlayer, movePlayer, movePlayerToPosition, addScore, getSortedPlayers) + _resolveRelativeLandmark in test/board.test.js; CSV parsers already in csv.test.js._ CSV parsers, `movePlayer`, `getSortedPlayers`, `_resolveRelativeLandmark`.
- [x] **T3 — Property test for `generateBoard`:** _Done as: test/board.test.js. It found a real bug: on short Swab Quest boards (~1 in 600) a deed could break its placement rule (move_forward reaching the finish, "next landmark" with none ahead) via the least-bad fallback. Fixed by swapping in an unused card that fits; 0 violations in 32,000 boards._ 1000 random boards per length/path → constraints hold (no `move_back N` before N, no `move_forward` past finish, landmark deeds resolvable, no consecutive same deed type).
- [x] **T4 — Server tests** `test/server.test.js` (24 tests): hosting/joining, roll guard + manual roll (B2), sync_state field preservation, remove/leave turn index (B5), rejoin + host rejoin, disconnects + host_left (B6). Verified: 5 fail against the pre-fix server.
- [x] **T5 — Host turn-logic tests** for `_nextTurnIndex`, undo-by-id merge, removal handling — write these during A2/A4 once the logic is separated from the DOM.

## Phase 5 — Gameplay

_Brainstormed 2026-10-17 with Mojeeb. Order: 5a → 5b → 5c. Every setting has a default in code (engine or edition); the rules panel only changes it for one game._

**Decided against**
- ~~G1 — Endgame pacing~~ — not needed: the GM can move a player or set the dice manually when an endgame drags.
- ~~G5 — Streaks, wagers, final round, sound effects~~ — dropped. Sound effects moved to *Future ideas* below.
- G2 (finish bonus) and G4 (landmark points) are now settings inside **G12**.

### 5a. Quick fixes
- [x] **G9 — Fit the board to the path, not the whole grid.** _Done as: the grid is drawn only as big as the path's bounding box (`pathBounds`); short paths used as little as 29% of the old grid._ Zoom-to-fit measures the full 12×12/13×13 grid incl. empty cells, so paths that use part of it (e.g. short path A: rows 3–11, cols 1–5) sit off to one side. Fit/centre on the bounding box of the path (or drop empty rows/columns when rendering).
- [x] **G10 — Dice animation on phones.** _Done as: shared `animateDieInto` (dice.js) used by host + phones; roller: tumbling die in the action box + vibration; others: small rolling strip above the feed._ Today the roller's phone shows one random static face, then the result; other phones only get a feed line. Show a short rolling animation on all phones, timed with the host's dice overlay (roller big, others small); vibrate on the result.

### 5b. Setup screen & rules
- [x] **G6 — Setup screen redesign.** _Done as: two tabs (New game / Rules); New game = accordion wizard — one step open, collapsed headings show the choice, choosing opens the next step; sticky footer with the whole setup + Start; mode toggle inside ④ Players; player chips; Rules tab with side tabs, changes saved immediately; 880px card; Join Info tab removed._ Numbered steps in play order: 1 Edition → 2 Length → 3 Board → 4 Players (board moves out of the settings). A **rules summary line** always visible ("Exact finish · Landmark +5 · Finish 10/7/5…", with an "N changed" badge) opens the rules panel (G12). Resume bar slimmer; the "Join Info" tab removed (its job moves to G11).
- [x] **G7 — Quick replay.** _Done as: setup returns pre-filled and fully collapsed (usually just Start); 🔁 Rematch on the end screen (network: same room, phones stay)._ "▶ Same as last time" on the setup screen (edition, length, board choice, players, rules → start straight away) and **Rematch** on the end screen (same setup, new board). Today "Play again" resets to Medium.
- [x] **G8 — Visual board picker.** _Done as: js/host/board-picker.js — SVG thumbnails from PATH_TEMPLATES (start green, finish gold), 🎲 Random first, length change resets to Random._ Thumbnails drawn from each `PATH_TEMPLATES` entry (boxy, like the path designer — no image files, new paths get one automatically); only the chosen length's paths, 🎲 Random first.
- [x] **G12 — Rules panel** _Done as: js/shared/rules.js (model) + js/host/rules-panel.js (panel, gameRules()); rules saved with the game (a resumed game used to lose its rules); presets in CONFIG.RULE_PRESETS + Copy-as-preset; landmark deed arrivals shown as a toast with points._ (all optional; defaults = today's behaviour). Remembered per edition. Presets set several at once: *Family* (default), *Kids*, *Quiz night*.
  - **Scoring**
    - Question points easy/hard: 1/2 (default), 1/3, 2/4
    - Action points performer/guesser
    - **Finish bonus (was G2):** Standard 10/7/5/4/3/2/1/1 · Small 5/3/2/1 · Off
    - **Landmark points (was G4)** — three values, each can be positive, negative or 0 (0 = just information). The award button on the landmark card is removed.
      - landing on it by a roll (default +5)
      - arriving via a **good** deed (moved forward to it)
      - arriving via a **bad** deed (sent back to it)
      - (deed arrivals today never trigger the landmark at all)
    - Allow negative scores (today scores stop at 0)
  - **Questions**
    - Difficulty: player chooses (default) · always easy · always hard
    - Question timer: manual (default) or auto-start, with seconds (default 30)
    - Question tracking, topic filter (existing)
  - **Action cards**
    - Digital (default when the edition has actions.csv) or physical deck — and the action card in-game always offers **"Use physical card instead"**, like questions do, so both are available
    - Kinds allowed: act / explain / sound
    - Action timer seconds (default 90)
  - **Board**
    - **Tile mix:** a percentage per tile type — action, good deed, bad deed, landmark, skip; **0 removes that type**; questions fill the rest. Defaults come from the edition for the chosen length. Presets: Balanced (default) · More questions · More action · Questions only. Guard rails: total of the special tiles capped (~70%) because the "no two identical special tiles in a row" rule turns the surplus into questions; landmarks are also capped by the edition's landmark count — the panel shows the resulting tile counts for the chosen length.
    - Deed effects: random effect each game (default) · always the card's first effect
    - Deed effect filter, e.g. *no going backwards* (removes move_back / previous-landmark / skip effects — good for kids); cards with no allowed effect are left out
  - **Turn & pace**
    - Exact finish (existing)
    - Who starts: setup order (default) · random
    - Animation speed: normal · fast (token hops, dice overlay)

### 5c. Play experience
- [x] **G3 — Answer on the phone.** _Done as: difficulty + multiple choice tapped on the phone (card_choice → host only), scored by the host; open questions shown on the phone, judged by the GM; rule questions.answerOnPhone. Steal not built (future idea)._ Multiple choice on the active player's phone, scored automatically, answer hidden on the host screen until answered; optional "steal" for others. Reuses the private-card channel from C3.
- [x] **G11 — QR code + join address in the host lobby** _Done as: server sends LAN join URLs; lobby QR (vendored qrcode-generator, MIT) + address + Game ID; GM 'Show join code' mid-game; phone `?game=` prefill (decoded + joined in headless Chrome)._, so phones join without typing an IP address (vanilla JS → a small QR library copied into the project).
- [x] **G15 — Presentation mode** _Done as: 📺 / P key, body.presenting + Fullscreen API, GM tools behind ⚙️, bigger sidebar and cards, idle pointer hides; CONFIG.PRESENTATION._ (works offline): one button → full screen, GM panel hidden, large board/scoreboard; a small floating ⚙️ opens GM controls. For playing on a TV mirrored from the laptop.
- [x] **G16 — Second-screen display** _Done as: /display?game=ID read-only TV page fed by the host (game/live/card/roll/timer), server replays latest state, secrets stripped via data-secret; board/viewport/edition helpers moved to js/shared._ (`/display`, needs the server): the TV shows board, tokens, scoreboard, dice and the public part of cards; the laptop keeps the host controls. Secrets stay hidden (action cards; question answers until revealed). Needs the host to send the board to the server at game start.
- [x] **G17 — Phone-less players in network games.** _Done as: add by name in the lobby or GM panel (add_local_player, noPhone seat without socket/token); host can change any badge in the lobby and GM panel (🎨), phones adopt it; zero-phone network games work; rejoin needs a real token._ The host can add players without a phone (rolled for and resolved on the host, action cards via the host-screen toggle). "Play without phones" can then run through the server with zero phones, so G16 works for every game; the current offline mode stays as the simple fallback for opening index.html from disk.
- [x] **G18 — "You're next" on phones** _Done as: banner in the phone's activity box (uses shared nextTurnIndex, so sitting-out/finished players are skipped), vibration when the turn starts._ + a vibration when it's your turn.
- [x] **G21 — Leave the lobby on the phone.** _Done as: Leave button in the phone lobby; host lobby + other phones update (the host lobby used to ignore leavers); join form keeps the Game ID._ A player waiting in the lobby can tap *Leave* (or *Change name / badge*) and join again, instead of closing the browser tab. _(feedback 2026-10-17: joined with the wrong badge, had to close the tab)_
- [x] **G13 — End screen stats and awards:** _Done as: js/shared/stats.js from history (landedOn + result per entry), stat line per player, CONFIG.AWARDS (editions rename), also on the TV._ per-player questions right, distance travelled, deeds, plus fun awards ("Quiz master", "Unluckiest roller").
- [x] **G14 — 🚩 Report question** _Done as: 🚩 on host question cards (host-only), same marked list as G19._ button for the GM during play: saves the question id + a note, to fix the content later.
- [x] **G19 — Question explorer tab** _Done as: setup tab 📚 Questions — tree with counts, search, difficulty, show answers, mark/note/unmark, marked-only, copy marked list._ on the setup screen: browse an edition's questions by category > subcategory > topic (question, options, answer, note, difficulty), search, see counts; **mark a question as wrong / unclear** with a note (same list as G14's in-game report) and export the marked list to fix in the CSV. Also lets the GM or players see what a category contains before choosing topics. _(idea 2026-10-17 — G14 would feed the same "marked questions" list)_
- [x] **G20 — Board designer tab:** _Done as: setup tab ✏️ Boards — draw, save to My boards (board picker), play, copy as template; js/shared/path-design.js._ the path designer (`tools/path-designer.html`) built into the setup screen as a tab — draw a new board path, preview it as a thumbnail, play it straight away, and copy it as a `PATH_TEMPLATES` entry (like "Copy as preset") or keep it as a saved custom board. _(idea 2026-10-17)_

### Future ideas (not planned)
- Sound effects (dice roll, correct answer, finish fanfare)
- Team mode
- Online multiplayer (beyond local Wi-Fi)

---

## Workflow

- `main` stays playable. One branch per item (or small group of related items), e.g. `fix/B1-B2-roll-turn-setup`.
- Each branch: fix → manually verify (offline mode **and** network mode with ≥1 phone) → commit referencing IDs → merge to `main` → tick box here.
- Update `CLAUDE.md` "Architecture" sections when an invariant changes (e.g. after A2, A3).
