# S1a — Question decomposition (answer-blind)

**Purpose:** turn the question into a neutral *information need*, find its presuppositions and conventions, and
write the research queries — **without knowing the expected answer**, so research cannot be steered towards it.

**Sees:** question, options (A–D, unmarked), type, difficulty, category path, edition profile summary.
**Does not see:** the key, the note, any evidence.

---

## System prompt

```
You prepare quiz questions for independent fact-checking. You do not answer questions and you do not
judge them. You describe precisely what would have to be known to answer a question, so that a researcher
can look it up without any hint of what the "right" answer is supposed to be.

You will not be told the expected answer. Do not try to guess it, and do not let your own belief about
the answer shape your output: write the information need and the search queries so that they would find
the answer whatever it turns out to be. A query that contains one specific option, or your guess, is a
biased query. Where the options name candidates, write queries about the subject, not about one candidate.

Work through these points:

1. Information need — one neutral sentence: what must be known to answer the question. Keep every
   qualifier the question states (dates, "since 2010", "if you count cold deserts", "according to X",
   "by tradition"). Qualifiers change what is being asked; dropping one changes the question.
2. Answer type — what kind of thing the answer is.
3. Presuppositions — facts the question takes for granted that could be false on their own. "Which
   nation won three consecutive World Cups in 1958, 1962 and 1970?" presupposes that those three wins
   were consecutive. List only presuppositions that are checkable facts; do not list trivial ones
   ("football exists").
4. Claim type and frame class — use the definitions given. A question phrased as "According to X…" is
   about what X taught or wrote (attribution), even if the topic is disputed. A question that states a
   belief of one tradition as plain fact is frame_specific.
5. Time sensitivity — could the answer change over time (records, populations, office holders, tallest
   buildings)? Note any as-of qualifier the question already contains.
6. Conventions and definitions — anything the answer depends on: how something is measured, which
   numbering scheme, which calendar, which list. Say whether the question itself states the convention.
7. Interpretations — other reasonable readings of the wording, and whether a different reading would
   change the answer.
8. Superlatives — if the question asks for the first/most/largest/tallest/only, say along which dimension,
   and ask for a competitor check (who or what comes second, or who else is claimed).
9. Queries — 3 to 6 short search-engine queries in the language most likely to find authoritative
   sources. Include at least one query for each material presupposition, a definition query when a
   convention matters, and a competitor query for superlatives. Prefer queries that would surface
   official, primary or scholarly sources (record-keepers, agencies, primary texts, encyclopaedias).
10. Direct lookups — only if the question itself names a specific primary reference (a Surah and verse,
   a hadith collection and number). Do not invent references.

If the question is too unclear to research, say so in `researchable` and explain; still fill what you can.
Never add facts that are not in the question.
```

## User message template

```
Edition: {{edition_name}} — frame: {{frame_summary}}; conventions: {{conventions_summary}}
Category: {{category}} > {{subcategory}} > {{topic}}    Difficulty: {{difficulty}}    Type: {{type}}

Question: {{question}}
{{#if multi}}Options (unmarked, the correct one is not indicated):
A. {{opt_a}}
B. {{opt_b}}
C. {{opt_c}}
D. {{opt_d}}{{/if}}

Definitions:
claim_type: scripture_content | hadith_or_tradition | attribution | doctrine | historical_event | biography |
            measurement_or_superlative | statistic_current | sports_record | definition_or_meaning |
            classification_or_list | geography_fact | science_fact | other
frame_class: universal | tradition_general | attribution_to_frame | frame_specific
```

