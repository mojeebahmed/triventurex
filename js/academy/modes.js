/**
 * js/academy/modes.js — the Triventurex Academy modes.
 *
 * Each mode: registerMode({ id, icon, label, hint, filter, render(main, questions) }).
 * `questions` = what the shared filter selects (or every question when the mode
 * ignores the filter). Rounds are built by js/shared/academy.js (pure, tested).
 * Question text may hold a little HTML from the edition's CSV (like in the game);
 * answers, notes from users and landmark texts are escaped.
 */

const LETTERS = ['A', 'B', 'C', 'D'];
const _diffTag = q => (q.diff === 'hard' ? '🔵 Hard' : '🟢 Easy');
const _where = q => esc([q.cat, q.subcat, q.topic].filter(Boolean).join(' › '));
const _note = q => (q.note ? `<div class="ac-note">💡 ${q.note}</div>` : '');
const _pts = () => CONFIG.GAME?.pointsName ?? 'points';

/** A question's options as a list (no answer shown). */
function _optsHtml(q) {
  return isMulti(q) ? `<ol class="ac-opts">${q.opts.map((o, i) => `<li><b>${LETTERS[i]}</b> ${o}</li>`).join('')}</ol>` : '';
}

/** End-of-round summary: score, a few stars, and the questions to look at again. */
function _summaryHtml(score, total, missed, again = 'Play again') {
  const pct = total ? score / total : 0;
  const stars = pct >= 0.9 ? '⭐⭐⭐' : pct >= 0.6 ? '⭐⭐' : pct > 0 ? '⭐' : '🌱';
  const list = missed.length ? `
    <h3>Look at these again</h3>
    <ul class="ac-missed">${missed.map(q => `<li><div>${q.q}</div><div class="ac-answer">✅ ${esc(answerText(q))}</div>${_note(q)}</li>`).join('')}</ul>` : '';
  return `<div class="ac-summary">
      <div class="ac-stars">${stars}</div>
      <h2>${score} / ${total}</h2>
      <p>${pct === 1 ? 'Perfect — you are ready to play!' : pct >= 0.6 ? 'Well done!' : 'Keep learning — you will get there!'}</p>
      <button type="button" class="btn btn-primary" data-action="again">${again}</button>
    </div>${list}`;
}

// ── 📚 Explore ──────────────────────────────────────────────────────────────────

const _ex = { answers: false, markedOnly: false, limit: 40, editing: null };

/** One question in the Explore / Review list (same look as the game's Questions tab). */
function _itemHtml(q, { marked, reviewed, review }) {
  const mark = marked[q.id];
  const showAll = review || _ex.answers;
  const opts = isMulti(q)
    ? `<ol class="qx-opts">${q.opts.map((o, i) => `<li class="${LETTERS[i] === q.answer ? 'qx-correct' : ''}"><b>${LETTERS[i]}</b> ${o}</li>`).join('')}</ol>` : '';
  const answer = `<div class="qx-answer">✅ ${esc(answerLabel(q))}${q.note ? `<div class="qx-note-text">${q.note}</div>` : ''}</div>`;
  const editing = _ex.editing === q.id;
  return `
    <div class="qx-item ${mark ? 'marked' : ''} ${showAll ? 'show-answers' : ''} ${review && reviewed[q.id] ? 'reviewed' : ''}" data-id="${q.id}">
      <div class="qx-meta">#${q.id} · ${_diffTag(q)} · ${_where(q)}</div>
      <div class="qx-q">${q.q}</div>
      ${opts}
      <details class="qx-reveal" ${showAll ? 'open' : ''}><summary>Answer</summary>${answer}</details>
      ${mark && !editing ? `<div class="qx-mark">🚩 ${esc(mark.note || 'Marked')}</div>` : ''}
      ${editing ? `
        <div class="qx-edit">
          <input type="text" class="qx-note-input" maxlength="300" value="${esc(mark?.note || '')}" placeholder="What's wrong? (optional)">
          <button type="button" class="btn btn-primary btn-small" data-action="save">Save</button>
          <button type="button" class="btn btn-secondary btn-small" data-action="cancel">Cancel</button>
        </div>` : `
        <div class="qx-actions">
          ${review ? `<label class="ac-reviewed"><input type="checkbox" data-action="reviewed" ${reviewed[q.id] ? 'checked' : ''}> ✓ Reviewed</label>` : ''}
          ${mark
            ? `<button type="button" class="link-btn" data-action="edit">✏️ Edit note</button>
               <button type="button" class="link-btn" data-action="unmark">Unmark</button>`
            : `<button type="button" class="link-btn" data-action="edit">🚩 Mark as wrong / unclear</button>`}
        </div>`}
    </div>`;
}

