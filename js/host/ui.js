/**
 * ui.js
 * UI helpers: screen switching, modal management, scoreboard, legend, timer.
 */

// ── Screen Management ─────────────────────────────────────────────────────────

function showScreen(screenId) {
  if (screenId === 'setup-screen' && isPresenting()) exitPresentation();   // back to setup = back to the laptop
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(screenId).classList.add('active');
}

// ── Current Player Display ────────────────────────────────────────────────────

function updateCurrentPlayerDisplay(player, phaseText) {
  const tokenEl = document.getElementById('current-player-token');
  tokenEl.style.backgroundColor = player.color;
  tokenEl.innerHTML = `
    <div class="token-emoji">${esc(player.token || '●')}</div>
    <div class="token-initial">${esc((player.name || '?').slice(0, 2).toUpperCase())}</div>`;
  document.getElementById('current-player-name').textContent = player.name;
  document.getElementById('current-turn-phase').textContent  = phaseText;
}

// ── Scoreboard ────────────────────────────────────────────────────────────────

function updateScoreboard(players) {
  const el = document.getElementById('scoreboard');
  el.innerHTML = getSortedPlayers(players).map(p => `
    <div class="score-row">
      <div class="score-token" style="background:${esc(p.color)}">
        <div class="token-emoji">${esc(p.token || '●')}</div>
        <div class="token-initial">${esc((p.name || '?').slice(0, 2).toUpperCase())}</div>
      </div>
      <div class="score-name">${esc(p.name)}</div>
      <div>
        <div class="score-points">${p.score} ${CONFIG.GAME?.pointsName ?? 'pts'}</div>
        <div class="score-position">Space ${p.position}${p.finished ? ' ✅' : ''}${p.inactive ? ' 💤' : ''}${p.disconnected ? ' <span title="Phone disconnected">⚠️</span>' : ''}</div>
      </div>
    </div>
  `).join('');
  if (typeof _displayLive === 'function') _displayLive();   // TV display (G16)
}

// ── GM Player Select ──────────────────────────────────────────────────────────

