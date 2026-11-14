# Question Validator — Architecture Review & Revised Design

*Review of "AI Question Validation Platform — PRD and Technical Specification" ([SPECIFICATION.md](SPECIFICATION.md)).
Written 2026-11-15, before any implementation. Priority throughout: factual reliability and evidence traceability
over speed.*

> The validation method itself — stages, what each may see, evidence requirements, verdict rules, prompts and
> schemas — is defined in [METHODOLOGY.md](METHODOLOGY.md) and [`prompts/`](prompts/). Where §3 below differs
> from it, METHODOLOGY.md wins (it adds S1a/S1b, answer-blind extraction, claim-level statuses and origin clusters).

---

## 0. Summary — the ten changes that matter most

1. **Reframe the goal.** The pipeline cannot *establish* truth; it can establish *"this answer is supported
   by these verbatim passages from these sources, retrieved on this date"*. Design every output around that
   claim, and make "not enough evidence" a normal, cheap, honest outcome.
2. **Research blind, then compare.** The spec gives the expected answer to the research stage. That biases
   the search queries towards confirming the key. Search from the *question*, have a model answer it from the
   evidence *without* seeing the key, and only then compare. Agreement between a blind answer and the key is
   the strongest signal this system can produce.
3. **Mechanical grounding of every citation.** URLs may only come from search/fetch logs, never from model text.
   Every quoted excerpt must be found (after whitespace/quote normalisation) in the stored copy of the page.
   A citation that fails this check is discarded, and the stage is retried or flagged. This removes the
   fabricated-citation problem by construction instead of by prompt.
4. **The final verdict is computed by code, not chosen by a model.** Models produce stances, passages and
   objections; a deterministic, versioned rules table turns those into `VERIFIED / INCORRECT / …`. A model
   can never write `VERIFIED` on its own.
5. **"Frame of reference" is a first-class concept.** A question can be correct *within the edition's declared
   convention* and contested outside it. This is essential for the Ahmadiyya editions (see §1.4) — including
   something the spec misses entirely: **Qur'an verse numbering**. Triventurex counts the Bismillah as verse 1,
   so `Surah Al-Baqarah 2:32` in our notes is 2:31 in the most common numbering online. A naive validator would
   flag almost every Qur'an reference as wrong.
6. **Validate the `note` field too.** In our editions the note is shown to players and often contains its own
   checkable claims (verse references, "known from hadith", dates). The spec treats it as context only.
7. **The independent reviewer must not be anchored.** Run a second *blind* verification (different model,
   ideally different provider) that does not see the first verdict, *then* a challenger that does. Disagreement
   between the two blind passes is more informative than a reviewer reading a confident first answer.
8. **Separate verdict from workflow.** `REVIEW_REQUIRED` is a routing state, not a fact about the question.
   Keep `verdict` (about the content), `quality` (about the wording) and `review_status` (about the workflow) apart.
9. **Cache documents, not conclusions.** Fetched pages and search results are safe to share between questions;
   verdicts are not. This gives most of the cost saving of "claim clustering" with none of its risk.
10. **Measure before trusting.** Build a labelled evaluation set (≈150 questions, including deliberately
    *seeded* errors) in phase 1. Ten acceptance cases cannot tell you whether the tool catches 50 % or 95 %
    of wrong answers — and that number is the whole point of the tool.

---

## 1. Architecture assessment

### 1.1 Can the pipeline reliably establish factual accuracy?

**Partly, and the spec slightly over-promises.** What is solid: separate stages, structured outputs, schema
validation, "absence of contradiction is not proof", no calibrated-confidence claims, human decisions stored
separately. These are the right instincts.

Weaknesses:

