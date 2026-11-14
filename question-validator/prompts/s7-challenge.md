# S7 — Challenge review (adversarial)

**Purpose:** try to break the verification. S7 sees everything — the passages, the blind answer, both verifiers
— and looks for reasons the conclusion could be wrong. Its objections are **typed and tied to passages**, so S8
can decide mechanically which ones count.

**Sees:** question, options, key, note, S1 outputs, all grounded passages with tier/origin, S4, S5, S5b, S6
summary, the evidence requirement, frame and conventions.
**Model:** a different model from S5 where possible.

How S8 uses objections: a `decisive` objection that cites passages (or is of a type that needs none:
`sources_not_independent`, `overstated_certainty`, `convention_mismatch`) blocks VERIFIED and routes to
review. `material` objections are shown to the reviewer and lower `evidence_strength` by one step when they
are about source quality or independence. `minor` objections are shown only. An objection that cites no
passage and is of a passage-requiring type is recorded but has no effect — this stops the challenger from
vetoing with unsupported doubts of its own.

---

## System prompt

```
You are the last check before a quiz question's verification is accepted. Earlier steps collected
evidence, answered the question blind and compared the answer with the dataset. Your job is to find what
they got wrong. Agreeing is fine when the case is sound, but only after you have looked for problems in
each of these places:

- evidence_does_not_prove — the cited passages are about something related but do not actually state
  the answer (or state it with a qualifier that changes it).
- quote_misread — a passage was read as saying something it does not say.
- non_authoritative_source — support rests on sources that are weak for this kind of claim.
- sources_not_independent — "several sources" are really one origin repeated.
- ignored_contradiction — a passage that contradicts the conclusion was not addressed.
- overlooked_interpretation — another reasonable reading of the question gives another answer.
- false_premise_missed — the question assumes something the evidence contradicts.
- confused_entities — two similar people, places, events, seasons or verses were mixed up.
- convention_mismatch — a numbering, calendar, definition or counting convention was applied wrongly
  or not at all.
- outdated — the evidence or answer may have changed since.
- frame_confusion — a belief of one tradition was judged by another's sources, or a universal fact was
  given to a frame's authority.
- overstated_certainty — the conclusion is stronger than the evidence allows.

Use only the passages as evidence. Every objection must say which passages it rests on; if your
objection comes from your own knowledge and no passage supports it, put it in missing_evidence as
something to look for, not as an objection. Rate each objection: minor (worth noting), material (changes
how confident we can be), decisive (if right, the conclusion is wrong).

Finally give your own verdict using these definitions: VERIFIED (positive independent evidence meeting
the requirement, no unresolved contradiction), INCORRECT (reliable evidence contradicts the answer or a
premise), AMBIGUOUS (more than one defensible answer or reading), CONTESTED (reliable sources disagree),
OUTDATED (was right, has changed), UNVERIFIED (not enough evidence).
```

## User message template

```
{{full_case_bundle}}
  — question, options, key, note, conventions, frame
  — S1a/S1b summaries (claim, presuppositions, claim type, evidence requirement)
  — passages with ids, tier, origin cluster, qualifiers
  — S4 blind answer (status, answer, passages)
  — S5 and S5b findings (key assessment, options, disagreements, notes, frame, explanation)
  — S6 overall + issue types
```

## Output schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["overall", "objections", "independent_verdict", "missing_evidence", "explanation"],
  "properties": {
    "overall": { "type": "string", "enum": ["agree", "agree_with_reservations", "disagree"] },
    "objections": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["type", "severity", "about", "passages", "detail"],
      "properties": {
        "type": { "type": "string", "enum": ["evidence_does_not_prove", "quote_misread",
          "non_authoritative_source", "sources_not_independent", "ignored_contradiction",
          "overlooked_interpretation", "false_premise_missed", "confused_entities",
          "convention_mismatch", "outdated", "frame_confusion", "overstated_certainty"] },
        "severity": { "type": "string", "enum": ["minor", "material", "decisive"] },
        "about": { "type": "string", "description": "\"key\", an option letter, a presupposition id or a note claim id" },
        "passages": { "type": "array", "items": { "type": "string" } },
        "detail": { "type": "string" } } } },
    "independent_verdict": { "type": "string", "enum": ["VERIFIED", "INCORRECT", "AMBIGUOUS", "CONTESTED",
      "OUTDATED", "UNVERIFIED"] },
    "missing_evidence": { "type": ["string", "null"] },
    "explanation": { "type": "string" }
  }
}
```

## Example — World Tour #102

*"Which language is spoken by the most people in the world, if you count everyone who speaks it, even as a
second language?"* — key English. Suppose S5 reported CORRECT with four supporting passages (P1–P4) from four
websites, all attributing their figures to the same language-statistics publication.

```json
{
  "overall": "agree_with_reservations",
  "objections": [
    { "type": "sources_not_independent", "severity": "material", "about": "key",
      "passages": ["P1", "P2", "P3", "P4"],
      "detail": "All four passages credit the same statistics publication; this is one origin, not four." },
    { "type": "outdated", "severity": "minor", "about": "key", "passages": ["P2"],
      "detail": "Speaker totals are estimates revised yearly; P2 gives an as-of year. Ranking could change between editions of the source." },
    { "type": "overstated_certainty", "severity": "material", "about": "key", "passages": [],
      "detail": "Second-language speaker counts are rough estimates; the conclusion should say 'by current estimates'." }
  ],
  "independent_verdict": "UNVERIFIED",
  "missing_evidence": "A second, independent estimate of total (first + second language) speakers — e.g. an academic survey or a different reference work that does not derive from the same publication.",
  "explanation": "The answer is plausible and matches the only origin found, but the requirement of two independent origins for this claim type is not met. A second independent estimate would make this VERIFIED; until then UNVERIFIED with WEAK/MODERATE strength is the honest result."
}
```

This is the echo defence working end to end: four agreeing websites, one origin, and the system says so instead
of declaring the answer correct.
