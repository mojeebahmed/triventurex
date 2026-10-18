/**
 * marks.js
 * Questions marked as wrong / unclear (G14 + G19) and, for reviewers, questions
 * ticked as reviewed (Academy). Stored per edition in localStorage, so the game's
 * 📚 Questions tab and the Academy (academy.html) share the same marks when they
 * are opened in the same browser.
 *
 *   triventurex_marked_<editionId>   = { [id]: { note, at } }
 *   triventurex_reviewed_<editionId> = { [id]: at }
 *
 * Top-level code does not touch the page (js/shared rule). `editionId` defaults
 * to getActiveEditionId(), which both pages define.
 */

const LS_MARKED_PREFIX   = 'triventurex_marked_';
const LS_REVIEWED_PREFIX = 'triventurex_reviewed_';

function _readJson(key) {
  try { return JSON.parse(localStorage.getItem(key)) || {}; } catch { return {}; }
}
function _writeJson(key, obj) {
  try {
    if (Object.keys(obj).length) localStorage.setItem(key, JSON.stringify(obj));
    else localStorage.removeItem(key);
  } catch {}
}

function loadMarkedQuestions(editionId = getActiveEditionId()) { return _readJson(LS_MARKED_PREFIX + editionId); }
function saveMarkedQuestions(marked, editionId = getActiveEditionId()) { _writeJson(LS_MARKED_PREFIX + editionId, marked); }

/** Mark (or update the note of) a question; note '' is fine. */
function markQuestion(id, note = '', editionId = getActiveEditionId()) {
  const marked = loadMarkedQuestions(editionId);
  marked[id] = { note: String(note).trim().slice(0, 300), at: new Date().toISOString() };
  saveMarkedQuestions(marked, editionId);
}

function unmarkQuestion(id, editionId = getActiveEditionId()) {
  const marked = loadMarkedQuestions(editionId);
  delete marked[id];
  saveMarkedQuestions(marked, editionId);
}

function loadReviewed(editionId = getActiveEditionId()) { return _readJson(LS_REVIEWED_PREFIX + editionId); }

/** Tick / untick a question as reviewed. */
function setReviewed(id, on, editionId = getActiveEditionId()) {
  const reviewed = loadReviewed(editionId);
  if (on) reviewed[id] = new Date().toISOString(); else delete reviewed[id];
  _writeJson(LS_REVIEWED_PREFIX + editionId, reviewed);
}

function clearReviewed(editionId = getActiveEditionId()) { _writeJson(LS_REVIEWED_PREFIX + editionId, {}); }
