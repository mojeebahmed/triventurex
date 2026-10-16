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
  - **Where:** `js/game.js` `TX_NET.on('roll_result')` (~L1033), `handleRoll()` (~L1273), `handleManualRoll()` (~L1235)
  - **Problem:** Only host-initiated rolls take `_preRollSnapshot`, set `turnPhase='resolving'`, bump `_turnToken`. Phone rolls go straight to `_processRoll()`. Undo then restores a stale snapshot; host Roll button stays enabled mid-turn; resume-reopen-modal never fires.
  - **Fix:** Extract `_beginTurn()` (snapshot + token + `turnPhase='resolving'` + disable roll/manual dice). Call it from `handleRoll`, `handleManualRoll`, and from `roll_result` when the roll was not host-initiated (i.e. when `!_awaitingRoll`).
  - **Verify:** Phone rolls → host Roll button disabled during turn → Undo restores the state from before *that* roll.

- [x] **B2 — Server accepts rolls at any time**
  - **Where:** `server.js` `roll` handler (~L191)
  - **Problem:** No `room.turnPhase` check; a second roll request would start a second concurrent turn.
  - **Fix:** Reject if `room.turnPhase !== 'roll'`; set `room.turnPhase = 'resolving'` when a roll is generated (host's next `sync_state` returns it to `'roll'`). Also guard on the host: ignore `roll_result` while `state.turnPhase === 'resolving'` and not `_awaitingRoll`.
  - **Depends on:** B1 (host must sync `'resolving'`/`'roll'` reliably).

- [x] **B3 — Exact-finish block never syncs to phones**
  - **Where:** `js/game.js` `_processRoll()` blocked branch (~L1366)
  - **Problem:** No `_syncStateToServer()` → next phone player can't roll. Also `saveGame()` runs before `endTurn()` (violates the "save after endTurn" invariant).
  - **Fix:** Route through the same end-of-turn path as `afterSpaceResolved` (see A2); minimal fix = `endTurn(); saveGame(); _syncStateToServer();`.

- [x] **B4 — Extra turn leaves phones stuck (likely)**
  - **Where:** `js/game.js` `afterSpaceResolved()` extra-turn branch (~L1460)
  - **Problem:** Returns without `saveGame()` / `_syncStateToServer()`; manual dice stay disabled (only `roll-btn` re-enabled).
  - **Fix:** Call `refreshUI()`, `saveGame()`, `_syncStateToServer()` before returning.
  - **Verify:** Land on an `extra_turn` deed from a phone → phone returns to dice mode.

- [x] **B15 — Host refresh mid-turn leaves the turn stuck** _(found while fixing B1)_
  - **Where:** `js/game.js` `saveGame()`, `_restoreGame()`, `host_rejoined` handler
  - **Problem:** `_pendingHistory` was null after restore, so `afterSpaceResolved()` bailed and the turn never ended; undo snapshot lost; finish-space modal not reopened. Also `host_rejoin` was only sent on socket `connect`, which has usually already fired before Resume is clicked.
  - **Fix:** Save a serialisable `pendingTurn` (roll, posBefore, scoreBefore, snapshot); restore it via `_beginTurn()`; rejoin immediately if already connected; host syncs state after `host_rejoined`.

- [x] **B16 — Phone roll ignored "skip next turn"** _(found while fixing B1)_
  - **Fix:** `roll_result` from a phone routes to `_handleSkippedTurn()`. The skip snapshot is now taken before the flag is cleared, so undo re-arms the skip.

- [x] **B17 — Phones never told the game ended**
  - **Where:** `state.phase` never became `'ended'`.
  - **Fix:** `_endGame()` sets `phase='ended'` and syncs; used by `afterSpaceResolved()` and `endTurn()`.

- [x] **B5 — Removing a player can skip a turn**
  - **Where:** `server.js` `remove_player` / `leave_game`; `js/game.js` `player_removed` handler (~L1046)
  - **Problem:** If the removed player's index < `currentPlayerIndex`, the index isn't decremented.
  - **Fix:** `if (idx < currentPlayerIndex) currentPlayerIndex--; else if (currentPlayerIndex >= length) currentPlayerIndex = 0;` in both places (or only on host once A3 makes the server a relay).

- [x] **B6 — `host_left` never fires when host is also a player**
  - **Where:** `server.js` `disconnect` (~L374)
  - **Fix:** Check `room.hostSocketId === socket.id` before the player match / `break`.

- [x] **B7 — GM score/move changes not synced or undoable**
  - **Where:** `js/game.js` `gmAdjustScore`, `gmMovePlayer`, `gmSkipTurn` (~L1497)
  - **Fix:** Call `_syncStateToServer()` after each. Decide whether GM actions go into history (recommended: yes, as a `gm` entry with snapshot, so they're undoable and visible in the log).

- [x] **B8 — Active/inactive player feature not wired**
  - **Where:** `TX_NET.setPlayerActive` exists, no UI calls it; `endTurn()` ignores `inactive`
  - **Fix:** Add toggle button in `_renderGMNetworkPlayers`; make `endTurn()` skip `inactive` (and maybe `disconnected`) players. Or remove the feature and the CLAUDE.md claim — decide first.

### 1b. Question tracking

- [x] **B9 — Asked-question keys shared across editions**
  - **Where:** `js/ui.js` `_askedKey()` (~L206)
  - **Problem:** `window._activeThemeId` is always undefined (`let` doesn't attach to `window`) → all editions write `triventurex_asked_default_*`.
  - **Fix:** Expose the active edition id properly (e.g. `window.getActiveEditionId()` or pass it in). Optionally clear the old `triventurex_asked_default_*` keys once.

- [x] **B10 — Question IDs are row positions**
  - **Where:** `js/game.js` `_parseQuestionsCSV()` (~L1832)
  - **Problem:** Inserting/deleting a CSV row reshuffles IDs and corrupts asked-tracking.
  - **Fix:** Add an `id` column to `questions.csv` (both editions + template); parser uses it, falls back to row index only if missing. Pairs well with C2 (validator checks uniqueness).

- [x] **B18 — 10 Football Quest questions broken by unquoted commas** _(found while fixing B10)_
  - **Problem:** ids 35, 40, 54, 57, 62, 66, 70, 73, 82, 86 had commas in question/answer text without CSV quotes → columns shifted, no valid difficulty, so they were never asked (and showed garbage if they had been).
  - **Fix:** Re-quoted the fields (wording unchanged), filled the lost category/difficulty, regenerated `questions.js`. Swab Quest and both deed files checked clean.
  - **Follow-up for content owner:** truncated notes and suspected factual errors listed in the batch-3 hand-off; C2 validator should catch this class of error automatically.

### 1c. Engine/edition leaks & finish logic

- [x] **B11 — Edition text and score values hardcoded in engine**
  - **Where:** `js/ui.js` landmark modal (~L131: "Holy Site", literal `5`), action modal (~L104 "+1"), question choice (~L271 "+1"), guesser modal (~L593 "+1"); stale comment in `js/config.js` `SCORE_VALUES`
  - **Fix:** Use `CONFIG.SCORE_VALUES.*` everywhere; move landmark fallback title to `CONFIG.GAME` (edition-overridable).

- [x] **B12 — Finishing via deed/GM move gives no bonus or finish order**
  - **Where:** bonus only awarded in `_processRoll()` (~L1389)
  - **Fix:** Move finish-order/bonus into a single `_checkFinish(player)` called after any movement (roll, deed, GM).
  - **Done as:** `_recordFinish(player)`; deed/GM finishes show a toast; a GM move that finishes the last player ends the game. B11 also: landmark/action modal icons from `SPACE_INFO`, editions can override `SCORE_VALUES` / `FINISH_BONUS`, removed "ptss" pluralisation.

### 1d. Security (LAN-scale)

- [x] **B13 — Player names rendered via `innerHTML`**
  - **Where:** `js/ui.js` scoreboard/end screen, `js/game.js` lobby + GM list, `js/player.js` other-players list
  - **Fix:** Add `esc()` helper; escape names everywhere they're interpolated. Server: trim/limit name length.

- [x] **B14 — Whole project folder served statically**
  - **Where:** `server.js` `express.static(__dirname)`
  - **Fix:** Short term: serve only an allowlist (`index.html`, `player.html`, `css/`, `js/`, `game_editions/`, `images/`). Long term: `public/` folder (A6).

---

## Phase 2 — Architecture

- [x] **A1 — Finish the theme → edition rename in code** (`loadTheme`, `_activeThemeId`, `themeId`, `CONFIG.THEME`, `onThemePicked`, server `themeId`). Mechanical; do first so later refactors use final names.
- [x] **A2 — Single turn pipeline.** `beginTurn() → move → resolveSpace() → finishTurn()`, where `finishTurn` *always* does history → finish check → extra-turn/endTurn → save → sync. Replaces scattered `_pendingHistory` / `_awaitingRoll` / early returns. Absorbs B1, B3, B4, B12.
- [ ] **A3 — Decide state ownership.** Recommended: host is sole authority; server is a relay + roll generator + room registry. Server forwards GM actions (`remove_player`, `set_player_active`) to the host instead of mutating `room.players` itself. Also: host-only checks on `turn_result` / `space_card` relays.
- [ ] **A4 — Split `game.js` (~2000 lines)** into `setup.js`, `badge-picker.js` (dedupe host + local), `net-host.js`, `viewport.js` (pan/zoom/background), `content-loader.js` (CSV + edition loading), `turn.js`. Consider native ES modules (`<script type="module">`, no build step).
- [ ] **A5 — Room lifecycle on server.** Delete rooms on game end, and after host absent > N minutes.
- [ ] **A6 — `public/` folder** for client files (completes B14).
- [ ] **A7 — `TX_NET.on` supports multiple handlers** per event.
- [ ] **A8 — Remove duplicate `renderDie`** inline copy in `player.html` (load `js/dice.js` instead).

## Phase 3 — Content pipeline

- [ ] **C1 — Replace "ask Claude to regenerate JS"** with `npm run build:content` (Node script), or drop generated `questions.js`/`deeds.js` entirely if file:// support is no longer needed.
- [ ] **C2 — Content validator** `npm run validate`: multi-choice answer 1–4 and option non-empty; known effect names; numeric values; unique question IDs; topics non-empty; landmark count vs. `move_to_*_landmark N` values.
- [ ] **C3 — Digital action cards** using `game_editions/template/action-cards-template.csv`; show privately on performer's phone.

## Phase 4 — Tests

- [x] **T1 — `node:test` setup.** `npm test` runs `test/**/*.test.js`. `server.js` exports `{ server, io, rooms }` and only listens when run directly. Client-side unit tests still need pure functions loadable in Node (after A2 / A4).
- [ ] **T2 — Unit tests:** CSV parsers, `movePlayer`, `getSortedPlayers`, `_resolveRelativeLandmark`.
- [ ] **T3 — Property test for `generateBoard`:** 1000 random boards per length/path → constraints hold (no `move_back N` before N, no `move_forward` past finish, landmark deeds resolvable, no consecutive same deed type).
- [x] **T4 — Server tests** `test/server.test.js` (24 tests): hosting/joining, roll guard + manual roll (B2), sync_state field preservation, remove/leave turn index (B5), rejoin + host rejoin, disconnects + host_left (B6). Verified: 5 fail against the pre-fix server.
- [x] **T5 — Host turn-logic tests** for `_nextTurnIndex`, undo-by-id merge, removal handling — write these during A2/A4 once the logic is separated from the DOM.

## Phase 5 — Gameplay (to be expanded)

- [ ] **G1 — Endgame pacing:** exact-finish alternatives (bounce back / within-1 / end N rounds after first finisher / end when all but one finished).
- [ ] **G2 — Score balance:** finish bonus (10) vs. questions (1–2) — make trivia matter more; per-edition tuning.
- [ ] **G3 — Answer on phone:** multiple choice on active player's phone, auto-score, answer hidden from host screen; optional "steal" for others.
- [ ] **G4 — Automatic landmark points** when landing by roll (drop GM award/visual-stop choice).
- [ ] **G5 — Ideas pool:** streak bonus, wager questions, final round at finish, sound effects.
- [ ] **G6+ — Mojeeb's own ideas** _(to be added)_

---

## Workflow

- `main` stays playable. One branch per item (or small group of related items), e.g. `fix/B1-B2-roll-turn-setup`.
- Each branch: fix → manually verify (offline mode **and** network mode with ≥1 phone) → commit referencing IDs → merge to `main` → tick box here.
- Update `CLAUDE.md` "Architecture" sections when an invariant changes (e.g. after A2, A3).
