# Edition template

Starter folder for a new Triventurex edition.

## Make a new edition

1. Copy this folder to `game_editions/<your-id>/`.
2. Edit `config.js`: the name, icon, points name, colours, landmarks and `SPACE_INFO`. Each option is explained in the file.
3. Edit `questions.csv`, `deeds.csv` and `actions.csv` (columns are described below). A spreadsheet app works fine. Save as CSV.
4. Run `npm run build:content <your-id>`. It checks the content and writes `questions.js` / `deeds.js` / `actions.js`. Those are the copies used when `index.html` is opened straight from disk. Never edit them by hand.
5. Add your edition to `game_editions/editions.js`.

`npm run check:content` checks every edition without writing anything. `npm test` runs the same checks.

**Any field that contains a comma must be in "double quotes".** Without them the row's columns shift and the question or deed silently breaks. The checker reports it as `N columns, expected M`.

## questions.csv

| Column | Meaning |
|---|---|
| `id` | Unique whole number. **Never reuse or renumber**: "already asked" tracking is stored by id. A new question gets the next unused number. |
| `question` | The question text |
| `type` | `multi` (multiple choice) or `open` (spoken answer) |
| `answer` | `multi`: the number of the correct option (1 = `opt_a` … 4 = `opt_d`). `open`: the answer text. |
| `opt_a` … `opt_d` | Options for `multi` (at least 2). Leave empty for `open`. |
| `difficulty` | `easy` or `hard` |
| `category`, `subcategory`, `topic` | The 3-level filter in Game Settings. If you use topics, give every question one. |
| `note` | Optional, shown to the GM after the answer is revealed |

## deeds.csv

| Column | Meaning |
|---|---|
| `type` | `good` or `bad` |
| `text` | Card text read aloud. `{landmark}` is replaced by the landmark the card moves to. |
| `effect`, `value`, `landmark` | The card's effect (see below) |
| `effect_2/3`, `value_2/3`, `landmark_2/3` | Optional alternatives. One effect is picked at random each game. |
| `mood` | Optional flavour tag (blessing, social, challenge, reflection, funny, risk…) |

### Effects

| Effect | `value` means |
|---|---|
| `score_add` / `score_remove` | points gained / lost |
| `move_forward` / `move_back` | spaces moved |
| `move_to_next_landmark` / `move_to_prev_landmark` | which landmark: 1 = nearest ahead / behind, 2 = the one after, … (needs `LANDMARKS` in config.js) |
| `move_to_landmark` | ignored. Put the exact landmark name from `LANDMARKS` in the `landmark` column. |
| `skip_turn` | ignored (use 0). The player skips their next turn. |
| `extra_turn` | ignored (use 0). The player rolls again. |
| `all_players_gain` / `all_players_lose` | points for every player |
| `protection` | ignored (use 1). Cancels the player's next bad deed. |

Board generation places deeds sensibly. For example, `move_back 3` never appears within the first 3 spaces.

## actions.csv

Optional. Without it, action spaces ask players to draw a card from a physical deck.

| Column | Meaning |
|---|---|
| `id` | Unique whole number. Never reuse or renumber: cards are not repeated until all have been used, tracked by id. |
| `text` | The card, e.g. `Act out a goalkeeper saving a penalty` or `Explain 'offside' without saying offside, line or defender` |
| `kind` | `act` (mime: no words, no sounds), `explain` (describe without the key words) or `sound` (hum or make sounds, no words) |
| `note` | Optional extra rule for this card, shown with it |

In a network game the card appears **only on the performer's phone**. Otherwise the host screen keeps it hidden until the performer taps *Show card* while everyone else looks away.
