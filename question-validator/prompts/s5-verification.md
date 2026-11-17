# S5 / S5b — Verification (key against evidence)

**Purpose:** compare the dataset's expected answer, presuppositions and note with the grounded evidence; assess
every option; identify acceptable alternatives; and classify any disagreement. S5 produces findings, **not the
verdict** — S8 (code) computes the verdict from them.

| | S5 | S5b (second verifier) |
|---|---|---|
| Model | strongest Claude model | a different provider when configured, otherwise a different Claude model |
| Sees blind answer (S4) | yes | **no** |
| Sees S5 | — | **no** |

Both see: question, options, key (letter + text), key components, answer equivalents, presuppositions, note +
note claims, all grounded passages (mode A and mode B) with tier and origin cluster, the evidence requirement for
the claim type (§4 of METHODOLOGY), and the edition frame and conventions.

---

**Version:** v2 (2026-11-17) — every key component gets its own status; a different value is `contradicted`
(never `supported` with another `evidence_value`). S8 verifies only when every component is supported (rules v2).
v1 is kept in `qv/prompts/s5.v1.system.txt`.

## System prompt

```
You check whether a quiz question's expected answer is supported by evidence. The expected answer was
written by someone else and may be wrong. The question itself may contain a false assumption. Your job
is to describe what the evidence shows, precisely and with citations — not to defend the dataset and not
to find fault for its own sake.

Use only the passages provided. Your own knowledge may help you notice what is missing, but it is not
evidence: report it under missing_evidence, never as a finding.

1. Key — compare the expected answer with what the passages assert. Wording differences are not errors:
   "An-Nas" and "Surah An-Nas" are the same answer. A passage only supports the key if it asserts
   the same answer, not if it merely mentions the same names.
   Key components — assess every component listed, each on its own, in component_assessments:
   supported only when a passage asserts the same value for it; contradicted when a passage gives a
   different value (a different year, number, place or person is a contradiction even when the rest of
   the answer is right) — put the value the evidence gives in evidence_value; unclear when no passage
   settles it. evidence_value is null when the evidence gives the same value. The answer is CORRECT only
   when every component is supported; if some are supported and some contradicted, it is
   PARTIALLY_CORRECT.
   {{#if blind}}An independent reader answered the question from the same passages without knowing the
   expected answer: {{s4_summary}}. If it differs from the expected answer, explain why, citing passages.{{/if}}
2. Evidence requirement — for this claim type the following counts as strong support:
   {{evidence_requirement}}. Say whether it is met. Count origin clusters, not passages.
3. Options (multiple choice) — for every option: correct, defensible (some reliable evidence supports it
   or the wording allows it), incorrect (evidence contradicts it, or it is clearly not the answer the
   evidence gives), or unclear (no evidence either way). Do not call a distractor incorrect without a
   reason.
4. Alternatives (open questions) — answers that should also be accepted, and why: equivalent wording,
   transliteration, partial but acceptable, or a different but valid convention.
5. Disagreement — if passages disagree, classify it:
   factual_conflict (same definition, different value), definitional (different measures or scopes),
   convention (numbering, transliteration, calendar, counting), interpretive (traditions or scholars
   understand it differently), temporal (true at one time, changed later), source_error (a lower-tier
   outlier against several better sources). Different classes have different consequences; choose
   carefully and explain.
6. Presuppositions — supported, contradicted, or unclear, with passages.
7. Note — for each note claim: supported, contradicted, convention_mismatch (right under the edition's
   declared convention but not under another), or unclear. Apply the edition's conventions:
   {{conventions_summary}}.
8. Time — is the answer time-sensitive, was it correct at some date, has it changed? If the question
   gives an as-of date, judge at that date.
9. Frame — the edition's frame of reference is: {{frame_summary}}. For claims about what this tradition
   teaches, judge against its own authoritative sources and record separately whether sources outside
   the frame disagree. Disagreement from outside the frame is not evidence that the answer is wrong
   within the frame. For universal facts, the frame gives no extra weight to any source.
10. Suggestions — only when the evidence supports them: a corrected answer; a corrected question if a
   presupposition is false (keep the intent and difficulty). Otherwise null.

If the evidence is insufficient, say UNCERTAIN and state what is missing. That is a correct result.
```

## User message template

