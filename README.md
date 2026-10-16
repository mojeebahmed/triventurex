# Triventurex

## About the name

**Triventurex** = Trivia + Adventure + X

A family/group board game engine where players roll dice, move along a path, and collect points through:
- **Quiz questions** — Easy (+1 pt) or Hard (+2 pt), chosen by the player
- **Action cards** — Charade-style performance; performer and guesser both earn points
- **Good/Bad deed/action cards** — Randomly assigned effects (move forward/back, score, skip turn, etc.)
- **Landmarks** — Visual stops with photos and descriptions; GM awards 5 pts

- **Tri** — three core mechanics: quiz questions (knowledge), action cards (performance), and deed cards (moral choices or events). Also a nod to "trivia".
- **Venture** — the board journey: players roll, move, and venture toward a destination.
- **X** — game editions are interchangeable. The same engine runs any content — Islamic, football, science — by swapping the edition folder.

---

## Game Editions

| Edition | Status | Points name | Finish | Questions | Landmarks |
|---|---|---|---|---|---|
| Swab Quest | ✅ Live | Sawab | Al-Ka'ba, Mecca | 432 | 20 mosques & Islamic sites |
| Football Quest | ✅ Live | Goals | The Final | 92 | 20 iconic stadiums & venues |

---

## How to run

### V1 — Single device (offline, no server)

Open `index.html` in any modern browser. No server or build step needed.

Without the server, the game runs from `file://` using the JS fallback data — fully playable, just without CSV hot-reloading.

### V2 — Local network multiplayer (server)

```bash
npm install
node server.js
# Host opens http://localhost:3000
# Players open http://<host-ip>:3000/player on their phones
```

The game auto-detects whether Socket.IO is available. If the server isn't running, it falls back silently to offline V1 mode.

---

## Project structure

```
Triventurex/
│
├── index.html                    Main game page (host / single-device)
├── player.html                   Lightweight player screen (phones/tablets)
├── server.js                     Node.js + Socket.IO server (V2)
├── package.json                  Dependencies: socket.io, express
│
├── js/                           Engine — mechanics only, no edition content
│   ├── config.js                 ← All engine settings (start here)
│   ├── board.js                  Board generation & rendering
│   ├── players.js                Player state helpers
│   ├── dice.js                   Dice roll + animation (CSS dot-based rendering)
│   ├── ui.js                     Modals, scoreboard, legend, timer, history
│   ├── socket-client.js          TX_NET singleton — shared Socket.IO event layer
│   └── game.js                   Main controller — wires everything together
│
├── css/
│   └── styles.css                All styling (colours driven by edition config)
│
├── images/
│   └── game-length-*.png         Setup screen game-length illustrations
│
└── game_editions/
    ├── editions.js               ← Edition registry (add new editions here)
    │
    ├── template/                 ← Blank starter — copy this for a new edition
    │   ├── README.md             How to make an edition + CSV column guide
    │   ├── config.js             Annotated template with all options
    │   ├── questions.csv         Example questions (edit these)
    │   └── deeds.csv             Example deed cards (edit these)
    │
    ├── swab-quest/               Islamic / Ahmadiyya edition
    │   ├── config.js             Name, colours, 20 landmarks (with descriptions), space distribution
    │   ├── questions.js          432 questions (auto-generated from CSV)
    │   ├── deeds.js              52 deed cards (auto-generated from CSV)
    │   ├── questions.csv         ← Edit this to add/change questions
    │   ├── deeds.csv             ← Edit this to add/change deed cards
    │   └── images/
    │       ├── landmarks/        20 mosque/site photos (shown on board + in info popup)
    │       └── backgrounds/      Board background images
    │
    └── football-quest/           Football trivia edition
        ├── config.js             Name, colours, 20 landmarks (with descriptions), space distribution
        ├── questions.js          92 questions (auto-generated from CSV)
        ├── deeds.js              52 deed cards (auto-generated from CSV)
        ├── questions.csv         ← Edit this to add/change questions
        └── deeds.csv             ← Edit this to add/change deed cards
```

---

## How game editions work

Editions are loaded **dynamically** at startup. The engine never changes when you add a new edition.

1. `game_editions/editions.js` — the registry listing all available editions.
2. On page load, `game.js` reads the last-used edition from localStorage (or picks the first in the registry).
3. `config.js` sets `window.EDITION_CONFIG` which is merged into `CONFIG`.
4. If more than one edition is registered, an **edition picker** appears on the setup screen.
5. Deed/question labels (e.g. "Good Deed" → "Good Play") are driven by `SPACE_INFO.good_deed.label` in `config.js`.

---

## Adding a new edition

1. Copy `game_editions/template/` to `game_editions/<your-id>/`
2. Edit `config.js`, `questions.csv`, `deeds.csv` and add your images (column guide: `game_editions/template/README.md`)
   then run `npm run build:content <your-id>` to check the content and generate `questions.js` / `deeds.js`
