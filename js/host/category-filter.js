/**
 * category-filter.js
 * Question topic filter in Game Settings (3 levels: cat > subcat > topic).
 */

function _catKey(editionId) {
  return LS_CAT_PREFIX + (editionId || 'default');
}

function _getSavedTopics(editionId) {
  try { return JSON.parse(localStorage.getItem(_catKey(editionId))); } catch { return null; }
}

function _saveSelectedTopics(editionId, topicArray) {
  try { localStorage.setItem(_catKey(editionId), JSON.stringify(topicArray)); } catch {}
}

// Builds a nested hierarchy object: { cat: { subcat: [topic, …], … }, … }
function _buildCatTree() {
  const tree = {};
  for (const q of (window.QUESTIONS_DATA || [])) {
    const cat = q.cat || 'General'; const subcat = q.subcat || 'Other'; const topic = q.topic || 'General';
    if (!tree[cat]) tree[cat] = {};
    if (!tree[cat][subcat]) tree[cat][subcat] = new Set();
    tree[cat][subcat].add(topic);
  }
  // Sort everything
  const sorted = {};
  for (const cat of Object.keys(tree).sort()) {
    sorted[cat] = {};
    for (const subcat of Object.keys(tree[cat]).sort())
      sorted[cat][subcat] = [...tree[cat][subcat]].sort();
  }
  return sorted;
}

// Returns a Set of selected topic keys ("cat › subcat › topic", see topicKey in
// js/shared/questions.js). If nothing saved, all topics are selected.
function getSelectedTopics() {
  return selectedTopicKeys(_getSavedTopics(_activeEditionId || 'default'), window.QUESTIONS_DATA || []);
}