```
Edition: {{edition_name}}
Question ({{type}}, {{difficulty}}): {{question}}
{{#if multi}}Options: A. {{opt_a}}  B. {{opt_b}}  C. {{opt_c}}  D. {{opt_d}}
Expected answer: {{key_letter}}. {{key_text}}{{else}}Expected answer: {{key_text}}{{/if}}
Key components: {{key_components_json}}
Accepted equivalents: {{answer_equivalents}}
Claim type: {{claim_type}} · frame class: {{frame_class}} · time-sensitive: {{time_sensitive}} {{as_of_in_question}}
Presuppositions: {{presuppositions_json}}
Note: {{note}}
Note claims: {{note_claims_json}}

Evidence passages:
{{#each passages}}[{{id}}] ({{publisher}} · {{page_kind}} · tier {{tier}} · origin {{cluster}}{{#if frame_authority}} · frame authority{{/if}}{{#if as_of}} · as of {{as_of}}{{/if}}) target {{target}}: "{{quote}}"{{#if qualifiers}} — qualifiers: {{qualifiers}}{{/if}}
{{/each}}
```

## Output schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["key_assessment", "component_assessments", "evidence_requirement_met", "option_assessments",
               "acceptable_alternatives", "disagreements", "presupposition_findings", "note_findings",
               "temporal", "frame", "suggested_answer", "suggested_question", "missing_evidence",
               "explanation"],
  "properties": {
    "key_assessment": { "type": "object", "additionalProperties": false,
      "required": ["factual_accuracy", "match_with_blind", "supporting_passages", "contradicting_passages"],
      "properties": {
        "factual_accuracy": { "type": "string", "enum": ["CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "UNCERTAIN"] },
        "match_with_blind": { "type": "string", "enum": ["same", "equivalent", "partially_overlapping",
          "different", "blind_insufficient", "not_shown"] },
        "supporting_passages": { "type": "array", "items": { "type": "string" } },
        "contradicting_passages": { "type": "array", "items": { "type": "string" } } } },
    "component_assessments": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "status", "evidence_value", "passages"],
      "properties": {
        "id": { "type": "string" },
        "status": { "type": "string", "enum": ["supported", "contradicted", "unclear"] },
        "evidence_value": { "type": ["string", "null"], "description": "the value the evidence gives, if different" },
        "passages": { "type": "array", "items": { "type": "string" } } } } },
    "evidence_requirement_met": { "type": "object", "additionalProperties": false,
      "required": ["met", "independent_origins_supporting", "highest_tier_supporting", "explanation"],
      "properties": {
        "met": { "type": "boolean" },
        "independent_origins_supporting": { "type": "integer" },
        "highest_tier_supporting": { "type": ["string", "null"], "enum": ["P", "S", "T", null] },
        "explanation": { "type": "string" } } },
    "option_assessments": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["option", "status", "passages", "reason"],
      "properties": {
        "option": { "type": "string", "enum": ["A", "B", "C", "D"] },
        "status": { "type": "string", "enum": ["correct", "defensible", "incorrect", "unclear"] },
        "passages": { "type": "array", "items": { "type": "string" } },
        "reason": { "type": "string" } } } },
    "acceptable_alternatives": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["answer", "basis", "passages"],
      "properties": {
        "answer": { "type": "string" },
        "basis": { "type": "string", "enum": ["equivalent_wording", "transliteration",
          "partial_but_acceptable", "alternative_convention"] },
        "passages": { "type": "array", "items": { "type": "string" } } } } },
    "disagreements": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["about", "kind", "side_a_passages", "side_b_passages", "explanation"],
      "properties": {
        "about": { "type": "string", "description": "\"key\", a component id, a presupposition id or a note claim id" },
        "kind": { "type": "string", "enum": ["factual_conflict", "definitional", "convention",
          "interpretive", "temporal", "source_error"] },
        "side_a_passages": { "type": "array", "items": { "type": "string" } },
        "side_b_passages": { "type": "array", "items": { "type": "string" } },
        "explanation": { "type": "string" } } } },
    "presupposition_findings": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "status", "passages", "explanation"],
      "properties": {
        "id": { "type": "string" },
        "status": { "type": "string", "enum": ["supported", "contradicted", "unclear"] },
        "passages": { "type": "array", "items": { "type": "string" } },
        "explanation": { "type": "string" } } } },
    "note_findings": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "status", "passages", "explanation"],
      "properties": {
        "id": { "type": "string" },
        "status": { "type": "string", "enum": ["supported", "contradicted", "convention_mismatch", "unclear"] },
        "passages": { "type": "array", "items": { "type": "string" } },
        "explanation": { "type": "string" } } } },
    "temporal": { "type": "object", "additionalProperties": false,
      "required": ["time_sensitive", "judged_as_of", "outdated", "previously_true_passages", "change_passages"],
      "properties": {
        "time_sensitive": { "type": "boolean" },
        "judged_as_of": { "type": ["string", "null"] },
        "outdated": { "type": "boolean" },
        "previously_true_passages": { "type": "array", "items": { "type": "string" } },
        "change_passages": { "type": "array", "items": { "type": "string" } } } },
    "frame": { "type": "object", "additionalProperties": false,
      "required": ["depends_on_frame", "within_frame", "contested_outside_frame", "frame_passages", "outside_passages"],
      "properties": {
        "depends_on_frame": { "type": "boolean" },
        "within_frame": { "type": "string", "enum": ["supported", "contradicted", "unclear", "not_applicable"] },
        "contested_outside_frame": { "type": "boolean" },
        "frame_passages": { "type": "array", "items": { "type": "string" } },
        "outside_passages": { "type": "array", "items": { "type": "string" } } } },
    "suggested_answer": { "type": ["string", "null"] },
    "suggested_question": { "type": ["string", "null"] },
    "missing_evidence": { "type": ["string", "null"] },
    "explanation": { "type": "string" }
  }
}
```

Code checks: cited ids exist; `CORRECT` requires non-empty `supporting_passages`; every `contradicted` status cites
at least one passage; a disagreement cites passages on both sides. S8 recomputes origin counts and tiers itself
and **ignores** `evidence_requirement_met` if it disagrees with its own count (the field exists to make the model
reason about it, and the mismatch is logged as a signal).

## Example — Prophets' Stories #3 (note under the edition's numbering)

Key C. *"The names of all things"*; note *"Surah Al-Baqarah 2:32"*. Passages: P1 = direct lookup of 2:32 under
`bismillah_is_verse_1` (tier P); P2 = a tafsir page (S) citing the verse as 2:31; P3 = an encyclopaedia (T).

```json
{
  "key_assessment": { "factual_accuracy": "CORRECT", "match_with_blind": "same",
                      "supporting_passages": ["P1", "P2", "P3"], "contradicting_passages": [] },
  "component_assessments": [ { "id": "K1", "status": "supported", "evidence_value": null, "passages": ["P1", "P2"] } ],
  "evidence_requirement_met": { "met": true, "independent_origins_supporting": 3, "highest_tier_supporting": "P",
    "explanation": "scripture_content requires the verse text itself; P1 is the verse and states it. P2 and P3 agree but are not needed." },
  "option_assessments": [
    { "option": "A", "status": "incorrect", "passages": ["P1"], "reason": "The verse names 'the names', not building." },
    { "option": "B", "status": "incorrect", "passages": ["P1"], "reason": "Not what the verse describes." },
    { "option": "C", "status": "correct", "passages": ["P1", "P2"], "reason": "Matches the verse." },
    { "option": "D", "status": "incorrect", "passages": ["P1"], "reason": "Not what the verse describes." }
  ],
  "acceptable_alternatives": [],
  "disagreements": [
    { "about": "N1", "kind": "convention", "side_a_passages": ["P1"], "side_b_passages": ["P2"],
      "explanation": "P2 cites the same verse as 2:31 under the common numbering; the edition counts the Bismillah as verse 1, so 2:32 is the same verse." }
  ],
  "presupposition_findings": [],
  "note_findings": [
    { "id": "N1", "status": "supported", "passages": ["P1"], "explanation": "Under the edition's numbering, 2:32 is the verse in which Adam is taught the names." }
  ],
  "temporal": { "time_sensitive": false, "judged_as_of": null, "outdated": false,
                "previously_true_passages": [], "change_passages": [] },
  "frame": { "depends_on_frame": false, "within_frame": "not_applicable", "contested_outside_frame": false,
             "frame_passages": [], "outside_passages": [] },
  "suggested_answer": null,
  "suggested_question": null,
  "missing_evidence": null,
  "explanation": "The verse text (P1) states that Adam was taught the names; option C. The note's verse number follows the edition's numbering and matches the same verse that P2 numbers 2:31."
}
```

P1 comes from the note's direct lookup (S3 mode B), so S4 never saw it — S4 reached "C" from P2 and P3 alone,
and `match_with_blind: "same"` is therefore a genuinely independent agreement. For `scripture_content` the verse
text (P1) is what makes the support STRONG; the tafsir and encyclopaedia would not be enough without it.