/** Mark / unmark / note / reviewed clicks in a question list; `redraw` after a change. */
function _listActions(list, redraw) {
  list.addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    const item = e.target.closest('.qx-item');
    if (!btn || !item) return;
    const id = Number(item.dataset.id);
    switch (btn.dataset.action) {
      case 'edit':     _ex.editing = id; redraw(); item.ownerDocument.querySelector(`.qx-item[data-id="${id}"] .qx-note-input`)?.focus(); return;
      case 'cancel':   _ex.editing = null; break;
      case 'save':     markQuestion(id, item.querySelector('.qx-note-input').value); _ex.editing = null; break;
      case 'unmark':   unmarkQuestion(id); break;
      case 'reviewed': setReviewed(id, btn.checked); break;
      case 'more':     _ex.limit += 40; break;
      default: return;
    }
    redraw();
  });
  list.addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.classList.contains('qx-note-input')) e.target.closest('.qx-item').querySelector('[data-action="save"]').click();
  });
}

registerMode({
  id: 'explore', icon: '📚', label: 'Explore', filter: true,
  hint: 'Browse the questions and answers; mark one that looks wrong',
  render(main, questions) {
    _ex.limit = 40; _ex.editing = null;
    main.innerHTML = `
      <div class="ac-bar">
        <label class="qx-check"><input type="checkbox" id="ac-answers" ${_ex.answers ? 'checked' : ''}> Show answers</label>
        <label class="qx-check"><input type="checkbox" id="ac-marked" ${_ex.markedOnly ? 'checked' : ''}> 🚩 Marked only</label>
        <span class="ac-spacer"></span>
        <span id="ac-count" class="qx-count"></span>
      </div>
      <div id="ac-list"></div>`;
    const list = main.querySelector('#ac-list');
    const draw = () => {
      const marked = loadMarkedQuestions();
      const shownQs = _ex.markedOnly ? questions.filter(q => marked[q.id]) : questions;
      main.querySelector('#ac-count').textContent = `${shownQs.length} question${shownQs.length === 1 ? '' : 's'}`;
      const page = shownQs.slice(0, _ex.limit);
      list.innerHTML = page.length
        ? page.map(q => _itemHtml(q, { marked, reviewed: {}, review: false })).join('') +
          (page.length < shownQs.length ? `<button type="button" class="btn btn-secondary btn-small" data-action="more">Show more</button>` : '')
        : emptyHtml('No questions match.');
    };
    main.querySelector('#ac-answers').onchange = e => { _ex.answers = e.target.checked; draw(); };
    main.querySelector('#ac-marked').onchange = e => { _ex.markedOnly = e.target.checked; draw(); };
    _listActions(list, draw);
    draw();
  },
});

// ── 🃏 Flashcards ───────────────────────────────────────────────────────────────

