/**
 * questions.js
 * Browsing an edition's questions (G19) and the list of questions marked as
 * wrong / unclear (G14 + G19). Pure: no page access — unit-tested.
 * A question: { id, q, opts, answer, diff, cat, subcat, topic, note, tags?, check? }.
 * `tags` (optional): lower-case tags from the CSV's `tags` column, e.g. ['animals', 'water'].
 * `check` (optional, from the Question Validator's export — see _questionCheck in csv.js):
 * { status: 'verified' | 'confirmed' | 'edited', on, how, sources: [{ name, url }], quote, asOf }.
 */

/**
 * The topic filter (Rules → Topics) selects by full path, because the same
 * topic name can sit under several categories ("Europe" under Capitals and
 * under Flags). Key = "cat › subcat › topic", with the same fallbacks the tree
 * uses ('General' / 'Other').
 */
const TOPIC_SEP = ' › ';
function topicKey(q) {
  return [q.cat || 'General', q.subcat || 'Other', q.topic || 'General'].join(TOPIC_SEP);
}

/**
 * The saved selection as a Set of topic keys. `saved` = the stored array or
 * null (null = everything selected). Selections saved before topic keys were
 * plain topic names; those select every path with that topic name.
 */
function selectedTopicKeys(saved, questions) {
  const all = [...new Set((questions || []).map(topicKey))];
  if (!Array.isArray(saved)) return new Set(all);
  const keys = new Set(saved.filter(s => String(s).includes(TOPIC_SEP)));
  const names = new Set(saved.filter(s => !String(s).includes(TOPIC_SEP)));
  return new Set(all.filter(k => keys.has(k) || names.has(k.split(TOPIC_SEP)[2])));
}

/** Plain text of a question field (content may hold a little HTML, e.g. <em>). */
const _qPlain = s => String(s ?? '').replace(/<[^>]*>/g, '');

/**
 * Category > subcategory > topic tree with question counts. Empty levels are
 * kept as '' (shown as "Other"); editions with only a category get one level.
 * @returns {Array<{ name, count, children }>}
 */
function questionTree(questions) {
  const roots = [];
  const child = (list, name) => {
    let node = list.find(n => n.name === name);
    if (!node) list.push(node = { name, count: 0, children: [] });
    return node;
  };
  for (const q of questions || []) {
    const cat = child(roots, q.cat || '');
    cat.count++;
    if (!q.subcat && !q.topic) continue;
    const sub = child(cat.children, q.subcat || '');
    sub.count++;
    if (!q.topic) continue;
    child(sub.children, q.topic).count++;
  }
  return roots;
}

const _LEVELS = ['cat', 'subcat', 'topic'];
const _inPath = (q, path) => path.every((v, i) => (q[_LEVELS[i]] || '') === v);

/**
 * Questions matching every filter given:
 *   paths    branches of the tree, each [cat, subcat?, topic?] ('' = "Other"); a question in ANY of them
 *            matches (none = every branch). `path` = one branch (older callers)
 *   text     words that must all appear (question, options, answer, note, id)
 *   diff     'easy' | 'hard' | 'all'
 *   onlyIds  Set of ids (e.g. the marked ones), or null
 *   checked  'all' | 'yes' (checked by the Question Validator) | 'no'
 *   tags     chosen tags (none = any question); tagMode 'all' = the question has every one,
 *            'any' = it has at least one
 */
function filterQuestions(questions, { path = [], paths = null, text = '', diff = 'all', onlyIds = null, checked = 'all',
  tags = [], tagMode = 'all' } = {}) {
  const words = String(text).toLowerCase().split(/\s+/).filter(Boolean);
  const branches = (paths || [path]).filter(p => p.length);
  const hasTag = t => q => q.tags?.includes(t);
  return (questions || []).filter(q => {
    if (diff !== 'all' && q.diff !== diff) return false;
    if (onlyIds && !onlyIds.has(q.id)) return false;
    if (checked !== 'all' && Boolean(q.check) !== (checked === 'yes')) return false;
    if (branches.length && !branches.some(p => _inPath(q, p))) return false;
    if (tags.length && !(tagMode === 'any' ? tags.some(t => hasTag(t)(q)) : tags.every(t => hasTag(t)(q)))) return false;
    if (!words.length) return true;
    const hay = [q.id, q.q, ...(q.opts || []), q.answer, q.note, q.cat, q.subcat, q.topic, ...(q.tags || [])]
      .map(_qPlain).join(' ').toLowerCase();
    return words.every(w => hay.includes(w));
  });
}

// ── Several branches of the tree ────────────────────────────────────────────────

const _samePath = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
const _isPrefix = (a, b) => a.length <= b.length && a.every((v, i) => v === b[i]);

/** Is this branch chosen? */
function pathChosen(paths, path) {
  return (paths || []).some(p => _samePath(p, path));
}

/**
 * Choose or un-choose one branch (a new array). Choosing a branch drops the ones it
 * contains or sits in, so "Capitals" then "Capitals › Europe" narrows down to Europe,
 * and "Europe" then "Capitals" widens to all of Capitals. [] = "All questions".
 */
