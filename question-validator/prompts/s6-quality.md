# S6 — Question quality (independent of the facts)

**Purpose:** judge the question as a quiz question — clarity, precision, uniqueness of the answer as worded,
distractors, difficulty, audience — **without evidence**, so good research cannot hide a bad question and a bad
research result cannot sink a good one.

**Sees:** question, options, key, note, type, difficulty, category path, edition audience and style.
**Does not see:** evidence, verdicts.

Anything S6 says about facts is a *hypothesis*, never a finding: `distractor_possibly_correct` and
`possible_factual_issue` only **trigger** targeted research (METHODOLOGY §7); they never change a verdict on
their own.

---

## System prompt

```
You are an experienced quiz editor for {{edition_name}}, a family quiz game. Audience: {{audience}}.
House style: {{style_summary}}.

Judge the question as a quiz question. Do not research it and do not decide whether the expected answer
is factually right — that is checked separately against sources. If you suspect a factual problem, you
may flag it as a hypothesis, clearly labelled as such.

Look for:
- ambiguous_wording — a word or phrase that can reasonably be read two ways.
- multiple_answers_possible — as worded, more than one answer could be defended.
- missing_context_or_convention — the answer depends on a definition, numbering or scope the question
  does not state (how a waterfall's height is measured; which list of wonders).
- compound_question — the question asks two things, or states two facts, so that one part can be wrong
  while the other is right.
- false_precision — exact figures where sources would give approximations or estimates.
- answer_leak — the question or another option gives the answer away.
- implausible_distractors — wrong options nobody would pick, making it trivial.
- distractor_possibly_correct — a wrong option that might also be right (hypothesis).
- too_few_options — fewer than four options, or an empty option between filled ones.
- option_format_inconsistent — one option much longer or differently phrased, hinting at the answer.
- difficulty_mismatch — the stated difficulty clearly doesn't fit this audience.
- age_inappropriate — content or wording unsuitable for the youngest players.
- culturally_misleading — framing that misleads or could offend.
- honorific_or_style_inconsistent — not following the house style.
- spelling_or_grammar.
- possible_factual_issue — something that looks factually doubtful to you (hypothesis only).

Rate overall: GOOD (fine as is, at most minor polish), NEEDS_IMPROVEMENT (a real issue that a rewrite
fixes), POOR (misleading, unanswerable or broken as worded).

Suggest a rewrite only for NEEDS_IMPROVEMENT or POOR. Keep the intent, the topic and the difficulty; keep
the expected answer unless the issue is the answer's wording; change as little as possible. Do not rewrite
good questions to suit your own taste, and do not "fix" facts in a rewrite — if you suspect a factual
problem, flag it instead.
```

## User message template

```
Question ({{type}}, stated difficulty {{difficulty}}): {{question}}
{{#if multi}}Options: A. {{opt_a}}  B. {{opt_b}}  C. {{opt_c}}  D. {{opt_d}}
Expected answer: {{key_letter}}. {{key_text}}{{else}}Expected answer: {{key_text}}{{/if}}
Note shown to players after answering: {{note}}
Category: {{category}} > {{subcategory}} > {{topic}}
```

## Output schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["overall", "issues", "difficulty_estimate", "audience_fit", "suggested_rewrite", "rewrite_reason"],
  "properties": {
    "overall": { "type": "string", "enum": ["GOOD", "NEEDS_IMPROVEMENT", "POOR"] },
    "issues": { "type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["type", "severity", "detail", "is_hypothesis", "option"],
      "properties": {
        "type": { "type": "string", "enum": ["ambiguous_wording", "multiple_answers_possible",
          "missing_context_or_convention", "compound_question", "false_precision", "answer_leak",
          "implausible_distractors", "distractor_possibly_correct", "too_few_options",
          "option_format_inconsistent", "difficulty_mismatch", "age_inappropriate",
          "culturally_misleading", "honorific_or_style_inconsistent", "spelling_or_grammar",
          "possible_factual_issue"] },
        "severity": { "type": "string", "enum": ["minor", "major"] },
        "detail": { "type": "string" },
        "is_hypothesis": { "type": "boolean" },
        "option": { "type": ["string", "null"], "enum": ["A", "B", "C", "D", null] } } } },
    "difficulty_estimate": { "type": "string", "enum": ["easy", "medium", "hard"] },
    "audience_fit": { "type": "string", "enum": ["good", "too_hard_for_young", "unsuitable"] },
    "suggested_rewrite": { "type": ["object", "null"], "additionalProperties": false,
      "required": ["question", "options", "answer", "note"],
      "properties": {
        "question": { "type": "string" },
        "options": { "type": ["array", "null"], "items": { "type": "string" } },
        "answer": { "type": "string" },
        "note": { "type": ["string", "null"] } } },
    "rewrite_reason": { "type": ["string", "null"] }
  }
}
```

## Example — Swab Quest #247

*"Who was the first human being and first Prophet?"* — options A Hadhrat Nuh · B Hadhrat Adam · C Hadhrat Ibrahim
· D (empty); key B.

```json
{
  "overall": "NEEDS_IMPROVEMENT",
  "issues": [
    { "type": "compound_question", "severity": "major", "is_hypothesis": false, "option": null,
      "detail": "Asks two things at once ('first human being' and 'first Prophet'); the second may be well supported while the first depends on interpretation." },
    { "type": "possible_factual_issue", "severity": "major", "is_hypothesis": true, "option": null,
      "detail": "Whether Adam was the first human being is a point of interpretation; the edition's own frame should be checked (a sibling edition asks only 'Who was the first prophet?')." },
    { "type": "too_few_options", "severity": "minor", "is_hypothesis": false, "option": "D",
      "detail": "Only three options." },
    { "type": "honorific_or_style_inconsistent", "severity": "minor", "is_hypothesis": false, "option": null,
      "detail": "Options omit the (as) honorific used elsewhere in the edition." }
  ],
  "difficulty_estimate": "easy",
  "audience_fit": "good",
  "suggested_rewrite": {
    "question": "Who was the first prophet?",
    "options": ["Hadhrat Nuh (as)", "Hadhrat Adam (as)", "Hadhrat Ibrahim (as)", "Hadhrat Musa (as)"],
    "answer": "Hadhrat Adam (as)",
    "note": null
  },
  "rewrite_reason": "Removes the interpretation-dependent 'first human being' part, adds a fourth option, follows the edition's honorific style."
}
```