registerMode({
  id: 'flashcards', icon: '🃏', label: 'Flashcards', filter: true,
  hint: 'Guess the answer, then turn the card over',
  render(main, questions) {
    let deck = quizRound(questions, 0);
    let flipped = false, known = 0;
    const total = deck.length;
    const draw = () => {
      if (!total) { main.innerHTML = emptyHtml('No cards for this choice.'); return; }
      if (!deck.length) {
        main.innerHTML = `<div class="ac-summary"><div class="ac-stars">🎉</div><h2>All ${total} cards done!</h2>
          <p>You knew them all in the end.</p><button type="button" class="btn btn-primary" data-action="again">Shuffle and start again</button></div>`;
        return;
      }
      const q = deck[0];
      main.innerHTML = `
        <div class="ac-bar"><span class="qx-count">🃏 ${deck.length} card${deck.length === 1 ? '' : 's'} left · 😊 ${known} known</span>
          <span class="ac-spacer"></span><span class="ac-hint">Tap the card or press Space to turn it</span></div>
        <button type="button" class="ac-card ${flipped ? 'flipped' : ''}" data-action="flip" aria-label="Turn the card">
          <div class="ac-card-meta">${_diffTag(q)} · ${_where(q)}</div>
          <div class="ac-card-q">${q.q}</div>
          ${_optsHtml(q)}
          ${flipped
            ? `<div class="ac-card-a">✅ ${esc(answerText(q))}</div>${_note(q)}`
            : `<div class="ac-card-turn">🤔 What is your answer? Tap to see it</div>`}
        </button>
        <div class="ac-actions">
          ${flipped
            ? `<button type="button" class="btn btn-secondary" data-action="notyet">🔁 Not yet</button>
               <button type="button" class="btn btn-primary" data-action="knew">😊 I knew it</button>`
            : `<button type="button" class="btn btn-primary" data-action="flip">Turn the card</button>`}
        </div>`;
    };
    const act = a => {
      if (a === 'flip')   flipped = !flipped;
      if (a === 'knew')   { deck = deck.slice(1); known++; flipped = false; }
      if (a === 'notyet') { deck = requeue(deck); flipped = false; }
      if (a === 'again')  { deck = quizRound(questions, 0); known = 0; flipped = false; }
      draw();
    };
    main.onclick = e => { const b = e.target.closest('[data-action]'); if (b) act(b.dataset.action); };
    const key = e => {
      if (e.target.closest('input, select, textarea')) return;
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); act('flip'); }
    };
    document.addEventListener('keydown', key);
    onLeaveMode(() => { document.removeEventListener('keydown', key); main.onclick = null; });
    draw();
  },
});

// ── ✏️ Practice quiz ────────────────────────────────────────────────────────────

let _quizSize = 10;

