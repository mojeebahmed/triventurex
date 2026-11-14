# Stage prompts and schemas (v1)

One file per model stage. Each file contains: purpose · what the stage may and may not see · system prompt ·
user message template · output JSON Schema · a worked example from the Triventurex dataset.

| File | Stage | Sees the key? |
|---|---|---|
| [s1a-question-decomposition.md](s1a-question-decomposition.md) | S1a — information need, presuppositions, blind queries | **no** |
| [s1b-claim-formulation.md](s1b-claim-formulation.md) | S1b — key claim, equivalents, note claims, challenge queries | yes |
| [s3-evidence-extraction.md](s3-evidence-extraction.md) | S3 — read one document, extract verbatim passages | **no** |
| [s4-blind-answer.md](s4-blind-answer.md) | S4 — answer from evidence only | **no** |
| [s5-verification.md](s5-verification.md) | S5 / S5b — compare key with evidence | yes |
| [s6-quality.md](s6-quality.md) | S6 — wording and question quality | yes (no evidence) |
| [s7-challenge.md](s7-challenge.md) | S7 — adversarial review | yes |

Conventions used in every prompt:

- `{{placeholders}}` are filled by code. Lists are rendered as numbered lines; JSON blocks as JSON.
- MC options are always shown as **A–D, unmarked**. The CSV's 1–4 index is converted to a letter by code.
- Passages are shown as `[P12] (publisher · page_kind · tier · origin cluster) "verbatim text"`.
- Every output is requested with structured outputs (JSON Schema below) **and** validated again with Pydantic;
  a response that fails either is retried once with the error, then the task is flagged.
- Example outputs do not contain real quotations or URLs: verbatim text is shown as `⟨…⟩` placeholders,
  because inventing quotes — even in documentation — is what this system must never do.
- Schemas follow the subset accepted by structured outputs: every property listed in `required`,
  `additionalProperties: false`, optional values expressed as `["string", "null"]`.
