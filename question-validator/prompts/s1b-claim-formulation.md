# S1b — Claim formulation (sees the key and the note)

**Purpose:** state precisely what the dataset *claims* — the key as a testable proposition, its acceptable
surface forms, and every checkable claim in the note — and add **challenge queries** that try to break the key.
It does not judge anything.

**Sees:** question, options, resolved key text (and letter), note, S1a output, edition profile.
**Does not see:** any evidence.

Its queries are run **in addition to** S1a's blind queries, never instead of them, and its note claims are
read in a separate extraction pass (S3 mode B) so the blind answer pass stays blind.

---

## System prompt

```
You write down exactly what a quiz question and its expected answer claim to be true, so that the claim
can be fact-checked. You do not decide whether it is true.

1. Key claim — one standalone factual sentence combining the question and the expected answer, keeping
   every qualifier from the question. If the expected answer contains several facts (a number AND a
   person AND a season), list each one as a component so they can be checked separately.
2. Answer equivalents — other ways of writing the same answer that should count as the same: spelling and
   transliteration variants, with or without honorifics, with or without "Surah"/"the", common English
   names (Hawwa / Eve). Only true equivalents: a broader or narrower answer is not an equivalent.
3. Note claims — split the note into separate checkable statements: scripture references, hadith or book
   references, and factual statements. Pure explanation or teaching text that asserts no checkable fact is
   kind "explanation". For a scripture reference, record the reference exactly as written and the
   numbering scheme the edition declares — do not convert it.
4. Direct lookups — for each scripture or hadith reference in the note, a lookup the system can perform
   (source + reference + scheme). Never invent a reference that is not written in the note.
5. Challenge queries — 2 to 4 search queries designed to find evidence AGAINST the key if it exists:
   the known record holder before/after, the commonly confused alternative, "disputed"/"myth" angles,
   later changes for time-sensitive facts. A challenge query that would only find pages repeating the
   expected answer is useless; aim at what would prove it wrong.
6. Note queries — 1 to 2 queries per factual note claim that cannot be checked by a direct lookup.

Treat the expected answer as an unproven claim written by someone else, which may be wrong.
```

## User message template

```
Edition: {{edition_name}} — frame: {{frame_summary}}; conventions: {{conventions_summary}}
Question: {{question}}
{{#if multi}}Options: A. {{opt_a}}  B. {{opt_b}}  C. {{opt_c}}  D. {{opt_d}}
Expected answer: {{key_letter}}. {{key_text}}{{else}}Expected answer: {{key_text}}{{/if}}
Note: {{note | "(none)"}}

Decomposition (from an answer-blind step):
{{s1a_json}}
```

## Output schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["key_claim", "key_components", "answer_equivalents", "note_claims", "direct_lookups",
               "challenge_queries", "note_queries"],
  "properties": {
    "key_claim": { "type": "string" },
    "key_components": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "text", "value"],
      "properties": {
        "id": { "type": "string", "description": "K1, K2, …" },
        "text": { "type": "string" },
        "value": { "type": "string", "description": "the specific value asserted, e.g. '34', 'Erling Haaland'" } } } },
    "answer_equivalents": { "type": "array", "items": { "type": "string" } },
    "note_claims": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "text", "kind", "reference", "scheme"],
      "properties": {
        "id": { "type": "string", "description": "N1, N2, …" },
        "text": { "type": "string" },
        "kind": { "type": "string", "enum": ["scripture_reference", "hadith_reference", "book_reference",
          "factual_statement", "explanation"] },
        "reference": { "type": ["string", "null"] },
        "scheme": { "type": ["string", "null"], "description": "numbering scheme declared by the edition" } } } },
    "direct_lookups": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["for_claim", "source", "ref", "scheme"],
      "properties": {
        "for_claim": { "type": "string" },
        "source": { "type": "string", "enum": ["quran", "hadith", "wikidata"] },
        "ref": { "type": "string" },
        "scheme": { "type": ["string", "null"] } } } },
    "challenge_queries": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["q", "angle"],
      "properties": {
        "q": { "type": "string" },
        "angle": { "type": "string", "enum": ["previous_or_later_holder", "commonly_confused",
          "disputed_or_myth", "change_over_time", "definition_variant", "other"] } } } },
    "note_queries": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["q", "for_claim"],
      "properties": { "q": { "type": "string" }, "for_claim": { "type": "string" } } } }
  }
}
```

## Example A — Football Quest #66

Key: *"34 goals — Erling Haaland for Manchester City in 2022–23"*, no note.

```json
{
  "key_claim": "The highest number of goals scored by one player in a single Premier League season is 34, scored by Erling Haaland for Manchester City in 2022–23.",
  "key_components": [
    { "id": "K1", "text": "The record number of goals in one Premier League season is 34.", "value": "34" },
    { "id": "K2", "text": "The record holder is Erling Haaland.", "value": "Erling Haaland" },
    { "id": "K3", "text": "The record was set in the 2022–23 season for Manchester City.", "value": "2022–23, Manchester City" }
  ],
  "answer_equivalents": ["Haaland", "Erling Braut Haaland"],
  "note_claims": [],
  "direct_lookups": [],
  "challenge_queries": [
    { "q": "Premier League single season goals record before Haaland Cole Shearer", "angle": "previous_or_later_holder" },
    { "q": "Haaland total Premier League goals 2022-23 season final tally", "angle": "commonly_confused" },
    { "q": "Premier League goals record 42-game season versus 38-game season", "angle": "definition_variant" }
  ],
  "note_queries": []
}
```

Splitting the key into K1–K3 is what lets S5 report "player right, number wrong" (PARTIALLY_CORRECT) instead of
a single yes/no.

## Example B — Prophets' Stories #2

Key: *"Hawwa (Eve)"*; note: *"Her name is known from hadith; the Qur'an calls her his "wife"."*

```json
{
  "key_claim": "The wife of Hadhrat Adam (as) was named Hawwa (Eve).",
  "key_components": [ { "id": "K1", "text": "Adam's wife was named Hawwa (Eve).", "value": "Hawwa" } ],
  "answer_equivalents": ["Hawwa", "Hawa", "Hauwa", "Eve", "Hazrat Hawwa"],
  "note_claims": [
    { "id": "N1", "text": "The name Hawwa for Adam's wife is known from hadith.", "kind": "hadith_reference", "reference": null, "scheme": null },
    { "id": "N2", "text": "The Qur'an refers to her as Adam's wife without naming her.", "kind": "factual_statement", "reference": null, "scheme": "bismillah_is_verse_1" }
  ],
  "direct_lookups": [],
  "challenge_queries": [
    { "q": "is Eve named in the Quran Adam's wife name", "angle": "commonly_confused" },
    { "q": "origin of the name Hawwa in Islamic sources hadith", "angle": "disputed_or_myth" }
  ],
  "note_queries": [
    { "q": "hadith mentioning Hawwa wife of Adam collection reference", "for_claim": "N1" },
    { "q": "Quran verses Adam and his wife zawj name not mentioned", "for_claim": "N2" }
  ]
}
```

N1 has no reference in the note, so no direct lookup is invented; it must be established through search, and
if no narration is found it ends as `note_status: unverified` → specialist review.
