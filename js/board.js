/**
 * board.js
 * Board generation and rendering.
 *
 * Board generation follows a deliberate order:
 *   1. Count spaces per type from SPACE_DISTRIBUTION.
 *   2. Pre-pick one active effect per deed card (before pool layout).
 *   3. Cap landmark count; rebuild question count to compensate.
 *   4. Build shuffled type pool with no consecutive same-deed-type.
 *   5. Constraint-aware deed-to-slot assignment (_assignDeedsToSlots):
 *      - move_back N → slot index ≥ N (not near start)
 *      - move_forward N → slot index ≤ poolLen-1-N (not near finish)
 *      - move_to_prev_landmark N → N landmarks must exist before the slot
 *      - move_to_next_landmark N → N landmarks must exist after the slot
 *   6. Resolve landmark names (stored as `resolvedLandmark` on each deed).
 *   7. Compute direction arrows; attach grid metadata.
 */

// Direction vectors
const DIR_VECTORS = {
  up:    [-1,  0],
  down:  [ 1,  0],
  left:  [ 0, -1],
  right: [ 0,  1],
};

const DIR_ARROWS = { right: '→', left: '←', up: '↑', down: '↓' };

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Fisher-Yates in-place shuffle. */
function shuffleArray(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/**
 * Build the label shown on a deed space on the board.
 * Line 1: the active effect for this game (chosen randomly from the card's effects).
 * Line 2+: the deed text (with no embedded effect description in the text itself).
 *
 * The effect tag is always dynamic — it reflects whatever effect was randomly
 * selected at board generation time, not the card's primary effect.
 */
function _deedLabel(card) {
  const pts = CONFIG.GAME?.pointsName ?? 'pts';
  const n   = card.value ?? 1;
  const lm  = card.resolvedLandmark || null;
  const effectTag = {
    score_add:              `+${n} ${pts}`,
    score_remove:           `−${n} ${pts}`,
    move_forward:           `▶ Move forward ${n}`,
    move_back:              `◀ Move back ${n}`,
    move_to_landmark:       `📍 Go to: ${card.landmark}`,
    move_to_next_landmark:  lm ? `📍 Advance to ${lm}` : `📍 Advance to next landmark`,
    move_to_prev_landmark:  lm ? `📍 Back to ${lm}`    : `📍 Back to previous landmark`,
    skip_turn:              `⏭ Skip next turn`,
    extra_turn:             `🎲 Roll again!`,
    all_players_gain:       `🌟 Everyone +${n} ${pts}`,
    all_players_lose:       `⚡ Everyone −${n} ${pts}`,
    protection:             `🛡️ Next bad deed cancelled`,
  }[card.effect] || '';
  return effectTag ? `${effectTag}\n${card.text}` : card.text;
}

/**
 * Swap the "content" of two space objects while keeping their grid position
 * (id, row, col, nextDir) fixed.
 */
function _swapSpaceData(sa, sb) {
  const POS = new Set(['id', 'row', 'col', 'nextDir']);
  const aData = {}, bData = {};
  for (const k of Object.keys(sa)) { if (!POS.has(k)) aData[k] = sa[k]; }
  for (const k of Object.keys(sb)) { if (!POS.has(k)) bData[k] = sb[k]; }
  for (const k of Object.keys(sa)) { if (!POS.has(k)) delete sa[k]; }
  for (const k of Object.keys(sb)) { if (!POS.has(k)) delete sb[k]; }
  Object.assign(sa, bData);
  Object.assign(sb, aData);
}

/**
 * Pick one effect from a deed card's available effects.
 * If the card has an `effects` array (variable rewards), choose randomly.
 * Otherwise fall back to the card's single effect/value fields.
 */
function _pickActiveEffect(card) {
  if (card.effects && card.effects.length > 1) {
    return card.effects[Math.floor(Math.random() * card.effects.length)];
  }
  return { effect: card.effect, value: card.value ?? 0 };
}

/**
 * Pick any effect from a card that is NOT a relative-landmark effect.
 * Used as fallback when a landmark constraint cannot be satisfied.
 * Returns null if every effect on the card is a landmark move.
 */
function _pickNonLandmarkEffect(card) {
  const LANDMARK_FX = new Set(['move_to_prev_landmark', 'move_to_next_landmark', 'move_to_landmark']);
  const alternatives = (card.effects || []).filter(e => !LANDMARK_FX.has(e.effect));
  if (alternatives.length) return alternatives[Math.floor(Math.random() * alternatives.length)];
  return null;
}

/**
 * Assign deed cards to pool slot indices with constraint awareness.
 *
 * Constraints checked for each deed:
 *   move_to_prev_landmark value=N  → slot must have ≥N landmarks BEFORE it
 *   move_to_next_landmark value=N  → slot must have ≥N landmarks AFTER it
 *   move_back  value=N             → slot index must be ≥N (N spaces before deed)
 *   move_forward value=N           → slot index must be ≤ poolLength-1-N (N spaces after deed)
 *
 * Fallback priority when no valid slot exists for a constrained deed:
 *   1. Try another effect from the card's effects array that passes its own constraint
 *   2. Keep the effect but place it at the least-bad slot (closest to valid)
 *
 * @param {Object[]} deeds       – pre-picked active-effect deed objects
 * @param {number[]} slots       – pool indices allocated for this deed type
 * @param {number[]} lmPositions – pool indices of landmark slots
 * @param {number}   poolLength  – total middle-space count (for move_forward bound)
 * @returns {Map<number, Object>} slotIndex → deed (with effect already set)
 */
function _assignDeedsToSlots(deeds, slots, lmPositions, poolLength) {
  const lmBefore = idx => lmPositions.filter(p => p < idx).length;
  const lmAfter  = idx => lmPositions.filter(p => p > idx).length;

  // Returns true when slotIdx satisfies the positional / landmark constraint for this deed.
  const isValidSlot = (deed, slotIdx) => {
    const n = Math.max(1, Math.round(deed.value) || 1);
    switch (deed.effect) {
      case 'move_to_prev_landmark': return lmBefore(slotIdx) >= n;
      case 'move_to_next_landmark': return lmAfter(slotIdx)  >= n;
      case 'move_back':             return slotIdx >= n;               // ≥N spaces before deed
      case 'move_forward':          return slotIdx <= poolLength - 1 - n; // ≥N spaces after deed
      default: return true;
    }
  };

  const CONSTRAINED_FX = new Set(['move_to_prev_landmark', 'move_to_next_landmark', 'move_back', 'move_forward']);

  const assignment = new Map();
  const freeSlots  = new Set(slots);

  // Separate constrained deeds from unconstrained ones.
  // Sort most-restrictive first: landmark effects (fewer valid slots) before positional.
  const LANDMARK_FX = new Set(['move_to_prev_landmark', 'move_to_next_landmark']);
  const constrained = deeds
    .filter(d => CONSTRAINED_FX.has(d.effect))
    .sort((a, b) => {
      const aLm = LANDMARK_FX.has(a.effect) ? 1 : 0;
      const bLm = LANDMARK_FX.has(b.effect) ? 1 : 0;
      if (bLm !== aLm) return bLm - aLm;           // landmark effects first
      return (b.value || 1) - (a.value || 1);       // higher N first within each group
    });
  const free = deeds.filter(d => !CONSTRAINED_FX.has(d.effect));

  for (const deed of constrained) {
    const valid = [...freeSlots].filter(s => isValidSlot(deed, s));

    if (valid.length > 0) {
      const chosen = valid[Math.floor(Math.random() * valid.length)];
      assignment.set(chosen, deed);
      freeSlots.delete(chosen);
    } else {
      // No fully valid slot. Try an alternative effect from the card that does fit.
      const LANDMARK_FX_SET = new Set(['move_to_prev_landmark', 'move_to_next_landmark', 'move_to_landmark']);
      const alt = (deed.effects || []).find(e =>
        e.effect !== deed.effect &&
        !LANDMARK_FX_SET.has(e.effect) &&
        [...freeSlots].some(s => isValidSlot({ ...deed, ...e }, s))
      );

      const activeDeed = alt ? { ...deed, ...alt } : deed;
      // Least-bad slot: the one closest to satisfying the constraint
      const ranked = [...freeSlots].sort((a, b) => {
        const scoreA = isValidSlot(activeDeed, a) ? 0 : 1;
        const scoreB = isValidSlot(activeDeed, b) ? 0 : 1;
        return scoreA - scoreB;
      });
      if (ranked.length) {
        assignment.set(ranked[0], activeDeed);
        freeSlots.delete(ranked[0]);
      }
    }
  }

  // Fill remaining slots with free deeds (round-robin if fewer cards than slots)
  const freeArr = shuffleArray([...free]);
  let fi = 0;
  for (const slot of shuffleArray([...freeSlots])) {
    if (!freeArr.length) break;
    assignment.set(slot, freeArr[fi % freeArr.length]);
    fi++;
  }

  return assignment;
}

/**
 * Ensure no two consecutive spaces are both 'good_deed' or both 'bad_deed'.
 * Runs in multiple passes until no violations remain.
 */
/**
 * Enforce adjacency constraints on the type pool:
 *   - No two consecutive 'good_deed' spaces
 *   - No two consecutive 'bad_deed' spaces
 *   - No two consecutive 'action' spaces
 *   - No two consecutive 'landmark' spaces
 * (good_deed next to bad_deed, or action next to landmark, etc. are all fine.)
 * Runs forward-only swap passes to avoid cycles; falls back to 'question'.
 */
function _fixConsecutiveSameDeeds(pool) {
  const CONSTRAINED = new Set(['good_deed', 'bad_deed', 'action', 'landmark']);
  let changed = true, guard = 0;
  while (changed && guard++ < 15) {
    changed = false;
    for (let i = 0; i < pool.length - 1; i++) {
      if (!CONSTRAINED.has(pool[i]) || pool[i] !== pool[i + 1]) continue;
      let swapped = false;
      for (let j = i + 2; j < pool.length; j++) {
        if (pool[j] !== pool[i]) {
          [pool[i + 1], pool[j]] = [pool[j], pool[i + 1]];
          swapped = true;
          changed = true;
          break;
        }
      }
      if (!swapped) { pool[i + 1] = 'question'; changed = true; }
    }
  }
}

/**
 * Same constraint as _fixConsecutiveSameDeeds but operating on the full space
 * objects (after landmark ordering swaps may have re-introduced violations).
 * Swaps space DATA between positions; falls back to converting the duplicate
 * to a question space.
 */
function _fixConsecutiveSameDeedsInSpaces(spaces) {
  const CONSTRAINED = new Set(['good_deed', 'bad_deed', 'action', 'landmark']);
  let changed = true, guard = 0;
  while (changed && guard++ < 15) {
    changed = false;
    for (let i = 0; i < spaces.length - 1; i++) {
      if (!CONSTRAINED.has(spaces[i].type) || spaces[i].type !== spaces[i + 1].type) continue;
      let swapped = false;
      for (let j = i + 2; j < spaces.length; j++) {
        if (spaces[j].type !== spaces[i].type) {
          _swapSpaceData(spaces[i + 1], spaces[j]);
          swapped = true;
          changed = true;
          break;
        }
      }
      if (!swapped) {
        // Convert duplicate to a plain question space as last resort
        const s = spaces[i + 1];
        s.type = 'question';
        delete s.deed;
        delete s.text;
        changed = true;
      }
    }
  }
}

// ── Path building ─────────────────────────────────────────────────────────────

/**
 * Pick a path template (random or explicit) and walk its segments.
 * @param {'short'|'medium'|'long'} gameLength
 * @param {Object} [explicitTemplate]
 * @returns {{ coords, gridRows, gridCols }}
 */
function buildPathCoords(gameLength, explicitTemplate) {
  const options  = CONFIG.PATH_TEMPLATES[gameLength];
  const template = explicitTemplate ?? options[Math.floor(Math.random() * options.length)];
  const gridRows = template.gridRows ?? CONFIG.GRID_SIZE.rows;
  const gridCols = template.gridCols ?? CONFIG.GRID_SIZE.cols;

  const coords = [[...template.start]];
  let [row, col] = template.start;
  for (const [dir, steps] of template.segments) {
    const [dr, dc] = DIR_VECTORS[dir];
    for (let i = 0; i < steps; i++) { row += dr; col += dc; coords.push([row, col]); }
  }
  return { coords, gridRows, gridCols };
}

// ── Board generation ──────────────────────────────────────────────────────────

/**
 * Generate a complete, randomised board for the given game length.
 *
 * Generation order:
 *   1. Count spaces per type (from SPACE_DISTRIBUTION; questions fill remainder).
 *   2. Pre-pick one active effect per deed card.
 *   3. Cap landmark count; rebuild question count.
 *   4. Build shuffled type pool with no consecutive same-deed-type.
 *   5. Constraint-aware deed-to-slot assignment (see _assignDeedsToSlots).
 *   6. Resolve landmark names per slot; store as resolvedLandmark.
 *   7. Compute direction arrows; attach grid metadata.
 *
 * @param {'short'|'medium'|'long'} gameLength
 * @param {Object} [explicitTemplate]
 * @returns {Array<Object>} spaces
 */
function generateBoard(gameLength, explicitTemplate) {
  const { coords: pathCoords, gridRows, gridCols } = buildPathCoords(gameLength, explicitTemplate);
  const totalSpaces = pathCoords.length;
  const middleCount = totalSpaces - 2;

  // ── 1. Base type counts ───────────────────────────────────────
  // Pick distribution: per-length edition override > flat edition override > engine default
  const edDist = CONFIG.EDITION_SPACE_DISTRIBUTION;
  const dist = (edDist && edDist[gameLength]) ? edDist[gameLength]
             : (edDist && edDist.question != null) ? edDist
             : CONFIG.SPACE_DISTRIBUTION;
  // Questions always fill whatever space remains after all other types — the
  // 'question' key in the distribution object is intentionally ignored here.
  const counts = {};
  for (const [t, r] of Object.entries(dist)) {
    if (t !== 'question') counts[t] = Math.round(r * middleCount);
  }
  const nonQ = Object.values(counts).reduce((s, c) => s + c, 0);
  counts.question = Math.max(0, middleCount - nonQ);

  // ── 2. Select and pre-pick deed cards ────────────────────────
  // Effects are picked NOW (before pool layout) so that landmark constraints
  // are known when we decide where to place each deed on the board.
  const allGood = shuffleArray([...(window.DEEDS_DATA || []).filter(d => d.type === 'good')]);
  const allBad  = shuffleArray([...(window.DEEDS_DATA || []).filter(d => d.type === 'bad')]);

  const prepareDeeds = (cards, count) =>
    cards.slice(0, count).map(card => {
      const active = _pickActiveEffect(card);
      return { ...card, effect: active.effect, value: active.value };
    });

  const selGoodDeeds = prepareDeeds(allGood, counts.good_deed);
  const selBadDeeds  = prepareDeeds(allBad,  counts.bad_deed);

  // ── 3. Landmark count — cap at available unique landmarks ────
  counts.landmark = Math.min(CONFIG.LANDMARKS.length, counts.landmark);
  counts.question = Math.max(0,
    middleCount - Object.entries(counts).filter(([t]) => t !== 'question').reduce((s, [, c]) => s + c, 0)
  );

  // ── 4. Build type pool ────────────────────────────────────────
  const pool = [];
  for (const [t, c] of Object.entries(counts)) {
    for (let i = 0; i < c; i++) pool.push(t);
  }
  while (pool.length < middleCount) pool.push('question');
  pool.length = middleCount;
  shuffleArray(pool);
  _fixConsecutiveSameDeeds(pool);

  // ── 5. Assign cards to spaces ─────────────────────────────────
  // Identify landmark slot positions in the pool so deed assignment can check
  // how many landmarks fall before/after any given deed slot.
  const lmPositions = pool.map((t, i) => t === 'landmark' ? i : -1).filter(i => i >= 0);
  const goodSlots   = pool.map((t, i) => t === 'good_deed' ? i : -1).filter(i => i >= 0);
  const badSlots    = pool.map((t, i) => t === 'bad_deed'  ? i : -1).filter(i => i >= 0);

  // Constraint-aware assignment: constrained deeds go to valid slots first,
  // falling back to a non-landmark effect (or a plain move) if no slot qualifies.
  const goodAssign = _assignDeedsToSlots(selGoodDeeds, goodSlots, lmPositions, pool.length);
  const badAssign  = _assignDeedsToSlots(selBadDeeds,  badSlots,  lmPositions, pool.length);

  // Pre-assign landmark names to their pool slots so deed labels can reference them.
  const shuffledLandmarks = shuffleArray([...CONFIG.LANDMARKS]);
  const lmNameByPoolIdx   = new Map();
  {
    const used = new Set();
    for (const pos of lmPositions) {
      const lm = shuffledLandmarks.find(l => !used.has(l.name))
               ?? shuffledLandmarks[lmNameByPoolIdx.size % shuffledLandmarks.length];
      used.add(lm.name);
      lmNameByPoolIdx.set(pos, lm.name);
    }
  }

  // Resolve which landmark a relative deed will actually target at this pool index.
  const resolveTargetLm = (effect, value, poolIdx) => {
    const n = Math.max(1, Math.round(value) || 1);
    if (effect === 'move_to_prev_landmark') {
      const prev = lmPositions.filter(p => p < poolIdx);
      return lmNameByPoolIdx.get(prev[prev.length - n]) ?? null;
    }
    if (effect === 'move_to_next_landmark') {
      const next = lmPositions.filter(p => p > poolIdx);
      return lmNameByPoolIdx.get(next[n - 1]) ?? null;
    }
    return null;
  };

  const midSpaces = [];

  for (let i = 0; i < pool.length; i++) {
    const type = pool[i];
    const [row, col] = pathCoords[i + 1];
    const space = { id: i + 1, type, row, col };

    if (type === 'landmark') {
      const lmName = lmNameByPoolIdx.get(i);
      const lmConfig = CONFIG.LANDMARKS.find(l => l.name === lmName) ?? shuffledLandmarks[0];
      space.name        = lmConfig.name;
      space.image       = lmConfig.image;
      space.description = lmConfig.description ?? '';

    } else if (type === 'good_deed') {
      const deed = goodAssign.get(i);
      if (deed) {
        const resolvedLandmark = resolveTargetLm(deed.effect, deed.value, i);
        space.deed = { ...deed, resolvedLandmark };
        space.text = _deedLabel(space.deed);
      }

    } else if (type === 'bad_deed') {
      const deed = badAssign.get(i);
      if (deed) {
        const resolvedLandmark = resolveTargetLm(deed.effect, deed.value, i);
        space.deed = { ...deed, resolvedLandmark };
        space.text = _deedLabel(space.deed);
      }
    }

    midSpaces.push(space);
  }

  // ── 6. Fix any consecutive-same-deed adjacency after assignment ──
  // (Assignment shuffles within constraint groups, but a second pass is cheap insurance.)
  _fixConsecutiveSameDeedsInSpaces(midSpaces);

  // ── 7. Assemble full board ────────────────────────────────────
  const [sr, sc] = pathCoords[0];
  const [fr, fc] = pathCoords[totalSpaces - 1];
  const spaces = [
    { id: 0, type: 'start', name: 'Start', row: sr, col: sc },
    ...midSpaces,
    { id: totalSpaces - 1, type: 'finish', name: CONFIG.GAME?.finishLabel ?? CONFIG.SPACE_INFO.finish?.label ?? 'Finish', row: fr, col: fc },
  ];

  // Direction arrows (based on grid position)
  for (let i = 0; i < spaces.length - 1; i++) {
    const dr = spaces[i + 1].row - spaces[i].row;
    const dc = spaces[i + 1].col - spaces[i].col;
    const entry = Object.entries(DIR_VECTORS).find(([, [r, c]]) => r === dr && c === dc);
    if (entry) spaces[i].nextDir = entry[0];
  }

  spaces._gridRows = gridRows;
  spaces._gridCols = gridCols;
  return spaces;
}

// ── Rendering ─────────────────────────────────────────────────────────────────

function renderBoard(spaces, players) {
  const board = document.getElementById('board');
  board.innerHTML = '';

  const gridRows = spaces._gridRows ?? (Math.max(...spaces.map(s => s.row)) + 1);
  const gridCols = spaces._gridCols ?? (Math.max(...spaces.map(s => s.col)) + 1);
  board.style.gridTemplateRows    = `repeat(${gridRows}, var(--space-size))`;
  board.style.gridTemplateColumns = `repeat(${gridCols}, var(--space-size))`;

  spaces.forEach(space => {
    const el = createSpaceElement(space, players);
    el.style.gridRow    = space.row + 1;
    el.style.gridColumn = space.col + 1;
    board.appendChild(el);
  });
}

function createSpaceElement(space, players) {
  const info = CONFIG.SPACE_INFO[space.type] || CONFIG.SPACE_INFO.question;

  const el = document.createElement('div');
  el.className = `space ${space.type}`;
  el.id        = `space-${space.id}`;
  el.title     = space.name || info.label;

  // Space number (top-left)
  const numEl = document.createElement('div');
  numEl.className   = 'space-num';
  numEl.textContent = space.id;
  el.appendChild(numEl);

  // Landmark image as background — dark overlay for text readability, golden border
  if (space.type === 'landmark' && space.image) {
    el.style.backgroundImage     = `linear-gradient(rgba(0,0,0,.28), rgba(0,0,0,.28)), url('${space.image}')`;
    el.style.backgroundSize      = 'cover';
    el.style.backgroundPosition  = 'center';
    el.style.border              = `3px solid var(--c-landmark)`;
    el.style.color               = '#fff';
    el.style.textShadow          = '0 1px 3px rgba(0,0,0,.8)';
  }

  // Landmark info popup on click (only when no game action is pending)
  if (space.type === 'landmark' && (space.description || space.image)) {
    el.classList.add('landmark-clickable');
    el.addEventListener('click', e => {
      if (typeof showLandmarkInfo === 'function') {
        e.stopPropagation();
        showLandmarkInfo(space);
      }
    });
  }

  // Icon / character rendering:
  //   question → big bold "?" character
  //   landmark with image → skip icon (image background is the visual)
  //   deed with text → skip icon (text is the hero)
  //   everything else → emoji icon from SPACE_INFO
  const isDeed = space.type === 'good_deed' || space.type === 'bad_deed';
  const hasLandmarkImage = space.type === 'landmark' && space.image;
  if (space.type === 'question') {
    const qMark = document.createElement('div');
    qMark.className   = 'space-big-char';
    qMark.textContent = '?';
    el.appendChild(qMark);
  } else if (!isDeed && !hasLandmarkImage) {
    const iconEl = document.createElement('div');
    iconEl.className   = 'space-icon';
    iconEl.textContent = info.icon;
    el.appendChild(iconEl);
  } else if (isDeed && !space.text) {
    const iconEl = document.createElement('div');
    iconEl.className   = 'space-icon';
    iconEl.textContent = info.icon;
    el.appendChild(iconEl);
  }

  // Label: landmark name, deed summary, nothing
  const labelEl = document.createElement('div');
  labelEl.className = 'space-label';
  if (space.name && space.type === 'landmark') {
    labelEl.textContent = space.name;
  } else if (space.text) {
    labelEl.textContent = space.text;
    labelEl.classList.add('deed-space-label');
  }
  el.appendChild(labelEl);

  // Direction arrow
  if (space.nextDir) {
    const arrowEl = document.createElement('div');
    arrowEl.className   = `space-arrow space-arrow--${space.nextDir}`;
    arrowEl.textContent = DIR_ARROWS[space.nextDir];
    el.appendChild(arrowEl);
  }

  // Player tokens
  const tokensContainer = document.createElement('div');
  tokensContainer.className = 'tokens-container';
  if (players) {
    players.filter(p => p.position === space.id).forEach(p => {
      tokensContainer.appendChild(makeToken(p));
    });
  }
  el.appendChild(tokensContainer);

  return el;
}

/**
 * Build a vertical token element: coloured box with emoji on top, initials below.
 */
function makeToken(player, animated = false) {
  const token = document.createElement('div');
  token.className = `token${animated ? ' token-hop' : ''}`;
  token.style.backgroundColor = player.color;
  token.title = player.name;

  const emoji = document.createElement('div');
  emoji.className   = 'token-emoji';
  emoji.textContent = player.token || '●';

  const initial = document.createElement('div');
  initial.className   = 'token-initial';
  initial.textContent = (player.name || '?').slice(0, 2).toUpperCase();

  token.appendChild(emoji);
  token.appendChild(initial);
  return token;
}

/**
 * Re-draw all player tokens on the board.
 * @param {Array<Object>} players
 * @param {number|null} animatedPlayerId  — if set, only THIS player's token gets the hop animation
 */
function updateBoardTokens(players, animatedPlayerId = null) {
  document.querySelectorAll('.tokens-container').forEach(c => (c.innerHTML = ''));
  players.forEach(player => {
    const spaceEl = document.getElementById(`space-${player.position}`);
    if (spaceEl) {
      const hop = animatedPlayerId !== null && player.id === animatedPlayerId;
      spaceEl.querySelector('.tokens-container').appendChild(makeToken(player, hop));
    }
  });
}

/**
 * Animate a player token hopping through each intermediate space step by step.
 * Replaces a direct movePlayer call for UI purposes — the player's position
 * is updated one space at a time with a configurable delay between steps.
 *
 * @param {Object}        player  — will be mutated (position updated)
 * @param {Array<Object>} spaces  — full board spaces array
 * @param {number}        steps   — positive = forward, negative = backward
 * @param {Array<Object>} allPlayers — needed to re-render all tokens each step
 * @returns {Promise<void>}
 */
// Returns true if the move was blocked by the exact-finish rule.
async function animatePlayerMovement(player, spaces, steps, allPlayers) {
  const delay = CONFIG.ANIMATION?.tokenHopMs ?? 200;
  const maxPos = spaces.length - 1;
  const dir = steps > 0 ? 1 : -1;
  const absSteps = Math.abs(steps);

  // Exact-finish: if moving forward and the roll overshoots the finish, block.
  if (dir === 1 && CONFIG.RULES?.exactFinish && !player.finished) {
    const spacesLeft = maxPos - player.position;
    if (absSteps > spacesLeft) return true; // blocked
  }

  for (let i = 0; i < absSteps; i++) {
    const next = Math.max(0, Math.min(player.position + dir, maxPos));
    if (next === player.position) break; // wall — can't go further
    player.position = next;

    if (player.position >= maxPos && !player.finished) {
      player.finished = true; // mark as finished mid-animation
    }

    updateBoardTokens(allPlayers, player.id); // only this player's token hops
    highlightSpace(player.position);

    if (delay > 0) await new Promise(r => setTimeout(r, delay));
  }
  return false; // not blocked
}

function highlightSpace(spaceId) {
  document.querySelectorAll('.space.active-space').forEach(el => el.classList.remove('active-space'));
  const spaceEl = document.getElementById(`space-${spaceId}`);
  if (spaceEl) {
    spaceEl.classList.add('active-space');
    // Note: scrollIntoView is intentionally omitted — inside overflow:hidden
    // containers it can trigger unexpected page scroll in some browsers.
  }
}

function getLandmarkSpace(spaces, landmarkName) {
  return spaces.find(s => s.type === 'landmark' && s.name === landmarkName);
}
