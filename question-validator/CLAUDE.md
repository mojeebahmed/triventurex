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
Phase 1 done (2026-11-15): foundation, DB, CSV import/export, structural checks, eval set. Next: Phase 2
(evidence layer), ARCHITECTURE.md §6. Open decisions: ARCHITECTURE.md §7 and METHODOLOGY.md §13.
Run `.venv/bin/python -m pytest` before merging (see README for setup).

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

## Coding standards (Python)
- Python 3.12+, own `pyproject.toml`; type hints on all signatures, docstrings on classes and functions,
  PEP 8, unit tests for new modules (`pytest`).
- CSV: read and write only through `qv/io/csv_format.py` (every field a string); keep the original
  file bytes; never renumber ids; never write into `../game_editions/`.
- Secrets only in `.env` (git-ignored); commit `.env.example`. `data/` is git-ignored.
- No real API calls in tests — use recorded fixtures. Any run that spends API money needs Mojeeb's OK first.
- Never let a model introduce a URL, title or quote: sources come from our fetch log, quotes must pass the
  grounding check (METHODOLOGY.md §1, principle 5).
