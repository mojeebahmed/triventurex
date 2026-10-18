/**
 * question-explorer.js
 * Setup screen tab *📚 Questions* (G19): browse the edition's questions by
 * category > subcategory > topic, search, filter by difficulty, peek at
 * answers, and mark a question as wrong / unclear with a note. The same
 * marked list is filled from the game (🚩 on a question card, G14) and can
 * be copied out to fix questions.csv. Pure parts: js/shared/questions.js.
 */

const QX_PAGE = 60;   // questions drawn at a time ("Show more" adds another page)

const _qx = { path: [], text: '', diff: 'all', markedOnly: false, answers: false, limit: QX_PAGE, editing: null };

const _qxQuestions = () => window.QUESTIONS_DATA || [];
const _qxLabel = name => name || 'Other';

function renderQuestionExplorer() {
  if (!document.getElementById('qx-list')) return;
  _renderQxTree();
  _renderQxList();
  updateMarkedBadge();
}

/** The edition changed: start again from "All questions". */
function resetQuestionExplorer() {
  Object.assign(_qx, { path: [], text: '', limit: QX_PAGE, editing: null });
  const search = document.getElementById('qx-search');
  if (search) search.value = '';
  renderQuestionExplorer();
}

// ── Tree (left) ─────────────────────────────────────────────────────────────────

function _renderQxTree() {
  const tree = questionTree(_qxQuestions());
  const [cat, sub] = _qx.path;
  const btn = (path, label, count, depth) => {
    const active = JSON.stringify(path) === JSON.stringify(_qx.path);
    return `<button type="button" class="qx-node depth-${depth} ${active ? 'active' : ''}"
              data-path="${esc(JSON.stringify(path))}"><span>${esc(label)}</span><small>${count}</small></button>`;
  };
  let html = btn([], 'All questions', _qxQuestions().length, 0);
  for (const c of tree) {
    html += btn([c.name], _qxLabel(c.name), c.count, 0);
    if (_qx.path.length && cat !== c.name) continue;                  // only the open branch
    for (const s of c.children) {
      html += btn([c.name, s.name], _qxLabel(s.name), s.count, 1);
      if (_qx.path.length < 2 || sub !== s.name) continue;
      for (const t of s.children) html += btn([c.name, s.name, t.name], t.name, t.count, 2);
    }
  }
  document.getElementById('qx-tree').innerHTML = html;
}

// ── List (right) ────────────────────────────────────────────────────────────────

function _renderQxList() {
  const marked = loadMarkedQuestions();
  const onlyIds = _qx.markedOnly ? new Set(Object.keys(marked).map(Number)) : null;
  const found = filterQuestions(_qxQuestions(), { path: _qx.path, text: _qx.text, diff: _qx.diff, onlyIds });
  const shown = found.slice(0, _qx.limit);
  const where = _qx.path.length ? _qx.path.map(_qxLabel).join(' › ') : 'All questions';
  document.getElementById('qx-count').textContent =
    `${where} · ${found.length} question${found.length === 1 ? '' : 's'}` + (shown.length < found.length ? ` (showing ${shown.length})` : '');
  document.getElementById('qx-list').innerHTML = shown.length
    ? shown.map(q => _qxItemHtml(q, marked[q.id])).join('') +
      (shown.length < found.length ? `<button type="button" class="btn btn-secondary btn-small qx-more" data-action="more">Show more</button>` : '')
    : `<p class="qx-empty">No questions match.</p>`;
}

function _qxItemHtml(q, mark) {
  const letters = ['A', 'B', 'C', 'D'];
  const opts = q.opts?.length
    ? `<ol class="qx-opts">${q.opts.map((o, i) =>
        `<li class="${letters[i] === q.answer ? 'qx-correct' : ''}"><b>${letters[i]}</b> ${o}</li>`).join('')}</ol>` : '';
  const answer = `<div class="qx-answer">✅ ${esc(answerLabel(q))}${q.note ? `<div class="qx-note-text">${q.note}</div>` : ''}</div>`;
  const editing = _qx.editing === q.id;
  return `
    <div class="qx-item ${mark ? 'marked' : ''} ${_qx.answers ? 'show-answers' : ''}" data-id="${q.id}">
      <div class="qx-meta">#${q.id} · ${q.diff === 'hard' ? '🔵 Hard' : '🟢 Easy'} · ${esc([q.cat, q.subcat, q.topic].filter(Boolean).join(' › '))}</div>
      <div class="qx-q">${q.q}</div>
      ${opts}
      <details class="qx-reveal" ${_qx.answers ? 'open' : ''}><summary>Answer</summary>${answer}</details>
      ${mark && !editing ? `<div class="qx-mark">🚩 ${esc(mark.note || 'Marked')}</div>` : ''}
      ${editing ? `
        <div class="qx-edit">
          <input type="text" class="qx-note-input" maxlength="300" value="${esc(mark?.note || '')}" placeholder="What's wrong? (optional)">
          <button type="button" class="btn btn-primary btn-small" data-action="save">Save</button>
          <button type="button" class="btn btn-secondary btn-small" data-action="cancel">Cancel</button>
        </div>` : `
        <div class="qx-actions">
          ${mark
            ? `<button type="button" class="link-btn" data-action="edit">✏️ Edit note</button>
               <button type="button" class="link-btn" data-action="unmark">Unmark</button>`
            : `<button type="button" class="link-btn" data-action="edit">🚩 Mark as wrong / unclear</button>`}
        </div>`}
    </div>`;
}

