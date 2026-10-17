# Triventurex

## About the name

**Triventurex** = Trivia + Adventure + X

A family/group board game engine where players roll dice, move along a path, and collect points through:
- **Quiz questions**: Easy (+1 pt) or Hard (+2 pt), chosen by the player
- **Action cards**: act it out, explain it without the key words, or hum it. Performer and guesser both earn points. In a network game the card appears only on the performer's phone.
- **Good/Bad deed cards**: randomly assigned effects (move forward/back, score, skip turn, etc.)
- **Landmarks**: visual stops with photos and descriptions. The GM awards 5 pts.

The name in three parts:
- **Tri**: three core mechanics, namely quiz questions (knowledge), action cards (performance) and deed cards (moral choices or events). Also a nod to "trivia".
- **Venture**: the board journey. Players roll, move, and venture toward a destination.
- **X**: game editions are interchangeable. The same engine runs any content (Islamic, football, science) by swapping the edition folder.

---

## Game Editions

| Edition | Status | Points name | Finish | Questions | Action cards | Landmarks |
|---|---|---|---|---|---|---|
| Swab Quest | ✅ Live | Sawab | Al-Ka'ba, Mecca | 432 | 26 | 20 mosques & Islamic sites |
| Football Quest | ✅ Live | Goals | The Final | 92 | 25 | 20 iconic stadiums & venues |

---

## How to run

### V1: Single device (offline, no server)

Open `index.html` in any modern browser. No server or build step needed.

Opened from disk (`file://`), the game uses the generated JS copies of the content (`questions.js`, `deeds.js`, `actions.js`). It's fully playable. When served over HTTP it reads the CSV files directly.

### V2: Local network multiplayer (server)

```bash
npm install
node server.js
# Host opens http://localhost:3000
# Players open http://<host-ip>:3000/player on their phones
```

The game auto-detects whether Socket.IO is available. If the server isn't running, it silently falls back to offline V1 mode.

> **After updating the code, restart `node server.js`** and reload the host and phone pages. Node loads `server.js` once at startup. A server started before an update keeps running the old server code even though the browser loads the new page code.

---

## Development

```bash
npm test                  # all tests (~200, a few seconds): server, turn flow, board generation, content
npm run build:content     # check every edition's CSV content, then regenerate questions.js / deeds.js / actions.js
npm run check:content     # check only: fails on content errors or out-of-date generated files
```

- **`CHANGELOG.md`**: what changed, release by release
- **`IMPROVEMENT-PLAN.md`**: the improvement backlog (bugs, architecture, content pipeline, tests, gameplay) with status
- **`TRIVENTUREX-DESIGN.md`**: design decisions and how the pieces fit together
- **`CLAUDE.md`**: detailed architecture rules and invariants (also the brief for AI assistants)

---

## Project structure

```
Triventurex/
│
├── index.html                    Host page (single device or network host)
├── player.html                   Phone page for network players
├── server.js                     Node.js + Socket.IO server (V2)
├── package.json                  Dependencies (express, socket.io) + npm scripts
│
├── js/                           Engine: mechanics only, no edition content
│   ├── shared/                   No page access at load time; used by more than one place
│   │   ├── config.js             ← All engine settings (start here)
│   │   ├── utils.js              esc(): HTML escaping for player-supplied text
│   │   ├── players.js            Player model: create, move, score, sort
│   │   ├── turn.js               Pure turn logic: next player, undo snapshots, history rows
│   │   ├── csv.js                CSV parsing for questions / deeds / action cards
│   │   ├── dice.js               CSS dot-die rendering + roll animation
│   │   └── socket-client.js      TX_NET: Socket.IO layer, safe no-ops when offline
│   ├── host/                     Host page only
│   │   ├── game.js               Shared game state, start / resume / reset, bootstrap (loaded last)
│   │   ├── turn-flow.js          The turn pipeline, undo, GM controls
│   │   ├── net-host.js           Host side of network play (lobby, sync, socket events)
│   │   ├── board.js              Board generation + rendering
│   │   ├── ui.js                 Modals (question, deed, action, landmark), scoreboard, timer, history
│   │   ├── setup.js              Setup screen, player rows
│   │   ├── badge-picker.js       Badge (emoji + colour) picker
│   │   ├── category-filter.js    3-level question topic filter
│   │   ├── edition-loader.js     Edition loading, colours, branding
│   │   ├── storage.js            Saved game + remembered preferences
│   │   └── viewport.js           Pan / zoom / board background
│   └── player/
│       └── player.js             Phone screen logic
│
├── css/styles.css                All styling (colours driven by edition config)
├── images/                       Setup screen game-length illustrations
├── scripts/                      Node-only dev tooling: content build + checker (not served)
├── tools/path-designer.html      Browser tool for designing board paths
├── test/                         Automated tests (npm test)
│
└── game_editions/
    ├── editions.js               ← Edition registry (add new editions here)
    │
    ├── template/                 ← Starter edition: copy this for a new edition
    │   ├── README.md             How to make an edition + CSV column guide
    │   ├── config.js             Annotated template with all options
    │   └── questions.csv, deeds.csv, actions.csv   Example content (edit these)
    │
    ├── swab-quest/               Islamic / Ahmadiyya edition
    │   ├── config.js             Name, colours, 20 landmarks (with descriptions), space distribution
    │   ├── questions.csv         ← Edit these…
    │   ├── deeds.csv
    │   ├── actions.csv
    │   ├── questions.js, deeds.js, actions.js   …these are generated (npm run build:content)
    │   └── images/               Landmark photos, board backgrounds
    │
    └── football-quest/           Football trivia edition (same layout)
```

