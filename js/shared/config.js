/**
 * config.js
 * Triventurex engine configuration — mechanics only.
 *
 * Edition-specific values (name, colours, landmarks, background, space overrides)
 * live in game_editions/<edition>/config.js and are merged into CONFIG at
 * startup via _mergeEditionConfig() in game.js.
 *
 * ENGINE defaults below are used as fallbacks if no edition is loaded.
 */

const CONFIG = {

  // Engine-level brand defaults (overridden by active edition's GAME block)
  GAME: {
    engineName:   'Triventurex',
    editionName:  '',          // set by edition
    editionIcon:  '🎯',
    subtitle:     '',
    gameIdPrefix: 'TX',
    pointsName:   'pts',      // overridden by edition (e.g. 'Sawab', 'Goals')
    // Finish space and end-screen text — overridden by edition
    finishLabel:      'Finish',                       // name of the finish space on the board
    finishCelebration: 'Well done! 🎉',               // body text in the finish modal
    finishButtonLabel: '🎉 Celebrate!',               // button in the finish modal
    endScreenMessage:  'All players have reached the finish!', // subtitle on the end screen
  },

  BOARD_SIZES: {
    short: 20,
    medium: 40,
    long: 60,
  },

  /**
   * GRID_SIZE — default board dimensions for all game lengths.
   * Change here to resize all boards at once. Individual PATH_TEMPLATES
   * can override with their own gridRows / gridCols if needed.
   */
  GRID_SIZE: { rows: 12, cols: 12 },

  // Proportion of each non-question space type in the middle section of the board.
  // Questions always fill whatever space remains — no 'question' key needed here.
  // Edition config.js files can override this per game length (short/medium/long).
  SPACE_DISTRIBUTION: {
    action:    0.15,
    good_deed: 0.15,
    bad_deed:  0.15,
    landmark:  0.10,
    skip:      0.05,
  },

  // Space type definitions — engine level.
  // Editions can override individual entries via EDITION_CONFIG.SPACE_INFO.
  // Colors here are neutral engine defaults; editions should override them.
  SPACE_INFO: {
    start:     { icon: '🚩', label: 'Start' },
    finish:    { icon: '🏁', label: 'Finish' },
    question:  { icon: '❓', label: 'Question',  color: '#3c8aef' },
    action:    { icon: '🎬', label: 'Action',    color: '#9526c0' },
    good_deed: { icon: '✅', label: 'Good', color: '#62ad65' },
    bad_deed:  { icon: '❌', label: 'Bad',  color: '#ed5653' },
    landmark:  { icon: '🌍', label: 'Landmark',  color: '#fbe092' },
    skip:      { icon: '⏭', label: 'Skip',      color: '#9E9E9E' },
  },

  // Engine-level colour fallbacks (overridden by active edition's COLORS block).
  // These match the fallbacks in styles.css :root.
  COLORS: {
    '--green':       '#2E7D32', '--green-dark':  '#1B5E20', '--green-light': '#E8F5E9',
    '--blue':        '#1565C0', '--gold':        '#F9A825', '--danger':      '#C62828',
    '--bg':          '#F0EBE0', '--card':        '#FFFFFF', '--text':        '#1A1A1A',
    '--text-muted':  '#666666', '--border':      '#E0E0E0',
    '--c-start':     '#00695C', '--c-finish':    '#FFD700',
    '--gradient-a':  '#f2b933', '--gradient-b':  '#2E7D32', '--gradient-c':  '#1565C0',
    '--vp-a':        '#C8E6C9', '--vp-b':        '#B2DFDB', '--vp-c':        '#C5CAE9',
    '--deed-good-bg': '#E8F5E9', '--deed-good-text': '#1B5E20',
    '--deed-bad-bg':  '#FFEBEE', '--deed-bad-text':  '#C62828',
  },

  /**
   * ZOOM — board zoom limits.
   *
   * maxScale  – maximum zoom-in factor.  2.0 = 200% (spaces appear 2× bigger).
   * outFactor – how far below the fit-to-screen scale the user can zoom out.
   *             0.65 ≈ 2 presses of the "−" button below the default fit view.
   *             Lower = more zoom-out allowed. Never goes below 0.15.
   */
  ZOOM: {
    maxScale:  2.0,
    outFactor: 0.65,
  },

  /**
   * ANIMATION — visual effect timings.
   * Change tokenHopMs to make token movement faster or slower.
   * Set to 0 to disable animation entirely.
   */
  ANIMATION: {
    tokenHopMs:    400,   // ms per space when token moves (e.g. 400 = 6 spaces in 2.4s)
    flyoutMs:      1000,  // ms for the score +/− flyout to fade out
    diceOverlayMs: 900,   // ms the large dice result is shown on the board before token moves
  },

  /**
   * AWARDS — fun awards on the end screen (G13), worked out from the game's
   * history by js/shared/stats.js. Editions may rename any of them in their
   * config.js (AWARDS: { quizMaster: { title: 'Golden boot' } }).
   * In `text`: {n} = the value, {s} = "s" unless {n} is 1, {good} / {bad} /
   * {landmark} = the edition's space labels, {points} = its points name.
   * minRolls – roll awards need at least this many rolls per player.
   */
  AWARDS: {
    quizMaster:    { icon: '🧠', title: 'Quiz master',       text: '{n} question{s} right' },
    performer:     { icon: '🎭', title: 'Star performer',    text: '{n} action{s} guessed' },
    goodDeeds:     { icon: '😇', title: 'Do-gooder',         text: '{n} × {good}' },
    badDeeds:      { icon: '😈', title: 'Trouble magnet',    text: '{n} × {bad}' },
    explorer:      { icon: '🌍', title: 'Explorer',          text: '{n} × {landmark}' },
    bigTurn:       { icon: '🚀', title: 'Big moment',        text: '+{n} {points} in one turn' },
    luckyRoller:   { icon: '🍀', title: 'Lucky roller',      text: 'average roll {n}' },
    unluckyRoller: { icon: '🐢', title: 'Unluckiest roller', text: 'average roll {n}' },
    patience:      { icon: '⏳', title: 'Patience award',    text: '{n} turn{s} skipped' },
  },
  AWARD_MIN_ROLLS: 3,

  /**
   * PRESENTATION — 📺 presentation mode (G15): full screen for a TV mirrored
   * from the laptop. The GM panel, game log and manual dice are tucked behind ⚙️.
   *
   * key          – keyboard shortcut that turns it on/off (Esc also leaves)
   * scale        – how much bigger the sidebar and space cards are drawn
   * maxFitScale  – how far the board may be enlarged to fill the screen
   *                (normal mode never draws spaces bigger than 100%)
   * cursorHideMs – the mouse pointer hides after this long without moving (0 = never)
   */
  PRESENTATION: {
    key:          'p',
    scale:        1.35,
    maxFitScale:  1.8,
    cursorHideMs: 3000,
  },

  // Action card kinds (actions.csv `kind` column). Shown on the host modal and
  // sent to the performer's phone with the card.
  ACTION_KINDS: {
    act:     { icon: '🎭', label: 'Act it out',   rule: 'No words, no sounds — just actions.' },
    explain: { icon: '💬', label: 'Explain it',   rule: "Describe it without saying the word(s) on the card." },
    sound:   { icon: '🎵', label: 'Hum or sound', rule: 'Hum or make sounds — no words.' },
  },

  /**
   * RULE_PRESETS — named rule sets for the rules panel (G12).
   * A game's rules = defaults (engine + edition) → a preset's `changes` → the
   * player's own changes. `changes` only lists what differs from the defaults,
   * using the shape of the rules object in js/shared/rules.js.
   * To add a preset: set up the rules panel, click "📋 Copy as preset", paste here.
   */
  RULE_PRESETS: {
    family: {
      label: 'Family',
      description: 'The standard game',
      changes: {},
    },
    kids: {
      label: 'Kids',
      description: 'Easy questions, no going backwards, more action',
      changes: {
        questions: { difficulty: 'easy' },
        board: {
          noBackwards: true,
          tileMix: { action: 20, good_deed: 15, bad_deed: 10, landmark: 8, skip: 0 },
        },
      },
    },
    quiz: {
      label: 'Quiz night',
      description: 'Questions count more, with a timer',
      changes: {
        scoring:   { questionEasy: 2, questionHard: 4, finishBonus: 'small' },
        questions: { timerAuto: true, timerSeconds: 30 },
        board:     { tileMix: { action: 8, good_deed: 8, bad_deed: 8, landmark: 6, skip: 3 } },
      },
    },
  },

  // Timer defaults (seconds)
  TIMER: {
    question: 30,
    action:   90,
    default:  30,
  },

  // LocalStorage key for save/resume
  STORAGE_KEY: 'triventurex_save',

  /**
   * RULES — optional gameplay rule toggles.
   * These are configurable from the setup screen.
   */
  RULES: {
    // Require exact dice roll to land on finish; overshoot = no move.
    exactFinish: true,
    // 'session' = asked-question list persists across games until exhausted;
    // 'game'    = list resets at the start of every new game.
    questionTracking: 'session',
  },

  // Board background — engine default (no image). Overridden by edition.
  BOARD_BACKGROUND: {
    image:          null,
    overlayOpacity: 0.65,
    size:           'cover',
    position:       'center',
    blur:           0,
  },

  // Landmarks — empty by default; must be provided by the active edition.
  // Each entry: { name: string, image: string|null }
  // `name` must match the `landmark` field in the edition's deeds.js exactly.
  LANDMARKS: [],

  /**
   * PLAYERS — all player configuration in one place.
   *
   * defaults  – default name, colour and token for each player slot (up to 8).
   *             Players can override these in the setup screen.
   *             Their choices are saved to localStorage and restored next game.
   *
   * colors    – full palette available in the player picker.
   * tokens    – full emoji set available in the player picker.
   */
  PLAYERS: {
    defaults: [
      { name: 'Player 1', color: '#E53935', token: '🚀' },
      { name: 'Player 2', color: '#1565C0', token: '⭐' },
      { name: 'Player 3', color: '#2E7D32', token: '⚡' },
      { name: 'Player 4', color: '#F9A825', token: '🎯' },
      { name: 'Player 5', color: '#6A1B9A', token: '🏆' },
      { name: 'Player 6', color: '#00838F', token: '🌙' },
      { name: 'Player 7', color: '#BF360C', token: '🦋' },
      { name: 'Player 8', color: '#37474F', token: '🎪' },
    ],

    colors: [
      // Existing
      '#E53935', '#C62828',
      '#1565C0', '#0D47A1',
      '#2E7D32',
      '#00838F',
      '#F9A825',
      '#E65100',
      '#6A1B9A',
      '#37474F',
      '#AD1457',
      '#00695C',

      // New vibrant additions
      '#7B1FA2', // Violet
      '#512DA8', // Deep Purple
      '#3949AB', // Indigo
      '#1E88E5', // Bright Blue
      '#039BE5', // Sky Blue
      '#00ACC1', // Cyan
      '#00897B', // Turquoise
      '#43A047', // Emerald
      '#7CB342', // Lime Green
      '#C0CA33', // Lime
      '#FDD835', // Yellow
      '#FFB300', // Amber
      '#FB8C00', // Orange
      '#F4511E', // Deep Orange
      '#8D6E63', // Brown
      '#757575', // Grey
      '#546E7A', // Blue Grey
      '#D81B60', // Pink
      '#EC407A', // Bright Pink
      '#5E35B1', // Royal Purple
      '#00C853', // Neon Green
      '#00BFA5', // Aqua
      '#FF4081', // Hot Pink
      '#651FFF', // Electric Purple
    ],

    tokens: [
      // Existing
      '🚀','⭐','⚡','🎯','🏆','🌙','🦋','🎪',
      '🌟','🔥','💎','🎈','🦁','🐉','🌺','🎵',
      // Fantasy / adventure
      '🛡️','⚔️','🧭','🗺️','🏹','👑','🔮','🪄',
      '🦅','🐺','🐯','🐻','🦄','🐢','🐬','🦊',
      // Fun / playful
      '🍀','🎲','🧩','🎨','🎮','🎤','🎸','🥇',
      '🎊','🎁','🎀','🪁','🎂','🍉','🍕','🍩',
      // Cosmic / magical
      '☀️','🪐','🌈','☄️','🌌','❄️','💫','✨',
      // Nature
      '🌸','🌻','🌴','🍁','🌵','🌊','⛰️','🌋',
      // Cute/simple
      '🐼','🐸','🐵','🐧','🐞','🐙','🐝','🦜',
    ],
  },

  // Bonus score for finishing order (index 0 = 1st to finish).
  // Editions can override with FINISH_BONUS in their config.js.
  FINISH_BONUS: [10, 7, 5, 4, 3, 2, 1, 1],

  // Points awarded per event — all UI labels and scoring read from here.
  // Editions can override individual values with SCORE_VALUES in their config.js.
  SCORE_VALUES: {
    question_easy:    1,
    question_hard:    2,
    action_performer: 1,
    action_guesser:   1,
    landmark:         5,
  },

  /**
   * PATH_TEMPLATES — one or more board shapes per game length.
   * A random path is chosen each game from the available options.
   *
   * HOW TO CUSTOMISE:
   *   • Each game length is an array — add more objects to get more variety.
   *   • `start` [row, col] — 0-indexed, top-left is (0,0).
   *   • `segments` — [direction, steps] pairs.
   *       directions: 'up' | 'down' | 'left' | 'right'
   *   • `gridRows` / `gridCols` — optional per-path override.
   *       Defaults to CONFIG.GRID_SIZE if omitted.
   *
   * SPACING RULE: leave ≥1 empty cell between parallel segments.
   * All paths below are pre-verified collision-free on 12×12.
   */
  PATH_TEMPLATES: {
    short: [
      { name: 'A — L-shape winding',   start: [11,1], segments: [['right',4],['up',6],['left',4],['up',2],['right',3]] },
      { name: 'B — Upward sweep',       start: [11,1], segments: [['up',6],['right',4],['up',4],['right',5]] },
      { name: 'C — Zigzag',             start: [11,1], segments: [['right',6],['up',3],['left',5],['up',2],['right',3]] },
      { name: 'D — Diamond',            start: [11,5], segments: [['up',3],['right',3],['up',3],['left',3],['up',2],['left',3],['down',2]] },
      { name: 'E — Snake rows',         start: [11,1], segments: [['right',8],['up',2],['left',6],['up',2],['right',1]] },
      { name: 'F — S shape', start: [4,0], gridRows: 8, gridCols: 8, segments: [['right',1],['down',1],['right',1],['down',1],['right',3],['up',2],['left',1],['up',1],['left',1],['up',1],['left',1],['up',2],['right',3],['down',1],['right',1],['down',1],['right',1]] },
    ],
    medium: [
      { name: 'A — Wide spiral',        start: [11,1], segments: [['right',9],['up',9],['left',7],['down',5],['right',4],['up',3],['left',2]] },
      { name: 'B — Stepped zigzag',     start: [11,1], segments: [['right',9],['up',4],['left',7],['up',3],['right',5],['up',2],['left',3],['up',2],['right',4]] },
      { name: 'C — Three-layer',        start: [11,1], segments: [['right',9],['up',4],['left',7],['up',4],['right',7],['up',2],['left',6]] },
      { name: 'D — Canyon',             start: [11,2], segments: [['up',5],['right',3],['down',2],['right',3],['up',4],['left',2],['up',2],['right',5],['down',8],['left',5]] },
      { name: 'E — Heart', start: [9,6], segments: [['up',2],['right',1],['up',1],['right',1],['up',2],['right',2],['up',3],['left',3],['down',1],['left',1],['down',1],['left',2],['up',1],['left',1],['up',1],['left',3],['down',3],['right',2],['down',2],['right',1],['down',1],['right',1],['down',2]] },
    ],
    long: [
      { name: 'A — Clockwise spiral',   start: [11,1], segments: [['right',10],['up',10],['left',9],['down',8],['right',6],['up',6],['left',4],['down',4],['right',2]] },
      { name: 'B — Anticlockwise peel', start: [11,1], segments: [['up',10],['right',10],['down',9],['left',8],['up',7],['right',6],['down',5],['left',4]] },
      { name: 'C — Grand spiral',       start: [11,0], segments: [['right',11],['up',11],['left',10],['down',9],['right',8],['up',7],['left',3]] },
      { name: 'D — Serpentine maze',    start: [11,1], segments: [['right',9],['up',2],['left',9],['up',2],['right',8],['up',2],['left',7],['up',2],['right',6],['up',2],['left',5],['up',1],['right',4]] },
      { name: 'E — Serpentine maze 2',  start: [12,1], gridRows: 13, gridCols: 13, segments: [['right',10],['up',2],['left',9],['up',2],['right',8],['up',2],['left',7],['up',2],['right',6],['up',2],['left',5],['up',2],['right',3]] },
    ],
  },
};

// ── Engine defaults snapshot ───────────────────────────────────────────────
// Used by loadEdition() in game.js to reset CONFIG before applying a new edition.
// Must be defined AFTER CONFIG is fully built.
const _ENGINE_DEFAULTS = {
  GAME:             JSON.parse(JSON.stringify(CONFIG.GAME)),
  COLORS:           JSON.parse(JSON.stringify(CONFIG.COLORS)),
  LANDMARKS:        [],
  BOARD_BACKGROUND: JSON.parse(JSON.stringify(CONFIG.BOARD_BACKGROUND)),
  SPACE_INFO:       JSON.parse(JSON.stringify(CONFIG.SPACE_INFO)),
  SCORE_VALUES:     JSON.parse(JSON.stringify(CONFIG.SCORE_VALUES)),
  FINISH_BONUS:     [...CONFIG.FINISH_BONUS],
  AWARDS:           JSON.parse(JSON.stringify(CONFIG.AWARDS)),
};
