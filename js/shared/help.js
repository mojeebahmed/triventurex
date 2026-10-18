/**
 * help.js — the in-game help: one ? button per screen opens the help for what
 * is on that screen (host setup tabs, lobby, game; phone; Academy modes).
 *
 * All help text lives here, in HELP. Each topic: { title, icon, body, more }.
 *   body   a little markup: blank line = new paragraph, "## " heading,
 *          "- " bullet, **bold**, {icon:name} (a registry icon — no raw emoji
 *          here), {points} {edition} {finish} {question} {action} {good} {bad}
 *          {landmark} {skip} — the edition's own words (helpWords)
 *   more   related topics, shown as links under the text
 *
 *   openHelp('setup-rules')                 the host page (words from CONFIG)
 *   openHelp('phone-game', { words })       the phone page passes its own words
 *
 * Top-level code does not touch the page; helpHtml / helpWords are pure and
 * tested in test/help.test.js (every topic, link and icon name must exist).
 */

const HELP = {

  // ── Shared: how the game works ────────────────────────────────────────────────
  'how-to-play': {
    title: 'How to play', icon: 'tileStart', more: [],
    body: `
Take turns rolling the dice and moving along the path to **{finish}**. The space you land on decides what happens. The player with the most **{points}** at the end wins.

## The spaces
- {icon:tileQuestion} **{question}**: answer a quiz question. Usually you choose easy or hard — a hard one is worth more {points}.
- {icon:tileAction} **{action}**: act it out, explain it without saying the word, or make the sound, while the others guess. You and the first right guesser both score.
- {icon:tileGoodDeed} **{good}** and {icon:tileBadDeed} **{bad}**: a short story with an effect — win or lose {points}, move forward or back, roll again or skip a turn.
- {icon:tileLandmark} **{landmark}**: a famous place on the way, with a photo and a fact. It can earn {points} too.
- {icon:tileSkip} **{skip}**: you miss your next turn.
- {icon:tileFinish} **{finish}**: the earlier you arrive, the bigger your bonus. The game ends when everyone has arrived.

## Good to know
- Usually you need the exact number to land on {finish} — rolling too high means you stay where you are.
- The host can change the points and rules before the game starts.
- Nothing is too easy or too hard: the fun is in learning something new.`,
  },

  // ── Host: setup screen, one topic per tab ─────────────────────────────────────
  'setup-new': {
    title: 'Start a new game', icon: 'tabNewGame', more: ['how-to-play', 'setup-rules', 'lobby'],
    body: `
Set up a game in four steps. Click a step to open it — each choice moves on to the next. The bar at the bottom shows your choices; press **Start Game** (or Enter) when you are ready.

## The steps
- **Edition**: the topic of the game — its questions, cards, places and words.
- **Game length**: Short (about 20–30 minutes), Medium (45–60) or Long (90 or more).
- **Board**: the shape of the path. {icon:boardRandom} Random picks one for you; boards with {icon:boardCustom} are ones you drew in the Boards tab.
- **Players**: who plays, and how — see below.

## Two ways to play
- {icon:onThisScreen} **On this screen**: everyone plays on this computer and takes turns. {icon:addPlayer} Add up to 8 players; click a badge to choose its picture and colour.
- {icon:onPhones} **On phones**: everyone uses their own phone to roll, answer and see secret cards. **Open lobby** shows a QR code to join. Say whether you play too, or only run the game as the game master (GM).

## Also here
- A game still going? {icon:saved} **Resume** carries on where you stopped.
- The other tabs: {icon:tabRules} **Rules** (points, timer, topics), {icon:tabQuestions} **Questions** (browse and check the questions) and {icon:tabBoards} **Boards** (draw your own board).`,
  },

  'setup-rules': {
    title: 'Rules', icon: 'tabRules', more: ['setup-new', 'how-to-play'],
    body: `
Change how the game plays. Every change is saved straight away for this edition, and used in every new game.

- **Preset**: a ready-made set to start from — Family (the standard game), Kids (easy questions, no going backwards, more action) or Quiz night (questions count more, with a timer). The badge shows how many settings you changed; {icon:reset} **Reset to preset** undoes them.
- {icon:rulesScoring} **Scoring**: {points} for questions, action cards, {landmark} spaces and the finish bonus; whether scores can go below 0.
- {icon:rulesQuestions} **Questions**: who picks easy or hard, avoiding repeated questions, answering on phones, the timer.
- {icon:rulesActions} **Action cards**: digital cards or your own deck, the general everyday cards, which kinds, the timer.
- {icon:rulesBoard} **Board**: how many of each space, and whether {bad} cards may send players back.
- {icon:rulesTurns} **Turn & pace**: exact finish, who starts, animation speed.
- {icon:rulesTopics} **Topics**: tick the question topics to play with — great for young players or a themed night.

{icon:copy} **Copy as preset** is for developers: it copies these settings to add them to the game as a new preset.`,
  },

  'setup-questions': {
    title: 'Questions', icon: 'tabQuestions', more: ['setup-new', 'academy'],
    body: `
Browse every question in this edition — to check them, or just to learn.

- Pick a topic on the left, or search for words or a question's #number. Filter by difficulty and show or hide the answers.
- {icon:markQuestion} **Mark** a question that looks wrong or unclear, and add a note. You can also mark a question during a game, on its card.
- **Marked only** shows just your marks. {icon:copy} **Copy marked list** copies them with your notes — send it to whoever looks after the questions.
- {icon:academy} **Academy** opens Triventurex Academy in a new tab: flashcards, quizzes and games with these questions.`,
  },

  'setup-boards': {
    title: 'Draw a board', icon: 'tabBoards', more: ['setup-new'],
    body: `
Draw your own path for the board.

- Click a square to start. Then click a square in a straight line (across, up or down) from the end of the path to add the next stretch.
- The preview shows the board and how many spaces it has compared with the usual number for each game length. It warns you when rows are too close together.
- {icon:boardUndo} **Undo** removes the last stretch; {icon:boardNew} **New** starts again.
- {icon:save} **Save board** keeps it: it appears with {icon:boardCustom} in the Board step of a new game. {icon:playBoard} **Play this board** starts a game on it straight away.
- {icon:copy} **Copy as template** is for developers, to add the board to the game for everyone.`,
  },

  // ── Host: lobby and game ──────────────────────────────────────────────────────
  'lobby': {
    title: 'Waiting for players', icon: 'hosting', more: ['how-to-play', 'game-gm'],
    body: `
Players join this game from their phones.

- Scan the QR code with a phone camera — or open the address shown and type the **Game ID**. Phones must be on the same Wi-Fi as this computer.
- Players appear in the list as they join. Click a badge to change it; {icon:remove} removes a player.
- No phone? Type a name and press {icon:addPlayer} **Add** — that player takes their turns on this screen.
- {icon:tvDisplay} **Open TV display** shows the board, scores and cards on a second screen, such as a TV or projector, with no buttons on it.
- Press **Start Game** when everyone is in. Latecomers can still join during the game.
- {icon:back} **Back** closes the lobby and ends the game on the phones.`,
  },

  'game': {
    title: 'Playing the game', icon: 'tabNewGame', more: ['game-cards', 'game-log', 'game-gm', 'how-to-play'],
    body: `
The board is on the left, the game's controls on the right.

## A turn
- The player whose turn it is shows at the top right. Press **Roll Dice** — in a game on phones, the player rolls on their own phone.
- The token moves and a card opens for the space. Follow the card: read the question, judge the answer, or let the player perform.
- Playing with real dice? Click the small die with the number you rolled, under Roll Dice.
- The {icon:timer} **Timer** helps with questions and action cards: start or pause it, reset it or add time.

## The board
- Drag the board to move it; zoom with the mouse wheel, a pinch, or {icon:zoomIn} {icon:zoomOut}. {icon:fitBoard} fits the whole board on the screen.
- {icon:presentation} **Presentation mode** (or press P): full screen for a TV, everything big and clear. {icon:gmControls} brings back the host's tools; Esc leaves.

## The scoreboard
Everyone's {points} and place. {icon:finished} has arrived, {icon:sittingOut} is sitting out, {icon:disconnected} has lost their phone connection (it reconnects by itself).`,
  },

  'game-cards': {
    title: 'The cards', icon: 'tileQuestion', more: ['game', 'how-to-play'],
    body: `
What to do when a card opens.

- {icon:tileQuestion} **{question}**: the player picks easy or hard (unless the rules decide). On phones, multiple-choice questions are answered on the phone and scored for you. Otherwise read the question out, press {icon:reveal} **Reveal Answer**, then {icon:judgeCorrect} or {icon:judgeWrong}. {icon:markQuestion} marks a question that looks wrong.
- {icon:tileAction} **{action}**: only the performer may see the card — on their phone, or with {icon:reveal} while the others look away. Start the timer; when someone guesses, press who guessed it, or {icon:timeUp} when nobody did.
- {icon:physicalCard} Have your own cards? Every question and action card can be swapped for a card from a physical deck.
- {icon:tileGoodDeed} {icon:tileBadDeed} **{good}** / **{bad}**: read the story out; the effect happens when you continue.
- {icon:tileLandmark} **{landmark}**: enjoy the photo and the fact; the {points} are added for you.`,
  },

  'game-log': {
    title: 'Game log and undo', icon: 'gameLog', more: ['game', 'game-gm'],
    body: `
{icon:gameLog} **Game Log** lists every turn: who rolled what, where they landed and what changed.

{icon:undoMove} **Undo Last Move** takes back a mistake:
- During a turn, it cancels the turn in progress — the player is back where they started.
- Between turns, it undoes the last turn (or the last GM change), one at a time.

Badges, and players who joined later, stay as they are.`,
  },

  'game-gm': {
    title: 'GM controls', icon: 'gmControls', more: ['game', 'game-log'],
    body: `
{icon:gmControls} **GM Controls** are for the game master — whoever runs the game — to fix mistakes and keep it fun. First pick a **player**.

- {icon:changeBadge} changes the player's badge and colour.
- **{points}**: add or take away points — for a brilliant answer, or a house rule.
- **Move**: move the player forward or back a few spaces.
- {icon:skipTurn} **Skip Turn**: the player misses their next turn.
- {icon:sitOut} **Sit Out / Rejoin**: leave a player out of the turns for a while, and bring them back.
- Every GM change shows in the game log and can be undone.

## Playing on phones
- Add a player without a phone by name — they play on this screen.
- {icon:showJoinCode} **Show join code** lets someone join late.
- {icon:tvDisplay} **Open TV display** opens a second screen with the board, scores and cards.
- The list shows who is connected. A phone that drops out reconnects by itself.`,
  },

  // ── Phone ─────────────────────────────────────────────────────────────────────
  'phone-join': {
    title: 'Join a game', icon: 'phone', more: ['how-to-play'],
    body: `
- Type your name and the **Game ID** shown on the host's screen, then **Join Game**. (Scanned the QR code? The Game ID is filled in already.)
- Tap your badge to choose its picture and colour.
- Your phone must be on the same Wi-Fi as the host's computer.`,
  },

  'phone-lobby': {
    title: 'Waiting to start', icon: 'hosting', more: ['how-to-play'],
    body: `
You are in! The game starts when the host presses Start.

- The list shows who has joined so far.
- Wrong name or badge? {icon:back} **Leave** and join again.`,
  },

  'phone-game': {
    title: 'Playing on your phone', icon: 'phone', more: ['how-to-play'],
    body: `
Your phone is your controller; the board is on the big screen.

- **Your turn**: tap the die to roll. Your phone buzzes when your turn starts, and shows "You're next" just before.
- **{question}**: choose easy or hard, then tap your answer — the host's screen scores it. For an open question, say your answer out loud.
- **{action}**: {icon:secret} only you see the card — perform it while the others guess.
- Everyone else's turns show in the list below, with everyone's {points}.
- Lost the connection? Just wait: your phone rejoins by itself, even after a refresh.`,
  },

  // ── Triventurex Academy ───────────────────────────────────────────────────────
  'academy': {
    title: 'Triventurex Academy', icon: 'academyLogo', more: [],
    body: `
Learn the questions of an edition before you play — or just for fun.

- Choose the **edition** at the top, and a **mode** in the row of tabs.
- **Choose what to learn** (left): tick topics, pick easy or hard, or search. Every mode uses this choice.
- {icon:marked} Marks on questions are shared with the game's Questions tab, on this device.
- {icon:playGame} **Play the game** goes back to the game.

## The modes
{icon:modeExplore} Explore · {icon:modeFlashcards} Flashcards · {icon:modeQuiz} Quiz · {icon:modeMatch} Match · {icon:modeTrueFalse} True or false · {icon:modeSpeed} Speed round · {icon:modePlaces} Places · {icon:modePrint} Print cards · {icon:modeReview} Review — each has its own help.`,
  },
  'academy-explore': {
    title: 'Explore', icon: 'modeExplore', more: ['academy'],
    body: `
Browse the questions with their answers and the fact behind each one.

- {icon:markQuestion} **Mark as wrong / unclear** with a note when something looks off; {icon:editNote} edits the note.
- **Marked only** shows just the marked questions.`,
  },
  'academy-flashcards': {
    title: 'Flashcards', icon: 'modeFlashcards', more: ['academy'],
    body: `
A set of cards: guess the answer, then tap the card to turn it over.

- Choose how many cards a set has (8, 9 or one at a time).
- {icon:turnAll} **Turn all** / {icon:hideAll} **Hide all**; move to the next set or {icon:back} back.
- {icon:shuffle} **Shuffle and start again** for a new order.`,
  },
  'academy-quiz': {
    title: 'Quiz', icon: 'modeQuiz', more: ['academy'],
    body: `
A practice round, with your score at the end.

- Choose how many questions, then think of the answer and show it.
- Be honest: {icon:answerRight} **I got it** or {icon:answerWrong} **Not quite**.`,
  },
  'academy-match': {
    title: 'Match', icon: 'modeMatch', more: ['academy'],
    body: `
Find the pairs: tap a question, then the answer that goes with it. Fewer tries is better.`,
  },
  'academy-truefalse': {
    title: 'True or false', icon: 'modeTrueFalse', more: ['academy'],
    body: `
Each question shows an answer — is it the right one? Tap {icon:answerRight} **True** or {icon:answerWrong} **False**.`,
  },
  'academy-speed': {
    title: 'Speed round', icon: 'modeSpeed', more: ['academy'],
    body: `
{icon:timer} As many questions as you can in one minute. Quick thinking beats long thinking!`,
  },
  'academy-places': {
    title: 'Places', icon: 'modePlaces', more: ['academy'],
    body: `
The famous places of this edition, with photos and facts.

- {icon:whereAmI} **Where am I?** shows a photo — guess which place it is.`,
  },
  'academy-print': {
    title: 'Print cards', icon: 'modePrint', more: ['academy'],
    body: `
Print the chosen questions as cards to cut out — for the car, the classroom, or as a physical deck for the game.

- **Double-sided**: answers on the back (print on both sides of the paper).
- **Fold-over**: question and answer on one side; fold each card in the middle.
- Use the filter on the left to choose which questions to print.`,
  },
  'academy-review': {
    title: 'Review', icon: 'modeReview', more: ['academy', 'academy-explore'],
    body: `
For checking an edition's questions, one by one.

- Tick a question as **reviewed** when it is right, or {icon:markQuestion} mark it with a note when it is not.
- Show all questions, those not reviewed yet, or the marked ones; the bar shows your progress.
- {icon:copy} **Copy report** copies your marks and notes — send them to whoever looks after the questions.`,
  },
};