---

## How game editions work

Editions are loaded **dynamically** at startup. The engine never changes when you add a new edition.

1. `game_editions/editions.js` is the registry listing all available editions.
2. On page load, the last-used edition is read from localStorage (or the first in the registry is used).
3. The edition's `config.js` sets `window.EDITION_CONFIG`, which is merged into `CONFIG`.
4. If more than one edition is registered, an **edition picker** appears on the setup screen.
5. Labels such as "Good Deed" → "Good Play" come from `SPACE_INFO.good_deed.label` in the edition's `config.js`. Point values (`SCORE_VALUES`, `FINISH_BONUS`) can also be overridden per edition.

---

## Adding a new edition

1. Copy `game_editions/template/` to `game_editions/<your-id>/`.
2. Edit `config.js`, `questions.csv`, `deeds.csv`, `actions.csv` and add your images (column guide: `game_editions/template/README.md`).
3. Run `npm run build:content <your-id>`. It checks the content and reports problems with file and line. Then it generates the JS files.
4. Add one entry to `game_editions/editions.js`:
   ```javascript
   { id: 'your-id', name: 'Your Edition', icon: '⚽', description: 'Short description.', accentColor: '#1565C0' }
   ```
5. Done. The edition picker appears automatically on the setup screen.

---

## Configuration: `js/shared/config.js`

Engine-level settings only. Edition values live in `game_editions/<id>/config.js`.

| Section | What it controls |
|---|---|
| `GAME` | Engine brand + per-edition overrides (name, pointsName, etc.) |
| `RULES` | Gameplay rules: `exactFinish`, `questionTracking` |
| `BOARD_SIZES` | Spaces per game length (short/medium/long) |
| `GRID_SIZE` | Board grid dimensions (default 12×12) |
| `SPACE_DISTRIBUTION` | Ratio of each non-question space type (questions fill the remainder) |
| `SPACE_INFO` | Icon, label, colour per space type |
| `ACTION_KINDS` | Action card kinds (act / explain / sound): icon, label, rule |
| `RULE_PRESETS` | Rule presets for the rules panel (Family, Kids, Quiz night) |
| `PLAYERS` | Default names, colours, tokens; picker palette |
| `FINISH_BONUS` | Score bonus for finishing order |
| `SCORE_VALUES` | Points for questions, actions, landmarks (every label in the game reads these) |
| `ZOOM` | Max zoom-in (200%), zoom-out factor |
| `TIMER` | Default timer duration per space type |
| `ANIMATION` | Token hop speed, flyout duration, dice overlay |
| `PRESENTATION` | 📺 presentation mode: shortcut key, how much bigger, board fill limit, pointer hide delay |
| `PATH_TEMPLATES` | Board path shapes per game length |

Editions can override `SPACE_DISTRIBUTION` in their own `config.js`, either as a flat object (same for all game lengths) or keyed by `short`/`medium`/`long`. They can also override `SCORE_VALUES` and `FINISH_BONUS`.

Server settings are at the top of `server.js`: `PORT` (env), and `ROOM_TTL`, which controls how long a finished or host-less room is kept.

---

## Game rules (in-game)

Rules have their own **⚙️ Rules** tab on the setup screen, with side tabs per section (Scoring, Questions, Action cards, Board, Turn & pace, Topics). Changes are saved as you make them; **↺ Reset to preset** undoes them. Rules are remembered **per edition**, and a running game keeps its own copy (also after a resume).

**Presets** set many rules at once: *Family* (the standard game), *Kids* (easy questions, no going backwards, more action) and *Quiz night* (questions count double, timer, more question tiles). After changing anything, the summary shows "N changed". **📋 Copy as preset** turns the current rules into a few lines of JSON you can paste into `RULE_PRESETS` in `js/shared/config.js` as a new preset.