3. Add one entry to `game_editions/editions.js`:
   ```javascript
   { id: 'your-id', name: 'Your Edition', icon: '⚽', description: 'Short description.', accentColor: '#1565C0' }
   ```
4. Done — the edition picker appears automatically on the setup screen.

---

## Configuration — `js/shared/config.js`

Engine-level settings only. Edition values live in `game_editions/<id>/config.js`.

| Section | What it controls |
|---|---|
| `GAME` | Engine brand + per-edition overrides (name, pointsName, etc.) |
| `RULES` | Gameplay rules: `exactFinish`, `questionTracking` |
| `BOARD_SIZES` | Spaces per game length (short/medium/long) |
| `GRID_SIZE` | Board grid dimensions (default 12×12) |
| `SPACE_DISTRIBUTION` | Ratio of each non-question space type (questions fill remainder) |
| `SPACE_INFO` | Icon, label, colour per space type |
| `PLAYERS` | Default names, colours, tokens; picker palette |
| `FINISH_BONUS` | Score bonus for finishing order |
| `SCORE_VALUES` | Points for questions, actions, landmarks |
| `ZOOM` | Max zoom-in (200%), zoom-out factor |
| `TIMER` | Default timer duration per space type |
| `ANIMATION` | Token hop speed, flyout duration, dice overlay |
| `PATH_TEMPLATES` | Board path shapes per game length |

Editions can override `SPACE_DISTRIBUTION` in their own `config.js` — as a flat object (same for all game lengths) or keyed by `short`/`medium`/`long`.

---

## Game Settings (in-game)

Accessible via the collapsible **⚙️ Game Settings** section on the setup screen.

| Setting | Options | Default |
|---|---|---|
| Board Layout | Random or a specific path shape | Random |
| Exact Finish | On / Off | On |
| Question Tracking | Remember across games / Reset every game | Remember |
| Question Topics | 3-level filter: category > subcategory > topic | All selected |

**Exact Finish:** player must roll the exact number to land on the finish space — overshooting does not move the token.

**Question Tracking:** when "Remember across games" is selected, questions already asked in previous games are skipped until all questions in that difficulty have been asked, then the pool resets.

**Question Topics:** questions are organised into three levels — **Category > Subcategory > Topic**. Checking or unchecking a category or subcategory toggles all its children. Parent checkboxes show a dash (−) when partially selected. Only questions whose topic is checked will be asked. Selections are saved per edition. At least one topic must stay checked.

---

## Adding content

### Questions (`game_editions/<id>/questions.csv`)

Edit in Excel, Numbers, or Google Sheets. Format:
```
id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note
433,How many daily prayers are obligatory?,multi,2,3,4,5,6,easy,Islam,Worship,Prayer,
434,What does Sawab mean?,open,"Reward, blessing",,,,,easy,Islam,Knowledge,Terms,
```
- `id`: unique number — never reuse or renumber; a new question gets the next unused number
- Wrap any field that contains a comma in "double quotes"
- `type`: `multi` (multiple choice, options shown in-game) or `open` (open-ended, answer revealed)
- `answer`: for `multi` — option number of correct answer (1–4); for `open` — the answer text
- `difficulty`: `easy` or `hard`
- `category`, `subcategory`, `topic`: three-level hierarchy that drives the **Question Topics** filter in Game Settings. All three should be filled in. Example: `Islam > Worship > Prayer`.
- After editing, run `npm run build:content` — it checks the content (with line numbers for any problem) and regenerates the JS files

### Deed cards (`game_editions/<id>/deeds.csv`)

```
type,text,effect,value,effect_2,value_2,effect_3,value_3,mood
good,"You helped someone in need.",move_forward,2,score_add,1,,,social
bad,"You missed your Fajr prayer.",score_remove,2,move_back,1,,,reflection
bad,"You were sent back to {landmark}.",move_to_prev_landmark,1,score_remove,1,,,reflection
```

- Each card can have up to 3 effects. One is picked randomly at board generation time (not at landing time).
- `{landmark}` in the text is automatically replaced with the resolved landmark name.
- `mood`: flavour tag (`blessing`, `social`, `challenge`, `reflection`, `funny`, `risk`) — not used mechanically.

**Effect types:**

| Effect | What happens |
|---|---|
| `score_add` | Player gains `value` points |
| `score_remove` | Player loses `value` points |
| `move_forward` | Player moves forward `value` spaces |
| `move_back` | Player moves back `value` spaces |
| `move_to_prev_landmark` | Player moves back to the Nth previous landmark (`value=1` = nearest) |
| `move_to_next_landmark` | Player advances to the Nth next landmark (`value=1` = nearest) |
| `skip_turn` | Player skips their next turn |
| `extra_turn` | Player rolls again immediately |
| `all_players_gain` | Everyone gains `value` points |
| `all_players_lose` | Everyone loses `value` points |
| `protection` | Player's next bad deed card is cancelled |