function _populateCategoryFilter() {
  const edId = _activeEditionId || 'default';
  const tree = _buildCatTree();
  const row  = document.getElementById('category-filter-row');
  const box  = document.getElementById('category-checkboxes');
  if (!row || !box) return;

  const allTopics = Object.values(tree).flatMap(sc => Object.values(sc).flat());
  if (allTopics.length === 0) { row.style.display = 'none'; return; }

  // Selection by full path: the same topic name can sit under several branches
  const selKeys = getSelectedTopics();
  const key = (cat, subcat, topic) => [cat, subcat, topic].join(TOPIC_SEP);
  const _allTopicsIn   = (cat, subcat, topics) => topics.every(t => selKeys.has(key(cat, subcat, t)));
  const _someTopicsIn  = (cat, subcat, topics) => topics.some(t => selKeys.has(key(cat, subcat, t)));

  const _saveCurrentState = () => {
    const nowSelected = [...box.querySelectorAll('input[data-level="topic"]:checked')].map(i => i.value);
    if (nowSelected.length === 0) return false; // block — must keep at least one
    _saveSelectedTopics(edId, nowSelected);
    return true;
  };

  const _syncParents = () => {
    // Sync subcat checkboxes
    box.querySelectorAll('input[data-level="subcat"]').forEach(scCb => {
      const topics = [...box.querySelectorAll(`input[data-subcat="${scCb.dataset.key}"][data-level="topic"]`)];
      const vals = topics.map(t => t.checked);
      scCb.checked = vals.every(Boolean);
      scCb.indeterminate = !scCb.checked && vals.some(Boolean);
    });
    // Sync cat checkboxes
    box.querySelectorAll('input[data-level="cat"]').forEach(cCb => {
      const topics = [...box.querySelectorAll(`input[data-cat="${cCb.dataset.key}"][data-level="topic"]`)];
      const vals = topics.map(t => t.checked);
      cCb.checked = vals.every(Boolean);
      cCb.indeterminate = !cCb.checked && vals.some(Boolean);
    });
  };

  // Questions per category / subcategory, shown on each row
  const qCount = {};
  for (const q of (window.QUESTIONS_DATA || [])) {
    const c = q.cat || 'General', sc = `${c}||${q.subcat || 'Other'}`;
    qCount[c] = (qCount[c] || 0) + 1;
    qCount[sc] = (qCount[sc] || 0) + 1;
  }
  const count = key => `<span class="tree-count">${qCount[key] || 0} questions</span>`;

  // Build HTML. A row has two parts: the checkbox + name (a <label>, toggles
  // the selection) and the rest of the row (expands / collapses the level below).
  let html = '';
  for (const [cat, subcats] of Object.entries(tree)) {
    const catAll    = Object.entries(subcats).every(([sc, ts]) => _allTopicsIn(cat, sc, ts));
    const catSome   = Object.entries(subcats).some(([sc, ts]) => _someTopicsIn(cat, sc, ts));
    const catInd    = !catAll && catSome;
    html += `<div class="cat-group">
      <div class="cat-label tree-row" role="button" aria-expanded="false">
        <label class="tree-check">
          <input type="checkbox" data-level="cat" data-key="${cat}"
            ${catAll ? 'checked' : ''} ${catInd ? 'data-indeterminate' : ''}>
          <span class="cat-name">${cat}</span>
        </label>
        ${count(cat)}
        <span class="cat-toggle tree-toggle" aria-hidden="true">▾</span>
      </div>
      <div class="subcat-list collapsed">`;
    for (const [subcat, topics] of Object.entries(subcats)) {
      const scKey  = `${cat}||${subcat}`;
      const scAll  = _allTopicsIn(cat, subcat, topics);
      const scSome = _someTopicsIn(cat, subcat, topics);
      const scInd  = !scAll && scSome;
      html += `<div class="subcat-group">
        <div class="subcat-label tree-row" role="button" aria-expanded="false">
          <label class="tree-check">
            <input type="checkbox" data-level="subcat" data-key="${scKey}" data-cat="${cat}"
              ${scAll ? 'checked' : ''} ${scInd ? 'data-indeterminate' : ''}>
            <span class="subcat-name">${subcat}</span>
          </label>
          ${count(scKey)}
          <span class="subcat-toggle tree-toggle" aria-hidden="true">▾</span>
        </div>
        <div class="topic-list collapsed">`;
      for (const topic of topics) {
        html += `<label class="topic-label">
          <input type="checkbox" data-level="topic" data-cat="${cat}" data-subcat="${scKey}" value="${esc(key(cat, subcat, topic))}"
            ${selKeys.has(key(cat, subcat, topic)) ? 'checked' : ''}>
          ${topic}
        </label>`;
      }
      html += `</div></div>`;
    }
    html += `</div></div>`;
  }
  box.innerHTML = html;

  // Set indeterminate state (can't do in HTML)
  box.querySelectorAll('[data-indeterminate]').forEach(el => { el.indeterminate = true; });

  // Clicking a row outside its checkbox + name expands / collapses it
  box.querySelectorAll('.tree-row').forEach(row => {
    row.addEventListener('click', e => {
      if (e.target.closest('.tree-check')) return;   // the checkbox / name handle selection
      const list = row.nextElementSibling;
      list.classList.toggle('collapsed');
      const open = !list.classList.contains('collapsed');
      row.setAttribute('aria-expanded', String(open));
      row.querySelector('.tree-toggle').textContent = open ? '▴' : '▾';
    });
  });

  // Cat checkbox → toggle all children
  box.querySelectorAll('input[data-level="cat"]').forEach(cb => {
    cb.addEventListener('change', () => {
      box.querySelectorAll(`input[data-cat="${cb.dataset.key}"][data-level="topic"]`)
        .forEach(t => { t.checked = cb.checked; });
      if (!_saveCurrentState()) {
        // Revert: re-check all if last one was being unchecked
        box.querySelectorAll(`input[data-cat="${cb.dataset.key}"][data-level="topic"]`)
          .forEach(t => { t.checked = true; });
        cb.checked = true;
      }
      _syncParents();
    });
  });

  // Subcat checkbox → toggle its topics
  box.querySelectorAll('input[data-level="subcat"]').forEach(cb => {
    cb.addEventListener('change', () => {
      box.querySelectorAll(`input[data-subcat="${cb.dataset.key}"][data-level="topic"]`)
        .forEach(t => { t.checked = cb.checked; });
      if (!_saveCurrentState()) {
        box.querySelectorAll(`input[data-subcat="${cb.dataset.key}"][data-level="topic"]`)
          .forEach(t => { t.checked = true; });
        cb.checked = true;
      }
      _syncParents();
    });
  });

  // Topic checkbox → save and sync parents
  box.querySelectorAll('input[data-level="topic"]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (!_saveCurrentState()) { cb.checked = true; }
      _syncParents();
    });
  });

  row.style.display = '';
}