function togglePath(paths, path) {
  if (!path.length) return [];
  if (pathChosen(paths, path)) return paths.filter(p => !_samePath(p, path));
  return [...(paths || []).filter(p => !_isPrefix(p, path) && !_isPrefix(path, p)), path];
}

/** Is this branch open in a tree that shows only chosen branches (it, or something inside it, is chosen)? */
function pathOpen(paths, path) {
  return (paths || []).some(p => _isPrefix(path, p));
}

/** "All questions", "Capitals › Europe" or "Capitals › Europe + Flags" for a count line. */
function pathsLabel(paths, label = n => n || 'Other', all = 'All questions') {
  return paths?.length ? paths.map(p => p.map(label).join(' › ')).join(' + ') : all;
}

// ── Tags ────────────────────────────────────────────────────────────────────────

/** Every tag used by the questions with how many questions carry it, most used first: [{ tag, count }]. */
function tagCounts(questions) {
  const counts = new Map();
  for (const q of questions || []) for (const t of q.tags || []) counts.set(t, (counts.get(t) || 0) + 1);
  return [...counts].map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
}

/** Add or remove one tag from a selection (a new array). */
function toggleTag(selected, tag) {
  return selected.includes(tag) ? selected.filter(t => t !== tag) : [...selected, tag];
}

/** Keep only selected tags that still exist (e.g. after the edition changed). */
function knownTags(selected, questions) {
  const all = new Set(tagCounts(questions).map(c => c.tag));
  return (selected || []).filter(t => all.has(t));
}

/**
 * The tag chips to filter with: one toggle button per tag (`data-tag`), with its
 * count in `counts` (the tag counts for the questions the other filters leave).
 * A selected tag shows as pressed; '' when the edition has no tags.
 * HTML — call it only in a page (uses icon() / esc()).
 */
function tagFilterHtml(allTags, selected, counts = null, tagMode = null) {
  if (!allTags.length) return '';
  const n = counts ? new Map(counts.map(c => [c.tag, c.count])) : new Map(allTags.map(c => [c.tag, c.count]));
  const chips = allTags.map(({ tag }) => {
    const on = selected.includes(tag);
    const count = n.get(tag) || 0;
    return `<button type="button" class="tag-chip ${on ? 'on' : ''}" data-tag="${esc(tag)}" aria-pressed="${on}" ${!on && !count ? 'disabled' : ''}>${icon('tag')} ${esc(tag)} <small>${count}</small></button>`;
  }).join('');
  return chips + (tagMode && selected.length > 1 ? tagModeHtml(tagMode) : '');
}

/** "Any of these tags / All of these tags" switch, shown once two or more tags are chosen (`data-tag-mode`). */
function tagModeHtml(tagMode) {
  const opt = (mode, label, title) =>
    `<button type="button" class="tag-mode-btn ${tagMode === mode ? 'on' : ''}" data-tag-mode="${mode}" aria-pressed="${tagMode === mode}" title="${title}">${label}</button>`;
  return `<span class="tag-mode" role="group" aria-label="Questions with">${opt('any', 'Any of these', 'A question needs at least one of the chosen tags')}${opt('all', 'All of these', 'A question needs every chosen tag')}</span>`;
}

/**
 * Tag counts for the chips. 'all': questions left by every filter (the tags included) — how many a
 * chip would leave. 'any': questions left by the other filters only — how many each tag adds.
 */
function tagChipCounts(questions, filter, tagMode) {
  return tagCounts(filterQuestions(questions, tagMode === 'any' ? { ...filter, tags: [] } : { ...filter, tagMode }));
}

/** A question's tags as small chips for a question list (click = filter by that tag). */
function questionTagsHtml(q) {
  if (!q?.tags?.length) return '';
  return `<span class="qx-tags">${q.tags.map(t => `<button type="button" class="tag-chip tag-chip-small" data-tag="${esc(t)}" title="Show questions tagged ${esc(t)}">${icon('tag')} ${esc(t)}</button>`).join('')}</span>`;
}

/** "B — Stockholm" for multiple choice, the answer text otherwise. */
function answerLabel(q) {
  if (!q.opts?.length) return _qPlain(q.answer);
  const i = ['A', 'B', 'C', 'D'].indexOf(q.answer);
  return `${q.answer} — ${_qPlain(q.opts[i] ?? '')}`;
}

/**
 * The marked questions as text to fix the CSV with: one block per question
 * (id, difficulty, category, question, answer, the note). `marked` is
 * { [id]: { note, at } }; ids no longer in the edition are listed too.
 */
