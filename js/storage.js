/**
 * storage.js
 * localStorage: saved game (save / load / resume prompt) and remembered
 * player + settings preferences.
 */

// ── Saved game ──────────────────────────────────────────────────────────────────

function saveGame() {
  if (state.phase !== 'playing') return;
  try {
    // state.turn is plain data, so a mid-turn save (space modal open) carries
    // everything needed to finish — or undo — that turn after a refresh.
    const save = {
      ...state,
      savedAt: new Date().toISOString(),
      // board._gridRows/Cols are non-enumerable — save them explicitly
      gridRows: state.board._gridRows,
      gridCols: state.board._gridCols,
    };
    localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(save));
  } catch (e) {
    console.warn('Could not save game:', e);
  }
}

function loadSave() {
  try {
    const raw = localStorage.getItem(CONFIG.STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function clearSave() {
  localStorage.removeItem(CONFIG.STORAGE_KEY);
}

function checkAndShowResume() {
  const save = loadSave();
  if (!save || save.phase !== 'playing') return;

  const prompt  = document.getElementById('resume-prompt');
  const meta    = document.getElementById('resume-meta');
  const elapsed = _friendlyTime(save.savedAt);
  meta.textContent =
    `${save.gameLength} game · ${save.players.length} players · saved ${elapsed}`;
  prompt.classList.remove('hidden');

  document.getElementById('resume-btn').addEventListener('click', () => {
    prompt.classList.add('hidden');
    _restoreGame(save);
  });
  document.getElementById('discard-btn').addEventListener('click', () => {
    clearSave();
    prompt.classList.add('hidden');
  });
}

function _friendlyTime(isoString) {
  const diff = Math.floor((Date.now() - new Date(isoString)) / 1000);
  if (diff < 60)  return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

// ── Remembered preferences ──────────────────────────────────────────────────────

const LS_PLAYER_PREFS  = 'triventurex_player_prefs';

const LS_HOST_PLAYER   = 'triventurex_host_player';

const LS_GAME_SETTINGS = 'triventurex_game_settings';

const LS_CAT_PREFIX    = 'triventurex_cats_';

function _savePlayerPrefs() {
  try {
    localStorage.setItem(LS_PLAYER_PREFS, JSON.stringify(
      state.players.map(p => ({
        name:  p.nameInput.value.trim() || '',
        color: p.color,
        token: p.token,
      }))
    ));
  } catch {}
}

function _loadPlayerPrefs() {
  try { return JSON.parse(localStorage.getItem(LS_PLAYER_PREFS)); } catch { return null; }
}

function _clearPlayerPrefs() {
  localStorage.removeItem(LS_PLAYER_PREFS);
}

function _saveHostPlayerPref(name, color, token) {
  try { localStorage.setItem(LS_HOST_PLAYER, JSON.stringify({ name, color, token })); } catch {}
}

function _loadHostPlayerPref() {
  try { return JSON.parse(localStorage.getItem(LS_HOST_PLAYER)); } catch { return null; }
}

function _saveGameSettings(gameLength, pathIndex) {
  try {
    localStorage.setItem(LS_GAME_SETTINGS, JSON.stringify({
      gameLength, pathIndex, playerCount: state.players.length,
      exactFinish:      CONFIG.RULES.exactFinish,
      questionTracking: CONFIG.RULES.questionTracking,
    }));
  } catch {}
}

function _loadGameSettings() {
  try { return JSON.parse(localStorage.getItem(LS_GAME_SETTINGS)); } catch { return null; }
}
