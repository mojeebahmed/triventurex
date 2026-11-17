# question-validator — notes for Claude

A **separate Python project** that lives inside the Triventurex repo. The game rules in the root `CLAUDE.md`
(vanilla JS, no build step, `npm test`, icons, edition config, etc.) do **not** apply here — only the root
*Memory & Context Files*, *About Me* and *Workflow* sections (branch per item, ask before pushing) do.

## Read first
- `METHODOLOGY.md` — how a question is judged. It is the source of truth for stages, what each stage may see,
  evidence requirements, verdict rules. Do not weaken the answer-blind design (S1a, S3, S4 never see the key).
- `ARCHITECTURE.md` — stack, database design, workflow, API strategy, phased plan (§6). Where §3 differs from
  METHODOLOGY.md, METHODOLOGY.md wins.
- `prompts/` — prompt + JSON schema per stage. Prompts are versioned: change a prompt → new version file.
- `KNOWLEDGE_BASE_PLAN.md` — the knowledge base plan and its 6-phase roadmap (start here for any phase).
- `USER_GUIDE.md` — the simple four-step workflow for Mojeeb (web page + `qv status` / `qv next` / `qv export`).
- `DATABASE.md` — tables in plain words, how to inspect the database, example queries. Update it when a table
  or an inspecting command changes.
