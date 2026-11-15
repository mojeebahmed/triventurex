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
Design only. Next: Phase 1 (foundation + evaluation set), ARCHITECTURE.md §6. Open decisions: ARCHITECTURE.md §7
and METHODOLOGY.md §13.

## Coding standards (Python)
- Python 3.12+, own `pyproject.toml`; type hints on all signatures, docstrings on classes and functions,
  PEP 8, unit tests for new modules (`pytest`).
- CSV: read every field as a string (`dtype=str, keep_default_na=False` or the `csv` module); keep the original
  file bytes; never renumber ids; never write into `../game_editions/`.
- Secrets only in `.env` (git-ignored); commit `.env.example`. `data/` is git-ignored.
- No real API calls in tests — use recorded fixtures. Any run that spends API money needs Mojeeb's OK first.
- Never let a model introduce a URL, title or quote: sources come from our fetch log, quotes must pass the
  grounding check (METHODOLOGY.md §1, principle 5).