/** The words help text uses, from an edition config (or the engine's defaults). */
function helpWords(config) {
  const g = config?.GAME || {};
  const s = config?.SPACE_INFO || {};
  const label = (type, fallback) => (s[type]?.label || fallback).replace(/!$/, '');
  return {
    points:   g.pointsName && g.pointsName !== 'pts' ? g.pointsName : 'points',
    edition:  g.editionName || 'Triventurex',
    finish:   g.finishLabel || 'the finish',
    question: label('question', 'Question'),
    action:   label('action', 'Action'),
    good:     label('good_deed', 'Good Deed'),
    bad:      label('bad_deed', 'Bad Deed'),
    landmark: label('landmark', 'Landmark'),
    skip:     label('skip', 'Skip Turn'),
  };
}

const _helpEsc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/** Help markup → HTML. Words are escaped (they may come from the network). */
function helpHtml(text, words = helpWords(null), iconFn = typeof icon === 'function' ? icon : () => '') {
  const inline = line => _helpEsc(line)
    .replace(/\{icon:([A-Za-z0-9]+)\}/g, (_, n) => iconFn(n))
    .replace(/\{([a-z]+)\}/g, (m, w) => (w in words ? _helpEsc(words[w]) : m))
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  const out = [];
  let list = null;
  for (const raw of String(text).trim().split('\n')) {
    const line = raw.trim();
    if (line.startsWith('- ')) { (list ||= []).push(`<li>${inline(line.slice(2))}</li>`); continue; }
    if (list) { out.push(`<ul>${list.join('')}</ul>`); list = null; }
    if (!line) continue;
    out.push(line.startsWith('## ') ? `<h3>${inline(line.slice(3))}</h3>` : `<p>${inline(line)}</p>`);
  }
  if (list) out.push(`<ul>${list.join('')}</ul>`);
  return out.join('');
}

