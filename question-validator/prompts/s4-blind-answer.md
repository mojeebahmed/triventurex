# S4 — Blind answer (from evidence only)

**Purpose:** answer the question using **only** the grounded passages, without knowing the expected answer.
Agreement between this answer and the key is the strongest signal the system has; disagreement is the
strongest error signal.

**Sees:** question, options (A–D unmarked), information need, presuppositions, grounded **mode A** passages with
their tier and origin cluster. Excluded-tier passages are not shown.
**Does not see:** key, note, note-claim passages, any verdict.

---

## System prompt

```
Answer a quiz question using only the evidence passages provided. You have not been told the expected
answer, and your own knowledge is not evidence here: if you know something the passages do not say, it
does not count. If the passages are not enough, say so — "insufficient evidence" is a correct and useful
answer, and guessing makes the whole check worthless.

How to weigh passages:
- Each passage has a tier: P (primary: the text itself, the official record, the author's own work),
  S (expert secondary), T (encyclopaedia/summary). Prefer higher tiers when they conflict.
- Passages in the same origin cluster are one source repeated, not independent confirmation. Five
  passages from one cluster count as one.
- Respect qualifiers. A passage about a "42-game season" or the "uninterrupted drop" answers a narrower
  or different question; say so when it matters.
- Respect the question's own qualifiers (dates, "if you count…", "according to…", "by tradition").

Decide one status:
- answered — the passages clearly support one answer.
- multiple_defensible — the passages support two or more different answers (for multiple choice: more
  than one option), for example because sources use different definitions or disagree.
- insufficient_evidence — the passages do not establish an answer.
- unanswerable_as_written — the question cannot be answered as worded (for example because a
  presupposition is false, or none of the options fits the evidence).

Then check each presupposition against the passages: supported, contradicted, or unclear.

Cite passage ids for everything. Keep the reasoning short and concrete.
```

## User message template

```
Question: {{question}}
{{#if multi}}Options (unmarked): A. {{opt_a}}  B. {{opt_b}}  C. {{opt_c}}  D. {{opt_d}}{{/if}}
Information need: {{information_need}}
Presuppositions:
{{#each presuppositions}}{{id}}: {{text}}
{{/each}}
Evidence passages:
{{#each passages}}[{{id}}] ({{publisher}} · {{page_kind}} · tier {{tier}} · origin {{cluster}}{{#if as_of}} · as of {{as_of}}{{/if}}) "{{quote}}"{{#if qualifiers}} — qualifiers: {{qualifiers}}{{/if}}
{{/each}}
```

## Output schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "answer", "option", "supporting_passages", "conflicting_passages",
               "alternative_answers", "presupposition_findings", "missing_evidence", "reasoning"],
  "properties": {
    "status": { "type": "string", "enum": ["answered", "multiple_defensible", "insufficient_evidence",
      "unanswerable_as_written"] },
    "answer": { "type": ["string", "null"] },
    "option": { "type": ["string", "null"], "enum": ["A", "B", "C", "D", null] },
    "supporting_passages": { "type": "array", "items": { "type": "string" } },
    "conflicting_passages": { "type": "array", "items": { "type": "string" } },
    "alternative_answers": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["answer", "option", "passages", "why_defensible"],
      "properties": {
        "answer": { "type": "string" },
        "option": { "type": ["string", "null"], "enum": ["A", "B", "C", "D", null] },
        "passages": { "type": "array", "items": { "type": "string" } },
        "why_defensible": { "type": "string" } } } },
    "presupposition_findings": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "status", "passages"],
      "properties": {
        "id": { "type": "string" },
        "status": { "type": "string", "enum": ["supported", "contradicted", "unclear"] },
        "passages": { "type": "array", "items": { "type": "string" } } } } },
    "missing_evidence": { "type": ["string", "null"], "description": "what evidence would settle it, used for the escalation round" },
    "reasoning": { "type": "string" }
  }
}
```

Code checks: every cited id exists in the input; `supporting_passages` non-empty when `answered`; `option`
consistent with `answer` for MC.

## Example — Football Quest #86

*"How many clubs have won the 'double' (league and FA Cup) in England most times, and which club is it?"*
(open). Passages (illustrative): P1/P2 from the FA and a reputable reference list of double winners.

```json
{
  "status": "multiple_defensible",
  "answer": null,
  "option": null,
  "supporting_passages": [],
  "conflicting_passages": [],
  "alternative_answers": [
    { "answer": "Manchester United (3 doubles)", "option": null, "passages": ["P1", "P2"],
      "why_defensible": "Listed with three league-and-FA-Cup doubles." },
    { "answer": "Arsenal (3 doubles)", "option": null, "passages": ["P1", "P2"],
      "why_defensible": "Also listed with three doubles, so the record is shared." }
  ],
  "presupposition_findings": [
    { "id": "PR1", "status": "contradicted", "passages": ["P1"] }
  ],
  "missing_evidence": null,
  "reasoning": "Both passages list two clubs on three doubles each (P1, P2), so no single club holds the record. PR1 ('one club has won the double the most times') is contradicted. The question's first clause ('How many clubs…') also does not match its second."
}
```

(The passage contents here are my expectation of what the sources say — this example becomes an eval case,
and the real passages decide.)
