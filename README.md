# Triventurex

## About the game

Triventurex is a board game for families and groups, played on a laptop or TV with phones as optional controllers. Players take turns rolling the dice and moving along a winding path from start to finish. Every space they land on does something, and the player with the most points at the end wins.

- **Questions**: answer a quiz question. Players pick an easy or a hard one; harder questions are worth more.
- **Action cards**: act it out, explain it without the key words, or hum it, while the others guess. Both the performer and the first correct guesser score.
- **Good and bad cards**: a short story with an effect that helps or hinders, such as gaining or losing points, moving forward or back, skipping a turn or rolling again.
- **Landmarks**: famous places along the way, with a photo and a short description. Reaching one can earn points.
- **Skip spaces**: miss your next turn.
- **The finish**: players who arrive earlier earn a bonus, and the game ends when everyone is there.

Each **edition** is its own content pack with its own questions, cards, landmarks, wording and colours. The engine stays the same, so a new topic only needs new content. Points and most rules can be changed per game.

**The name:** *Triventurex* = **Tri**via + Ad**venture** + **X**. *Tri* also stands for the three core mechanics (questions for knowledge, action cards for performance, good and bad cards for luck and choices). *Venture* is the journey along the board, and *X* is the interchangeable edition.

---

## Game Editions

| Edition | Status | Points name | Finish | Questions | Action cards | Landmarks |
|---|---|---|---|---|---|---|
| Swab Quest | ✅ Live | Sawab | Al-Ka'ba, Mecca | 432 | 26 | 20 mosques & Islamic sites |
| Football Quest | ✅ Live | Goals | The Final | 92 | 25 | 20 iconic stadiums & venues |
| World Tour | ✅ Live | Stamps | Home Again | 220 | 25 | 26 world wonders |
| Animal Safari | ✅ Live | Paw Prints | Safari Lodge | 220 | 25 | 26 wild places & reserves |
| Prophets' Stories | 🔍 In review | Noor | Al-Ka'ba, Mecca | 221 | 25 | 24 blessed places from the stories |