function markedReport(marked, questions, editionName = '') {
  const ids = Object.keys(marked || {}).map(Number).sort((a, b) => a - b);
  const byId = new Map((questions || []).map(q => [q.id, q]));
  const lines = [`Reported questions${editionName ? ` — ${editionName}` : ''} (${ids.length})`, ''];
  for (const id of ids) {
    const q = byId.get(id);
    const note = marked[id]?.note ? `   Note: ${marked[id].note}` : '   Note: —';
    if (!q) { lines.push(`#${id} (no longer in questions.csv)`, note, ''); continue; }
    const where = [q.cat, q.subcat, q.topic].filter(Boolean).join(' > ');
    lines.push(`#${id} [${q.diff}]${where ? ` ${where}` : ''}`, `   ${_qPlain(q.q)}`, `   Answer: ${answerLabel(q)}`, note, '');
  }
  return lines.join('\n').trimEnd() + '\n';
}

// ── How a question was checked (Question Validator export) ─────────────────────

/** Short label per check status. */
const CHECK_LABELS = {
  verified:  'Checked against sources',
  confirmed: 'Confirmed by a reviewer',
  edited:    'Corrected by a reviewer',
};

/** "Checked against sources" etc., or '' for a question without a check. */
function checkLabel(q) {
  return q?.check ? (CHECK_LABELS[q.check.status] ?? 'Checked') : '';
}

/** How many of the questions carry a check. */
function checkedCount(questions) {
  return (questions || []).filter(q => q.check).length;
}

/** A link only for plain http(s) addresses (source text comes from the web). */
function _safeUrl(url) {
  return /^https?:\/\//i.test(url || '') ? url : '';
}

/**
 * Small badge for a question list's meta line ('' when not checked).
 * HTML — call it only in a page (uses icon() / esc()).
 */
function checkBadgeHtml(q) {
  if (!q?.check) return '';
  const name = q.check.status === 'verified' ? 'checkVerified' : 'checkReviewer';
  return `<span class="qx-check-badge qx-check-${esc(q.check.status)}" title="${esc(checkLabel(q))}">${icon(name)} ${esc(checkLabel(q))}</span>`;
}

/**
 * How the question was checked, for under the answer: the plain line, the date,
 * the sources (links open in a new tab) and a short quote from the best one.
 * Source names and quotes come from web pages, so everything is escaped.
 */
function checkDetailsHtml(q) {
  const c = q?.check;
  if (!c) return '';
  const sources = c.sources.map(s => {
    const url = _safeUrl(s.url);
    return url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(s.name)}</a>` : esc(s.name);
  }).join(' · ');
  const when = [c.on && `checked ${esc(c.on)}`, c.asOf && `true as of ${esc(c.asOf)}`].filter(Boolean).join(' · ');
  return `
    <div class="qx-check-info">
      <div>${icon(c.status === 'verified' ? 'checkVerified' : 'checkReviewer')} ${esc(c.how || checkLabel(q))}${when ? ` <span class="qx-check-when">(${when})</span>` : ''}</div>
      ${sources ? `<div class="qx-check-sources">${icon('checkSource')} ${sources}</div>` : ''}
      ${c.quote ? `<blockquote class="qx-check-quote">“${esc(c.quote)}”</blockquote>` : ''}
    </div>`;
}

/**
 * "About this answer" — what the info button on an Academy learning card opens:
 * the answer, the note, where it comes from (how it was checked, the sources with
 * links, a short quote — or that it was not checked yet), and the topic and tags.
 * Written for children and grown-ups alike: short headings, plain words.
 * HTML — call it only in a page (uses icon() / esc()). The note is edition content
 * (may hold a little HTML, like everywhere it is shown); web text is escaped.
 */
function questionInfoHtml(q) {
  if (!q) return '';
  const where = [q.cat, q.subcat, q.topic].filter(Boolean).join(' › ');
  const tags = (q.tags || []).map(t => `<span class="tag-chip tag-chip-small">${icon('tag')} ${esc(t)}</span>`).join(' ');
  const from = q.check
    ? checkDetailsHtml(q)
    : `<p class="qi-unchecked">${icon('notChecked')} Not checked against sources yet. Curious? Look it up together in a book or a trusted website.</p>`;
  return `
    <div class="qi">
      <div class="qi-q">${q.q}</div>
      <div class="qi-answer">${icon('answer')} ${esc(answerLabel(q))}</div>
      ${q.note ? `<h4>${icon('note')} Good to know</h4><div class="qi-note">${q.note}</div>` : ''}
      <h4>${icon('checkSource')} Where the answer comes from</h4>
      ${from}
      <h4>${icon('tag')} Topic</h4>
      <div class="qi-topic">${esc(where || 'General')} · ${q.diff === 'hard' ? `${icon('hard')} Hard` : `${icon('easy')} Easy`} · #${Number(q.id)}${tags ? `<div class="qi-tags">${tags}</div>` : ''}</div>
    </div>`;
}

if (typeof module !== 'undefined') {
  module.exports = { questionTree, filterQuestions, answerLabel, markedReport, topicKey, selectedTopicKeys, TOPIC_SEP,
                     checkLabel, checkedCount, CHECK_LABELS, tagCounts, toggleTag, knownTags, tagChipCounts,
                     pathChosen, togglePath, pathOpen, pathsLabel,
                     checkBadgeHtml, checkDetailsHtml, tagFilterHtml, tagModeHtml, questionTagsHtml, questionInfoHtml };
}