| # | Weakness | Consequence | Fix |
|---|---|---|---|
| W1 | Research receives the expected answer "as context" | Confirmation bias in query choice and in what is read as relevant | Answer-blind query generation + blind answering (§3, stages S1/S4) |
| W2 | One model family does research, verification and quality | Correlated errors: the same misconception passes every stage | Blind second verifier on another model/provider; mechanical checks between stages |
| W3 | Final verdict is an LLM field | Verdicts drift with prompt wording; untestable | Deterministic aggregation rules (§3.4), unit-tested |
| W4 | Source quality judged per call by the model (`reliability_assessment: string`) | Inconsistent, unauditable reliability | Configurable source registry (domain → tier, type, profile) applied by code; the model may only *add* concerns |
| W5 | "Two independent sources" undefined | Wikipedia + a Wikipedia mirror count as two | Independence = different publisher **and** passage text not near-duplicate (rapidfuzz/shingles) |
| W6 | Distractors: "verify incorrect options are genuinely incorrect" | Proving a negative for 3 options × 7,000 MC questions is expensive and often impossible | Targeted: only investigate a distractor when the blind answer picks it, evidence mentions it, or the quality stage flags it |
| W7 | No evaluation methodology | No way to know recall/precision; prompt changes are guesswork | Labelled eval set + seeded-error set, re-run on every prompt/model change |
| W8 | Time-sensitive facts have no "as of" | "Correct" sports records silently rot | Store `valid_as_of` and `time_sensitive`; `OUTDATED` requires evidence of the change |
| W9 | Prompt injection from fetched pages not considered | A web page can instruct the verifier | Fetched text is delimited data; judgement stages have no tools; grounding check limits damage |
| W10 | Audience not considered | Our questions mix ages 5+ to adults (see project notes); "too hard / misleading for a child" is a real defect | Quality stage receives the edition's audience profile |

### 1.2 Is the separation between research, verification and review sufficient?

The **stage** separation is good; the **information** separation is not. What matters is *what each stage is
allowed to see*:

| Stage | Sees question | Sees options | Sees key | Sees evidence | Sees other verdicts |
|---|---|---|---|---|---|
| Analysis | yes | yes | yes (to understand what is tested) | — | — |
| Query planning | yes | yes | **no** (plus one *separate* answer-aware "counter-check" query) | — | — |
| Evidence extraction | claim only | yes | as one candidate among the options | one document at a time | no |
| Blind answer | yes | yes, **unmarked** | **no** | passages | no |
| Verification | yes | yes | yes | passages | blind answer |
| Second blind verifier | yes | yes | yes | passages | **no** |
| Challenger | everything | | | | yes |
| Quality | yes | yes | yes | no (independent of facts) | no |

### 1.3 Retrieving and assessing online sources

- **Own search + own fetcher**, not the model's built-in browsing, for the research stage: we must store the
  exact text we cite (for the grounding check and for the reviewer), cache it across questions, swap providers,
  and keep the judgement stages batchable. (Anthropic's server-side `web_search`/`web_fetch` tools are a
  reasonable later option for a "deep research" escalation path, but they make snapshots and caching harder.)
- **Direct sources before search** where a structured primary source exists:
  - Qur'an: a local corpus (Arabic + one or two English translations) with **both numbering schemes**, so a
    reference can be checked deterministically: "does 2:32 (Bismillah-as-1) say what the note says?"
  - Wikipedia/Wikidata via their APIs (good for dates, capitals, heights, populations — and as a *pointer* to
    primary sources, not as the final authority).
  - Official Ahmadiyya sources (alislam.org, reviewofreligions.org …) for Ahmadiyya-specific questions.
  - Later: sports federations' statistics pages, national statistics offices.
- **Fetch pipeline:** URL → HTTP fetch (polite UA, robots.txt, timeouts, size cap) → main-text extraction
  (trafilatura; PDF via pypdf) → normalise → store text + SHA-256 + fetch date + final URL + status.
  Snippets are only used to *choose* what to fetch.
- **Assessment:** source tier comes from a YAML registry per profile (A = primary/official, B = reputable
  secondary/encyclopaedic, C = general web, X = blocked: content farms, AI-generated quiz sites, forums).
  The model may *lower* a source's standing for a stated reason ("this page is about a different person"),
  never raise it.

### 1.4 Conflicting sources — religious and historical questions

The core idea: **a verdict is relative to a declared frame of reference.**

- Each edition/profile declares its frame, e.g. *Prophets' Stories*: "Ahmadiyya understanding; Qur'an
  numbering with Bismillah as verse 1; honorifics (as)/(sa)/(ra) are not part of the answer."
- Analysis classifies each question as `universal` (a date, a capital), `tradition-general` (what the Qur'an
  says), or `frame-specific` (Ahmadiyya belief, e.g. Hadhrat Isa (as) surviving the crucifixion).
- For frame-specific questions, supporting evidence must come from the frame's authoritative sources; evidence
  from other frames is recorded as **"contested outside the frame"**, not as contradiction. The result is
  `VERIFIED (within frame)` + a `contested` flag, never `INCORRECT` merely because mainstream sources differ.
- For universal and historical questions, conflicts are recorded as such: if tier-A/B sources disagree, the
  verdict is `CONTESTED` and goes to a human with both sides' passages side by side. Never auto-resolve.
