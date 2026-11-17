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
 * Optional `tags` column: a few lower-case tags separated by ";" (e.g. "animals;water") —
 *   see _parseTags; shown as chips and used to filter in the Questions tab and the Academy.
 * Optional check columns (from the Question Validator's export — see _questionCheck):
 *   checked, checked_on, check_how, sources, source_links, source_quote, as_of, check_hash
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
        ...(_parseTags(r.tags).length ? { tags: _parseTags(r.tags) } : {}),
        ...(r.checked ? { check: _questionCheck(r) } : {}),
      };
    });
}

/** Separator between tags in the `tags` column. */
const TAG_SEP = ';';

/**
 * The `tags` column as a list: split on ";", trimmed, lower-case, inner spaces
 * collapsed, empties and repeats dropped ("Animals; water;;water" → ['animals', 'water']).
 */
function _parseTags(v) {
  const tags = String(v ?? '').split(TAG_SEP).map(t => t.trim().toLowerCase().replace(/\s+/g, ' ')).filter(Boolean);
  return [...new Set(tags)];
}

/**
 * How a question was checked — the optional check columns the Question Validator's
 * game export adds (checked, checked_on, check_how, sources, source_links,
 * source_quote, as_of). `sources` and `source_links` are lists split on " | ",
 * matched by position (a book page has no link).
 */
function _questionCheck(r) {
  const list = v => (v ? v.split('|').map(x => x.trim()) : []);
  const links = list(r.source_links);
  return {
    status:  r.checked,
    on:      r.checked_on   || '',
    how:     r.check_how    || '',
    sources: list(r.sources).filter(Boolean).map((name, i) => ({ name, url: links[i] || '' })),
    quote:   r.source_quote || '',
    asOf:    r.as_of        || '',
  };
}

/**
 * Parse deeds.csv into the DEEDS_DATA format.
 *
 * CSV columns (header row required):
 *   type, text, effect, value, effect_2, value_2, effect_3, value_3, mood
 *
 * type   = "good" or "bad"
 * effect = score_add | score_remove | move_forward | move_back | move_to_prev_landmark |
 *          move_to_next_landmark | skip_turn | extra_turn | all_players_gain |
 *          all_players_lose | protection
 * value  = number of points or spaces (landmark moves: 1 = the nearest landmark)
 * effect_2/value_2 — optional second effect for variable rewards
 * effect_3/value_3 — optional third effect for variable rewards
 * mood   = flavour tag (e.g. blessing, social, challenge, reflection, funny, risk)
 */
function _parseDeedsCSV(text) {
  return _parseCSV(text)
    .filter(r => r.type && r.text && r.effect)
    .map((r, i) => {
      const buildEffect = (eff, val) => eff ? { effect: eff, value: parseFloat(val) || 0 } : null;

      const effects = [
        buildEffect(r.effect,   r.value),
        buildEffect(r.effect_2, r.value_2),
        buildEffect(r.effect_3, r.value_3),
      ].filter(Boolean);

      return {
        id:       i + 1,
        type:     r.type,
        text:     r.text,
        effects,                        // all possible effects (for variable rewards)
        effect:   effects[0]?.effect,   // primary (used as default)
        value:    effects[0]?.value  ?? 0,
        mood:     r.mood || '',
      };
    });
}

/**
 * Parse actions.csv into the ACTIONS_DATA format (digital action cards).
 *
 * CSV columns (header row required):
 *   id, text, kind, note
 *
 * id   = unique number per edition; never reuse or renumber (no-repeat tracking)
 * kind = act | explain | sound   (see CONFIG.ACTION_KINDS)
 * note = optional extra rule for this card, shown to the performer
 */
function _parseActionsCSV(text) {
  return _parseCSV(text)
    .filter(r => r.text)
    .map((r, i) => ({
      id:   Number(r.id) || i + 1,
      text: r.text,
      kind: r.kind || 'act',
      note: r.note || '',
    }));
}

if (typeof module !== 'undefined') {
  module.exports = { _csvSplit, _parseTags, TAG_SEP, _parseCSV, _parseQuestionsCSV, _parseDeedsCSV, _parseActionsCSV };
}