| Section | Rules (default) |
|---|---|
| Scoring | Easy/hard question points (1/2) · action performer/guesser (1/1) · finish bonus: Standard 10/7/5…, Small 5/3/2/1 or Off · landmark points when **landing by a roll** (+5), **sent there by a good deed** (0), **sent back there by a bad deed** (0); each can be negative, 0 = just information · allow negative scores (off) |
| Questions | Difficulty: player chooses / always easy / always hard · auto-start timer (off) and its seconds (30) · avoid repeats: remember across games / reset every game · **question topics** (category > subcategory > topic) |
| Action cards | Digital (when the edition has cards) or physical deck; a digital card can always be swapped for a physical one in play · kinds allowed (act / explain / sound) · action timer (90 s) |
| Board | **Tile mix**: % per tile type, 0 removes it, questions fill the rest; presets Balanced / More questions / More action / Questions only, with a live preview of the tile counts (special tiles capped at 70% in total) · deed effects: varied or always the first · no going backwards (leaves out move-back, back-to-landmark and skip-turn effects) |
| Turn & pace | Exact finish (on) · who starts: first player or random · animation speed: normal / fast |

**Exact finish:** the player must roll the exact number to land on the finish space. Overshooting does not move the token.

**Avoid repeated questions:** questions already asked are skipped until every question of that difficulty has been asked, then the pool resets. Each edition keeps its own list. Action cards are tracked the same way.

**Question topics:** questions are organised into three levels, **Category > Subcategory > Topic**. Checking or unchecking a category or subcategory toggles all its children. Parent checkboxes show a dash (−) when partially selected. Only questions whose topic is checked are asked. Selections are saved per edition, and at least one topic must stay checked.

---

## Adding content

Edit the CSV files in Excel, Numbers or Google Sheets, then run `npm run build:content`. The full column reference is in `game_editions/template/README.md`. Two rules matter most:
- **Every question and action card has a unique `id`.** Never reuse or renumber them, because "already asked" tracking is stored by id.
- **Wrap any field that contains a comma in "double quotes".** Otherwise the columns shift and the row silently breaks. The checker catches this.

### Questions (`questions.csv`)

```
id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note
433,How many daily prayers are obligatory?,multi,2,3,4,5,6,easy,Islam,Worship,Prayer,
434,What does Sawab mean?,open,"Reward, blessing",,,,,easy,Islam,Knowledge,Terms,
```
- `type`: `multi` (multiple choice, options shown in-game) or `open` (open-ended, answer revealed)
- `answer`: for `multi`, the option number of the correct answer (1–4); for `open`, the answer text
- `difficulty`: `easy` or `hard`
- `category`, `subcategory`, `topic`: the three-level hierarchy behind the **Question Topics** filter. Fill in all three, e.g. `Islam > Worship > Prayer`.

### Deed cards (`deeds.csv`)

```
type,text,effect,value,effect_2,value_2,effect_3,value_3,mood
good,"You helped someone in need.",move_forward,2,score_add,1,,,social
bad,"You missed your Fajr prayer.",score_remove,2,move_back,1,,,reflection
bad,"You were sent back to {landmark}.",move_to_prev_landmark,1,score_remove,1,,,reflection
```

- Each card can have up to 3 effects. One is picked at random when the board is generated, not when a player lands on it.
- `{landmark}` in the text is replaced with the resolved landmark name.
- `mood`: flavour tag (`blessing`, `social`, `challenge`, `reflection`, `funny`, `risk`). Not used mechanically.
- Board generation places each deed so its effect makes sense. For example, `move_back 3` is never within 3 spaces of the start, and `move_forward` never carries a player onto the finish.

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

### Action cards (`actions.csv`)

```
id,text,kind,note
1,Act out a goalkeeper saving a penalty,act,
11,"Explain 'offside' without saying offside, line or defender",explain,
21,Hum 'You'll Never Walk Alone',sound,Hum only — no words
```
- `kind`: `act` (mime: no words, no sounds), `explain` (describe it without the key words) or `sound` (hum or make sounds, no words)
- `note`: optional extra rule shown with the card
- Optional file. Without it, action spaces ask players to draw a card from a physical deck.

### Landmarks (`config.js` → `LANDMARKS` array)

```javascript
{
  name:        'Wembley Stadium',
  image:       'game_editions/football-quest/images/landmarks/wembley-stadium.jpg',
  description: 'A short paragraph shown in the landing modal and the info popup.',
}
```

- `image` path is relative to `index.html`
- `description` appears in the modal when a player lands on the space, and in an info popup when anyone clicks the board tile during play
- Any number of landmarks can be defined; the engine picks as many as fit on the board
- Recommended image size: 800×500px minimum; JPG or WebP

---

## Gameplay summary