function updateGMPlayerSelect(players) {
  const sel = document.getElementById('gm-player-select');
  const selected = sel.value; // keep the GM's choice across refreshes
  sel.innerHTML = players.map(p =>
    `<option value="${p.id}">${esc(p.name)}${p.inactive ? ' 💤' : ''}</option>`).join('');
  if (players.some(p => String(p.id) === selected)) sel.value = selected;
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function showModal({ icon, title, content, actions }) {
  if (typeof _displayCard === 'function') _displayCard({ icon, title, content });   // TV display (G16)
  document.getElementById('modal-icon').textContent = icon;
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-content').innerHTML = content;

  const actionsEl = document.getElementById('modal-actions');
  actionsEl.innerHTML = '';
  actions.forEach(({ label, class: cls, callback }) => {
    const btn = document.createElement('button');
    btn.className = cls || 'btn btn-primary';
    btn.textContent = label;
    btn.addEventListener('click', () => { hideModal(); callback(); });
    actionsEl.appendChild(btn);
  });

  document.getElementById('modal-overlay').classList.remove('hidden');
}

function hideModal() {
  if (typeof _displayCard === 'function') _displayCard(null);
  document.getElementById('modal-overlay').classList.add('hidden');
}

// ── Space Modal ───────────────────────────────────────────────────────────────

/**
 * Show the space-landing modal for the given space type.
 * For 'question' spaces, first shows a difficulty choice, then the question.
 * For deed spaces, shows the deed card text and applies the effect.
 */
function showSpaceModal(space, player, onDone) {
  // Set the modal accent colour to match this space type
  const spaceColor = CONFIG.SPACE_INFO[space.type]?.color;
  if (spaceColor) {
    document.documentElement.style.setProperty('--modal-accent', spaceColor);
  } else {
    document.documentElement.style.removeProperty('--modal-accent');
  }

  switch (space.type) {

    case 'question':
      _showQuestionChoice(player, space, onDone);
      break;

    case 'action':
      _showActionModal(player, onDone);
      break;

    case 'good_deed':
      _showDeedCard(space, player, onDone);
      break;

    case 'bad_deed':
      _showDeedCard(space, player, onDone);
      break;

    case 'landmark': {
      const imgHtml = space.image
        ? `<img src="${space.image}" alt="${space.name}" class="landmark-modal-img"
               onerror="this.style.display='none'">`
        : '';
      const descHtml = space.description
        ? `<p class="landmark-description">${space.description}</p>`
        : '';
      // Edition-neutral: icon/label come from SPACE_INFO.landmark (e.g. 🏟️ Stadium)
      const lmInfo = CONFIG.SPACE_INFO.landmark ?? {};
      const lmName = space.name || lmInfo.label || 'Landmark';
      // Points come from the rules (0 = just information) — no GM decision needed
      const lmPts  = landmarkPoints(gameRules(), 'roll');
      const pts    = CONFIG.GAME?.pointsName ?? 'pts';
      const signed = `${lmPts > 0 ? '+' : ''}${lmPts} ${pts}`;
      showModal({
        icon: lmInfo.icon ?? '🌍',
        title: lmName,
        content: `${imgHtml}${descHtml}
                  <p style="margin-top:8px"><strong>${esc(player.name)}</strong> has arrived at
                  <strong>${lmName}</strong>!</p>
                  ${lmPts ? `<div class="landmark-points ${lmPts > 0 ? 'pos' : 'neg'}">${signed}</div>` : ''}`,
        actions: [
          { label: lmPts > 0 ? `⭐ Collect ${signed}` : lmPts < 0 ? `OK (${signed})` : 'Continue',
            class: 'btn btn-primary',
            callback: () => { if (lmPts) addScore(player, lmPts); onDone(); } },
        ],
      });
      break;
    }

    case 'skip':
      showModal({
        icon: '⏭',
        title: 'Skip a Turn',
        content: `<strong>${esc(player.name)}</strong> must skip their next turn.`,
        actions: [{ label: 'OK', class: 'btn btn-primary',
          callback: () => { player.skipNextTurn = true; onDone(); } }],
      });
      break;

    case 'start':
      showModal({
        icon: '🚩', title: 'Start',
        content: 'The journey begins! May the best adventurer win! 🏁',
        actions: [{ label: "Let's go!", class: 'btn btn-primary', callback: onDone }],
      });
      break;

    case 'finish': {
      const order       = player.finishOrder || 1;
      const bonus       = finishBonusFor(gameRules(), CONFIG, order);
      const ordinal     = ['1st','2nd','3rd','4th','5th','6th','7th','8th'][order - 1] || `${order}th`;
      const finishIcon  = CONFIG.SPACE_INFO.finish?.icon ?? '🏁';
      const celebration = CONFIG.GAME?.finishCelebration ?? 'Well done! 🎉';
      const btnLabel    = CONFIG.GAME?.finishButtonLabel  ?? '🎉 Celebrate!';
      const pts         = CONFIG.GAME?.pointsName ?? 'pts';
      showModal({
        icon: finishIcon,
        title: `${CONFIG.GAME?.finishLabel ?? 'Finish'}!`,
        content: `${_playerBadgeHtml(player)}
                  <div class="finish-announcement">
                    <div class="finish-ordinal">${ordinal} to arrive!</div>
                    ${bonus ? `<div class="finish-bonus-display">+${bonus} ${pts} bonus awarded</div>` : ''}
                  </div>
                  <p style="margin-top:10px;color:#666;font-size:.9rem">${celebration}</p>`,
        actions: [{ label: btnLabel, class: 'btn btn-primary', callback: onDone }],
      });
      break;
    }

    default:
      onDone();
  }
}

// ── Question Flow ─────────────────────────────────────────────────────────────

function _playerBadgeHtml(player) {
  return `<div class="modal-player-badge" style="background:${esc(player.color)}">
    <div class="token-emoji">${esc(player.token || '●')}</div>
    <span>${esc(player.name)}</span>
  </div>`;
}

// ── Question tracking (no-repeat) ─────────────────────────────────────────────

function _askedKey(diff) {
  const editionId = (typeof getActiveEditionId === 'function' && getActiveEditionId()) || 'default';
  return `triventurex_asked_${editionId}_${diff}`;
}

// One-off cleanup: before this was fixed every edition shared the
// '..._default_*' keys, so their contents are a mix of editions — drop them.
try {
  localStorage.removeItem('triventurex_asked_default_easy');
  localStorage.removeItem('triventurex_asked_default_hard');
} catch {}

function _getAskedIds(diff) {
  try { return new Set(JSON.parse(localStorage.getItem(_askedKey(diff))) || []); } catch { return new Set(); }
}

function _markAsked(diff, id) {
  const asked = _getAskedIds(diff);
  asked.add(id);
  try { localStorage.setItem(_askedKey(diff), JSON.stringify([...asked])); } catch {}
}

function _clearAskedIds(diff) {
  try { localStorage.removeItem(_askedKey(diff)); } catch {}
}

/** Called by game.js on new game when questionTracking === 'game'. */
function resetAskedQuestions() {
  _clearAskedIds('easy');
  _clearAskedIds('hard');
  _clearAskedIds('actions');
}

/** Returns the unasked pool for a difficulty. Resets tracking if all are asked. */
function _availablePool(diff) {
  const selTopics = typeof getSelectedTopics === 'function' ? getSelectedTopics() : null;
  const all = (window.QUESTIONS_DATA || []).filter(q => {
    if (q.diff !== diff) return false;
    if (selTopics && q.topic && !selTopics.has(q.topic)) return false;
    return true;
  });
  if (!all.length) return { pool: [], recycled: false };
  const asked = _getAskedIds(diff);
  let pool = all.filter(q => !asked.has(q.id));
  let recycled = false;
  if (!pool.length) {
    _clearAskedIds(diff);
    pool = all;
    recycled = true;
  }
  return { pool, recycled };
}

function _showQuestionChoice(player, space, onDone) {
  const R = gameRules();
  // Rules can fix the difficulty (e.g. always easy for kids) — skip the choice
  if (R.questions.difficulty !== 'choose') { _showQuestion(R.questions.difficulty, player, onDone); return; }

  const { pool: easyPool } = _availablePool('easy');
  const { pool: hardPool } = _availablePool('hard');
  const pts = CONFIG.GAME?.pointsName ?? 'pts';

  // Both exhausted at the same time means _availablePool already recycled them above.
  // Build actions — disable whichever type has no questions in the active topic filter.
  const selTopics = typeof getSelectedTopics === 'function' ? getSelectedTopics() : null;
  const _inTopic = q => !selTopics || !q.topic || selTopics.has(q.topic);
  const allEasy = (window.QUESTIONS_DATA || []).filter(q => q.diff === 'easy' && _inTopic(q));
  const allHard = (window.QUESTIONS_DATA || []).filter(q => q.diff === 'hard' && _inTopic(q));

  const easyExhausted = allEasy.length > 0 && easyPool.length === 0;
  const hardExhausted = allHard.length > 0 && hardPool.length === 0;

  let note = '';
  if (easyExhausted) note = `<p class="question-exhausted-note">🟢 Easy questions exhausted — only Hard available!</p>`;
  if (hardExhausted) note = `<p class="question-exhausted-note">🔵 Hard questions exhausted — only Easy available!</p>`;

  // The GM's button wins over a later tap on the phone
  const choose = diff => { _cancelPhonePrompt(); _showQuestion(diff, player, onDone); };
  const easyBtn = { id: 'easy', label: `🟢 Easy  (+${R.scoring.questionEasy} ${pts})`, class: 'btn btn-primary',
    callback: () => choose('easy') };
  const hardBtn = { id: 'hard', label: `🔵 Hard  (+${R.scoring.questionHard} ${pts})`, class: 'btn btn-primary btn-blue',
    callback: () => choose('hard') };

  const actions = [];
  if (!easyExhausted) actions.push(easyBtn);
  if (!hardExhausted) actions.push(hardBtn);
  // Both exhausted at init time shouldn't happen (pool recycles), but fallback just in case
  if (!actions.length) actions.push(easyBtn, hardBtn);

  // Network game: the player chooses on their phone (G3); the GM can still click
  const token = state.turn?.token;
  const onPhone = R.questions.answerOnPhone && _askOnPhone(player, {
    title: '❓ Question time',
    text:  `Choose your difficulty — more ${pts} for a harder question.`,
    hint:  '📱 Tap to choose',
    choices: actions.map(a => ({ id: a.id, label: a.label })),
  }, diff => { if (!_isStale(token)) { hideModal(); _showQuestion(diff, player, onDone); } });

  showModal({
    icon: '❓',
    title: 'Question Time!',
    content: _playerBadgeHtml(player) +
      `<p>Choose your difficulty. You score more ${pts} for a harder question!</p>${note}` +
      (onPhone ? _phoneWaitHtml(player, 'to choose') : ''),
    actions,
  });
}

/** "📱 Waiting for Sara to answer on their phone…" under a host card. */
function _phoneWaitHtml(player, what) {
  return `<p class="phone-wait">📱 Waiting for <strong>${esc(player.name)}</strong> ${what} on their phone…</p>`;
}

function _showQuestion(diff, player, onDone) {
  const R = gameRules();
  timerSet(R.questions.timerSeconds);
  if (R.questions.timerAuto) timerStart();

  // Pick an unasked question; pool recycles automatically if all exhausted
  const { pool, recycled } = _availablePool(diff);
  if (recycled) showToast(`All ${diff} questions asked — reshuffling!`);
  const q = pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;
  const pts  = diff === 'easy' ? R.scoring.questionEasy : R.scoring.questionHard;

  if (!q) {
    // No questions loaded — use physical card fallback
    showModal({
      icon: diff === 'easy' ? '🟢' : '🔵',
      title: `${diff === 'easy' ? 'Easy' : 'Hard'} Question`,
      content: `<strong>${esc(player.name)}</strong>, draw a <em>${diff === 'easy' ? 'Easy' : 'Hard'}</em>
                question card from the physical deck and read it aloud.
                <br><br>GM: award <strong>${pts} ${CONFIG.GAME?.pointsName ?? 'pts'}</strong> if correct.`,
      actions: [
        { label: `✅ Correct (+${pts})`, class: 'btn btn-primary',
          callback: () => { _noteQuestion(true); addScore(player, pts); onDone(); } },
        { label: '❌ Incorrect', class: 'btn btn-secondary', callback: () => { _noteQuestion(false); onDone(); } },
        { label: '📋 Use physical card instead', class: 'btn btn-secondary',
          callback: () => _showPhysicalCard(diff, player, pts, onDone) },
      ],
    });
    return;
  }

  // Network game (G3): multiple choice is answered + scored on the phone.
  // Open questions are shown on the phone and judged by the GM as usual.
  const letters = ['A', 'B', 'C', 'D'];
  const token   = state.turn?.token;
  const ptsName = CONFIG.GAME?.pointsName ?? 'pts';
  const title   = `${diff === 'easy' ? '🟢 Easy' : '🔵 Hard'} question (+${pts} ${ptsName})`;
  let onPhone = false;
  if (R.questions.answerOnPhone && q.opts?.length) {
    onPhone = _askOnPhone(player, {
      title, text: _plainText(q.q), hint: '📱 Tap your answer',
      choices: q.opts.map((o, i) => ({ id: letters[i], label: `${letters[i]}  ${_plainText(o)}` })),
    }, letter => { if (!_isStale(token)) { hideModal(); _showPhoneAnswer(q, diff, pts, player, letter, onDone); } });
  } else if (R.questions.answerOnPhone) {
    _sendPhoneCard(player, { title, text: _plainText(q.q), hint: '🗣 Say your answer out loud', note: 'The GM judges your answer.' });
  }
  // The GM judges instead: a late tap on the phone is ignored
  const judgeHere = () => _cancelPhonePrompt('The GM is judging this one — say your answer out loud.');

  // Build question HTML
  let optionsHtml = '';
  if (q.opts && q.opts.length) {
    const letters = ['A', 'B', 'C', 'D'];
    optionsHtml = `<div class="question-options">` +
      q.opts.map((o, i) => `
        <div class="question-option" id="qopt-${i}">
          <span class="option-letter">${letters[i]}</span>
          <span>${o}</span>
        </div>`).join('') +
      `</div>`;
  }

  const contentHtml = `
    <div class="question-text">${q.q}</div>
    ${optionsHtml}
    ${onPhone ? _phoneWaitHtml(player, 'to answer') : ''}
    <div id="question-answer-reveal" class="hidden" data-secret>
      <div class="answer-box">✅ Answer: <strong>${
        q.opts && q.opts.length
          ? `${q.answer} — ${q.opts[['A','B','C','D'].indexOf(q.answer)] ?? q.answer}`
          : q.answer
      }</strong></div>
      ${q.note ? `<div class="answer-note">${q.note}</div>` : ''}
    </div>
    ${reportQuestionHtml(q)}`;

  showModal({
    icon: diff === 'easy' ? '🟢' : '🔵',
    title: `${diff === 'easy' ? 'Easy' : 'Hard'} Question  (+${pts} ${CONFIG.GAME?.pointsName ?? 'pts'})`,
    content: contentHtml,
    actions: [
      { label: onPhone ? '👁 Reveal answer (judge here)' : '👁 Reveal Answer', class: 'btn btn-secondary',
        callback: () => {
          judgeHere();
          _markAsked(diff, q.id); // mark as used when the answer is revealed
          _showQuestionWithAnswer(q, diff, pts, player, onDone);
        }},
      { label: '📋 Use physical card', class: 'btn btn-secondary',
        callback: () => { judgeHere(); _showPhysicalCard(diff, player, pts, onDone); } },
    ],
  });
}

/** Question text for the phone: content may hold a little HTML (<em>); the phone escapes. */
function _plainText(html) {
  return String(html ?? '').replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
}

/**
 * The phone answered a multiple-choice question (G3): score it, show the
 * result on both screens. The GM only continues (Undo can still take it back).
 */
function _showPhoneAnswer(q, diff, pts, player, letter, onDone) {
  const letters = ['A', 'B', 'C', 'D'];
  const ptsName = CONFIG.GAME?.pointsName ?? 'pts';
  const right   = letter === q.answer;
  _noteQuestion(right);
  _markAsked(diff, q.id);
  if (right) addScore(player, pts);

  const answerLabel = `${q.answer} — ${q.opts[letters.indexOf(q.answer)] ?? q.answer}`;
  _sendPhoneCard(player, {
    title: right ? `✅ Correct! +${pts} ${ptsName}` : '❌ Not quite',
    text:  right ? `${letter} — ${_plainText(q.opts[letters.indexOf(letter)])}` : `The answer was ${_plainText(answerLabel)}`,
    hint:  `You answered ${letter}`,
    note:  _plainText(q.note),
  });

  const optionsHtml = `<div class="question-options">` + q.opts.map((o, i) => {
    const cls = letters[i] === q.answer ? 'option-correct' : letters[i] === letter ? 'option-wrong' : '';
    const tag = letters[i] === letter ? `<span class="option-picked">📱 ${esc(player.name)}</span>` : '';
    return `<div class="question-option ${cls}"><span class="option-letter">${letters[i]}</span><span>${o}</span>${tag}</div>`;
  }).join('') + `</div>`;

  showModal({
    icon: right ? '✅' : '❌',
    title: right ? `Correct! +${pts} ${ptsName}` : 'Not quite!',
    content: _playerBadgeHtml(player) + `
      <div class="question-text">${q.q}</div>
      ${optionsHtml}
      <div class="answer-box">✅ Answer: <strong>${answerLabel}</strong></div>
      ${q.note ? `<div class="answer-note">${q.note}</div>` : ''}
      ${reportQuestionHtml(q)}`,
    actions: [{ label: 'Continue ▶', class: 'btn btn-primary', callback: onDone }],
  });
}

function _showQuestionWithAnswer(q, diff, pts, player, onDone) {
  const letters = ['A', 'B', 'C', 'D'];
  let optionsHtml = '';
  if (q.opts && q.opts.length) {
    optionsHtml = `<div class="question-options">` +
      q.opts.map((o, i) => {
        const isCorrect = letters[i] === q.answer;
        return `<div class="question-option ${isCorrect ? 'option-correct' : ''}">
          <span class="option-letter">${letters[i]}</span><span>${o}</span></div>`;
      }).join('') + `</div>`;
  }

  const answerLabel = q.opts && q.opts.length
    ? `${q.answer} — ${q.opts[letters.indexOf(q.answer)] ?? q.answer}`
    : q.answer;

  showModal({
    icon: diff === 'easy' ? '🟢' : '🔵',
    title: `${diff === 'easy' ? 'Easy' : 'Hard'} Question  (+${pts} ${CONFIG.GAME?.pointsName ?? 'pts'})`,
    content: `
      <div class="question-text">${q.q}</div>
      ${optionsHtml}
      <div class="answer-box">✅ Answer: <strong>${answerLabel}</strong></div>
      ${q.note ? `<div class="answer-note">${q.note}</div>` : ''}
      ${reportQuestionHtml(q)}`,
    actions: [
      { label: `✅ Correct (+${pts})`, class: 'btn btn-primary',
        callback: () => { _noteQuestion(true); addScore(player, pts); onDone(); } },
      { label: '❌ Incorrect', class: 'btn btn-secondary', callback: () => { _noteQuestion(false); onDone(); } },
    ],
  });
}

/** How the turn's question went — kept on the turn for the end-screen stats (G13). */
function _noteQuestion(right) { if (state.turn) state.turn.result = { question: right }; }

function _showPhysicalCard(diff, player, pts, onDone) {
  showModal({
    icon: diff === 'easy' ? '🟢' : '🔵',
    title: `${diff === 'easy' ? 'Easy' : 'Hard'} Question (physical card)`,
    content: `<strong>${esc(player.name)}</strong>, draw a <em>${diff}</em> card from the deck and read it aloud.
              <br><br>GM: award <strong>${pts} ${CONFIG.GAME?.pointsName ?? 'pts'}</strong> if correct.`,
    actions: [
      { label: `✅ Correct (+${pts})`, class: 'btn btn-primary',
        callback: () => { _noteQuestion(true); addScore(player, pts); onDone(); } },
      { label: '❌ Incorrect', class: 'btn btn-secondary', callback: () => { _noteQuestion(false); onDone(); } },
    ],
  });
}

// ── Action cards ──────────────────────────────────────────────────────────────

/**
 * The action space. Uses a digital card when the rules say so and the
 * edition has cards, otherwise the physical deck; a digital card can always be
 * swapped for a physical one. A resumed turn (host refresh) shows the same
 * card again: state.turn.actionCard holds it (null = physical deck).
 */
function _showActionModal(player, onDone) {
  const R = gameRules();
  timerSet(R.actions.timerSeconds);
  const perf  = R.scoring.actionPerformer;
  const guess = R.scoring.actionGuesser;

  let card = state.turn?.actionCard;
  if (card === undefined) card = R.actions.cards === 'digital' ? _drawActionCard(R.actions.kinds, R.actions.general) : null;
  if (state.turn) state.turn.actionCard = card;
  const onPhone = card ? _sendPrivateCard(player, card) : false;

  const actions = [
    { label: perf === guess ? `✅ Guessed! (+${perf} each)` : `✅ Guessed! (+${perf})`,
      class: 'btn btn-primary',
      callback: () => { addScore(player, perf); onDone(true); } },
    { label: '⏱ No guess / Time up', class: 'btn btn-secondary', callback: () => onDone(false) },
  ];
  if (card) {
    actions.push({ label: '📋 Use a physical card instead', class: 'btn btn-secondary',
      callback: () => {
        if (state.turn) state.turn.actionCard = null;
        if (onPhone) _sendPrivateCard(player, { kind: '', text: 'Draw a card from the physical deck instead.', note: '' });
        _showActionModal(player, onDone);
      } });
  }

  showModal({
    icon: CONFIG.SPACE_INFO.action?.icon ?? '🎬',
    title: 'Action Card!',
    content: _playerBadgeHtml(player) +
             (card ? _actionCardHtml(card, player, onPhone)
                   : `<p>Draw an <em>Action Card</em> from the deck and perform it!</p>`) +
             `<p>If guessed: performer <strong>+${perf}</strong>, guesser <strong>+${guess}</strong>.<br>
              <small data-host-only>Use the timer in the sidebar to manage time.</small></p>`,
    actions,
  });
}

/**
 * The action deck: the edition's cards, plus the general cards when `general`
 * is on (C4). General ids get a 'g' prefix ('g7') so they never clash with the
 * edition's numeric ids in the no-repeat tracking.
 */
function _actionDeck(general = true) {
  const deck = [...(window.ACTIONS_DATA || [])];
  if (general) deck.push(...(window.GENERAL_ACTIONS_DATA || []).map(a => ({ ...a, id: `g${a.id}` })));
  return deck;
}

/**
 * Draw an action card the table hasn't had yet (same no-repeat tracking as
 * questions, under the 'actions' key). Reshuffles when all have been used.
 * `kinds` limits the draw to the allowed kinds (rules); `general` mixes in the
 * general cards. Returns null if there are no (allowed) action cards.
 */
function _drawActionCard(kinds = null, general = true) {
  const all = _actionDeck(general).filter(a => !kinds || kinds.includes(a.kind));
  if (!all.length) return null;
  const used = _getAskedIds('actions');
  let pool = all.filter(a => !used.has(a.id));
  if (!pool.length) {
    _clearAskedIds('actions');
    pool = all;
    showToast('All action cards used — reshuffling!');
  }
  const card = pool[Math.floor(Math.random() * pool.length)];
  _markAsked('actions', card.id);
  return card;
}

/**
 * The card section of the action modal. The card text starts hidden behind a
 * toggle: on a phone game the performer already has it (the GM can peek);
 * otherwise the performer reveals it while the others look away.
 */
function _actionCardHtml(card, player, onPhone) {
  const kind = CONFIG.ACTION_KINDS?.[card.kind] ?? { icon: '🎬', label: 'Action', rule: '' };
  const who = onPhone
    ? `📱 The card is on <strong>${esc(player.name)}</strong>'s phone.`
    : `<strong>${esc(player.name)}</strong>, reveal your card — everyone else look away!`;
  return `
    <div class="action-card">
      <div class="action-card-kind">${kind.icon} ${esc(kind.label)}</div>
      <div class="action-card-rule">${esc(kind.rule)}</div>
      <p class="action-card-who">${who}</p>
      <button type="button" class="btn btn-secondary btn-small"
              onclick="this.nextElementSibling.classList.toggle('hidden')">
        ${onPhone ? '👁 GM: show / hide card' : '👁 Show / hide card'}
      </button>
      <div class="action-card-secret hidden" data-secret>
        <div class="action-card-text">${esc(card.text)}</div>
        ${card.note ? `<div class="action-card-note">${esc(card.note)}</div>` : ''}
      </div>
    </div>`;
}

// ── Deed Card Flow ────────────────────────────────────────────────────────────

function _showDeedCard(space, player, onDone) {
  const isGood     = space.type === 'good_deed';
  const card       = space.deed; // pre-assigned from deeds.js during board generation
  const spaceInfo  = CONFIG.SPACE_INFO[space.type] ?? {};
  const deedIcon   = spaceInfo.icon  ?? (isGood ? '✅' : '❌');
  const deedLabel  = spaceInfo.label ?? (isGood ? 'Good Deed' : 'Bad Deed');

  // Protection card absorbs one bad deed
  if (!isGood && player.protectedFromBadDeed) {
    player.protectedFromBadDeed = false;
    showModal({
      icon: '🛡️',
      title: 'Protected!',
      content: `${_playerBadgeHtml(player)}
                <p>Your protection card blocked this — the effect is cancelled!</p>`,
      actions: [{ label: '🛡️ Nice!', class: 'btn btn-primary', callback: onDone }],
    });
    return;
  }

  if (!card) {
    // No data loaded — fallback to physical card prompt
    showModal({
      icon: deedIcon,
      title: deedLabel,
      content: `<strong>${esc(player.name)}</strong>, draw a <em>${deedLabel}</em>
                card and read it aloud. Apply the effect shown on the card.
                <br>Use GM controls to adjust score or position if needed.`,
      actions: [{ label: 'Done', class: 'btn btn-primary', callback: onDone }],
    });
    return;
  }

  // Apply the effect automatically and show the result
  let effectDesc = '';
  const beforeApply = onDone; // we call this after showing the result

  switch (card.effect) {
    case 'score_add':
      effectDesc = `<div class="deed-effect deed-good">+${card.value} ${CONFIG.GAME?.pointsName ?? 'pts'}</div>`;
      break;
    case 'score_remove':
      effectDesc = `<div class="deed-effect deed-bad">−${card.value} ${CONFIG.GAME?.pointsName ?? 'pts'}</div>`;
      break;
    case 'move_forward':
      effectDesc = `<div class="deed-effect deed-good">▶ Move forward ${card.value} space${card.value !== 1 ? 's' : ''}</div>`;
      break;
    case 'move_back':
      effectDesc = `<div class="deed-effect deed-bad">◀ Move back ${card.value} space${card.value !== 1 ? 's' : ''}</div>`;
      break;
    case 'move_to_landmark':
      effectDesc = `<div class="deed-effect ${isGood ? 'deed-good' : 'deed-bad'}">📍 Go to: ${card.landmark}</div>`;
      break;
    case 'move_to_prev_landmark':
    case 'move_to_next_landmark': {
      const rel = _resolveRelativeLandmark(card.effect, player.position, card.value);
      const relName = rel?.name ?? 'nearest landmark';
      const relDir = card.effect === 'move_to_prev_landmark' ? '◀' : '▶';
      effectDesc = `<div class="deed-effect ${isGood ? 'deed-good' : 'deed-bad'}">${relDir} Go to: ${relName}</div>`;
      break;
    }
    case 'skip_turn':
      effectDesc = `<div class="deed-effect deed-bad">⏭ Skip your next turn</div>`;
      break;
    case 'extra_turn':
      effectDesc = `<div class="deed-effect deed-good">🎲 Roll again!</div>`;
      break;
    case 'all_players_gain':
      effectDesc = `<div class="deed-effect deed-good">Everyone +${card.value} ${CONFIG.GAME?.pointsName ?? 'pts'}</div>`;
      break;
    case 'all_players_lose':
      effectDesc = `<div class="deed-effect deed-bad">Everyone −${card.value} ${CONFIG.GAME?.pointsName ?? 'pts'}</div>`;
      break;
    case 'protection':
      effectDesc = `<div class="deed-effect deed-good">🛡️ Next bad deed cancelled</div>`;
      break;
    // move_to_next_landmark is now handled in the relative-landmark block above

  }

  // Resolve {landmark} placeholder in deed text using the relative target
  let deedText = card.text || '';
  if (deedText.includes('{landmark}')) {
    const relLm = _resolveRelativeLandmark(card.effect, player.position, card.value);
    deedText = deedText.replace(/\{landmark\}/g, relLm?.name ?? 'a landmark');
  }

  showModal({
    icon: deedIcon,
    title: isGood ? `${deedLabel}! 🌟` : deedLabel,
    content: `<div class="deed-text">${deedText}</div>${effectDesc}`,
    actions: [
      { label: 'Apply Effect', class: 'btn btn-primary',
        callback: () => { _applyDeedEffect(card, player); onDone(); } },
    ],
  });
}

/**
 * Resolve the target landmark for a relative-landmark effect given the player's
 * current position and the effect's value (1 = nearest, 2 = second, etc.).
 * Returns the landmark space object, or null if none found.
 */
function _resolveRelativeLandmark(effect, playerPosition, value) {
  const board = window._gameBoard;
  if (!board) return null;
  const n = Math.max(1, Math.round(value) || 1);
  if (effect === 'move_to_next_landmark') {
    const candidates = board.filter(s => s.type === 'landmark' && s.id > playerPosition);
    return candidates[n - 1] ?? candidates[candidates.length - 1] ?? null;
  }
  if (effect === 'move_to_prev_landmark') {
    const candidates = board.filter(s => s.type === 'landmark' && s.id < playerPosition).reverse();
    return candidates[n - 1] ?? candidates[candidates.length - 1] ?? null;
  }
  return null;
}

/** Apply a deed card, then give landmark points if it moved the player onto one. */
function _applyDeedEffect(card, player) {
  const before = player.position;
  _applyDeedEffectOnly(card, player);
  _landmarkArrival(card, player, before);
}

/**
 * A deed moved the player onto a landmark: points by the rules for good /
 * bad deed arrivals (0 = just information), announced with a small toast.
 */
function _landmarkArrival(card, player, before) {
  const space = window._gameBoard?.[player.position];
  if (!space || space.type !== 'landmark' || player.position === before) return;
  const pts = landmarkPoints(gameRules(), card.type === 'good' ? 'good' : 'bad');
  if (pts) addScore(player, pts);
  const unit = CONFIG.GAME?.pointsName ?? 'pts';
  showToast(`📍 ${player.name} arrived at ${space.name}${pts ? ` · ${pts > 0 ? '+' : ''}${pts} ${unit}` : ''}`, 3500);
}

function _applyDeedEffectOnly(card, player) {
  // game.js exposes state.board for landmark lookup
  switch (card.effect) {
    case 'score_add':
      addScore(player, card.value);
      break;
    case 'score_remove':
      addScore(player, -card.value);
      break;
    case 'move_forward':
      movePlayer(player, window._gameBoard, card.value);
      break;
    case 'move_back':
      movePlayer(player, window._gameBoard, -card.value);
      break;
    case 'move_to_landmark': {
      // Board generation guarantees the landmark is correctly positioned:
      //   bad deed → landmark is behind player (backward move / penalty)
      //   good deed → landmark is ahead of player (forward move / reward)
      const target = getLandmarkSpace(window._gameBoard, card.landmark);
      if (target) movePlayerToPosition(player, window._gameBoard, target.id);
      break;
    }
    case 'skip_turn':
      player.skipNextTurn = true;
      break;

    case 'extra_turn':
      player.hasExtraTurn = true;
      break;

    case 'all_players_gain': {
      const allP = window._gamePlayers || [];
      allP.forEach(p => addScore(p, card.value));
      break;
    }

    case 'all_players_lose': {
      const allP = window._gamePlayers || [];
      allP.forEach(p => addScore(p, -card.value));
      break;
    }

    case 'protection':
      player.protectedFromBadDeed = true;
      break;

    case 'move_to_next_landmark':
    case 'move_to_prev_landmark': {
      const target = _resolveRelativeLandmark(card.effect, player.position, card.value);
      if (target) movePlayerToPosition(player, window._gameBoard, target.id);
      break;
    }
  }
}

// ── Guesser Award ─────────────────────────────────────────────────────────────

function showGuesserModal(players, performer, onDone) {
  const others = players.filter(p => p.id !== performer.id);
  const guessPts = gameRules().scoring.actionGuesser;
  const options = others.map(p => ({
    label: `${p.name} guessed it! (+${guessPts})`,
    class: 'btn btn-secondary',
    callback: () => { addScore(p, guessPts); onDone(); },
  }));
  options.push({ label: 'No one guessed', class: 'btn btn-secondary', callback: onDone });
  showModal({
    icon: '🎯', title: 'Who guessed it?',
    content: `Award ${guessPts} ${CONFIG.GAME?.pointsName ?? 'pts'} to the first player who guessed correctly.`,
    actions: options,
  });
}

// ── End Screen ────────────────────────────────────────────────────────────────

function showEndScreen(players) {
  const sorted = getSortedPlayers(players);
  const ranks  = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣'];
  const { stats, awards } = endOfGameSummary(players, state.history);
  const statsById = new Map(stats.map(s => [s.id, s]));
  document.getElementById('final-scores').innerHTML = sorted.map((p, i) => `
    <div class="final-score-row">
      <div class="final-rank">${ranks[i] || `${i + 1}.`}</div>
      <div class="end-token" style="background:${esc(p.color)}">
        <div class="token-emoji">${esc(p.token || '●')}</div>
        <div class="token-initial">${esc((p.name || '?').slice(0, 2).toUpperCase())}</div>
      </div>
      <div class="final-name">${esc(p.name)}
        <div class="final-stats">${esc(statLine(statsById.get(p.id)))}</div>
      </div>
      <div class="final-points">${p.score} ${CONFIG.GAME?.pointsName ?? 'pts'}</div>
    </div>`).join('');
  document.getElementById('end-awards').innerHTML = awardsHtml(awards, players);
  showScreen('end-screen');
}

// ── End-of-game stats + awards (G13) ──────────────────────────────────────────

/** Stats per player and the awards, from the game history (js/shared/stats.js). */
function endOfGameSummary(players, history) {
  const stats  = gameStats(history, players);
  const labels = {
    good:     CONFIG.SPACE_INFO.good_deed?.label,
    bad:      CONFIG.SPACE_INFO.bad_deed?.label,
    landmark: CONFIG.SPACE_INFO.landmark?.label,
    points:   CONFIG.GAME?.pointsName,
  };
  const awards = gameAwards(stats, CONFIG.AWARDS, { minRolls: CONFIG.AWARD_MIN_ROLLS })
    .map(a => ({ ...a, text: awardText(a, labels) }));
  return { stats, awards };
}

/** "✅ 3/5 questions · 🎬 1/2 actions · 🎲 avg 3.4 · 👣 38 spaces" (empty parts left out). */
function statLine(s) {
  if (!s) return '';
  return [
    s.questions && `✅ ${s.questionsRight}/${s.questions} questions`,
    s.actions   && `🎬 ${s.actionsGuessed}/${s.actions} actions`,
    s.rolls     && `🎲 avg ${s.avgRoll}`,
    s.spaces    && `👣 ${s.spaces} spaces`,
  ].filter(Boolean).join(' · ');
}

/** Award cards: icon, title, who, why. */
function awardsHtml(awards, players) {
  if (!awards.length) return '';
  const name = id => players.find(p => p.id === id)?.name ?? '?';
  return `<h3 class="awards-title">Awards</h3><div class="awards-grid">` + awards.map(a => `
    <div class="award-card">
      <div class="award-icon">${esc(a.icon)}</div>
      <div class="award-title">${esc(a.title)}</div>
      <div class="award-who">${esc(a.playerIds.map(name).join(' & '))}</div>
      <div class="award-why">${esc(a.text)}</div>
    </div>`).join('') + `</div>`;
}

// ── Score Flyout ──────────────────────────────────────────────────────────────

function showScoreFlyout(player, amount) {
  const spaceEl = document.getElementById(`space-${player.position}`);
  if (!spaceEl) return;
  const rect = spaceEl.getBoundingClientRect();
  const flyout = document.createElement('div');
  flyout.className = `score-flyout ${amount > 0 ? 'score-pos' : 'score-neg'}`;
  const ptsLabel = CONFIG.GAME?.pointsName ?? 'pts';
  flyout.textContent = amount > 0 ? `+${amount} ${ptsLabel}` : `${amount} ${ptsLabel}`;
  flyout.style.left = `${rect.left + rect.width / 2}px`;
  flyout.style.top  = `${rect.top  + rect.height * 0.3}px`;
  flyout.style.animationDuration = `${CONFIG.ANIMATION?.flyoutMs ?? 1000}ms`;
  document.body.appendChild(flyout);
  flyout.addEventListener('animationend', () => flyout.remove());
}

// ── Game History ──────────────────────────────────────────────────────────────

function _spaceIcon(type) {
  return CONFIG.SPACE_INFO[type]?.icon ?? { question: '❓', action: '🎬', landmark: '🌍', skip: '⏭', finish: '🏁', start: '🚩', gm: '⚙️' }[type] ?? '•';
}

function renderHistoryPanel(history) {
  const list    = document.getElementById('history-list');
  const undoBtn = document.getElementById('undo-btn');
  if (!list) return;
  if (undoBtn) undoBtn.disabled = !history?.length;

  if (!history?.length) {
    list.innerHTML = '<div class="history-empty">No moves yet</div>';
    return;
  }

  list.innerHTML = [...history].reverse().map((e, i) => {
    const scoreDiff = e.scoreAfter - e.scoreBefore;
    const scoreStr  = scoreDiff !== 0
      ? `<span class="history-score ${scoreDiff > 0 ? 'hs-pos' : 'hs-neg'}">${scoreDiff > 0 ? '+' : ''}${scoreDiff}</span>`
      : '';
    const rollStr   = e.roll ? `🎲 ${e.roll}` : (e.spaceType === 'gm' ? '⚙️ GM' : '⏭ skipped');
    return `<div class="history-entry${i === 0 ? ' history-latest' : ''}">
      <div class="history-badge" style="background:${esc(e.playerColor)}">${esc(e.playerToken)}</div>
      <div class="history-info">
        <div class="history-main">${esc(e.playerName)} · ${rollStr}</div>
        <div class="history-detail">${_spaceIcon(e.spaceType)} Sp.${e.posAfter}${e.spaceName && e.spaceType !== 'skip' ? ' · ' + e.spaceName : ''} ${scoreStr}</div>
      </div>
    </div>`;
  }).join('');
}

// ── Board Legend ──────────────────────────────────────────────────────────────

function renderLegend() {
  const existing = document.getElementById('board-legend');
  if (existing) existing.remove();
  const legend = document.createElement('div');
  legend.id = 'board-legend';
  const types = ['question', 'action', 'good_deed', 'bad_deed', 'landmark', 'skip'];
  legend.innerHTML = types.map(t => {
    const info = CONFIG.SPACE_INFO[t];
    const icon = t === 'question' ? '<span class="legend-q">?</span>' : info.icon;
    return `<div class="legend-item">
      <div class="legend-space" style="background:${info.color}">${icon}</div>
      <span>${info.label}</span>
    </div>`;
  }).join('');
  // Inside the board area, so it only shows with the board (not on the end screen)
  document.getElementById('board-viewport').appendChild(legend);
}

// ── Timer ─────────────────────────────────────────────────────────────────────

const timer = {
  duration:  60,
  remaining: 60,
  running:   false,
  _interval: null,
};

function timerSet(secs) {
  timerStop();
  timer.duration  = secs;
  timer.remaining = secs;
  _timerRender();
}

function timerStartStop() {
  timer.running ? timerPause() : timerStart();
}

function timerStart() {
  if (timer.remaining <= 0) { timer.remaining = timer.duration; }
  timer.running = true;
  document.getElementById('timer-startstop-btn').textContent = '⏸ Pause';
  _timerRender();
  timer._interval = setInterval(() => {
    timer.remaining = Math.max(0, timer.remaining - 1);
    _timerRender();
    if (timer.remaining === 0) timerPause();
  }, 1000);
}

function timerPause() {
  timer.running = false;
  clearInterval(timer._interval);
  if (typeof _displayTimer === 'function') _displayTimer();
  const btn = document.getElementById('timer-startstop-btn');
  if (btn) btn.textContent = '▶ Start';
}

function timerStop() {
  timerPause();
  timer.remaining = timer.duration;
  _timerRender();
}

function timerReset() { timerStop(); }

function timerAdd(secs) {
  timer.remaining = Math.min(599, timer.remaining + secs);
  _timerRender();
}

function _timerRender() {
  const timeEl = document.getElementById('timer-time');
  const barEl  = document.getElementById('timer-bar');
  if (!timeEl || !barEl) return;

  const pct = timer.duration > 0 ? timer.remaining / timer.duration : 0;
  const mins = Math.floor(timer.remaining / 60);
  const secs = timer.remaining % 60;
  timeEl.textContent = mins > 0
    ? `${mins}:${String(secs).padStart(2, '0')}`
    : `${timer.remaining}s`;

  barEl.style.width = (pct * 100) + '%';
  barEl.style.background =
    pct > 0.5 ? '#43A047' :
    pct > 0.25 ? '#FF9800' : '#E53935';
  if (typeof _displayTimer === 'function') _displayTimer();   // TV display (G16)
}

// ── Toast notification ────────────────────────────────────────────────────────

function showToast(message, durationMs = 2500) {
  let el = document.getElementById('tx-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'tx-toast';
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.add('tx-toast-visible');
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => el.classList.remove('tx-toast-visible'), durationMs);
}

// ── Landmark Info Popup ───────────────────────────────────────────────────────

function showLandmarkInfo(space) {
  let overlay = document.getElementById('landmark-info-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'landmark-info-overlay';
    overlay.innerHTML = `
      <div id="landmark-info-box">
        <button id="landmark-info-close" aria-label="Close">✕</button>
        <img id="landmark-info-img" src="" alt="" onerror="this.style.display='none'">
        <h2 id="landmark-info-name"></h2>
        <p id="landmark-info-desc"></p>
      </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', e => { if (e.target === overlay) hideLandmarkInfo(); });
    document.getElementById('landmark-info-close').addEventListener('click', hideLandmarkInfo);
  }

  const img = document.getElementById('landmark-info-img');
  if (space.image) {
    img.src   = space.image;
    img.alt   = space.name;
    img.style.display = '';
  } else {
    img.style.display = 'none';
  }
  document.getElementById('landmark-info-name').textContent = space.name || 'Landmark';
  document.getElementById('landmark-info-desc').textContent = space.description || '';
  overlay.classList.add('visible');
}

function hideLandmarkInfo() {
  const overlay = document.getElementById('landmark-info-overlay');
  if (overlay) overlay.classList.remove('visible');
}