- `SPECIFICATION.md` — the original PRD (unchanged copy; don't edit).

## Status
- Phase 1 done (2026-11-15): foundation, DB, CSV import/export, structural checks, eval set.
- Phase 2 done (2026-11-15): evidence layer — S1a/S1b/S3, search, fetch, Qur'an source, grounding, quotas,
  read-only web view (`qv ui`). Merged to `main` and pushed.
- Pilot (runs 2–3, 10 Swab Quest questions: 2,5,34,52,70,127,247,285,391,418): 80 grounded passages, 2.4 % quotes
  dropped (target < 2 %), 90 % of questions with a passage on the need (target ≥ 85 %), $0. #70 found no evidence.
- Local models (2026-11-15, merged): `OllamaProvider`, cross-provider pools
  (`provider/model` entries). S3 trial on 3 pilot documents: gemma3:12b grounded 13/15 quotes, qwen3:8b 19/24,
  qwen3:14b 4/7 (Gemini ≈ 98 %), but 1–4 min per document vs ≈ 1.5 s on Gemini → local = $0 overflow after the
  free Gemini quota (`cheap_then_local` pool), not first. S3 default stays `cheap`. Relevance of local passages
  not yet judged; S1a/S1b/S6 locally not tried yet.
- Phase 3 built (2026-11-16, branch `feat/qv-phase3-judgement`): S4/S5/S6, S8 rules, `validations` table,
  `qv validate | judge | verdicts | verdict | eval score`, web view with a plain summary + legend. Pilot (run 3,
  judged): 4 VERIFIED (#5, #34, #52, #418), #2 needs_review (verifier: PARTIALLY_CORRECT), #127/#247
  needs_specialist (scripture/doctrine without the verse or a frame authority), #70/#391/#285 needs_evidence.
  S5b and S7 stay in phase 6. Merged to `main` and pushed.
- **Eval measurement (in progress, 2026-11-16):** `qv eval import` stores eval-known-errors, the seeded set split
  per edition (`eval-seeded-<edition>`, judged with that edition's profile) and the seeded questions' originals
  in each edition as **controls** (label `control`: anything but an error verdict is right) — controls give the
  false-INCORRECT rate. 104 questions; ≈ 2 Flash requests each (S4 is shared when only the key/note was mutated),
  judge pool ≈ 57/day → several days. Score with `qv eval score <runs…>` (runs on an older eval version are
  skipped). Day 1 (runs 4–6): 36 of 57 Flash requests were lost to overloaded 3.8/3.7 Flash (503s, 120 s
  timeouts) → pool now retries once, rests a failing model for 10 min, judge pool starts with 3.6. Known
  errors: 4/4 routed to review (#73 INCORRECT; #66/#86 UNVERIFIED with the right answer suggested; #70's
  false premise flagged by S6 only). **Flash-Lite as judge** (`--judge-pool cheap`, runs 7–14, 2026-11-16): 47 of 104
  labelled before both Flash-Lite quotas ran out (run 14 stopped: `qv resume 14`, then football-quest seeded +
  controls). Error recall 88 % (22/25 routed to review; seeded swab #2/#18 → needs_evidence), false INCORRECT 0 %
  (0/21), 1 false verification: seeded animal-safari #37 (kangaroo hop 8 → 9 m) — 3 sources say 9 m, so the
  mutation is probably not an error (seeder label issue). Many seeded errors come back UNVERIFIED rather than
  INCORRECT (verdict agreement 60 %) but still reach review. Seeder fixed: decades ("1880s") are no longer mutated (set regenerated;
  40 of 50 mutations unchanged). Next: `qv resume 6`, then the remaining seeded + control datasets. Seen: #127 and #285 (same question) got different claim types from
  S1a → different routes (cross-question consistency, next-work item 4).
- Run `.venv/bin/python -m pytest` before merging (see README for setup). Open points of METHODOLOGY.md §13 were answered on 2026-11-16.

## Simple workflow (built 2026-11-16)
Mojeeb wants the tool usable with very few steps, in the web page: `Start Question Validator.command` → Overview
(menu since 2026-11-16 evening: Import · Prepare · Validate · Daily run · Review · Export, + Advanced pages). Commands: `qv status`, `qv next`,
`qv export corrected|ready|results`, `qv auto on|off|status|run`. User-facing description: `USER_GUIDE.md` (keep
it current). One-click import fixes and the automatic daily batch were added on 2026-11-16. This is ARCHITECTURE.md phases 4–5, made simple;
all other commands stay for power users and debugging.

## Next work (agreed order, 2026-11-15)
1. **Local model provider (Ollama)** — Mojeeb's Mac: M2 Pro, 32 GB, Ollama installed with `qwen3:14b`, `gemma3:12b`,
   `mistral-nemo`. Add an `OllamaProvider` (structured output via `format` = JSON schema) to the model pools;
   first target S3 (most calls; grounding catches bad quotes), then try S1a/S1b/S6. Not for S4/S5 until the eval set
   says it is good enough. Config decides order (local first or Gemini first).
2. **Phase 3 — judgement** (built; eval measurement still to run): S4 blind answer, S5 verification, S6 quality, S8 rules engine (pure code), `validations`
   table, `qv validate`; measure on the eval set (incl. eval/known_errors.csv). Also give the web view a plain
   per-question summary (e.g. "Evidence: 540 ×2, 556 ×1, 558 ×2 — key 540"), clearer labels and a legend —
   Mojeeb found the current view hard to read.
3. **PDF library** — built 2026-11-16 (v1, see *Implementation invariants (library)*); German book translated for
   search (`translate_for_search`); Urdu OCR waits (the German book is probably a translation of it). Original plan: Ahmadiyya books as an authoritative local source in
   `data/library/` + a metadata file (title, author, language, edition, tier, frame authority). Page-by-page text
   (pypdf; OCR with Tesseract `urd` for scanned/Nastaliq Urdu), local full-text search (SQLite FTS5) and
   cross-language retrieval (Urdu books, English questions). Citations as book + page; quotes stay in the original
   language, translations are display only, never evidence. Books stay local; exports carry short excerpts only.
4. **Knowledge base** — the agreed plan is **`KNOWLEDGE_BASE_PLAN.md`** (2026-11-17, after two review rounds with
   ChatGPT): what exists, decisions + risks, and a 6-phase roadmap, each phase its own session and branch:
   1 unified FTS5 index over all stored documents + book pages (`data/kb/index.sqlite`, a rebuildable cache) + retrieval
   benchmark · 2 knowledge search page + saved topics · 3 stored pages first in research (+ web PDFs) · 4 embeddings /
   local-model experiments with a decision rule · 5 same fact, different result (duplicates) · 6 facts + question
   generation (leave-one-out validation). Read the plan's ground rules and "Explicitly not now" before starting a phase.
   **Phase 1 built 2026-11-17** (merged to main): `qv/kb/`, `qv kb …` commands, baseline benchmark — see
   the plan's phase-1 result note. **Phase 2 built 2026-11-17** (merged): Knowledge
   page, topics, relevance judgements — see the plan's phase-2 result note. **Phase 3 code built 2026-11-17**
   (merged): stored pages first + web PDFs; eval-set acceptance run 2026-11-17 → stored pages stay on (plan's
   phase-3 note). Known judge weakness from it: a key with several facts (place + size + year) is judged as one
   claim, so a wrong year can be "supported" (swab seeded #20) — fixed 2026-11-17 by key components (rules v2,
   see *Implementation invariants (key components)*).
5. **Order agreed 2026-11-17** (plan → *Agreed order from 2026-11-17*): first priority is validating the real
   editions (Swab Quest first) and using the export in the game — incl. a **validated export** with extra columns
   shown in the game's Questions tab and the Academy. Quota runs grouped (eval "before" with stored pages off, "after"
   with them on, then the editions); code meanwhile: validated export, phase 5, phase 4 code, phase 6 code with
   samples only — full question generation waits for Mojeeb.

Smaller open items: retry S3 when ≥ 1 quote is dropped (to reach < 2 %); web PDFs are read page by page since
KB phase 3; refused sites are now listed for Mojeeb on the Websites page (alislam.org itself answered 500 ×11 —
worth a look); no hadith direct source yet. Done 2026-11-16: `QV_CONTACT` is set (Wikipedia searches run); the
free Gemini limits were checked in AI Studio — 4 more models with 20/day each were added to the pools
(gemini-4-hydrogen, gemini-3-flash-preview, gemini-2.5-flash in `judge`; gemini-2.5-flash-lite in `cheap`), their
quality not measured yet; Pro / 4 Argon / 4 Carbon have no free quota.

## Decisions (Mojeeb, 2026-11-15) — replace ARCHITECTURE.md §7
- **Free services only, $0 budget.** No paid API usage, no card-required plans. Budgets are tracked as
  requests/day and credits/month per provider, not dollars; a provider with no free quota left is skipped,
  never billed. Existing subscriptions (Google AI Plus, Claude) only where they cost nothing extra.
- **LLM:** Gemini API free tier (Mojeeb's key, billing disabled). Model ids and limits are configuration —
  the free tier is small (≈20 requests/day for Flash, ≈500 for Flash-Lite, no Pro, Nov 2026), so cheap
  stages use Flash-Lite. Second independent verifier / small pilots: Claude Code itself (subscription),
  one fresh subagent per request so blind stages stay blind. No Anthropic/OpenAI API keys.
- **Search:** several free pools behind one interface with quota tracking, in order: Parallel's free hosted
  MCP (anonymous, own soft cap of 300/day), Tavily (1,000 credits/month), Exa ($10 credit/month). Brave needs a
  card → not used. Direct sources first (free). Wikipedia only when `QV_CONTACT` is set (Wikimedia requires a
  contact in the user agent; never Mojeeb's email unless he sets it).
- **Open points answered (2026-11-16)** — METHODOLOGY.md §13: frame confirmed (alislam.org incl. its library,
  alhakam.org, reviewofreligions.org; Qur'an = alislam.org/quran/app, Sher Ali, Bismillah = verse 1); hadith: a
  frame-authority book is enough when it gives no collection reference; reword AI-generated or ambiguous wording
  freely; 5 % spot check. Mojeeb has downloaded books from new.alislam.org/library for the PDF library (next).
- **alhakam.org** is searched through its sitemap (`SitemapSearch`, `providers.yaml search.sitemaps`, cache in
  `data/cache/sitemaps/`, refreshed weekly) because its own search page is built in the browser.
- **Ahmadiyya source: alislam.org.** Qur'an verses from `alislam.org/quran/app/<s>:<v>` (Arabic + Sher Ali
  English, Bismillah = verse 1, allowed by robots.txt and listed in its sitemap); site search via
  `alislam.org/?s=<query>`. Respect robots.txt (`/quran/view/`, `/quran/tafseer/`, `/library/browse/…` are
  disallowed).
- **First runs:** pilot = 5–10 Swab Quest questions inside the free daily limits; first full run = Swab Quest.

## Implementation invariants (phase 1)
- **CSV = the game's parser**, not Python's `csv` module: `qv/io/csv_format.py` re-implements
  `js/shared/csv.js` (line-based, JS `trim()`, no line breaks in fields). Parity is tested against the real JS
  via node (`tests/test_csv_format.py`, `tests/test_structural.py`). Change both together.
- **Structural errors ⊇ the game's checker errors** (`scripts/content.js → checkEdition`), tested via node.
  Difficulty values come from the profile (game: `easy|hard`; the PRD's `medium` is not valid in the game).
- **Imports are immutable**: SQLite triggers abort any UPDATE of `questions` or of a version's file bytes.
  Original bytes are stored in `dataset_versions.original_bytes` (not in `data/imports/` as ARCHITECTURE.md
  §3.1 said — one transactional store). Corrections only exist at export time.
- **Corrected export = patch the original bytes** (`apply_patches`): only approved fields change; `id` can never
  change; output is re-parsed and re-checked; new structural errors abort the export.
- Schema changes → new Alembic revision in `qv/db/migrations/versions/` (never edit an applied one);
  `tests/test_db.py` fails if models and migrations differ.
- `eval/seeded.*` are generated (`qv eval seed`); a test fails when they are stale after content edits.

## Implementation invariants (phase 2)
- **What each stage sees is enforced by the render functions** in `qv/pipeline/stages.py`; tests assert the key
  and note never appear in S1a/S3 prompts (`tests/test_stages.py`, `tests/test_research.py`). Keep it that way.
- **Prompts:** `qv/prompts/<stage>.v<N>.system.txt` must equal the design block in `prompts/*.md`
  (test). Changing a prompt = new version file + bump `PROMPT_VERSIONS`. Stage output models in
  `qv/domain/stages.py` must match the design JSON schemas (test).
- **Only grounded passages are stored** (`qv/pipeline/grounding.py`: exact substring after normalisation; no
  fuzzy matching). Documents and passages are immutable (triggers).
- **Never past a free quota:** every LLM/search call goes through `QuotaLedger` (5 % reserve) and the rate
  limiter; a provider's 429 marks it used up for the period. Model pools fall back to the next model.
  `QuotaExhausted` stops a run cleanly; `qv resume <run>` continues (stage outputs reused by input hash —
  the hash excludes the model so pools can switch models).
- **Tests never touch the network** (autouse respx guard in `tests/conftest.py`).

## Implementation invariants (phase 3)
- **S8 is pure code** (`qv/pipeline/rules.py`, `RULES_VERSION`): it recounts origin clusters and tiers from the
  passage ids the verifier cites, never trusting the model's own count; ids that were not shown are ignored.
  What counts as STRONG per claim type is `config/evidence_requirements.yaml`. Interpretations of the
  methodology are listed in the module docstring — change them there and in the tests together.
- **No VERIFIED without grounded support** and a matching blind answer (test). S4 sees mode-A passages only
  (note-claim passages could leak the answer); S6 sees no evidence (tests).
- System prompts with placeholders (S5, S6) are filled by `fill_template`; the filled values are part of the
  input hash. Passage ids P1… are numbered by `number_passages` (mode A first) and stored per validation
  (`passage_map_json`), so reasons and the web view use the same ids.
- A pool moves to its next model after a model's transient-error retries run out (free Flash models are often
  overloaded); failed attempts still count in the ledger.

## Implementation invariants (key components — rules v2, 2026-11-17)
- S1b v2 lists every checkable part of the key as K1, K2 … (answer + every detail written into it); S5 v2 gives each
  a status (`check_s5(..., s1b)` asks for a missing one). S8 (`rules.py`, `RULES_VERSION = "2"`): VERIFIED needs every
  part supported; a part contradicted with STRONG evidence → INCORRECT (row 2b), below the bar → review;
  `supported` + an `evidence_value` whose numbers differ (`values_differ`) → contradicted; a part whose value is not
  in the key text (`written_in`) is skipped. Older S1b outputs without components keep the v1 behaviour.
- `qv judge <run> --rules-only` (`services/judgement.rejudge_run`) applies the current rules to the stored S4/S5/S6
  outputs: no model call, no quota. `store_validation` updates the row in place — decisions point at
  `validations.id`, so never delete-and-insert a validation.
- Measured on a copy of the database (rules-only, 2026-11-17, eval runs 18 19 21 23 25 26): error recall
  90.7 → 93.0 %, false verifications 2 → 1 (swab seeded #20 now INCORRECT), false INCORRECT 0 %. Real editions:
  animal-safari #107 / #170 → INCORRECT (review), swab-quest #410 → UNVERIFIED (part "Lajna Imaillah" unsupported).
  The new prompts (S1b v2 / S5 v2) are not measured yet — that needs quota.

## Implementation invariants (simple workflow)
- **Status by content**: `qv/services/workflow.py` works on a dataset's latest version and matches validations and
  decisions to a question by `(ext_id, content_hash)` across all versions of the dataset — an unchanged question
  keeps its result in a new version; a changed one is "not checked" again (priority reason "changed since it was
  last checked"). One dataset = one question file (one game edition); eval-… datasets are hidden by default.
- **Decisions are append-only** (`decisions` table + triggers); the newest per question wins. Actions: keep, edit
  (`changes_json`, only question/answer/options/note), specialist, remove, later. Edits never touch the import;
  they are applied at export (`corrected_csv` patches + `drop_rows` for removed questions) or stored as a new
  version by "Check my edits again".
- **One batch at a time**: `qv next` holds `data/batch.lock.json` (pid); the web page starts `python -m qv.cli next
  … --yes` detached (`qv/services/worker.py`, log in `data/logs/`). A dead pid = stale lock. `qv next` first
  continues the newest unfinished validate run of the version, then plans a new one from the selection
  (category / subcategory / topic / difficulty / wording-risk level / ids; order file (default) | hard | easy |
  risk; edited questions always first); batch size = today's free judge requests / 2.2, at most
  `research.yaml batch_size`.
- **"Fact-heavy wording"** (`qv/pipeline/priority.py`, internally "priority") is pure code from the wording; it
  only orders work and must always be explained as *not* a prediction (Mojeeb found "priority" misleading).
  `SIGNALS` (shown on the page) must match the scoring (test).
- **Web page**: `st.navigation` with sections (Overview · Files · Check questions · Advanced; `SECTIONS` in
  `qv/ui/app.py`). The file being worked on is `st.session_state.dataset` (plain state, not a widget key, so it
  survives pages without the file bar); the "Working on" bar (`file_header`, pages in `WITH_FILE`) edits it
  through its own widget key. Every table goes through `data_table()` → our own read-only component
  `qv/ui/table.py` (Streamlit components v2, inline HTML/JS, values set with `textContent` only): sort by a header
  click and an optional search box, both **in the browser only**; rows are reported by their position in the data
  (never the screen position), with a click id (every click is new) and the viewer's visible order. Details open in
  a popup via `on_open` → an `@st.dialog(..., on_dismiss="rerun")`; only one dialog per script run. Popups over a
  list use `popup_nav` (Previous / Next in the viewer's order) and change their view with `st.rerun(scope=
  "fragment")`; a widget key changed by a move goes through a `*_next` state key (set before the widget exists).
  **Help rule**: each page has `page_title(title, key, intro)` → a Help button opening `qv/ui/help_text.py`
  `HELP[key]` (sections → tabs, each scrolling in a medium popup); on the page only a one-line intro, state messages and short captions; field explanations are `help=`
  tooltips; expanders only for data (logs, format problems), never for explanations. Layout CSS (in `CSS`): the
  collapsed sidebar is kept as a 56 px icon strip (page names as hover tooltips from the nav link's `label`
  attribute; « / » inside the menu), the "Working on" bar is `position: fixed` in the app header (right).
  Book library = tabs Search (first) · Books · Found on the web.
  "Ready" = `workflow.READY_STATUSES` (verified automatically + confirmed by you + edited by you); the export kind is
  `ready` (old name `verified` still accepted).
- The web page now writes (imports, decisions, new versions, starting batches) — through services only; it never
  calls a model itself. Streamlit keeps imported modules loaded: restart `qv ui` after changing `qv/services`.

## Implementation invariants (Prepare, 2026-11-17)
- **Prepare page** (`qv/services/prepare.py`, page `prepare` in Check questions): wording flags + the quality check
  (S6) alone, before any research. Flags are pure code (`qv/pipeline/wording.py`, `FLAGS` shown in Help; thresholds
  `prepare_long_*` in research.yaml) — hints, never verdicts, never change anything.
- **S6 cache is shared**: `s6_hash_inputs` (pipeline/judgement.py) + `StageRunner.hash_for` / `stored` — the Prepare
  check (stage output with `run_id` NULL) is reused by `judge_question` for the same wording (test). Keep both on
  `s6_hash_inputs`; never add run-specific values to it.
- **Prepare decisions** `reword` / `wording_ok` (`workflow.PREPARE_ACTIONS`) live in `decisions` but are read apart
  (`QuestionState.prepare*`): they never change the review status, so a reworded question is never "ready".
  `apply_edits_as_new_version(prepared=True)` turns pending rewords into a new version (review edits stay as they are).
- `qv prepare <file>` and the page's button (`worker.start_background(..., command="prepare")`, log
  `data/logs/prepare-*.log`) take the same lock as batches.

## Implementation invariants (import fixes, daily run)
- **Import fixes** (`qv/services/import_fixes.py`) only make changes whose result is certain, never touch `id`,
  skip rows with comma/quote problems, and row changes go through `apply_patches` (verified read-back). The page
  lists every change before applying and offers the fixed file for download.
- **Daily run** (`qv/services/daily.py`): a macOS LaunchAgent `com.triventurex.question-validator.daily` runs
  `qv auto run` at the chosen time; settings in `data/auto.json`, log `data/logs/daily.log`. `qv auto run` calls
  `qv next <file> --yes` per chosen file while `suggested_batch_size` > 0 and no batch is running. Only the person
  turns it on (page or `qv auto on`).

## Implementation invariants (library)
- `qv/library.py`: books in `config/library.yaml`, PDFs in `data/library/` (git-ignored; never shared), page text
  (pypdf, cleaned: repeated runs collapsed, line-end hyphens joined) in `data/library/index.sqlite` (FTS5, a
  rebuildable cache, outside the Alembic database). A book whose text quality is < 0.85 is `needs_ocr` and not
  searchable (Mojeeb's Urdu *Deeni Maloomat* — its fonts extract as garbage).
- Research (`_library_pages`): for editions listed on a book, the best `library_pages_per_question` pages for the
  core + 2 blind queries become documents `library://<book>/p<pdf page>` (source_kind `library`, title = book,
  printed page, PDF page) read by S3 in mode A. Tier = the book's tier and is **not** lowered by S3's page kind
  (the person chose the book); frame authority = the book's `publisher` is in the frame's authorities.
- **Translations are search-only** (`qv library translate`, `qv/services/translate.py`, prompt `translate.v1` in
  code): stored per page in the index's `translations` table keyed by the original text's hash (kept across
  re-indexing, redone when the page text changes) and indexed as extra FTS rows (`kind` = language). Search returns
  the original page; S3 quotes the original — a translation never becomes evidence (METHODOLOGY principle 5).
- `pdfs_found_on_web` (views) lists web PDFs that research skipped (`fetches.status = not_text`, pdf) as
  candidate books (Advanced → Book library, `qv library suggestions`).
- **Books added on the page** (`qv/services/books.py`): the person's own list `data/library/books.yaml`
  (`books`, `removed` = config book ids hidden, `dismissed` = web PDF urls hidden), merged by `load_books`;
  `config/library.yaml` is never written. Removing a book deletes its PDF and index rows; stored documents /
  passages that cite it stay (immutable history). Download only on the person's click, PDF magic checked, 80 MB max.

## Implementation invariants (local models)
- **Pools are cross-provider**: `llm.pools` entries are `provider/model` (split on the first `/`; Ollama model
  names contain `:`). Local entries have no quota limits but still go through the rate limiter and call log.
  `ProviderUnavailable` (Ollama down, model not pulled) moves to the next entry without marking anything used up.
- **Ollama prompts must fit `num_ctx`**: Ollama silently cuts a longer prompt, so a prompt that fills the window
  is an error, never a result. `think` is off by default (qwen3).
- **Grounding strips only our `<document>` delimiters at a quote's edges** (local models copy them); nothing else
  in a quote is changed.

## Implementation invariants (websites)
- `qv/services/websites.py`: the person's marks per domain (`source_marks`, append-only + triggers, newest wins,
  `clear` = back to sources.yaml) are applied by `registry_with_marks` — research always builds its registry with
  it. `use` = tier P/S/T, `dont_use` = X, `needs_access` = `Registry.skip_domains` (dropped before fetching like X,
  tier unchanged). Subdomains inherit. A mark never touches `config/sources.yaml`.
- Refused list = `fetches` failures grouped by domain (web PDFs excluded — they are book candidates); note that
  failures older than `FAILURE_RETRY_AFTER` are deleted when retried, so the list shows recent problems.
  "Possibly good" = web domains with grounded quotes that sources.yaml does not list and the person has not marked.

## Implementation invariants (knowledge index — KB phase 1, 2026-11-17)
- `qv/kb/`: `text.py` (normalize_url, chunk_text + `CHUNKER_VERSION`, guess_language — pure), `index.py`
  (`<data_dir>/kb/index.sqlite`: kb_docs / kb_chunks / kb_fts / meta), `search.py` (BM25, filters, one result per
  `canon_key`), `benchmark.py` (labels from stored research, metrics, decision rule `compare`).
- The index is a **cache**: derived only from `validation.db` + the library index; no Alembic; `SCHEMA_VERSION`
  change → dropped and rebuilt. Anything a person decides or that cost model requests belongs in Alembic instead.
- Doc keys: `doc:<documents.id>`, `book:<book>/p<page>`. A `library://` document is indexed once, as its book page
  (alias in `meta.aliases`). Chunk offsets always reproduce the stored text (test); never alter text when chunking.
- `canon_key` = union of "same normalised URL" (versions) and "same content hash" (copies); search returns one hit per
  canon key, the benchmark judges canon keys. Older versions: `is_current = 0`, hidden by default, never deleted.
- Metadata (tier from `registry_with_marks`, language, current, canon, editions / categories / question count) is
  recomputed on every update; only new / changed texts or a new `CHUNKER_VERSION` are re-chunked.
- Translations of book pages are extra FTS rows with `chunk_id NULL`: they find the page, the hit shows the original.
- The CLI updates the index after every batch (`_print_run_report` → `update_quietly`, never raises) and after
  `qv library index`. Commands: `qv kb index | rebuild | status | search | benchmark`.
- Benchmark labels: relevant = read, `about_right_subject`, ≥ 1 passage with `target = 'need'`; not relevant =
  off-topic, or read without any passage. Questions keyed `<edition>#<id>@<hash8>`; queries = S1a only.

## Implementation invariants (knowledge search page — KB phase 2, 2026-11-17)
- Advanced → Knowledge (`page_knowledge`); all logic in `qv/services/knowledge.py`. The popup's text comes from where
  it is stored (`documents.text`, library page), never from the index; chunk offsets mark the passages. Stored text,
  titles and URLs are untrusted: HTML only via `marked_html` (escapes everything), Markdown via `md_escape`, links
  only through `safe_link` (plain http/https). Table cells mark words with `data_table(marks=…)` (text nodes only).
- `topics` (Alembic 0006) are **mutable** (rename / change / delete) — a later `topic_links` table points at
  `topics.id` and must not require changing `topics`. Filters are stored as `filters_to_dict(SearchFilters)`.
- `relevance_labels` are **append-only** (triggers); newest per (dataset, ext_id, content_hash, doc_key) wins;
  `clear` takes one back. They belong to a question's exact wording. `qv kb benchmark` always passes
  `knowledge.benchmark_labels(db)` as `extra_labels` (key `<profile>#<id>@<hash8>`, profile of the version holding
  that wording). Judgements never change a result.

## Implementation invariants (stored pages first + web PDFs — KB phase 3, 2026-11-17)
- **Stored pages** (`research._stored_pages`): before the web, the knowledge index is searched with **S1a's blind
  queries only** (`stored_queries`; never S1b, key, note or options), each query BM25 then RRF (k = 60); up to
  `stored_pages_per_question` (research.yaml, default 2) documents are added in **mode A**, on top of the web budget,
  and S3 reads them blind like any document. **Documents only**: never another question's passages or asserted
  answers (test proves the S3 prompt has none). `found_by = {via: "stored", query, doc_key, rank}`; a `book:` hit
  becomes the same `library://` document the library path makes (`_store_book_page`), a `doc:` hit reuses its
  `documents.id`. Skipped: anything this question already read (any run, by canon key), tier X and "needs special
  access" sites, books not listed for the edition, a second page from the same site / book (echo defence), and — for
  time-sensitive questions (`is_time_sensitive`: S1a flag, or claim type / presupposition `statistic_current` /
  `sports_record`) — pages fetched more than `stored_max_age_days` ago or without a date (book pages).
- The index is opened **read-only** (`KnowledgeIndex.open_readonly`); research never creates or rebuilds it. A
  missing / broken index or a search error is logged in the stats (`stored_index_unavailable`, `stored_errors`,
  `errors`) and research goes on — never fails.
- Web searches still run. `stored_first_skip_web` (off by default; keep it off until the eval set says otherwise)
  skips the **paid-pool** web queries when ≥ `stored_skip_web_min` stored pages qualify; free searches (Wikipedia,
  alislam.org, sitemaps) and the library still run. Stats per question: `stored_pages`, `stored_searches`,
  `searches_total`; `search_summary(db, run)` → the "searches per question" line after a batch.
- **Web PDFs** (`Fetcher._store_pdf`): fetched like pages (robots.txt, rate limit, `fetch.max_pdf_bytes`), read with
  the library reader (`read_pdf_pages` takes bytes too, `clean_page`, `text_quality` ≥ `pdf_min_quality`); one
  document per readable page: `source_kind = pdf`, `url` = the PDF, `final_url` = `<pdf url>#page=N`, trust = the
  **site's** registry tier (lowered by S3's page kind like any web page). No readable page → fetch status
  `needs_ocr`, no text stored. `FetchResult.page_ids` lists the pages (also from the cache); research reads the
  `pdf_pages_per_document` pages that best match the queries that found the PDF (`found_by[].pdf_page`).
  `normalize_url` keeps a `#page=N` fragment so PDF pages are separate documents in the index, not versions.
- `views.pdfs_found_on_web` lists every web PDF met (read / needs OCR / not read, column `read`) — still the Book
  library's "Found on the web" candidates. Websites' refused list skips PDF statuses; "possibly good" counts `pdf`
  pages with `web` pages.
- `qv kb benchmark` adds `stored_pages` (hit / recall in the top `stored_pages_per_question` of bm25-queries-rrf —
  an upper bound of what research picks). Tests: `tests/test_stored_pages.py`.

## Implementation invariants (check columns in game exports, 2026-11-17)
- `corrected` and `ready` exports run `check_export.add_check_columns` last: `CHECK_COLUMNS` (qv/domain/question.py)
  are added at the end of the header if missing and filled for ready questions only (`checked` = verified /
  confirmed / edited), emptied for every other row (`csv_format.set_columns`, verified read-back like
  `apply_patches`). Built in code from the validation (key's `passages_for` → passages, best tier first, ≤ 3 sources,
  quote ≤ 240 chars on one line); an **edited** question gets no sources / quote (they supported the old answer).
- `content_hash` ignores the check columns, and the structural check does not report them as unknown — re-importing an
  exported file keeps results. `check_hash` (10 hex of sha256 over question, type, answer, opt_a–d, note joined with
  `\n`) must equal `checkHash` in scripts/content.js (`tests/test_check_export.py` runs node to compare).
- `apply_edits_as_new_version` uses `corrected_csv`, not the game export — stored versions never get check columns from us.

## Coding standards (Python)
- Python 3.12+, own `pyproject.toml`; type hints on all signatures, docstrings on classes and functions,
  PEP 8, unit tests for new modules (`pytest`).
- CSV: read and write only through `qv/io/csv_format.py` (every field a string); keep the original
  file bytes; never renumber ids; never write into `../game_editions/`.
- Secrets only in `.env` (git-ignored); commit `.env.example`. `data/` is git-ignored.
- No real API calls in tests — use recorded fixtures. Any run that spends API money needs Mojeeb's OK first.
- Never let a model introduce a URL, title or quote: sources come from our fetch log, quotes must pass the
  grounding check (METHODOLOGY.md §1, principle 5).