- As the spec says, an official organisational source is not automatically final on *everything*: the frame
  only applies to frame-specific claims. "In which year was Qadian founded?" is a historical question.
- Specialist review for religious questions should be routed to the edition's existing human reviewer —
  the tool's job is to *prepare* the case (claim, frame, passages, disagreement), not to decide it.

### 1.5 Preventing hallucinations and fabricated citations

Defence in depth; only the first two are hard guarantees, the rest reduce risk:

1. **Provenance:** a source exists in the result only if it is a row in `documents` created by our fetcher.
   Models refer to passages by ID (`P17`), never by URL or title.
2. **Grounding check:** every excerpt must be a substring (normalised) of the stored document text; we store
   char offsets. Failure → retry once with the error, then flag the stage.
3. **Closed-book prohibition:** judgement prompts must answer *only* from supplied passages; a claim in the
   explanation without a passage ID is treated as unsupported by the rules engine.
4. **Blind agreement:** key ≠ blind answer is a strong error signal regardless of how confident any stage is.
5. **Second blind verifier + challenger** on a different model.
6. **Structured outputs** (schema-constrained decoding) + Pydantic validation; never silently accept partial JSON.

### 1.6 Minimising API calls and research cost

- Stage 1 (structural) is free; run it on everything and fix obvious problems before spending money.
- Document cache and search-result cache (keyed by normalised query + provider, with a TTL per profile —
  long for history/religion, short for sports/current affairs).
- Exact-duplicate claims share retrieval; near-duplicate claims share *candidate documents* but each
  question still gets its own extraction and judgement.
- Model tiering per stage (cheap model for extraction/analysis, strongest model for verification and review) —
  a configurable choice measured in the pilot, not assumed.
- Batch API (≈50 % cheaper, asynchronous) for every stage that does not need live tool use: analysis,
  extraction, blind answer, verification, quality, review.
- Prompt caching: stable system prompt + profile instructions first, the question last.
- Adaptive depth: stop researching when the verdict rules are already satisfied (e.g. two tier-A passages
  agree with the blind answer); escalate only when they are not.
- Pilot run (50–100 questions, stratified by category) gives measured cost per question before a full run.

### 1.7 Processing 2,000–10,000 questions reliably

- **Long work must not run inside Streamlit.** Streamlit re-runs the script on every interaction; a job
  started from a page dies or duplicates. Use a separate worker process (`qv worker`) that the UI starts and
  observes through the database.
- A durable **task table** (question × stage) with status, attempts, lease expiry and an `input_hash`. A stage
  is skipped if an output with the same input hash, prompt version and model already exists → resume and
  "revalidate only what changed" fall out naturally.
- asyncio workers with per-provider semaphores and a token-bucket limiter; exponential backoff with jitter on
  429/5xx; `retry-after` respected; circuit breaker if a provider keeps failing.
- SQLite in WAL mode, one writer connection in the worker, short transactions. Fine for this volume
  (≈10k questions × ≈10 stage rows + ≈50k documents).
- Budget guard: the run stops when the configured cost ceiling is reached.

### 1.8 Is the technology stack appropriate?

| Choice | Verdict | Notes |
|---|---|---|
| Python 3.12 | ✔ | Best ecosystem for extraction, fuzzy matching, LLM SDKs; matches your usual stack |
| SQLite | ✔ | Single user, local; WAL mode. Store document text in the DB (compressed) or as files keyed by hash |
| SQLAlchemy 2 + Alembic | ✔ | Add Alembic from day one — the schema will change |
| Pydantic v2 | ✔ | Also used to generate the JSON schemas for structured outputs |
| Pandas | ⚠ | Only for import/export. **Read CSV with `dtype=str, keep_default_na=False`** or ids like `007`, answers like `1997`, and empty strings get mangled. Round-trip with the `csv` module to keep quoting |
| Streamlit | ⚠ acceptable for v1 | Good for tables/filters; weaker for a fast keyboard-driven review queue. Keep all logic in services so the UI can be replaced (e.g. FastAPI + a small page) later |
| Tavily | ✔ | Or Brave Search API; keep behind an interface. Consider both to diversify results |
| Anthropic + OpenAI | ✔ | Anthropic first. OpenAI's main value here is an *independent* second verifier — add it in that phase rather than maintaining two providers from day one |
| Docker | later | Agreed |
| Additional | | `httpx`, `trafilatura`, `pypdf`, `rapidfuzz`, `tenacity`, `typer` (CLI), `pytest`, `respx`/VCR-style recorded fixtures for provider tests |

