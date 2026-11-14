# js/player — the phone page (player.html)

Notes for Claude, loaded automatically when working in this folder. The project-wide rules are in the
root `CLAUDE.md`. Keep invariants for this area here; update them when one changes.

## Files
- `player.html` + `js/player/player.js` — phone screen (join, action box, answering, session management)

## Architecture — V2 (don't revert)
- **Phone turn cues (G18)**: player.js uses `nextTurnIndex` (js/shared/turn.js, loaded by player.html) to show *"You're next"* in the activity box (skips finished / sitting-out players like the host) and buzzes (`navigator.vibrate`) once when the phone's turn starts
- **Leaving the lobby (G21)**: phone *← Leave · change name or badge* → `leave_game`; the server sends the new list with `player_removed`, which updates the host lobby (`_updateLobby`, also before the game starts) and the other phones; the join form keeps the Game ID
- **Join by QR (G11)**: server's `hosted` reply carries `joinUrls` (every LAN IPv4 → `http://ip:port/player?game=ID`; the host page on localhost can't see these). Lobby shows a QR (`js/vendor/qrcode.js`, MIT, Kazuhiko Arase — third-party, don't edit), the address and the Game ID; GM panel has *📱 Show join code* for latecomers. `player.html?game=ID` pre-fills the Game ID and wins over an old saved session for another game. The `?game=` link is read once and removed from the address (`history.replaceState`) — otherwise a phone refresh re-applies an old link and drops the session for the game actually joined
- **Edition on phones**: player.html loads no edition. The host sends the game's details as `edition: { name, icon, pointsName, finishLabel, icons, labels, board: { length, name, spaces } }` (`_phoneEdition()` in net-host.js) with `host_game` (lobby) and every `sync_state`; the server cleans it (`cleanEdition`: short strings, identifier keys, icon values `emoji:` / `<set>:<icon>` / `url:game_editions/…`), keeps it on the room and sends it in `joined`, `rejoined` and every `state_update`. The phone's `_applyEdition` sets its stand-in `CONFIG.EDITION_ICONS` (so `icon()` resolves edition → engine), the tile names in `SPACE_META`, and the edition banner (`.game-info`, lobby + game). Phone text uses the edition's words — `_pts()`, `_finish()`, `_tile(type)` — never a fixed "pts" / "finish" / "landmark"
- **Token-based rejoin**: each player gets a `rejoinToken` on join; saved to `triventurex_game_session`; used to re-register the socket on any reconnect (page refresh OR phone screen wake)
- **Mid-session reconnect**: `connect` handler in player.js checks `_myId` + `_gameId`; if set, loads session and calls `rejoinGame()` automatically — no page refresh needed
- **Action box**: fixed-height area on player screen; modes = `dice` | `rolled` | `card` | `activity`
- **Mode transitions**: `dice` → (tap roll) → `rolled` → (space_card) → `card` → (space_card_done) → `activity`
- **state_update must NOT override rolled/card mode**: `renderGameView()` skips mode change when box is in `rolled-mode` or `card-mode` during a resolving turn
- **turn_result before space_card_done**: `_finishTurn()` emits `turn_result` first so activity feed updates before card clears
