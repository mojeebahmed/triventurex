/**
 * questions.js
 * Browsing an edition's questions (G19) and the list of questions marked as
 * wrong / unclear (G14 + G19). Pure: no page access — unit-tested.
 * A question: { id, q, opts, answer, diff, cat, subcat, topic, note }.
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

/**
 * Questions matching every filter given:
 *   path     [cat, subcat?, topic?] — a branch of the tree ('' = "Other")
 *   text     words that must all appear (question, options, answer, note, id)
 *   diff     'easy' | 'hard' | 'all'
 *   onlyIds  Set of ids (e.g. the marked ones), or null
 */
function filterQuestions(questions, { path = [], text = '', diff = 'all', onlyIds = null } = {}) {
  const words = String(text).toLowerCase().split(/\s+/).filter(Boolean);
  const levels = ['cat', 'subcat', 'topic'];
  return (questions || []).filter(q => {
    if (diff !== 'all' && q.diff !== diff) return false;
    if (onlyIds && !onlyIds.has(q.id)) return false;
    if (!path.every((v, i) => (q[levels[i]] || '') === v)) return false;
    if (!words.length) return true;
    const hay = [q.id, q.q, ...(q.opts || []), q.answer, q.note, q.cat, q.subcat, q.topic]
      .map(_qPlain).join(' ').toLowerCase();
    return words.every(w => hay.includes(w));
  });
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

if (typeof module !== 'undefined') {
  module.exports = { questionTree, filterQuestions, answerLabel, markedReport, topicKey, selectedTopicKeys, TOPIC_SEP };
}