Every edition also gets **40 general action cards** (`game_editions/shared/`), mixed in with its own. Switch them off in ⚙️ Rules → Action cards. Ideas for further editions, and how one is built, are in [`game_editions/IDEAS.md`](game_editions/IDEAS.md).

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
npm test                  # all tests (~440, a few seconds): server, turn flow, board generation, rules, stats, content
npm run build:content     # check every edition's CSV content (and the shared action cards), then regenerate questions.js / deeds.js / actions.js
npm run check:content     # check only: fails on content errors or out-of-date generated files
node scripts/commons-image.js search "Eiffel Tower"   # find free-licence landmark photos on Wikimedia Commons (see IDEAS.md)
node scripts/review-sheet.js <edition>                 # printable question review sheet (REVIEW.md) for someone without the game
npm run build:icons                                    # bundle the icons the game uses (names in js/shared/icon-registry.js; emoji in content) — run after adding one
npm run check:icons                                    # check only: fails if the bundled icons are out of date
```

- **`CHANGELOG.md`**: what changed, release by release
- **`TRIVENTUREX-DESIGN.md`**: design decisions and how the pieces fit together
- **`game_editions/IDEAS.md`**: ideas for new editions, content targets per edition, and how an edition is built
- **Icons**: an edition changes icons in one `ICONS` block in its `config.js` (`tileGoodDeed: '⚽'`) — see `game_editions/template/README.md`. Engine code uses icons by name — `icon('undo')`, `<i data-icon="undo"></i>` — from `js/shared/icon-registry.js` (Lucide line icons for controls, Fluent Emoji Flat for game symbols). New icon: add a name there and run `npm run build:icons`. To try other icons, open `/tools/icon-picker.html`. Details in `CLAUDE.md` → Icons
- **`CLAUDE.md`**: detailed architecture rules and invariants (also the brief for AI assistants)

---

## Project structure

```
Triventurex/
│
├── index.html                    Host page (single device or network host)
├── player.html                   Phone page for network players
├── display.html                  TV display: read-only second screen (/display?game=ID)
├── academy.html                  🎓 Triventurex Academy: learn an edition's questions (/academy, works from disk)
├── server.js                     Node.js + Socket.IO server (V2)
├── package.json                  Dependencies (express, socket.io) + npm scripts
│
├── js/                           Engine: mechanics only, no edition content
│   ├── shared/                   No page access at load time; used by more than one place
│   │   ├── config.js             ← All engine settings (start here)
│   │   ├── utils.js              esc(): HTML escaping for player-supplied text
│   │   ├── icon-registry.js      Every icon by name (ICONS, ICON_OVERRIDES) + badges and badge colours
│   │   ├── icons.js              icon() / iconText(), data-icon placeholders, emoji → bundled images
│   │   ├── help.js               In-game help: all help text + the help window (? button / ? key)
│   │   ├── icons-data.js         Generated: bundled line icons (npm run build:icons)
│   │   ├── players.js            Player model: create, move, score, sort
│   │   ├── turn.js               Pure turn logic: next player, undo snapshots, history rows
│   │   ├── csv.js                CSV parsing for questions / deeds / action cards
│   │   ├── dice.js               CSS dot-die rendering + roll animation
│   │   ├── rules.js              Per-game rules model: defaults → preset → changes
│   │   ├── board.js              Board generation + rendering (host + TV display)
│   │   ├── viewport.js           Pan / zoom / fit / board background (host + TV display)
│   │   ├── edition.js            Edition config merge + colours (host + TV display)
│   │   ├── stats.js              End-screen stats + awards
│   │   ├── questions.js          Question tree / search / marked-questions report
│   │   ├── marks.js              🚩 Marked questions + reviewed ticks (host page and Academy)
│   │   ├── academy.js            Academy rounds, flashcard sets, print sheets
│   │   ├── path-design.js        Drawing board paths (✏️ Boards tab)
│   │   └── socket-client.js      TX_NET: Socket.IO layer, safe no-ops when offline
│   ├── host/                     Host page only
│   │   ├── game.js               Shared game state, start / resume / reset, bootstrap (loaded last)
│   │   ├── turn-flow.js          The turn pipeline, undo, GM controls
│   │   ├── net-host.js           Host side of network play (lobby, sync, socket events)
│   │   ├── ui.js                 Modals (question, deed, action, landmark), scoreboard, timer, history
│   │   ├── setup.js              Setup screen, player rows
│   │   ├── setup-flow.js         New game tab: steps ① Edition → ④ Players, summary + Start
│   │   ├── board-picker.js       Board thumbnails for the chosen length
│   │   ├── rules-panel.js        ⚙️ Rules tab; gameRules()
│   │   ├── badge-picker.js       Badge (emoji + colour) picker
│   │   ├── category-filter.js    3-level question topic filter
│   │   ├── edition-loader.js     Edition loading, colours, branding
│   │   ├── question-explorer.js  Setup tab 📚 Questions + 🚩 report during play
│   │   ├── board-designer.js     Setup tab ✏️ Boards: draw, save, play a board
│   │   ├── presentation.js       📺 Presentation mode
│   │   ├── help-host.js          Which help the host's ? button opens (setup tab, lobby, game)
│   │   └── storage.js            Saved game, preferences, custom boards, marked questions
│   ├── player/
│   │   └── player.js             Phone screen logic
│   ├── display/
│   │   └── display.js            TV display logic
│   ├── academy/
│   │   ├── academy.js            Academy page: edition, filter, mode switching
│   │   └── modes.js              The Academy's nine modes
│   └── vendor/
│       └── qrcode.js             QR codes for joining (qrcode-generator, MIT — don't edit)
│
├── css/styles.css                All styling (colours driven by edition config)
├── css/academy.css               Academy page styling
├── css/help.css                  The ? help button and help window (host, phones, Academy)
├── images/                       Setup screen game-length illustrations; emoji/ = bundled Fluent Emoji images
├── scripts/                      Node-only dev tooling: content build + checker, icon bundler, review sheet, Wikimedia Commons image tool (not served)
├── tools/icon-picker.html        Try other icons for the engine or an edition → a list of changes to apply
├── tools/path-designer.html      Older standalone board path designer (the ✏️ Boards tab replaces it)
├── test/                         Automated tests (npm test)
│
└── game_editions/
    ├── editions.js               ← Edition registry (add new editions here)
    ├── IDEAS.md                  Edition ideas + how we build an edition (steps, images, credits)
    ├── shared/                   General action cards mixed into every edition (actions.csv → actions.js)
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
    ├── football-quest/           Football trivia edition (same layout)
    │
    ├── world-tour/               Travel & geography edition (same layout, plus OUTLINE.md and CREDITS.md for its photos)
    │
    ├── animal-safari/            Animals & wild places edition (same layout as world-tour)
    │
    └── prophets-stories/         Stories of the prophets, Ahmadiyya understanding (plus REVIEW.md, a printable question review sheet)
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

Pick a theme and check its size against the content targets in [`game_editions/IDEAS.md`](game_editions/IDEAS.md) (20+ landmarks, 50+ deeds, 25+ actions, 200+ questions).

1. Copy `game_editions/template/` to `game_editions/<your-id>/`. The template already has the standard board mix (`SPACE_DISTRIBUTION`).
2. Edit `config.js`, `questions.csv`, `deeds.csv`, `actions.csv` and add your images (column guide: `game_editions/template/README.md`). Landmark photos from Wikimedia Commons: `node scripts/commons-image.js` finds, crops and credits them (list the credits in `CREDITS.md`).
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
| `RULES` | Defaults for `exactFinish`, `questionTracking` (per game: the ⚙️ Rules tab) |
| `BOARD_SIZES` | Typical spaces per game length (used by the rules panel's tile preview) |
| `GRID_SIZE` | Board grid dimensions (default 12×12) |
| `SPACE_DISTRIBUTION` | Ratio of each non-question space type (questions fill the remainder) |
| `SPACE_INFO` | Icon, label, colour per space type |
| `ACTION_KINDS` | Action card kinds (act / explain / sound): icon, label, rule |
| `RULE_PRESETS` | Rule presets for the rules panel (Family, Kids, Quiz night) |
| `PLAYERS` | Default names, colours, badges (the picker's badges and colours: `BADGES`, `BADGE_COLORS` in `js/shared/icon-registry.js`) |
| `FINISH_BONUS` | Score bonus for finishing order |
| `SCORE_VALUES` | Points for questions, actions, landmarks (every label in the game reads these) |
| `ZOOM` | Max zoom-in (200%), zoom-out factor |
| `TIMER` | Default timer duration per space type |
| `ANIMATION` | Token hop speed, flyout duration, dice overlay |
| `AWARDS`, `AWARD_MIN_ROLLS` | End-screen awards: icon, title, text (editions can rename); rolls needed for the roller awards |
| `PRESENTATION` | 📺 presentation mode: shortcut key, how much bigger, board fill limit, pointer hide delay |
| `PATH_TEMPLATES` | Board path shapes per game length |

Editions can override `SPACE_DISTRIBUTION` in their own `config.js`, either as a flat object (same for all game lengths) or keyed by `short`/`medium`/`long`. The template ships Swab Quest's mix (10% action / good / bad deeds, 8% landmarks, 5% skips). They can also override `SCORE_VALUES` (defaults: easy 1, hard 2, landmark 3), `FINISH_BONUS` and `AWARDS`.

Server settings are at the top of `server.js`: `PORT` (env), and `ROOM_TTL`, which controls how long a finished or host-less room is kept.

---

## Game rules (in-game)

Rules have their own **⚙️ Rules** tab on the setup screen, with side tabs per section (Scoring, Questions, Action cards, Board, Turn & pace, Topics). Changes are saved as you make them; **↺ Reset to preset** undoes them. Rules are remembered **per edition**, and a running game keeps its own copy (also after a resume).

**Presets** set many rules at once: *Family* (the standard game), *Kids* (easy questions, no going backwards, more action) and *Quiz night* (questions count double, timer, more question tiles). After changing anything, the summary shows "N changed". **📋 Copy as preset** turns the current rules into a few lines of JSON you can paste into `RULE_PRESETS` in `js/shared/config.js` as a new preset.

| Section | Rules (default) |
|---|---|
| Scoring | Easy/hard question points (1/2) · action performer/guesser (1/1) · finish bonus: Standard 10/7/5…, Small 5/3/2/1 or Off · landmark points when **landing by a roll** (+3), **sent there by a good deed** (0), **sent back there by a bad deed** (0); each can be negative, 0 = just information · allow negative scores (off) |
| Questions | Difficulty: player chooses / always easy / always hard · auto-start timer (off) and its seconds (30) · avoid repeats: remember across games / reset every game · **players answer on their phone** (on; network games) · **question topics** (category > subcategory > topic) |
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
- Optional file. These cards are mixed with the **general cards** in `game_editions/shared/actions.csv` (same columns; edit it and run `npm run build:content shared`). With no cards at all, action spaces ask players to draw from a physical deck.

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
- Recommended image: landscape 4:3, 800×600 JPG (the game crops it wide on cards and square on the board, so keep the subject in the middle). `scripts/commons-image.js` produces this from a Wikimedia Commons photo and records the credit

---

## Gameplay summary

New to the game? Press the **?** button on any screen (or the ? key) — it explains what you can do there, in the edition's own words.

1. The setup screen has four tabs: **🎲 New game**, **⚙️ Rules**, **📚 Questions** and **✏️ Boards**. On *New game*: ① edition → ② game length → ③ board (🎲 Random or a path, shown as thumbnails) → ④ players. Each choice moves on to the next step; collapsed steps show what's chosen, and the footer shows the whole setup next to **Start**. Next time everything is pre-filled with your last choices, so it's usually just Start.
2. On your turn, roll the dice. Your token hops to a space and its event triggers:
   - **Question**: choose Easy (+1) or Hard (+2), answer, then the GM reveals the answer
   - **Action**: perform the card (act / explain / hum). Performer and first correct guesser each earn +1.
   - **Good Deed / Good Play**: one effect applied automatically (varies each game)
   - **Bad Deed / Foul Play**: one effect applied automatically (varies each game)
   - **Landmark / Stadium**: points by the rules (default +3 when landing by a roll; also settable for arriving via a deed)
   - **Skip**: lose your next turn
3. To reach the finish you must roll the **exact** number (on by default). Finishing earns a bonus by finishing order (1st +10, 2nd +7, …), however you got there.
4. The game ends when all players reach the finish. **Winner = most points.** The end screen also shows each player's stats (questions right, actions guessed, average roll, spaces travelled) and fun awards — 🧠 Quiz master, 🍀 Lucky roller, 🐢 Unluckiest roller and more (names set in `CONFIG.AWARDS`, editions can rename them). Then **🔁 Rematch** (same players and settings, new board) or **New game setup**.

**GM controls** (⚙️ on the game screen): adjust score, move a player, skip their next turn, **sit out / rejoin** (skipped in turn order but keeps their place and score), and remove a network player. Score/move/skip changes appear in the move history and can be undone.

**📺 Presentation mode** (for a TV mirrored from the laptop): click 📺 next to the zoom buttons, or press **P**. The game goes full screen, the board fills the screen, and the current player, dice, timer and scoreboard are drawn bigger. GM controls, the game log, manual dice and the timer buttons are behind the small ⚙️ in the top corner. **Esc** (or ✕) goes back. Works offline too.

**✏️ Designing boards:** the setup screen's **✏️ Boards** tab: pick the game length and grid size, click a cell for the start, then click cells in a straight line to add runs (↩ Undo takes the last one back). The preview shows the board and its number of spaces. **💾 Save board** adds it to *My boards* and to the board picker (marked ✏️); **▶ Play this board** saves it and chooses it for the next game; **📋 Copy as template** gives a line to paste into `CONFIG.PATH_TEMPLATES` so everyone gets it. *Start from a board…* copies a built-in board to change.

**🚩 Reporting questions:** a question card on the host has *🚩 Report this question* (with an optional note) — for a wrong answer, a typo or an unclear question. The setup screen's **📚 Questions** tab lists every question by category › subcategory › topic, with search, a difficulty filter and *Show answers*. Mark or unmark questions there too, filter *🚩 Marked only*, and **📋 Copy marked list** to fix them in `questions.csv` (marks are kept per edition until you clear them).

**🎓 Triventurex Academy** (`academy.html`, or `http://<host>:3000/academy`; also 🎓 Academy in the 📚 Questions tab): learn an edition's questions before playing. Works opened from disk too. Pick the edition at the top and what to learn on the left (topic tree, difficulty, search); then choose a mode. Every mode shows questions on the same white cards with the edition's colour:
- **📚 Explore**: every question with its answer and note; 🚩 mark one as wrong / unclear (the same marks as in the game, in the same browser)
- **🃏 Flashcards**: a set of 8 (4 × 2), 9 (3 × 3) or 1 card in random order — guess, tap a card to turn it (or 🔄 Turn all), then *Next set →*
- **✏️ Quiz**: rounds of 5 / 10 / 20 with a score and the questions to look at again
- **🧩 Match**: tap a question, then its answer
- **✔️ True or false**: is the answer shown right?
- **⚡ Speed round**: as many as you can in 60 seconds
- **🗺️ Places**: the edition's landmarks with photos and descriptions, and a *🧭 Where am I?* game
- **🖨️ Print cards**: the chosen questions as same-size cards — **double-sided** (8 per A4 page, answers on the next page, mirrored so each lands behind its question; print on both sides, flip on the long edge, 100% scale) or **fold-over** (4 per page, fold line in the middle of every card)
- **🔍 Review**: for reviewers — tick each question as reviewed, mark problems with a note, see progress, **📋 Copy report**

**Undo:** while a space card is open, Undo cancels just that turn (back to before the roll). Between turns, it undoes the last turn or GM change.

### Network game (V2)

1. The host starts the server, opens `http://localhost:3000`, chooses edition, length and board, picks **📱 On phones** in ④ Players, and clicks **Open lobby**.
2. The lobby shows a **QR code**, the join address and a 4-digit Game ID (e.g. `4823`).
3. Players **scan the QR code** with their phone camera (the Game ID is filled in), or open the address and type the ID, then set their name/badge. Latecomers can join mid-game: *GM controls → 📱 Show join code*.
4. Someone without a phone? Type their name under the player list in the lobby (*No phone? Add a player by name*) — they play on the host screen: the GM rolls for them and handles their cards. Also possible mid-game in *GM controls*. A game can even run with no phones at all. In the lobby the host can click any player's badge (including their own) to change its icon and colour; phones pick up the change. During the game the GM can do the same (*GM controls → 🎨*).
5. The host clicks Start and the game begins. (Joined with the wrong name or badge? Tap *← Leave* in the phone lobby and join again.)
6. The turn before yours, your phone shows *"You're next — get ready!"*. On your turn it buzzes (where supported) and shows an active **Roll Dice** box (green glow). Tap to roll.
7. After rolling, your phone shows the die result while the GM resolves the space on the host screen.
8. **Questions are answered on your phone**: tap Easy or Hard, then tap A / B / C. The host scores it automatically and both screens show the right answer. Open questions appear on your phone too; say the answer out loud and the GM judges it. (The GM can still answer for you on the host. Rule: *Rules → Questions → Players answer on their phone*.)
9. Your phone then shows your space card. **Action cards appear only on the performer's phone** ("🤫 Only you can see this"). The host screen shows it only if the GM taps *show card*.
10. The activity feed on your phone shows what happened (score gained/lost, movements, etc.). Phones use the edition's words, icons and tile names (e.g. *Goals*, *Good Play*), and the lobby and game screens show the edition, game length and board — as does the host's lobby.
11. **📺 TV display**: in the lobby (or *GM controls*) click **📺 Open TV display** and drag the window to the TV (or open the shown address on a smart TV). The TV shows the lobby QR code, then the board, tokens, scoreboard, dice, timer and the open card — never an unrevealed answer or an action card. The laptop keeps all the controls.
12. If your phone screen turns off and back on, it reconnects and resumes automatically. If the host refreshes, phones show "host disconnected" until the host is back.
13. The GM can click a specific die face on the host screen to use a physical dice result instead of rolling digitally.
14. **New game setup** on the end screen (or ← Back in the lobby) closes the game for everyone; **🔁 Rematch** keeps the room and the phones. Finished or abandoned games are cleaned up automatically on the server.

---

## LocalStorage keys

The full list of saved keys (game save, preferences, asked questions/cards, phone sessions) is in `TRIVENTUREX-DESIGN.md` → *State & Persistence*.

---

## Roadmap

### V1: Complete ✅
- Edition-neutral engine (Swab Quest, Football Quest, World Tour, Animal Safari, Prophets' Stories)
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

### V2.2: Gameplay & play experience ✅ (2026-10)
- Setup screen with tabs and a step-by-step New game flow; rules panel with presets; visual board picker; 🔁 Rematch
- Join by QR code; *"You're next"*; leave the lobby; answering questions on the phone; players without a phone
- 📺 Presentation mode and a 📺 TV display (second screen)
- End-screen stats and awards; 🚩 question reporting + 📚 Questions tab; ✏️ board designer
- ~310 automated tests — details in `CHANGELOG.md`

### Unreleased (2026-10)
- **Help on every screen**: a ? button opens help for the screen you are on (setup tabs, lobby, game, phone, every Academy mode), with *How to play* for everyone
- **Last turn** line on the board (what just happened), **What we learned today** on the end screen, and a printable **rules card** (Rules tab)
- **🎓 Triventurex Academy** (academy.html): explore, flashcards, quiz, match, true or false, speed round, places, print cards and a reviewer mode
- **Icons**: Fluent Emoji (game symbols) and Lucide (controls) everywhere, used by name; editions change icons in one `ICONS` block; `tools/icon-picker.html` to try other icons
- **Phones**: the same badges and colours as the host; the edition's words, icons and tile names; an edition banner on the phone and host lobby
- **World Tour** 🌍, **Animal Safari** 🦁 and **Prophets' Stories** 📖 editions; 40 general action cards for every edition; landmark points 3 by default; Rules tab as a one-line action bar with the same control style as the other tabs; Wikimedia Commons image tool — details in `CHANGELOG.md`

### Future ideas
- Sound effects (dice roll, correct answer, finish fanfare)
- *Steal*: others answer when the active player gets a phone question wrong
- Content review: the draft action cards in both editions, and the Football Quest notes flagged in 2.1 (truncated notes; possible factual errors in #66, #70, #73, #86) — mark them in the 📚 Questions tab
- More editions: same engine, different content. Ideas and sizing in `game_editions/IDEAS.md`; start from `game_editions/template/`
- More questions in every edition, and a Football Quest revisit (more questions, a proper category structure)
- First-game walkthrough; celebrations (landmark, finish, hard question); kids mode on the phone (bigger buttons, read aloud); fun facts on the TV between turns
- Team mode
- Online multiplayer (beyond local Wi-Fi)

Decided against (2026-10): endgame pacing rules (the GM can move a player or set the dice) and streaks / wagers / a final round.

---

## Credits

- **Emoji**: [Microsoft Fluent Emoji](https://github.com/microsoft/fluentui-emoji) (Flat), MIT License — bundled in `images/emoji/` (licence in `images/emoji/LICENSE.txt`)
- **Control icons**: [Lucide](https://lucide.dev), ISC License — bundled in `js/shared/icons-data.js`
- **Landmark photos** (World Tour, Animal Safari, Prophets' Stories): Wikimedia Commons — authors and licences in each edition's `CREDITS.md`
- **QR codes**: qrcode-generator by Kazuhiko Arase, MIT License (`js/vendor/qrcode.js`)
