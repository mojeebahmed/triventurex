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

// Returns a Set of selected topic strings. If nothing saved, all topics are selected.
function getSelectedTopics() {
  const edId  = _activeEditionId || 'default';
  const tree  = _buildCatTree();
  const allTopics = Object.values(tree).flatMap(sc => Object.values(sc).flat());
  const saved = _getSavedTopics(edId);
  if (!saved) return new Set(allTopics);
  return new Set(saved.filter(t => allTopics.includes(t)));
}

function _populateCategoryFilter() {
  const edId = _activeEditionId || 'default';
  const tree = _buildCatTree();
  const row  = document.getElementById('category-filter-row');
  const box  = document.getElementById('category-checkboxes');
  if (!row || !box) return;

  const allTopics = Object.values(tree).flatMap(sc => Object.values(sc).flat());
  if (allTopics.length === 0) { row.style.display = 'none'; return; }

  const saved = _getSavedTopics(edId);
  const selTopics = new Set(saved || allTopics);

  const _allTopicsIn   = (topics) => topics.every(t => selTopics.has(t));
  const _someTopicsIn  = (topics) => topics.some(t => selTopics.has(t));

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

  // Build HTML
  let html = '';
  for (const [cat, subcats] of Object.entries(tree)) {
    const catTopics = Object.values(subcats).flat();
    const catAll    = _allTopicsIn(catTopics);
    const catSome   = _someTopicsIn(catTopics);
    const catInd    = !catAll && catSome;
    html += `<div class="cat-group">
      <label class="cat-label">
        <input type="checkbox" data-level="cat" data-key="${cat}"
          ${catAll ? 'checked' : ''} ${catInd ? 'data-indeterminate' : ''}>
        <span class="cat-name">${cat}</span>
        <button class="cat-toggle" type="button" aria-label="expand">▾</button>
      </label>
      <div class="subcat-list collapsed">`;
    for (const [subcat, topics] of Object.entries(subcats)) {
      const scKey  = `${cat}||${subcat}`;
      const scAll  = _allTopicsIn(topics);
      const scSome = _someTopicsIn(topics);
      const scInd  = !scAll && scSome;
      html += `<div class="subcat-group">
        <label class="subcat-label">
          <input type="checkbox" data-level="subcat" data-key="${scKey}" data-cat="${cat}"
            ${scAll ? 'checked' : ''} ${scInd ? 'data-indeterminate' : ''}>
          <span class="subcat-name">${subcat}</span>
          <button class="subcat-toggle" type="button" aria-label="expand">▾</button>
        </label>
        <div class="topic-list collapsed">`;
      for (const topic of topics) {
        html += `<label class="topic-label">
          <input type="checkbox" data-level="topic" data-cat="${cat}" data-subcat="${scKey}" value="${topic}"
            ${selTopics.has(topic) ? 'checked' : ''}>
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

  // Cat expand/collapse toggles
  box.querySelectorAll('.cat-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const list = btn.closest('.cat-group').querySelector('.subcat-list');
      list.classList.toggle('collapsed');
      btn.textContent = list.classList.contains('collapsed') ? '▾' : '▴';
    });
  });
  box.querySelectorAll('.subcat-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const list = btn.closest('.subcat-group').querySelector('.topic-list');
      list.classList.toggle('collapsed');
      btn.textContent = list.classList.contains('collapsed') ? '▾' : '▴';
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

// ── Setup Screen ──────────────────────────────────────────────────────────────
