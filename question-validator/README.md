# Question Validator

An AI-assisted tool that checks Triventurex quiz questions (and any CSV in the same format) for
factual accuracy and quality, with traceable evidence for every conclusion.

**Status:** phase 1 implemented (foundation, database, CSV import/export, structural checks,
evaluation set). No AI or network calls yet — research and verification come in phases 2–3.

- [`SPECIFICATION.md`](SPECIFICATION.md) — the original PRD and technical specification (unchanged copy).
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — review of the specification, the revised architecture, database
  design, processing workflow, API strategy and phased plan.
- [`METHODOLOGY.md`](METHODOLOGY.md) — the factual validation method: claims, evidence requirements,
  source tiers and origins, how disagreements are classified, verdict rules, worked examples from the editions.
- [`prompts/`](prompts/) — the prompt and JSON output schema for every model stage, each with a dataset example.
- [`CLAUDE.md`](CLAUDE.md) — working notes for Claude Code sessions in this folder.

## Relationship to the game

- Reads the same CSV format as `game_editions/<id>/questions.csv`
  (`id,question,type,answer,opt_a..opt_d,difficulty,category,subcategory,topic,note`).
- **Never writes into `game_editions/`.** It exports a corrected CSV containing only changes a human
  approved; you copy it in and run `npm run build:content` as usual.
- It is a separate Python program. The game stays vanilla HTML/CSS/JS + Node, and `server.js` does
  not serve this folder (it is not in `PUBLIC_DIRS`).

## Setup and use

Python 3.12+. From this folder:

```bash
uv venv --python 3.12 && uv pip install -e '.[dev]'
cp .env.example .env            # optional; data goes to ./data by default
```

```bash
.venv/bin/qv check ../game_editions/world-tour/questions.csv --profile world-tour   # no database
.venv/bin/qv import ../game_editions/world-tour/questions.csv --dataset world-tour  # new immutable version
.venv/bin/qv datasets                                  # datasets and versions
.venv/bin/qv issues world-tour --severity warning      # stored structural findings
.venv/bin/qv diff football-quest 1 2                   # what changed between versions (by id)
.venv/bin/qv export original world-tour                 # byte-identical copy of the import
.venv/bin/qv export report world-tour                   # structural report CSV
.venv/bin/qv export corrected world-tour --changes approved.json   # {"<id>": {"<column>": "<value>"}}
.venv/bin/qv eval check | seed | sample out.csv        # evaluation set tools
.venv/bin/python -m pytest                             # tests (~3 s; parity tests need node)
```

## Layout

```
qv/domain/      typed models (Pydantic): Question, CsvRow, StructuralIssue, DatasetDiff …
qv/io/          game-compatible CSV parser + byte-faithful patch writer
qv/pipeline/    stages; structural.py = S0 (no AI)
qv/db/          SQLAlchemy models, sessions (SQLite WAL), Alembic migrations (applied automatically)
qv/services/    application logic used by CLI/UI: datasets (import, versions, diff), exports
qv/evaluation.py  eval cases, seeded errors, stratified sampling
qv/cli.py       `qv` command (thin)
config/profiles/  per-edition profile: audience, frame, conventions, structural rules
eval/           cases.yaml, known_errors.csv, seeded.csv + seeded_labels.yaml
tests/          pytest
```