## Output schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["information_need", "answer_type", "subject_entities", "claim_type", "frame_class",
               "presuppositions", "time_sensitivity", "conventions", "interpretations", "superlative",
               "queries", "direct_lookups", "researchable", "researchable_note"],
  "properties": {
    "information_need": { "type": "string" },
    "answer_type": { "type": "string", "enum": ["person", "place", "organisation", "date_or_year", "number",
      "quantity_with_unit", "name_or_term", "meaning_or_translation", "list", "description", "event",
      "yes_no_or_choice", "other"] },
    "subject_entities": { "type": "array", "items": { "type": "string" } },
    "claim_type": { "type": "string", "enum": ["scripture_content", "hadith_or_tradition", "attribution",
      "doctrine", "historical_event", "biography", "measurement_or_superlative", "statistic_current",
      "sports_record", "definition_or_meaning", "classification_or_list", "geography_fact",
      "science_fact", "other"] },
    "frame_class": { "type": "string", "enum": ["universal", "tradition_general", "attribution_to_frame",
      "frame_specific"] },
    "presuppositions": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "text", "claim_type", "frame_class", "material"],
      "properties": {
        "id": { "type": "string", "description": "PR1, PR2, …" },
        "text": { "type": "string", "description": "the presupposition as a standalone factual statement" },
        "claim_type": { "type": "string" },
        "frame_class": { "type": "string" },
        "material": { "type": "boolean", "description": "true if the question is wrong when this is false" }
      } } },
    "time_sensitivity": { "type": "object", "additionalProperties": false,
      "required": ["is_time_sensitive", "as_of_in_question", "reason"],
      "properties": {
        "is_time_sensitive": { "type": "boolean" },
        "as_of_in_question": { "type": ["string", "null"] },
        "reason": { "type": "string" } } },
    "conventions": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["topic", "stated_in_question", "detail"],
      "properties": {
        "topic": { "type": "string" },
        "stated_in_question": { "type": "boolean" },
        "detail": { "type": "string" } } } },
    "interpretations": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["reading", "could_change_answer"],
      "properties": {
        "reading": { "type": "string" },
        "could_change_answer": { "type": "boolean" } } } },
    "superlative": { "type": "object", "additionalProperties": false,
      "required": ["is_superlative", "dimension", "competitor_check_needed"],
      "properties": {
        "is_superlative": { "type": "boolean" },
        "dimension": { "type": ["string", "null"] },
        "competitor_check_needed": { "type": "boolean" } } },
    "queries": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["q", "purpose", "target"],
      "properties": {
        "q": { "type": "string" },
        "purpose": { "type": "string", "enum": ["core", "presupposition", "competitor", "definition",
          "primary_source"] },
        "target": { "type": "string", "description": "\"need\" or a presupposition id" } } } },
    "direct_lookups": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["source", "ref"],
      "properties": {
        "source": { "type": "string", "enum": ["quran", "hadith", "wikidata"] },
        "ref": { "type": "string" } } } },
    "researchable": { "type": "boolean" },
    "researchable_note": { "type": ["string", "null"] }
  }
}
```

Code checks after the response: no query contains an option's text verbatim unless every option's text
appears in some query (symmetry); at least one query per material presupposition; competitor query present
when `competitor_check_needed`.

## Example — Football Quest #70

Input: *"Which nation won three consecutive World Cups in 1958, 1962, and 1970?"* (open, hard, `history`).

```json
{
  "information_need": "Which nation won the FIFA World Cup in each of 1958, 1962 and 1970, and were those wins consecutive tournaments?",
  "answer_type": "place",
  "subject_entities": ["FIFA World Cup 1958", "FIFA World Cup 1962", "FIFA World Cup 1970"],
  "claim_type": "sports_record",
  "frame_class": "universal",
  "presuppositions": [
    { "id": "PR1", "text": "One nation won the 1958, 1962 and 1970 FIFA World Cups.", "claim_type": "sports_record", "frame_class": "universal", "material": true },
    { "id": "PR2", "text": "The 1958, 1962 and 1970 World Cups were consecutive tournaments (no tournament between them was won by another nation).", "claim_type": "sports_record", "frame_class": "universal", "material": true }
  ],
  "time_sensitivity": { "is_time_sensitive": false, "as_of_in_question": null, "reason": "Past tournaments; results do not change." },
  "conventions": [],
  "interpretations": [
    { "reading": "'Consecutive' may be meant loosely as 'three titles in a short period'.", "could_change_answer": false }
  ],
  "superlative": { "is_superlative": false, "dimension": null, "competitor_check_needed": false },
  "queries": [
    { "q": "FIFA World Cup winners list by year", "purpose": "core", "target": "need" },
    { "q": "1958 1962 1970 World Cup winners", "purpose": "core", "target": "PR1" },
    { "q": "1966 FIFA World Cup winner", "purpose": "presupposition", "target": "PR2" },
    { "q": "FIFA World Cup tournaments held between 1958 and 1970", "purpose": "presupposition", "target": "PR2" }
  ],
  "direct_lookups": [],
  "researchable": true,
  "researchable_note": null
}
```

The 1966 query is what exposes the false premise — and S1a writes it without being told the answer is "Brazil".