### Landmarks (`game_editions/<id>/config.js` → `LANDMARKS` array)

Each landmark is an object with three fields:

```javascript
{
  name:        'Wembley Stadium',
  image:       'game_editions/football-quest/images/landmarks/wembley-stadium.jpg',
  description: 'A short paragraph shown in the landing modal and the info popup.',
}
```

- `image` path is relative to `index.html`
- `description` appears in the modal when a player lands on the space, and in an info popup when anyone clicks the board tile during play
- Any number of landmarks can be defined — the engine picks as many as fit on the board
- Recommended image size: 800×500px minimum; JPG or WebP

---

## Gameplay summary

1. Choose edition, game length, board layout → Start
2. On your turn: roll dice → token hops to space → event triggers:
   - **Question** → choose Easy (+1) or Hard (+2) → answer → reveal
   - **Action** → perform charade → performer and guesser each earn +1
   - **Good Deed / Good Play** → one effect applied automatically (varies each game)
   - **Bad Deed / Foul Play** → one effect applied automatically (varies each game)
   - **Landmark / Stadium** → GM awards 5 pts or visual stop
   - **Skip** → lose next turn
3. To reach the finish, you must roll the **exact** number (exact finish is on by default).
4. Game ends when all players reach the finish. **Winner = most points.**

### Network game (V2)

1. Host starts the server, opens `http://localhost:3000`, selects edition + length, clicks **Host Network Game**
2. A 4-digit Game ID is shown on screen (e.g. `4823`)
3. Players open `http://<host-ip>:3000/player` on their phones, enter the Game ID, set their name/badge
4. Host clicks Start — game begins
5. On your turn, your phone shows an active **Roll Dice** box (green glow); tap to roll
6. After rolling, your phone shows the die result while the GM resolves the space on the host screen
7. Your phone then shows your space card (question, deed, action) — read-only alongside the host
8. The activity feed on your phone shows what happened (score gained/lost, movements, etc.)
9. If your phone screen turns off and back on, it reconnects and resumes automatically
10. The GM can click a specific die face on the host screen to use a physical dice result instead of rolling digitally

---

## LocalStorage keys

| Key | Contents |
|---|---|
| `triventurex_save` | Full game state for resume on refresh (V1 / host) |
| `triventurex_player_prefs` | Player names, colours, tokens (local game) |
| `triventurex_host_player` | Host player name/colour/token (network host mode) |
| `triventurex_game_settings` | Last game length, path choice, exact finish, question tracking |
| `triventurex_edition` | Last active edition ID |
| `triventurex_asked_<editionId>_<diff>` | Asked question IDs per edition and difficulty |
| `triventurex_cats_<editionId>` | Selected question topic names per edition (3-level filter) |
| `triventurex_player_identity` | Player name/token/colour saved on player device (V2) |
| `triventurex_game_session` | Rejoin token + game/player IDs saved on player device (V2) |
| `tx_net_game` | Host's active network game ID for host-rejoin after refresh (V2) |

---

## Roadmap

### V1 — Complete ✅
- Edition-neutral engine (Swab Quest + Football Quest)
- Variable deed effects: up to 3 effects per card, one picked at board-gen time
- Constraint-aware board generation: no move-back near start, no move-forward near finish
- Relative landmark deeds (`move_to_prev/next_landmark`) with resolved names on board tiles
- Exact finish rule (configurable)
- No-repeat question tracking with auto-recycle (per-edition, per-difficulty)
- 3-level question topic filter in Game Settings (category > subcategory > topic)
- SPACE_DISTRIBUTION configurable per edition and game length
- Landmark descriptions: shown in landing modal and clickable info popup on board tiles
- Save/resume, GM controls, game log, undo
- Setup screen: game length picker, collapsible settings, badge picker modal

### V2 — Local network multiplayer ✅ Complete
- Node.js + Express + Socket.IO server
- Host opens full board view; players join on phones via 4-digit Game ID
- Players set own name/badge from their device (saved to their localStorage)
- CSS 3D dot-based dice — no images, renders on all devices
- Single action box on player screen: dice → rolled result → space card → activity feed
- Rejoin on refresh: token-based session saved to localStorage, auto-rejoined on reconnect
- Reconnect on phone screen-off: socket reconnects mid-session without page refresh
- GM controls: adjust score, move player, skip turn, remove/deactivate players
- Manual dice selection: host can click a die face to use a physical dice result
- Skip turn broadcast: skipped turns update player screens, appear in game log, and are undoable
- Turn cancellation system (`_turnToken`): stale async callbacks are cancelled on undo

### V3 — More editions
- Any topic: same engine, different content + colour scheme
- Use `game_editions/template/` as the starting point

### Future ideas
- Sound effects (dice roll, correct answer, finish fanfare)
- Football Quest subcategory/topic structure
- Team mode
- Online multiplayer (beyond local Wi-Fi)
