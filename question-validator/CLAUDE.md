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
- `SPECIFICATION.md` — the original PRD (unchanged copy; don't edit).

## Status
Phase 1 done (2026-11-15): foundation, DB, CSV import/export, structural checks, eval set.
Phase 2 done (2026-11-15): evidence layer — S1a/S1b/S3, search, fetch, Qur'an source, grounding, quotas, read-only
web view (`qv ui`). Next: Phase 3 (judgement: S4 blind answer, S5 verification, S6 quality, S8 rules).
Open points: METHODOLOGY.md §13.
Run `.venv/bin/python -m pytest` before merging (see README for setup).

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

## Coding standards (Python)
- Python 3.12+, own `pyproject.toml`; type hints on all signatures, docstrings on classes and functions,
  PEP 8, unit tests for new modules (`pytest`).
- CSV: read and write only through `qv/io/csv_format.py` (every field a string); keep the original
  file bytes; never renumber ids; never write into `../game_editions/`.
- Secrets only in `.env` (git-ignored); commit `.env.example`. `data/` is git-ignored.
- No real API calls in tests — use recorded fixtures. Any run that spends API money needs Mojeeb's OK first.
- Never let a model introduce a URL, title or quote: sources come from our fetch log, quotes must pass the
  grounding check (METHODOLOGY.md §1, principle 5).