1. On the setup screen (*🎲 New game* tab): ① edition → ② game length → ③ board (🎲 Random or a path, shown as thumbnails) → ④ players. Each choice moves on to the next step; collapsed steps show what's chosen, and the footer shows the whole setup next to **Start**. Next time everything is pre-filled with your last choices, so it's usually just Start.
2. On your turn, roll the dice. Your token hops to a space and its event triggers:
   - **Question**: choose Easy (+1) or Hard (+2), answer, then the GM reveals the answer
   - **Action**: perform the card (act / explain / hum). Performer and first correct guesser each earn +1.
   - **Good Deed / Good Play**: one effect applied automatically (varies each game)
   - **Bad Deed / Foul Play**: one effect applied automatically (varies each game)
   - **Landmark / Stadium**: points by the rules (default +5 when landing by a roll; also settable for arriving via a deed)
   - **Skip**: lose your next turn
3. To reach the finish you must roll the **exact** number (on by default). Finishing earns a bonus by finishing order (1st +10, 2nd +7, …), however you got there.
4. The game ends when all players reach the finish. **Winner = most points.** Then **🔁 Rematch** (same players and settings, new board) or **New game setup**.

**GM controls** (⚙️ on the game screen): adjust score, move a player, skip their next turn, **sit out / rejoin** (skipped in turn order but keeps their place and score), and remove a network player. Score/move/skip changes appear in the move history and can be undone.

**📺 Presentation mode** (for a TV mirrored from the laptop): click 📺 next to the zoom buttons, or press **P**. The game goes full screen, the board fills the screen, and the current player, dice, timer and scoreboard are drawn bigger. GM controls, the game log, manual dice and the timer buttons are behind the small ⚙️ in the top corner. **Esc** (or ✕) goes back. Works offline too.

**Undo:** while a space card is open, Undo cancels just that turn (back to before the roll). Between turns, it undoes the last turn or GM change.

### Network game (V2)

1. The host starts the server, opens `http://localhost:3000`, chooses edition, length and board, picks **📱 On phones** in ④ Players, and clicks **Open lobby**.
2. The lobby shows a **QR code**, the join address and a 4-digit Game ID (e.g. `4823`).
3. Players **scan the QR code** with their phone camera (the Game ID is filled in), or open the address and type the ID, then set their name/badge. Latecomers can join mid-game: *GM controls → 📱 Show join code*.
4. The host clicks Start and the game begins. (Joined with the wrong name or badge? Tap *← Leave* in the phone lobby and join again.)
5. The turn before yours, your phone shows *"You're next — get ready!"*. On your turn it buzzes (where supported) and shows an active **Roll Dice** box (green glow). Tap to roll.
6. After rolling, your phone shows the die result while the GM resolves the space on the host screen.
7. **Questions are answered on your phone**: tap Easy or Hard, then tap A / B / C. The host scores it automatically and both screens show the right answer. Open questions appear on your phone too; say the answer out loud and the GM judges it. (The GM can still answer for you on the host. Rule: *Rules → Questions → Players answer on their phone*.)
8. Your phone then shows your space card. **Action cards appear only on the performer's phone** ("🤫 Only you can see this"). The host screen shows it only if the GM taps *show card*.
9. The activity feed on your phone shows what happened (score gained/lost, movements, etc.).
10. If your phone screen turns off and back on, it reconnects and resumes automatically. If the host refreshes, phones show "host disconnected" until the host is back.
11. The GM can click a specific die face on the host screen to use a physical dice result instead of rolling digitally.
12. Clicking **Play again** (or Cancel in the lobby) closes the game for everyone. Finished or abandoned games are cleaned up automatically on the server.

---

## LocalStorage keys

The full list of saved keys (game save, preferences, asked questions/cards, phone sessions) is in `TRIVENTUREX-DESIGN.md` → *State & Persistence*.

---

## Roadmap

### V1: Complete ✅
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

### V2: Local network multiplayer ✅ Complete
- Node.js + Express + Socket.IO server
- Host opens full board view; players join on phones via 4-digit Game ID
- Players set their own name/badge from their device
- CSS dot-based dice: no images, renders on all devices
- Single action box on player screen: dice → rolled result → space card → activity feed
- Rejoin on refresh / screen-off: token-based session, auto-rejoined on reconnect
- GM controls, manual dice selection, skipped turns broadcast to phones

### V2.1: Code review & hardening ✅ (2026-10)
- 18 bugs fixed (network turn flow, player management, question tracking, security), see `CHANGELOG.md`
- One turn pipeline; clear host/server state ownership; `game.js` split into focused files
- Content build + checker (`npm run build:content`), digital action cards
- ~200 automated tests (`npm test`)

### Next: gameplay
- See *Phase 5* in `IMPROVEMENT-PLAN.md` (endgame pacing, score balance, answering on the phone, …)

### Future ideas
- Sound effects (dice roll, correct answer, finish fanfare)
- More editions: same engine, different content (start from `game_editions/template/`)
- Football Quest subcategory/topic structure
- Team mode
- Online multiplayer (beyond local Wi-Fi)
