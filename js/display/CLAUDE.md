# js/display — the TV display (display.html)

Notes for Claude, loaded automatically when working in this folder. The project-wide rules are in the
root `CLAUDE.md`. Keep invariants for this area here; update them when one changes.

## Files
- `display.html` + `js/display/display.js` — TV display (read-only)

## Architecture — V2 (don't revert)
- **TV display (G16)**: `display.html` + `js/display/display.js` at `/display?game=ID`, read-only. Host → `display` {kind, data} → server relays to room `display:<id>` only (host socket only; never to phones). Kinds: `game` (edition + board, from `_displayGame` in `_enterGameScreen` / host rejoin), `live` (players + turn, from `updateBoardTokens` + `updateScoreboard` → every hop / score change), `card` (open modal or null, from `showModal` / `hideModal`), `roll`, `timer`. Server keeps the last game/live/card/timer and replays them to a display that (re)joins; lobby list via `displayLobby(room)`; `host` gone/back; `closed`. **Secrets**: `_publicHtml` strips `[data-secret]`, `[data-host-only]`, `.hidden`, buttons and inputs from card HTML — mark any new secret in a modal template with `data-secret`. Host buttons: lobby + GM panel *📺 Open TV display* (`openDisplay`)