// ── The help window ───────────────────────────────────────────────────────────────

const LS_HELP_SEEN = 'triventurex_help_seen';
let _helpWords = null;

/** Open the help for `topic` (a HELP key). `words`: the edition's words, else from CONFIG. */
function openHelp(topic, { words } = {}) {
  const t = HELP[topic] || HELP['how-to-play'];
  // the page's edition words: passed in (phone), else from CONFIG (host, Academy), else the last ones
  const fromConfig = typeof CONFIG !== 'undefined' && CONFIG.GAME ? helpWords(CONFIG) : null;
  _helpWords = words || fromConfig || _helpWords || helpWords(null);
  let box = document.getElementById('help-overlay');
  if (!box) {
    box = document.createElement('div');
    box.id = 'help-overlay';
    box.className = 'help-overlay';
    box.addEventListener('click', e => { if (e.target === box) closeHelp(); });
    document.body.appendChild(box);
  }
  const more = (t.more || []).filter(k => HELP[k]);
  box.innerHTML = `
    <div class="help-card" role="dialog" aria-modal="true" aria-labelledby="help-title">
      <div class="help-head">
        <span class="help-head-icon">${typeof icon === 'function' ? icon(t.icon) : ''}</span>
        <h2 id="help-title">${_helpEsc(t.title)}</h2>
        <button type="button" class="help-close" onclick="closeHelp()" aria-label="Close help">${typeof icon === 'function' ? icon('close') : 'x'}</button>
      </div>
      <div class="help-body">${helpHtml(t.body, _helpWords)}</div>
      ${more.length ? `<div class="help-more"><span>More help:</span>${more.map(k =>
        `<button type="button" class="help-link" onclick="openHelp('${k}')">${typeof icon === 'function' ? icon(HELP[k].icon) : ''} ${_helpEsc(HELP[k].title)}</button>`).join('')}</div>` : ''}
    </div>`;
  box.classList.add('open');
  box.querySelector('.help-close').focus();
  try { localStorage.setItem(LS_HELP_SEEN, '1'); } catch {}
  document.querySelectorAll('.help-btn.help-new').forEach(b => b.classList.remove('help-new'));
}

function closeHelp() {
  document.getElementById('help-overlay')?.classList.remove('open');
}

const isHelpOpen = () => !!document.getElementById('help-overlay')?.classList.contains('open');

/**
 * Wire this page's help: Esc closes, ? opens `topicFn()`'s topic, and the ?
 * buttons glow until someone has opened help once on this device.
 */
function startHelp(topicFn, opts = {}) {
  let seen = false;
  try { seen = !!localStorage.getItem(LS_HELP_SEEN); } catch {}
  if (!seen) document.querySelectorAll('.help-btn').forEach(b => b.classList.add('help-new'));
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && isHelpOpen()) { e.stopImmediatePropagation(); closeHelp(); return; }
    if (e.key !== '?' || e.ctrlKey || e.metaKey || e.altKey) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable) return;
    e.preventDefault();
    isHelpOpen() ? closeHelp() : openHelp(topicFn(), opts);
  }, true);
}

if (typeof module !== 'undefined') module.exports = { HELP, helpWords, helpHtml };
