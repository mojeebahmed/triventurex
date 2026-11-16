# Question Validator

An AI-assisted tool that checks Triventurex quiz questions (and any CSV in the same format) for
factual accuracy and quality, with traceable evidence for every conclusion.

**Status:** phases 1–3 implemented — import/structural checks, the evidence layer (answer-blind question
analysis, free web search, page fetching, Qur'an verses from alislam.org, verbatim passages checked against the
stored pages) and judgement (blind answer, verification, quality, rule-based verdict). Free services only.

**New here? Start with [`USER_GUIDE.md`](USER_GUIDE.md)** — the four-step workflow (import, validate, review,
export).

- [`SPECIFICATION.md`](SPECIFICATION.md) — the original PRD and technical specification (unchanged copy).
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — review of the specification, the revised architecture, database
  design, processing workflow, API strategy and phased plan.
- [`METHODOLOGY.md`](METHODOLOGY.md) — the factual validation method: claims, evidence requirements,
  source tiers and origins, how disagreements are classified, verdict rules, worked examples from the editions.
- [`DATABASE.md`](DATABASE.md) — what is stored in `data/validation.db` and how to look inside (web view,
  `qv` commands, DB Browser for SQLite, example queries).
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
.venv/bin/qv quota                                     # free quota left (Gemini, Parallel, Tavily, Exa; local models)
.venv/bin/qv research swab-quest --ids 1,5,10-12       # evidence for some questions (asks first)
.venv/bin/qv validate swab-quest --ids 1,5             # research + verdict (blind answer, verification, quality)
.venv/bin/qv judge 3                                   # verdicts for an existing research run (stored outputs reused)
.venv/bin/qv verdicts 3 | verdict 3 12                 # all verdicts of a run · why one question got its verdict
.venv/bin/qv resume 3                                  # continue a run stopped by a free limit
.venv/bin/qv runs | metrics 3 | evidence 3 12 | usage  # inspect runs, one question's evidence, API use
.venv/bin/qv ui                                        # read-only web view → http://localhost:8501
.venv/bin/qv eval check | seed | sample out.csv        # evaluation set tools
.venv/bin/qv eval import                              # eval set as datasets + the validate commands to run
.venv/bin/qv eval score 5 6 7                          # verdicts of runs vs the labels (Phase 3 exit metrics)
.venv/bin/python -m pytest                             # tests (~3 s; parity tests need node)
```

### Local models (optional, $0)

Stages can run on a local model through [Ollama](https://ollama.com) instead of (or before) Gemini. Models,
their `num_ctx` and the pools are in `config/providers.yaml`: a pool entry is `provider/model`, e.g.
`ollama/qwen3:14b`. A pool tries its entries in order; when Ollama is not running or a model is not pulled,
the next entry (e.g. Gemini) takes over. Point a stage at a pool under `stage_pools`.

## Layout

```
qv/domain/      typed models (Pydantic): Question, CsvRow, StructuralIssue, DatasetDiff …
qv/io/          game-compatible CSV parser + byte-faithful patch writer
qv/pipeline/    structural.py (S0), stages.py (S1a/S1b/S3 prompts + checks), grounding.py,
                judgement.py (S4/S5/S6 prompts + checks), evidence.py (passage ids, origin clusters),
                rules.py (S8: evidence requirements → claim statuses → verdict → review route; pure)
qv/providers/   llm/ (Gemini, Ollama + model pools), search/ (Parallel MCP, Tavily, Exa, Wikipedia, alislam),
                fetch.py, quran.py, usage.py (free-quota ledger, rate limits, call log)
qv/prompts/     versioned system prompts (copied from prompts/*.md)
qv/ui/          Streamlit read-only view (thin; queries in qv/services/views.py)
qv/db/          SQLAlchemy models, sessions (SQLite WAL), Alembic migrations (applied automatically)
qv/services/    application logic used by CLI/UI: datasets, exports, research (pipeline), judgement, views
qv/evaluation.py  eval cases, seeded errors, stratified sampling
qv/cli.py       `qv` command (thin)
config/profiles/  per-edition profile: audience, frame, conventions, structural rules
config/providers.yaml  free-tier limits, local models, model pools, search order · research.yaml depth · sources.yaml tiers
config/evidence_requirements.yaml  what counts as STRONG support per kind of fact (METHODOLOGY §4)
eval/           cases.yaml, known_errors.csv, seeded.csv + seeded_labels.yaml
tests/          pytest
```
