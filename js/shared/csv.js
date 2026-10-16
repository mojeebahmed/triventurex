/**
 * csv.js
 * CSV parsing for edition content (questions.csv, deeds.csv).
 * Pure — no DOM. Unit-tested in test/csv.test.js.
 */

/** Split one CSV line, respecting quoted fields. */
function _csvSplit(line) {
  const out = []; let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      if (inQ && line[i+1] === '"') { cur += '"'; i++; }
      else inQ = !inQ;
    } else if (c === ',' && !inQ) { out.push(cur); cur = ''; }
    else cur += c;
  }
  out.push(cur);
  return out;
}

/** Parse a full CSV text into an array of objects keyed by the header row. */
function _parseCSV(text) {
  const lines  = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const headers = _csvSplit(lines[0]).map(h => h.trim().toLowerCase().replace(/\s+/g,'_'));
  return lines.slice(1)
    .map(l => l.trim()).filter(Boolean)
    .map(l => {
      const vals = _csvSplit(l);
      const row = {};
      headers.forEach((h, i) => { row[h] = (vals[i] ?? '').trim(); });
      return row;
    });
}

/**
 * Parse questions.csv into the QUESTIONS_DATA format.
 *
 * CSV columns (header row required):
 *   id, question, type, answer, opt_a, opt_b, opt_c, opt_d, difficulty, category, subcategory, topic, note
 *
 * id     = unique number per edition; never reuse or renumber — asked-question
 *          tracking is stored by id. New question → next unused number.
 * type = "multi"  → answer is the correct option NUMBER (1=opt_a, 2=opt_b, …)
 * type = "open"   → answer is the text; opt_a-d left blank
 */
function _parseQuestionsCSV(text) {
  const seen = new Set();
  return _parseCSV(text)
    .filter(r => r.question && r.type)
    .map((r, i) => {
      const isMulti = r.type.trim() === 'multi';
      const opts    = [r.opt_a, r.opt_b, r.opt_c, r.opt_d].filter(Boolean);
      const answer  = isMulti
        ? (['A','B','C','D'][parseInt(r.answer, 10) - 1] ?? 'A')
        : r.answer;
      // Fall back to row position only for old CSVs without an id column
      const id = Number(r.id) || i + 1;
      if (!r.id)        console.warn(`questions.csv: row ${i + 2} has no id — using ${id}`);
      if (seen.has(id)) console.warn(`questions.csv: duplicate id ${id} (row ${i + 2})`);
      seen.add(id);
      return {
        id,
        q:      r.question,
        opts:   isMulti ? opts : [],
        answer,
        diff:   r.difficulty   || 'easy',
        cat:    r.category     || 'general',
        subcat: r.subcategory  || '',
        topic:  r.topic        || '',
        note:   r.note         || '',
      };
    });
}

/**
 * Parse deeds.csv into the DEEDS_DATA format.
 *
 * CSV columns (header row required):
 *   type, text, effect, value, landmark, effect_2, value_2, landmark_2,
 *   effect_3, value_3, landmark_3, mood
 *
 * type   = "good" or "bad"
 * effect = score_add | score_remove | move_forward | move_back | move_to_landmark |
 *          move_to_next_landmark | skip_turn | extra_turn | all_players_gain |
 *          all_players_lose | protection
 * value  = number of points or spaces (0 for landmark-targeting effects)
 * landmark = landmark name (only for move_to_landmark, otherwise blank)
 * effect_2/value_2/landmark_2 — optional second effect for variable rewards
 * effect_3/value_3/landmark_3 — optional third effect for variable rewards
 * mood   = flavour tag (e.g. blessing, social, challenge, reflection, funny, risk)
 */
function _parseDeedsCSV(text) {
  return _parseCSV(text)
    .filter(r => r.type && r.text && r.effect)
    .map((r, i) => {
      const buildEffect = (eff, val, lm) =>
        eff ? { effect: eff, value: parseFloat(val) || 0, landmark: lm || null } : null;

      const effects = [
        buildEffect(r.effect,   r.value,   r.landmark),
        buildEffect(r.effect_2, r.value_2, r.landmark_2),
        buildEffect(r.effect_3, r.value_3, r.landmark_3),
      ].filter(Boolean);

      return {
        id:       i + 1,
        type:     r.type,
        text:     r.text,
        effects,                        // all possible effects (for variable rewards)
        effect:   effects[0]?.effect,   // primary (used as default)
        value:    effects[0]?.value  ?? 0,
        landmark: effects[0]?.landmark ?? null,
        mood:     r.mood || '',
      };
    });
}

if (typeof module !== 'undefined') {
  module.exports = { _csvSplit, _parseCSV, _parseQuestionsCSV, _parseDeedsCSV };
}
