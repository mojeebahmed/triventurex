/**
 * icon-registry.js — every icon the game engine uses, by name.
 *
 * Engine code never types an emoji or icon symbol: it asks for a name.
 *   icon('undo')          → HTML (an inline line icon, or an emoji image)
 *   iconText('tileSkip')  → plain text, for places that cannot hold HTML
 *                           (tile labels, <option>, phone text); line icons give ''
 *   <i data-icon="undo"></i> in HTML pages (filled in by startIcons())
 * See js/shared/icons.js. `npm test` fails when engine code contains a raw
 * emoji or icon symbol outside this file.
 *
 * Each entry: '<set>:<icon>'
 *   'lucide:<name>'  a Lucide line icon (ISC) — for buttons, tabs and other controls;
 *                    drawn in the text colour of the control
 *   'emoji:<emoji>'  an emoji, drawn with the game's emoji set (Fluent Emoji Flat)
 *                    — for game symbols: tiles, cards, awards, status
 *   '<set>:<name>'   any other installed @iconify-json set (overrides — keep them few)
 *
 * Adding an icon: add a name here (say what it is for), use it, run
 * `npm run build:icons`. Editions can override any name in their config.js
 * (ICONS block) — see game_editions/template/README.md.
 */

const ICONS = {
  // ── Setup screen ────────────────────────────────────────────────────────────
  tabNewGame:      'lucide:dices',            // setup tab ① New game
  tabRules:        'lucide:settings',         // setup tab ⚙️ Rules
  tabQuestions:    'lucide:library-big',      // setup tab 📚 Questions
  tabBoards:       'lucide:pencil',           // setup tab ✏️ Boards
  onThisScreen:    'lucide:monitor',          // players play on the host screen
  onPhones:        'lucide:smartphone',       // players join from phones
  addPlayer:       'lucide:plus',
  removePlayer:    'lucide:minus',
  reset:           'lucide:rotate-ccw',       // reset players / rules to the preset
  copy:            'lucide:clipboard-copy',   // copy text (rules, marked list, template, report)
  academy:         'lucide:graduation-cap',   // open Triventurex Academy
  boardUndo:       'lucide:undo-2',           // board designer: remove the last run
  boardNew:        'lucide:sparkles',         // board designer: start a new board
  save:            'lucide:save',
  playBoard:       'lucide:play',             // play the designed board
  startGame:       'lucide:play',             // Start Game ▶ / Open lobby ▶
  rulesScoring:    'lucide:trophy',           // Rules side tabs
  rulesQuestions:  'lucide:circle-help',
  rulesActions:    'lucide:clapperboard',
  rulesBoard:      'lucide:map',
  rulesTurns:      'lucide:timer',
  rulesTopics:     'lucide:tags',

  // ── Lobby, game screen, GM panel ────────────────────────────────────────────
  back:            'lucide:arrow-left',
  forward:         'lucide:arrow-right',      // Start Game → in the lobby, Join Game →, Next →
  tvDisplay:       'lucide:cast',             // open the TV display page
  presentation:    'lucide:tv',               // presentation mode (full screen)
  zoomIn:          'lucide:plus',
  zoomOut:         'lucide:minus',
  fitBoard:        'lucide:house',            // fit the board to the screen
  close:           'lucide:x',
  gmControls:      'lucide:sliders-horizontal',
  gameLog:         'lucide:scroll-text',
  undoMove:        'lucide:undo-2',           // GM: undo last move
  changeBadge:     'lucide:palette',
  skipTurn:        'lucide:skip-forward',
  sitOut:          'lucide:pause',            // GM: sit out / rejoin
  showJoinCode:    'lucide:qr-code',
  timerStart:      'lucide:play',
  timerPause:      'lucide:pause',
  timerReset:      'lucide:rotate-ccw',
  rematch:         'lucide:repeat',
  remove:          'lucide:x',                // remove a player from the lobby / network list

  // ── Cards and judging (buttons in the space cards) ──────────────────────────
  judgeCorrect:    'lucide:check',            // GM: the answer is right
  judgeWrong:      'lucide:x',                // GM: the answer is wrong
  reveal:          'lucide:eye',              // show the answer / the card
  physicalCard:    'lucide:layers',           // use a card from the physical deck instead
  timeUp:          'lucide:timer-off',        // action card: no guess / time up
  continue:        'lucide:arrow-right',

  // ── Questions tab, Academy ──────────────────────────────────────────────────
  markQuestion:    'lucide:flag',             // mark a question as wrong / unclear
  editNote:        'lucide:pencil',
  search:          'lucide:search',
  modeExplore:     'lucide:library-big',      // Academy mode tabs
  modeFlashcards:  'lucide:layers',
  modeQuiz:        'lucide:pencil',
  modeMatch:       'lucide:puzzle',
  modeTrueFalse:   'lucide:circle-check',
  modeSpeed:       'lucide:zap',
  modePlaces:      'lucide:map',
  modePrint:       'lucide:printer',
  modeReview:      'lucide:search-check',
  playGame:        'lucide:dices',            // Academy → back to the game
  turnAll:         'lucide:refresh-cw',       // flashcards: turn every card
  hideAll:         'lucide:eye-off',
  shuffle:         'lucide:shuffle',
  print:           'lucide:printer',
  whereAmI:        'lucide:compass',
  answerRight:     'lucide:check',            // Academy: "I got it" / True
  answerWrong:     'lucide:x',                // Academy: "Not quite" / False

  // ── Board tiles and spaces (editions usually override these) ────────────────
  tileStart:       'emoji:🚩',
  tileFinish:      'emoji:🏁',
  tileQuestion:    'emoji:❓',
  tileAction:      'emoji:🎬',
  tileGoodDeed:    'emoji:✅',
  tileBadDeed:     'emoji:❌',
  tileLandmark:    'emoji:🌍',
  tileSkip:        'emoji:⏭️',
  historyGm:       'emoji:⚙️',                // a GM change in the game log
  dirRight:        'lucide:arrow-right',      // path direction arrows on the tiles
  dirLeft:         'lucide:arrow-left',
  dirUp:           'lucide:arrow-up',
  dirDown:         'lucide:arrow-down',
  boardRandom:     'emoji:🎲',                // board picker: a random path
  boardCustom:     'emoji:✏️',                // a board drawn in the Boards tab

  // ── Deed effects ────────────────────────────────────────────────────────────
  moveForward:     'emoji:▶️',
  moveBack:        'emoji:◀️',
  goToLandmark:    'emoji:📍',
  extraTurn:       'emoji:🎲',
  everyoneGain:    'emoji:🌟',
  everyoneLose:    'emoji:⚡',
  protection:      'emoji:🛡️',
  goodDeedCheer:   'emoji:🌟',                // after a good deed's title

  // ── Questions and actions ───────────────────────────────────────────────────
  easy:            'emoji:🟢',
  hard:            'emoji:🔵',
  answer:          'emoji:✅',                // in front of the correct answer
  resultRight:     'emoji:✅',
  resultWrong:     'emoji:❌',
  note:            'emoji:💡',                // the fact behind an answer
  marked:          'emoji:🚩',                // a question marked as wrong / unclear
  actAct:          'emoji:🎭',                // action card kinds
  actExplain:      'emoji:💬',
  actSound:        'emoji:🎵',
  whoGuessed:      'emoji:🎯',
  landmarkCollect: 'emoji:⭐',                // collect a landmark's points
  sayAnswer:       'emoji:🗣️',                // phone: say your answer out loud
  secret:          'emoji:🤫',                // phone: only you can see this card
  thinking:        'emoji:🤔',
  celebrate:       'emoji:🎉',
  oops:            'emoji:🙈',
  star:            'emoji:⭐',
  sprout:          'emoji:🌱',                // "keep learning" score
  speed:           'emoji:⚡',
  timer:           'emoji:⏱️',
  places:          'emoji:🗺️',
  printCards:      'emoji:🖨️',
  flashcards:      'emoji:🃏',
  matchPairs:      'emoji:🧩',
  compass:         'emoji:🧭',

  // ── Players and status ──────────────────────────────────────────────────────
  finished:        'emoji:✅',
  sittingOut:      'emoji:💤',
  disconnected:    'emoji:⚠️',
  warning:         'emoji:⚠️',
  noPhone:         'emoji:🖥️',
  phone:           'emoji:📱',
  tv:              'emoji:📺',
  network:         'emoji:📡',
  hosting:         'emoji:🎮',
  reconnecting:    'emoji:🔄',
  hostLeft:        'emoji:🚪',
  rolled:          'emoji:🎲',
  stats:           'emoji:📊',
  steps:           'emoji:👣',
  saved:           'emoji:💾',                // a saved game to resume
  medal1:          'emoji:🥇',
  medal2:          'emoji:🥈',
  medal3:          'emoji:🥉',
  rank4:           'emoji:4️⃣',
  rank5:           'emoji:5️⃣',
  rank6:           'emoji:6️⃣',
  rank7:           'emoji:7️⃣',
  rank8:           'emoji:8️⃣',
  trophy:          'emoji:🏆',
  appLogo:         'emoji:🎯',                // Triventurex itself (phone page, default edition icon)
  academyLogo:     'emoji:🎓',

  // ── End-screen awards (editions rename / re-icon them in their config.js) ───
  awardQuizMaster:    'emoji:🧠',
  awardPerformer:     'emoji:🎭',
  awardGoodDeeds:     'emoji:😇',
  awardBadDeeds:      'emoji:😈',
  awardExplorer:      'emoji:🌍',
  awardBigTurn:       'emoji:🚀',
  awardLuckyRoller:   'emoji:🍀',
  awardUnluckyRoller: 'emoji:🐢',
  awardPatience:      'emoji:⏳',
};

/**
 * Badges players can pick (data, not icons by name): the host's badge picker
 * shows BADGES; default players take the first eight; phones show PHONE_BADGES.
 */
const BADGES = [
  '🚀','⭐','⚡','🎯','🏆','🌙','🦋','🎪',
  '🌟','🔥','💎','🎈','🦁','🐉','🌺','🎵',
  '🛡️','⚔️','🧭','🗺️','🏹','👑','🔮','🪄',
  '🦅','🐺','🐯','🐻','🦄','🐢','🐬','🦊',
  '🍀','🎲','🧩','🎨','🎮','🎤','🎸','🥇',
  '🎊','🎁','🎀','🪁','🎂','🍉','🍕','🍩',
  '☀️','🪐','🌈','☄️','🌌','❄️','💫','✨',
  '🌸','🌻','🌴','🍁','🌵','🌊','⛰️','🌋',
  '🐼','🐸','🐵','🐧','🐞','🐙','🐝','🦜',
];
const PHONE_BADGES = ['🌟','⚡','🔥','💎','🏆','🎯','🚀','🌙','🍀','🎲','🎸','🏅','🦁','🐉','🌊','🌺'];

if (typeof module !== 'undefined') module.exports = { ICONS, BADGES, PHONE_BADGES };