Where it lives: a separate Python project in `Triventurex/question-validator/` with its own
`pyproject.toml`, own tests and own `.gitignore` (data/, .env). It reads/exports game CSVs but never writes
into `game_editions/`. (If the repo gets crowded later, it can move to its own repository without changes.)

### 1.9 Missing requirements

- **Frame of reference / conventions per edition** (§1.4), incl. Qur'an numbering and honorifics in answers.
- **Note validation** (§0.6).
- **Audience/age appropriateness** in the quality stage.
- **Cross-question consistency:** two questions in a dataset that contradict each other (different dates for
  the same event) — cheap to detect once claims are extracted.
- **Answer normalisation rules** for open questions (honorifics, transliteration variants: Hawwa/Eve,
  Isma'il/Ismail, "Surah An-Nas"/"An-Nas") — partly rules, partly model.
- **Export must pass the game's checker**: the corrected CSV should pass `npm run check:content`.
- **Ids are sacred** in Triventurex (asked-question tracking and 🚩 marks are by id): corrections never
  renumber; a rejected question is reported, not deleted.
- **Run reproducibility:** each run stores model ids, prompt versions, registry version, profile and config.
- **Evaluation set & regression metrics** (§0.10).
- **Cost ceiling per run**, not just an estimate.
- **Data handling:** API keys in `.env`; page snapshots are stored locally for personal verification and never
  exported in full (excerpts only).
- **Review throughput:** with 10k questions, even 15 % flagged is 1,500 reviews. The UI must prioritise
  (likely-wrong first) and support bulk actions for trivial fixes (spelling, normalisation).

---

## 2. Revised technical architecture

```
                ┌────────────────────────── Streamlit UI ──────────────────────────┐
                │ Datasets · Runs · Results · Review queue · Question detail · Export│
                └───────────────┬───────────────────────────────▲──────────────────┘
                                │ commands (start/pause run,    │ reads
                                │ human decisions)              │
                        ┌───────▼───────────────────────────────┴───────┐
                        │                SQLite (WAL)                    │
                        │ datasets · questions · runs · tasks · outputs  │
                        │ documents · passages · validations · decisions │
                        └───────▲───────────────────────────────┬───────┘
                                │ claim / write task rows       │
                ┌───────────────┴──────────── Worker (qv worker) ┴──────────────┐
                │  Scheduler → stage runners (async, rate-limited, idempotent)  │
                │                                                               │
                │  S0 Structural ─► S1 Analysis ─► S2 Retrieval ─► S3 Extraction │
                │        │                                            │         │
                │        └─► S6 Quality        S4 Blind answer ◄──────┘         │
                │                                   │                           │
                │                     S5 Verification + S5b Second blind verify │
                │                                   │                           │
                │                             S7 Challenger                     │
                │                                   │                           │
                │                     S8 Verdict rules engine (pure code)       │
                └──────┬──────────────┬──────────────┬──────────────┬───────────┘
                       │              │              │              │
                 LLM providers   Search providers  Fetcher +     Direct sources
                 (Anthropic,     (Tavily, Brave)   extractor     (Qur'an corpus,
                  OpenAI)                          (trafilatura) Wikipedia API …)
```

Folder layout (adjusted from the spec):

```
question-validator/
  pyproject.toml   .env.example   README.md   ARCHITECTURE.md
  qv/
    cli.py                    # typer: import, run, worker, export, eval
    config.py                 # settings from env + config/*.yaml
    domain/                   # Pydantic models: question, analysis, evidence, verdict, decision
    db/                       # SQLAlchemy models, session, repositories; alembic/
    pipeline/
      structural.py  analysis.py  retrieval.py  extraction.py
      blind_answer.py  verification.py  quality.py  challenge.py
      rules.py                # deterministic verdict aggregation (no I/O)
      grounding.py            # substring / offset verification
      scheduler.py            # tasks, leases, retries, budgets
    providers/
      llm/ base.py anthropic.py openai.py
      search/ base.py tavily.py brave.py
      fetch.py extract.py
      direct/ quran.py wikipedia.py
    prompts/                  # versioned: analysis.v1.md, …
    ui/                       # streamlit app + pages (thin; calls services only)
  config/
    profiles/ general.yaml islamic.yaml ahmadiyya.yaml sports.yaml
    sources.yaml              # domain registry: tier, type, profiles
    rules.yaml                # thresholds used by rules.py (N sources, tiers)
  data/ (git-ignored)         # validation.db, imports/, exports/, quran/
  eval/                       # labelled questions + expected verdicts + seeded errors
  tests/
```

Design rules:

- **Stages are pure-ish functions** `(inputs) -> output model`, with all I/O through providers. Each output
  row records `stage`, `schema_version`, `prompt_version`, `model`, `input_hash`, usage and cost.
- **No stage reads another stage's free text**, only structured fields (claim, passage IDs, stances).
- **Prompts are versioned files**; changing a prompt creates a new version, so old results stay explainable.
- **The UI never calls an LLM directly**; "Revalidate" creates tasks for the worker.

---

## 3. Detailed processing workflow

### 3.1 Import (no AI)

1. Upload CSV → store the original bytes unchanged (`data/imports/<sha256>.csv`) + a `dataset_version`.
2. Parse as strings; record row number and raw row JSON for every row, including malformed ones.
3. Structural checks: required columns; type ∈ {multi, open}; difficulty ∈ {easy, medium, hard}; multi answer ∈
   1–4 and that option non-empty; open answer non-empty; duplicate ids; duplicate options within a question;
   empty options between filled ones; exact and near-duplicate questions (normalised text, rapidfuzz ≥ 90,
   reported as "possibly the same question" — never merged).
4. Summary screen (counts per the spec) → user confirms → version is frozen.
5. Re-importing an edited file creates a new version and a **diff by id** (added / changed / removed);
   a later run can validate only changed rows.

### 3.2 Run setup

User chooses dataset version, subset (all / filter / changed since run X / marked ids), profile per
category, model per stage, research depth, independent review on/off, budget ceiling. Then:

- **Pilot** (default 50, stratified sample) → shows measured calls, tokens, cost/question, projected total.
- **Full run** → creates task rows for every question × enabled stage; worker picks them up.

### 3.3 Per-question stages

| Stage | Input | Output | Model | Batchable |
|---|---|---|---|---|
| **S1 Analysis** | question, options, key (resolved to text), category path, note, profile | factual claim(s) incl. note claims; what is asked; frame class (`universal` / `tradition-general` / `frame-specific`); time-sensitivity; conventions needed; interpretations; **answer-blind queries** + one counter-check query; direct-source lookups (e.g. `quran:2:32@bismillah1`) | mid | ✔ |
| **S2 Retrieval** | queries, lookups, profile | direct-source texts; search results; fetched + extracted docs (cached); ranked by registry tier; dedupe by content hash | none | — |
| **S3 Extraction** | claim + candidate answers (all options / key + alternatives), one doc at a time | passages: verbatim text, offsets, stance per candidate (`supports A`, `contradicts B`, `irrelevant`), → **grounding check** | cheap/mid | ✔ |
| **S4 Blind answer** | question + unmarked options + passages | chosen option / free answer + passage IDs, or `insufficient` | strong | ✔ |
| **S5 Verification** | everything + blind answer | factual_accuracy, answer_uniqueness, per-option assessment, acceptable alternatives, false premise?, outdated?, frame dependence; each judgement with passage IDs | strong | ✔ |
| **S5b Second blind verifier** | same as S5 **minus** S4/S5 outputs | same schema | strong, other provider when available | ✔ |
| **S6 Quality** | question, options, key, difficulty, audience profile | clarity, precision, answer-leak, distractor quality, difficulty fit, age fit, suggested rewrite (only when needed) | mid | ✔ |
| **S7 Challenger** | all of the above | objections, each typed (`unsupported`, `misread_source`, `missed_alternative`, `weak_source`, `false_premise`, `frame_confusion`) and grounded in passage IDs or explicitly "no evidence" | strong | ✔ |
| **S8 Rules** | structured outputs + registry | verdict, evidence_strength, contested flag, review routing + human-readable reasons | code | — |

Escalation: if S8 lands on `UNVERIFIED` because evidence is thin (not because sources disagree) and depth
allows, run **one** extra retrieval round with queries suggested by S5/S7, then S3–S8 again. Never loop more
than the configured depth.

### 3.4 Verdict rules (first draft — lives in `rules.yaml` + `rules.py`, unit-tested)

Definitions: *support(X)* = grounded passages supporting answer X from **independent** publishers;
tier weights from the registry; *frame sources* for frame-specific claims.

| Verdict | Conditions (all must hold) |
|---|---|
| **VERIFIED** | blind answer = key (or accepted alternative) · support(key) ≥ 2 independent tier ≤ B, **or** ≥ 1 tier-A primary source for a direct-source claim (Qur'an verse) · no grounded tier ≤ B contradiction · both verifiers `CORRECT` · no unresolved grounded objection from S7 |
| **INCORRECT** | grounded tier ≤ B contradiction(s) of the key (≥ 1 tier-A or ≥ 2 tier-B) · blind answer ≠ key · at least one verifier `INCORRECT` · *a proposed correction is a suggestion only — always human-approved* |
| **AMBIGUOUS** | ≥ 2 options/answers each have grounded support, or S5 finds multiple interpretations with different correct answers |
| **CONTESTED** *(new)* | tier ≤ B sources disagree with each other on the claim (outside a declared frame) |
| **OUTDATED** | grounded support that the key *was* true + grounded tier ≤ B evidence of a later change |
| **UNVERIFIED** | none of the above; in particular too little grounded support |

Routing (`review_status`), separate from the verdict:

- `needs_review` if verdict ∈ {INCORRECT, AMBIGUOUS, CONTESTED, OUTDATED}, if the two blind verifiers
  disagree, if S7 has a grounded objection, if the frame class is `frame-specific` and the profile requires it,
  or if quality = POOR.
- `needs_specialist` for religious frame-specific claims with any disagreement.
- `auto_ok` only for VERIFIED with no flags — still visible and reversible in the UI.

`evidence_strength` is computed: STRONG (≥ 2 independent tier-A/B or 1 tier-A primary), MODERATE (2 tier ≤ C
incl. ≥ 1 B), WEAK (1 source), NONE.

### 3.5 Human review

Queue sorted by: INCORRECT → disagreement → CONTESTED → AMBIGUOUS → OUTDATED → quality POOR → rest.
Detail view shows the claim, frame, key vs blind answer, passages grouped *supports / contradicts* with tier
badges and links to the stored snapshot, both verifiers, challenger objections, quality notes and the
suggested correction. Actions (as in the spec) write **append-only** `human_decisions`; the latest decision
wins; nothing is ever written back to the original rows.

### 3.6 Export

1. Original CSV (byte-identical copy of the import).
2. Validation report CSV (one row per question: verdict, strength, flags, reasons, top 2 source URLs).
3. Excel workbook: Summary · All results · Needs review · Sources · Proposed changes · Decisions.
4. Corrected CSV: original rows with **only approved** field changes applied, same column order and quoting,
   ids untouched; then validated with the same structural checks (and you run `npm run check:content`).

---

## 4. Database design (SQLite)

```
datasets            id, name, created_at, description
dataset_versions    id, dataset_id, version_no, source_filename, file_sha256, imported_at,
                    row_count, parent_version_id, profile_map_json
questions           id, dataset_version_id, row_no, ext_id (csv id), raw_json (all original columns, as text),
                    type, question, answer, opt_a..opt_d, difficulty, category, subcategory, topic, note,
                    content_hash, resolved_answer_text
structural_issues   id, question_id NULL, dataset_version_id, row_no, code, severity, message

runs                id, dataset_version_id, name, kind (pilot|full|revalidate), status, created_at,
                    config_json (models per stage, depth, profiles, rules version, prompt versions),
                    budget_usd, spent_usd
tasks               id, run_id, question_id, stage, status (pending|running|done|failed|skipped),
                    attempts, lease_until, input_hash, last_error, updated_at
                    UNIQUE(run_id, question_id, stage)
stage_outputs       id, task_id, stage, schema_version, prompt_version, provider, model,
                    input_hash, output_json, valid (bool), created_at
                    INDEX(stage, input_hash, prompt_version, model)   -- reuse across runs

search_queries      id, provider, query_norm, params_json, results_json, fetched_at, expires_at
documents           id, url, final_url, domain, publisher, title, source_type, tier (snapshot of registry),
                    http_status, fetched_at, content_sha256, text (compressed) or text_path,
                    extract_method, language, char_len
                    UNIQUE(final_url, content_sha256)
direct_texts        id, source (quran|wikidata|…), ref (e.g. "2:32"), scheme ("bismillah1"|"hafs"),
                    translation, text
passages            id, run_id, question_id, document_id NULL, direct_text_id NULL, char_start, char_end,
                    text, grounded (bool), extracted_by_output_id
passage_stances     passage_id, candidate (option index or answer text), stance (supports|contradicts|mentions)

validations         id, run_id, question_id, verdict, evidence_strength, factual_accuracy,
                    answer_uniqueness, question_quality, contested (bool), frame_class,
                    blind_answer, verifiers_agree (bool), review_status, reasons_json,
                    suggested_answer, suggested_question, acceptable_alternatives_json,
                    valid_as_of, rules_version, created_at
                    UNIQUE(run_id, question_id)
objections          id, validation_id, type, text, passage_ids_json, resolved_by_rules (bool)

human_decisions     id, question_id, validation_id NULL, action (approve_original|approve_suggestion|
                    edit|specialist|reject|revalidate), field_changes_json, comment, decided_at
                    -- append-only
api_calls           id, run_id, task_id NULL, provider, model, kind (llm|search|fetch), batch_id NULL,
                    input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd,
                    latency_ms, status, created_at
```

Notes:
- `raw_json` + exact original file bytes ⇒ no loss of metadata and byte-faithful re-export.
- `input_hash` = hash of (stage inputs + prompt version + model + schema version) ⇒ idempotent resume and
  cheap revalidation.
- Comparing runs = join `validations` of two runs on `questions.ext_id` (+ content hash to show edits).
- The source registry and profiles stay in YAML (versioned in git); their version is stamped on each run and
  the tier is snapshotted on each document.

---

## 5. API integration strategy

### 5.1 Provider interfaces

```python
class LLMProvider(Protocol):
    def complete_structured(self, *, stage: str, system: str, user: str,
                            schema: type[BaseModel], model: str, effort: str) -> StructuredResult: ...
    def submit_batch(self, requests: list[BatchItem]) -> str: ...      # returns batch id
    def collect_batch(self, batch_id: str) -> Iterator[BatchResult]: ...

class SearchProvider(Protocol):
    def search(self, query: str, *, max_results: int, include_domains: list[str] | None) -> list[SearchHit]: ...
```

`StructuredResult` always carries usage, model actually used, stop reason and the raw response id.

### 5.2 Anthropic specifics (current API, checked 2026-11)

- **Structured outputs** via `output_config.format` / `messages.parse()` with the Pydantic-generated
  schema; still validate with Pydantic and reject on failure (retry once with the validation error).
- **Citations feature** (document blocks with `citations: {enabled: true}`) gives exact cited spans, but it
  **cannot be combined with structured outputs**. Recommendation: use our own grounding check (provider-agnostic,
  works with OpenAI too); keep citations as an option for the extraction stage if the grounding failure rate
  is high.
- **Message Batches API** for S1, S3–S7: ~50 % cheaper, results within hours, keyed by `custom_id`
  (`<run>:<question>:<stage>`), results in any order. Interactive mode (single question revalidation) uses
  the normal endpoint.
- **Prompt caching**: system prompt + profile + schema description first and identical across questions;
  question-specific content last. Verify with `usage.cache_read_input_tokens`.
- **Refusals**: check `stop_reason == "refusal"` before reading content; treat as a stage failure with its
  own error code (religious or violent historical topics might occasionally trigger this) → route to review.
- **Models**: the defaults to evaluate in the pilot are Claude Opus 5.5 for S4/S5/S7 (reliability matters most
  there) and a choice of Sonnet 5.5 or Haiku 5.5 for S1/S3/S6. Which cheaper model is good enough is *your*
  call after seeing pilot numbers against the eval set — not something to assume. Note that on Opus 5.5 effort
  defaults to `medium`; set it explicitly per stage.
- **Thinking** is always on for Opus 5.5/Sonnet 5.5 (adaptive); control depth with `effort`, not budgets.
- **Keys**: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY` in `.env` (git-ignored); `.env.example`
  committed. As the spec says, a Claude subscription does not cover API usage.

### 5.3 Independence

The second blind verifier (S5b) should use OpenAI (or another provider) when a key is configured; otherwise a
different Claude model with a differently written prompt. Disagreement rates between providers are themselves
a useful health metric in the run summary.

### 5.4 Rate limits and retries

Per-provider token buckets (requests/min and tokens/min from config), `tenacity` exponential backoff with
jitter for 429/5xx/timeouts, honour `retry-after`, max attempts per task (default 3), then `failed` with the
error kept — the run continues. Search and fetch have their own limits; fetches are also limited per domain.

### 5.5 Cost estimate (rough — the pilot replaces this with measured numbers)

Assumed per question at standard depth: 3 searches, 4 fetched documents (~3k tokens each after extraction),
≈ 30k input and ≈ 5k output tokens across all stages (thinking included).

| Mix | ≈ cost / question | 2,000 q | 10,000 q |
|---|---|---|---|
| All stages Opus 5.5, no batching | $0.25–0.35 | $500–700 | $2,500–3,500 |
| Opus 5.5 for judgement, cheaper model for S1/S3/S6, batched | $0.08–0.15 | $160–300 | $800–1,500 |
| + search API (≈ $0.005–0.01 per query, check current pricing) | +$0.02–0.03 | +$40–60 | +$200–300 |

Document and search caches should cut the search/extraction share noticeably for themed editions where many
questions draw on the same pages. The current Triventurex content (~1,190 questions across five editions) is a
natural first full run: big enough to be meaningful, small enough to cost tens to a few hundred dollars.

---

## 6. Implementation plan

Each phase ends with something runnable and tested; nothing moves on until the exit criteria hold.

### Phase 1 — Foundation & evaluation set
- `pyproject.toml`, package layout, config, Alembic, SQLite (WAL).
- CSV import (strings only, original bytes kept), structural checks, near-duplicates, dataset versions + diff.
- Exports: original, structural report, round-trip test (import → export → byte-identical).
- CLI: `qv import`, `qv check`, `qv export`.
- **Eval set:** ≈150 labelled questions drawn from the existing editions (mixed categories, both types, the
  ten spec cases) + ≈50 seeded errors (wrong key, swapped option, wrong year, wrong verse number in a note,
  a distractor that is also correct).
- **Exit:** all five edition CSVs import cleanly; structural findings reviewed; round-trip byte-identical.

### Phase 2 — Evidence layer (no verdicts yet)
- Search provider (Tavily), fetcher + extractor, document and query caches, source registry + profiles.
- Direct sources: Qur'an corpus with both numbering schemes; Wikipedia API.
- S1 analysis and S3 extraction with the grounding check.
- CLI: `qv research <dataset> <id>` prints claim, queries, documents, grounded passages.
- **Exit:** on the eval set, grounding failure < 2 %; for ≥ 85 % of non-frame-specific questions at least one
  relevant tier ≤ B passage is found; zero ungrounded excerpts reach the database.

### Phase 3 — Judgement
- S4 blind answer, S5 verification, S6 quality, S8 rules engine (pure, fully unit-tested), `validations` table.
- CLI: `qv validate <dataset> --ids …` synchronous mode.
- **Exit:** on the eval set: seeded-error recall ≥ 90 % (caught as INCORRECT, AMBIGUOUS, CONTESTED or routed
  to review); false INCORRECT on known-good questions ≤ 3 %; no VERIFIED without grounded support (test).
  Tune prompts and rules here, re-running the eval each time.

### Phase 4 — Reliability & scale
- Task table, worker, leases, resume, retries/backoff, rate limiting, budget ceiling.
- Batch API path; prompt caching; `api_calls` usage and cost tracking.
- Pilot run + cost projection.
- **Exit:** kill the worker mid-run and restart → no duplicate work, no lost results; pilot of 100 questions
  produces a cost report; one full edition (e.g. World Tour, 220 q) runs unattended.

### Phase 5 — Review UI & corrected export
- Streamlit: dashboard, import, run settings, results table with filters, review queue, question detail,
  human decisions, exports (report CSV, Excel, corrected CSV).
- **Exit:** a reviewer can work through the queue of a full edition; the corrected CSV passes the game's
  `npm run check:content`; ids unchanged.

### Phase 6 — Independence & refinement
- OpenAI provider and S5b second blind verifier; S7 challenger; disagreement routing.
- Run comparison view; revalidate changed rows only; cross-question consistency check; escalation round.
- **Exit:** eval metrics no worse than phase 3, and disagreement routing catches at least some seeded errors
  that a single verifier missed (otherwise reconsider the cost of S5b/S7).

---

## 7. Decisions needed from you before phase 1

1. **Frame definitions per edition** — especially which sources are authoritative for Ahmadiyya-specific
   questions, and whether the Qur'an translation to quote is the Ahmadiyya one (Sher Ali / Five Volume) — the
   edition's knowledgeable reviewer is the right person to confirm this.
2. **Search provider** — Tavily, Brave, or both.
3. **Second provider** — is an OpenAI key available for the independent verifier, or should S5b use a second
   Claude model?
4. **Budget ceiling** for the first full run.
5. **Scope of the first run** — all five editions (~1,190 questions), or start with one (Football Quest, which
   is already flagged for possible errors, is a good candidate).
6. **Validate notes?** Recommended yes for editions where notes are shown to players.