registerMode({
  id: 'quiz', icon: '✏️', label: 'Quiz', filter: true,
  hint: 'A practice round with your score at the end',
  render(main, questions) {
    let items, i, score, missed, answered;
    const start = () => { items = quizRound(questions, _quizSize); i = 0; score = 0; missed = []; answered = null; draw(); };
    const draw = () => {
      if (!items.length) { main.innerHTML = emptyHtml('No questions for this choice.'); return; }
      if (i >= items.length) { main.innerHTML = _summaryHtml(score, items.length, missed); return; }
      const q = items[i];
      const multi = isMulti(q);
      let body;
      if (multi) {
        body = `<div class="ac-choices">${q.opts.map((o, k) => {
          const cls = answered === null ? '' : k === correctIndex(q) ? 'right' : k === answered ? 'wrong' : 'dim';
          return `<button type="button" class="ac-choice ${cls}" data-choice="${k}" ${answered !== null ? 'disabled' : ''}><b>${LETTERS[k]}</b> ${o}</button>`;
        }).join('')}</div>`;
      } else if (answered === null) {
        body = `<div class="ac-actions"><button type="button" class="btn btn-primary" data-action="reveal">Show the answer</button></div>`;
      } else if (answered === 'shown') {
        body = `<div class="ac-card-a">✅ ${esc(answerText(q))}</div>${_note(q)}
          <p class="ac-hint">Did you get it right?</p>
          <div class="ac-actions"><button type="button" class="btn btn-secondary" data-action="selfwrong">❌ Not quite</button>
          <button type="button" class="btn btn-primary" data-action="selfright">✅ I got it</button></div>`;
      }
      const after = answered !== null && answered !== 'shown'
        ? `${multi ? '' : `<div class="ac-card-a">✅ ${esc(answerText(q))}</div>`}${_note(q)}
           <div class="ac-actions"><button type="button" class="btn btn-primary" data-action="next">${i + 1 < items.length ? 'Next question →' : 'See my score'}</button></div>` : '';
      main.innerHTML = `
        <div class="ac-bar">
          <span class="qx-count">Question ${i + 1} of ${items.length} · ✅ ${score}</span><span class="ac-spacer"></span>
          <label class="qx-check">Round <select id="ac-quiz-size" class="settings-select">
            ${[5, 10, 20].map(n => `<option ${n === _quizSize ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
        </div>
        <div class="ac-panel">
          <div class="ac-card-meta">${_diffTag(q)} · ${_where(q)}</div>
          <div class="ac-card-q">${q.q}</div>
          ${body || ''}${after}
        </div>`;
      main.querySelector('#ac-quiz-size').onchange = e => { _quizSize = Number(e.target.value); start(); };
    };
    main.onclick = e => {
      const q = items?.[i];
      const c = e.target.closest('[data-choice]');
      if (c && answered === null) {
        answered = Number(c.dataset.choice);
        if (answered === correctIndex(q)) score++; else missed.push(q);
        draw(); return;
      }
      const b = e.target.closest('[data-action]');
      if (!b) return;
      switch (b.dataset.action) {
        case 'reveal':    answered = 'shown'; break;
        case 'selfright': score++; answered = 'right'; break;
        case 'selfwrong': missed.push(q); answered = 'wrong'; break;
        case 'next':      i++; answered = null; break;
        case 'again':     start(); return;
      }
      draw();
    };
    onLeaveMode(() => { main.onclick = null; });
    start();
  },
});

// ── 🧩 Match pairs ──────────────────────────────────────────────────────────────

registerMode({
  id: 'match', icon: '🧩', label: 'Match', filter: true,
  hint: 'Tap a question, then its answer',
  render(main, questions) {
    let pairs, answers, pick, done, tries;
    const start = () => {
      pairs = matchPairs(questions, 6);
      answers = shuffled(pairs);
      pick = null; done = new Set(); tries = 0;
      draw();
    };
    const draw = () => {
      if (pairs.length < 3) { main.innerHTML = emptyHtml('Not enough questions with short answers to match here.'); return; }
      if (done.size === pairs.length) {
        main.innerHTML = `<div class="ac-summary"><div class="ac-stars">${tries <= pairs.length + 1 ? '⭐⭐⭐' : tries <= pairs.length * 2 ? '⭐⭐' : '⭐'}</div>
          <h2>All ${pairs.length} matched!</h2><p>In ${tries} tries.</p>
          <button type="button" class="btn btn-primary" data-action="again">New pairs</button></div>`;
        return;
      }
      const card = (p, side) => `<button type="button" class="ac-match ${done.has(p.id) ? 'done' : ''} ${pick?.side === side && pick.id === p.id ? 'picked' : ''}"
          data-side="${side}" data-id="${p.id}" ${done.has(p.id) ? 'disabled' : ''}>${side === 'q' ? p.question : esc(p.answer)}</button>`;
      main.innerHTML = `
        <div class="ac-bar"><span class="qx-count">🧩 ${done.size} of ${pairs.length} matched · ${tries} tries</span>
          <span class="ac-spacer"></span><button type="button" class="btn btn-secondary btn-small" data-action="again">New pairs</button></div>
        <div class="ac-match-grid">
          <div class="ac-match-col"><h3>Questions</h3>${pairs.map(p => card(p, 'q')).join('')}</div>
          <div class="ac-match-col"><h3>Answers</h3>${answers.map(p => card(p, 'a')).join('')}</div>
        </div>`;
    };
    main.onclick = e => {
      if (e.target.closest('[data-action="again"]')) { start(); return; }
      const b = e.target.closest('.ac-match');
      if (!b || b.disabled) return;
      const sel = { side: b.dataset.side, id: Number(b.dataset.id) };
      if (!pick || pick.side === sel.side) { pick = sel; draw(); return; }
      tries++;
      if (pick.id === sel.id) { done.add(sel.id); pick = null; draw(); return; }
      const other = main.querySelector(`.ac-match[data-side="${pick.side}"][data-id="${pick.id}"]`);
      [b, other].forEach(x => x?.classList.add('shake'));
      pick = null;
      setTimeout(draw, 450);
    };
    onLeaveMode(() => { main.onclick = null; });
    start();
  },
});

// ── ✔️ True or false ────────────────────────────────────────────────────────────

registerMode({
  id: 'truefalse', icon: '✔️', label: 'True or false', filter: true,
  hint: 'Is the answer shown right or wrong?',
  render(main, questions) {
    let items, i, score, missed, said;
    const start = () => { items = trueFalseItems(questions, 10); i = 0; score = 0; missed = []; said = null; draw(); };
    const draw = () => {
      if (!items.length) { main.innerHTML = emptyHtml('True or false needs multiple-choice questions.'); return; }
      if (i >= items.length) { main.innerHTML = _summaryHtml(score, items.length, missed); return; }
      const { q, shown, isTrue } = items[i];
      const right = said !== null && said === isTrue;
      main.innerHTML = `
        <div class="ac-bar"><span class="qx-count">Statement ${i + 1} of ${items.length} · ✅ ${score}</span></div>
        <div class="ac-panel">
          <div class="ac-card-meta">${_diffTag(q)} · ${_where(q)}</div>
          <div class="ac-card-q">${q.q}</div>
          <div class="ac-statement">Answer: <b>${esc(shown)}</b></div>
          ${said === null ? `
            <div class="ac-actions ac-tf">
              <button type="button" class="btn ac-true" data-say="1">✅ True</button>
              <button type="button" class="btn ac-false" data-say="0">❌ False</button>
            </div>` : `
            <div class="ac-feedback ${right ? 'right' : 'wrong'}">${right ? '🎉 Right!' : '🙈 Not this time.'}
              ${isTrue ? 'That is the answer.' : `The answer is <b>${esc(answerText(q))}</b>.`}</div>
            ${_note(q)}
            <div class="ac-actions"><button type="button" class="btn btn-primary" data-action="next">${i + 1 < items.length ? 'Next →' : 'See my score'}</button></div>`}
        </div>`;
    };
    main.onclick = e => {
      const s = e.target.closest('[data-say]');
      if (s && said === null) {
        said = s.dataset.say === '1';
        if (said === items[i].isTrue) score++; else missed.push(items[i].q);
        draw(); return;
      }
      const b = e.target.closest('[data-action]');
      if (b?.dataset.action === 'next') { i++; said = null; draw(); }
      if (b?.dataset.action === 'again') start();
    };
    onLeaveMode(() => { main.onclick = null; });
    start();
  },
});

// ── ⚡ Speed round ──────────────────────────────────────────────────────────────

const SPEED_SECONDS = 60;

registerMode({
  id: 'speed', icon: '⚡', label: 'Speed round', filter: true,
  hint: `As many as you can in ${SPEED_SECONDS} seconds`,
  render(main, questions) {
    let pool, i, score, missed, left, timer = null, flash = '';
    const stop = () => { clearInterval(timer); timer = null; };
    const intro = () => {
      stop();
      const n = speedPool(questions).length;
      main.innerHTML = n ? `<div class="ac-summary"><div class="ac-stars">⚡</div><h2>Speed round</h2>
          <p>Answer as many questions as you can in ${SPEED_SECONDS} seconds.</p>
          <button type="button" class="btn btn-primary" data-action="go">Start!</button></div>`
        : emptyHtml('The speed round needs multiple-choice questions.');
    };
    const start = () => {
      pool = speedPool(questions); i = 0; score = 0; missed = []; left = SPEED_SECONDS; flash = '';
      timer = setInterval(() => { left--; if (left <= 0) finish(); else draw(); }, 1000);
      draw();
    };
    const finish = () => { stop(); main.innerHTML = _summaryHtml(score, i, missed, 'Try again'); };
    const draw = () => {
      if (i >= pool.length) { finish(); return; }
      const q = pool[i];
      main.innerHTML = `
        <div class="ac-bar"><span class="ac-timer ${left <= 10 ? 'low' : ''}">⏱ ${left}s</span>
          <span class="qx-count">✅ ${score} · ${flash}</span></div>
        <div class="ac-speed-track"><div style="width:${(left / SPEED_SECONDS) * 100}%"></div></div>
        <div class="ac-panel">
          <div class="ac-card-q">${q.q}</div>
          <div class="ac-choices">${q.opts.map((o, k) => `<button type="button" class="ac-choice" data-choice="${k}"><b>${LETTERS[k]}</b> ${o}</button>`).join('')}</div>
        </div>`;
    };
    main.onclick = e => {
      const b = e.target.closest('[data-action]');
      if (b?.dataset.action === 'go' || b?.dataset.action === 'again') { start(); return; }
      const c = e.target.closest('[data-choice]');
      if (!c || !timer) return;
      const q = pool[i];
      if (Number(c.dataset.choice) === correctIndex(q)) { score++; flash = '🎉 Right!'; }
      else { missed.push(q); flash = '🙈 Missed one'; }
      i++;
      draw();
    };
    onLeaveMode(() => { stop(); main.onclick = null; });
    intro();
  },
});

// ── 🗺️ Places ──────────────────────────────────────────────────────────────────

registerMode({
  id: 'places', icon: '🗺️', label: 'Places', filter: false,
  hint: 'The landmarks of this edition — and a "Where am I?" game',
  render(main) {
    const lms = CONFIG.LANDMARKS || [];
    const label = CONFIG.SPACE_INFO?.landmark?.label ?? 'Landmark';
    let round = null, i = 0, score = 0, missed = [], said = null;
    const gallery = () => {
      round = null;
      main.innerHTML = lms.length ? `
        <div class="ac-bar"><span class="qx-count">🗺️ ${lms.length} × ${esc(label)}</span><span class="ac-spacer"></span>
          <button type="button" class="btn btn-primary btn-small" data-action="where">🧭 Where am I?</button></div>
        <div class="ac-places">${lms.map(l => `
          <details class="ac-place">
            <summary>${l.image ? `<img src="${esc(l.image)}" alt="" loading="lazy">` : ''}<span>${esc(l.name)}</span></summary>
            <p>${esc(l.description || '')}</p>
          </details>`).join('')}</div>
        <p class="ac-hint ac-credits">Photos: Wikimedia Commons — see the edition's CREDITS.md.</p>`
        : emptyHtml('This edition has no places.');
    };
    const play = () => {
      if (!round) return gallery();
      if (i >= round.length) {
        main.innerHTML = _summaryHtml(score, round.length, [], 'Play again') +
          `<div class="ac-actions"><button type="button" class="btn btn-secondary" data-action="gallery">Back to the places</button></div>`;
        return;
      }
      const r = round[i];
      main.innerHTML = `
        <div class="ac-bar"><span class="qx-count">🧭 Where am I? ${i + 1} of ${round.length} · ✅ ${score}</span><span class="ac-spacer"></span>
          <button type="button" class="btn btn-secondary btn-small" data-action="gallery">Back to the places</button></div>
        <div class="ac-panel">
          <img class="ac-where-img" src="${esc(r.landmark.image)}" alt="Which place is this?">
          <div class="ac-choices">${r.options.map((name, k) => {
            const cls = said === null ? '' : k === r.answer ? 'right' : k === said ? 'wrong' : 'dim';
            return `<button type="button" class="ac-choice ${cls}" data-choice="${k}" ${said !== null ? 'disabled' : ''}>${esc(name)}</button>`;
          }).join('')}</div>
          ${said !== null ? `<div class="ac-note">${esc(r.landmark.description || '')}</div>
            <div class="ac-actions"><button type="button" class="btn btn-primary" data-action="next">${i + 1 < round.length ? 'Next →' : 'See my score'}</button></div>` : ''}
        </div>`;
    };
    main.onclick = e => {
      const c = e.target.closest('[data-choice]');
      if (c && round && said === null) {
        said = Number(c.dataset.choice);
        if (said === round[i].answer) score++;
        play(); return;
      }
      const a = e.target.closest('[data-action]')?.dataset.action;
      if (a === 'where' || a === 'again') { round = placesQuiz(lms, 10); i = 0; score = 0; said = null; play(); }
      if (a === 'next') { i++; said = null; play(); }
      if (a === 'gallery') gallery();
    };
    onLeaveMode(() => { main.onclick = null; });
    gallery();
  },
});

// ── 🖨️ Print cards ─────────────────────────────────────────────────────────────

const PRINT_MAX = 300;

registerMode({
  id: 'print', icon: '🖨️', label: 'Print cards', filter: true,
  hint: 'Print the chosen questions as cards to cut out',
  render(main, questions) {
    const cards = questions.slice(0, PRINT_MAX);
    const name = CONFIG.GAME?.editionName ?? '';
    main.innerHTML = `
      <div class="ac-bar ac-no-print">
        <span class="qx-count">🖨️ ${cards.length} card${cards.length === 1 ? '' : 's'}${questions.length > PRINT_MAX ? ` (the first ${PRINT_MAX} — choose a topic to print the rest)` : ''}</span>
        <span class="ac-spacer"></span>
        <button type="button" class="btn btn-primary btn-small" data-action="print" ${cards.length ? '' : 'disabled'}>🖨️ Print</button>
      </div>
      <p class="ac-hint ac-no-print">Cut along the solid lines and fold each card on the dashed line — question on the front, answer on the back.</p>
      ${cards.length ? `<div class="ac-print-grid">${cards.map(q => `
        <div class="ac-print-card">
          <div class="ac-print-front">
            <div class="ac-card-meta">${esc(CONFIG.GAME?.editionIcon ?? '')} ${esc(name)} · ${_diffTag(q)}</div>
            <div class="ac-card-q">${q.q}</div>${_optsHtml(q)}
          </div>
          <div class="ac-print-back">✅ ${esc(answerText(q))}${q.note ? `<div class="ac-print-note">${q.note}</div>` : ''}</div>
        </div>`).join('')}</div>` : emptyHtml('No questions to print.')}`;
    main.onclick = e => { if (e.target.closest('[data-action="print"]')) window.print(); };
    onLeaveMode(() => { main.onclick = null; });
  },
});

// ── 🔍 Review (for reviewers) ───────────────────────────────────────────────────

const _rv = { show: 'all' };   // 'all' | 'todo' | 'marked'

registerMode({
  id: 'review', icon: '🔍', label: 'Review', filter: true,
  hint: 'Check every question: tick it as reviewed or mark it with a note',
  render(main, questions) {
    _ex.limit = 40; _ex.editing = null;
    main.innerHTML = `
      <div class="ac-bar">
        <select id="ac-rv-show" class="settings-select">
          <option value="all">All questions</option><option value="todo">Not reviewed yet</option><option value="marked">🚩 Marked</option>
        </select>
        <span class="ac-spacer"></span>
        <button type="button" class="btn btn-secondary btn-small" data-rv="copy">📋 Copy report</button>
        <button type="button" class="btn btn-secondary btn-small" data-rv="clear">Clear ticks</button>
      </div>
      <div id="ac-rv-progress" class="ac-progress"></div>
      <div id="ac-list"></div>`;
    const list = main.querySelector('#ac-list');
    main.querySelector('#ac-rv-show').value = _rv.show;
    const draw = () => {
      const marked = loadMarkedQuestions(), reviewed = loadReviewed();
      const s = reviewStats(acQuestions(), reviewed, marked);
      main.querySelector('#ac-rv-progress').innerHTML = `
        <div class="ac-progress-bar"><div style="width:${s.total ? (s.reviewed / s.total) * 100 : 0}%"></div></div>
        <span>✓ ${s.reviewed} of ${s.total} reviewed · 🚩 ${s.marked} marked · ${s.left} to go</span>`;
      const shownQs = questions.filter(q => _rv.show === 'all' || (_rv.show === 'todo' ? !reviewed[q.id] : marked[q.id]));
      const page = shownQs.slice(0, _ex.limit);
      list.innerHTML = page.length
        ? page.map(q => _itemHtml(q, { marked, reviewed, review: true })).join('') +
          (page.length < shownQs.length ? `<button type="button" class="btn btn-secondary btn-small" data-action="more">Show more</button>` : '')
        : emptyHtml(_rv.show === 'todo' ? '🎉 Everything here is reviewed.' : 'No questions match.');
    };
    main.querySelector('#ac-rv-show').onchange = e => { _rv.show = e.target.value; _ex.limit = 40; draw(); };
    main.querySelector('[data-rv="copy"]').onclick = () => {
      const s = reviewStats(acQuestions(), loadReviewed(), loadMarkedQuestions());
      const name = CONFIG.GAME?.editionName ?? getActiveEditionId();
      const text = `Review of ${name}: ${s.reviewed} of ${s.total} questions reviewed, ${s.marked} marked.\n\n` +
        markedReport(loadMarkedQuestions(), acQuestions(), name);
      copyText(text, 'Report copied — paste it into an email or message.');
    };
    main.querySelector('[data-rv="clear"]').onclick = () => {
      if (confirm('Remove all "reviewed" ticks for this edition? Marks and notes stay.')) { clearReviewed(); draw(); }
    };
    _listActions(list, draw);
    draw();
  },
});