// ── Marked list ─────────────────────────────────────────────────────────────────

/** Open Triventurex Academy (academy.html) for the active edition in a new tab. */
function openAcademy() {
  window.open(`academy.html?edition=${encodeURIComponent(getActiveEditionId() || '')}`, '_blank', 'noopener');
}

/** Tab badge + footer line: how many questions are marked in this edition. */
function updateMarkedBadge() {
  const n = Object.keys(loadMarkedQuestions()).length;
  const badge = document.getElementById('qx-tab-badge');
  if (badge) { badge.textContent = `🚩 ${n}`; badge.classList.toggle('hidden', !n); }
  const sum = document.getElementById('qx-marked-summary');
  if (sum) sum.textContent = n ? `🚩 ${n} marked in this edition` : 'No questions marked';
}

/** Copy the marked questions (with notes) as text, to fix questions.csv. */
function copyMarkedQuestions() {
  const text = markedReport(loadMarkedQuestions(), _qxQuestions(), CONFIG.GAME?.editionName || '');
  const box = document.getElementById('qx-export');
  box.value = text;
  box.classList.remove('hidden');
  box.select();
  navigator.clipboard?.writeText(text).then(() => showToast('📋 Marked questions copied'), () => {});
}

function clearMarkedQuestions() {
  if (!Object.keys(loadMarkedQuestions()).length || !confirm('Remove all marks in this edition?')) return;
  saveMarkedQuestions({});
  document.getElementById('qx-export').classList.add('hidden');
  renderQuestionExplorer();
}

// ── During a game: 🚩 on a question card (G14) ──────────────────────────────────

/** Host-only "Report this question" box for a question card (kept off the TV). */
function reportQuestionHtml(q) {
  if (!q?.id) return '';
  const mark = loadMarkedQuestions()[q.id];
  return `
    <details class="q-report" data-host-only ${mark ? 'open' : ''}>
      <summary>${mark ? '🚩 Reported' : '🚩 Report this question'}</summary>
      <div class="q-report-row">
        <input type="text" id="q-report-note" maxlength="300" value="${esc(mark?.note || '')}" placeholder="What's wrong? (optional)">
        <button type="button" class="btn btn-secondary btn-small" onclick="reportQuestion(${Number(q.id)})">${mark ? 'Update' : 'Save'}</button>
      </div>
    </details>`;
}

function reportQuestion(id) {
  markQuestion(id, document.getElementById('q-report-note')?.value || '');
  const box = document.querySelector('.q-report');
  if (box) box.querySelector('summary').textContent = '🚩 Reported';
  updateMarkedBadge();
  showToast('🚩 Question reported — see Setup › 📚 Questions');
}

// ── Wiring ──────────────────────────────────────────────────────────────────────

function initQuestionExplorer() {
  const list = document.getElementById('qx-list');
  if (!list) return;
  document.getElementById('qx-tree').addEventListener('click', e => {
    const node = e.target.closest('.qx-node');
    if (!node) return;
    _qx.path = JSON.parse(node.dataset.path);
    _qx.limit = QX_PAGE;
    renderQuestionExplorer();
  });
  let typing;
  document.getElementById('qx-search').addEventListener('input', e => {
    clearTimeout(typing);
    typing = setTimeout(() => { _qx.text = e.target.value; _qx.limit = QX_PAGE; _renderQxList(); }, 150);
  });
  document.getElementById('qx-diff').addEventListener('change', e => { _qx.diff = e.target.value; _renderQxList(); });
  document.getElementById('qx-marked-only').addEventListener('change', e => { _qx.markedOnly = e.target.checked; _renderQxList(); });
  document.getElementById('qx-answers').addEventListener('change', e => { _qx.answers = e.target.checked; _renderQxList(); });

  list.addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const id = Number(btn.closest('.qx-item')?.dataset.id);
    switch (btn.dataset.action) {
      case 'more':   _qx.limit += QX_PAGE; break;
      case 'edit':   _qx.editing = id; break;
      case 'cancel': _qx.editing = null; break;
      case 'unmark': unmarkQuestion(id); break;
      case 'save':
        markQuestion(id, btn.closest('.qx-item').querySelector('.qx-note-input').value);
        _qx.editing = null;
        break;
    }
    renderQuestionExplorer();
    if (btn.dataset.action === 'edit') list.querySelector(`.qx-item[data-id="${id}"] .qx-note-input`)?.focus();
  });
  list.addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.classList.contains('qx-note-input')) {
      e.preventDefault();
      e.stopPropagation();   // Enter here saves the note — it must not also start the game
      e.target.closest('.qx-item').querySelector('[data-action="save"]').click();
    }
  });
  updateMarkedBadge();
}
