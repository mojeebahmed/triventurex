/**
 * game_editions/template/questions.js
 * Question bank for this edition.
 *
 * HOW TO ADD QUESTIONS:
 *   Copy an entry, give it a unique `id`, and fill in the fields.
 *
 * Fields:
 *   id      – unique number (required)
 *   q       – question text
 *   opts    – array of 4 answer options [A, B, C, D]
 *             Omit opts entirely for open-ended questions (no options shown)
 *   answer  – correct letter "A"/"B"/"C"/"D", or the answer text for open-ended
 *   diff    – "easy" (lower points) or "hard" (higher points)
 *   cat     – category tag for filtering (e.g. "general", "history", "science")
 *   note    – optional GM hint shown after the answer is revealed (leave "" if none)
 */

window.QUESTIONS_DATA = [

  // ── Easy questions ────────────────────────────────────────────────────────

  {
    id: 1,
    q: "Example easy question?",
    opts: ["Option A", "Option B", "Option C", "Option D"],
    answer: "A",
    diff: "easy",
    cat: "general",
    note: "",
  },

  // ── Hard questions ────────────────────────────────────────────────────────

  {
    id: 101,
    q: "Example hard question with no options (open-ended)?",
    opts: [],            // no options = open-ended
    answer: "The answer",
    diff: "hard",
    cat: "general",
    note: "Optional GM hint.",
  },

];
