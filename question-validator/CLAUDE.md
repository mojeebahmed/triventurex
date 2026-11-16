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
(menu since 2026-11-16 evening: Import · Validate · Daily run · Review · Export, + Advanced pages). Commands: `qv status`, `qv next`,
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
4. **Reuse of stored research** — plan agreed to keep (2026-11-16; 290 stored pages ≈ 3 M chars, 596 quotes for 67
   questions at that time). Build in this order:
   - **A. Stored pages first**: a full-text index (FTS5, like the library) over every stored document; per question
     search it with the same answer-blind queries as the web (S1a core + blind queries) and send the best stored
     pages to S3 in mode A next to the web results (found_by `via: stored`). Saves search requests and fetches,
     grows with every batch. Show "found in stored pages" as a source on the page.
   - **B. Same question, same judgement**: find identical / near-identical questions within and across editions;
     flag differing claim types or verdicts (e.g. #127 vs #285) in a new Review group.
   - **C. Suggestions from stored passages** (later): notes and new questions from stored quotes — each suggestion
     carries its source quote, goes through the same validation + duplicate check + Mojeeb's approval, exported as
     new rows with new ids, never written into `game_editions/`.


Smaller open items: retry S3 when ≥ 1 quote is dropped (to reach < 2 %); PDF pages from the web are skipped
(`not_text`); refused sites are now listed for Mojeeb on the Websites page (alislam.org itself answered 500 ×11 —
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

## Coding standards (Python)
- Python 3.12+, own `pyproject.toml`; type hints on all signatures, docstrings on classes and functions,
  PEP 8, unit tests for new modules (`pytest`).
- CSV: read and write only through `qv/io/csv_format.py` (every field a string); keep the original
  file bytes; never renumber ids; never write into `../game_editions/`.
- Secrets only in `.env` (git-ignored); commit `.env.example`. `data/` is git-ignored.
- No real API calls in tests — use recorded fixtures. Any run that spends API money needs Mojeeb's OK first.
- Never let a model introduce a URL, title or quote: sources come from our fetch log, quotes must pass the
  grounding check (METHODOLOGY.md §1, principle 5).
