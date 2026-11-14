# Question Validator

An AI-assisted tool that checks Triventurex quiz questions (and any CSV in the same format) for
factual accuracy and quality, with traceable evidence for every conclusion.

**Status:** design only — no code yet.

- [`SPECIFICATION.md`](SPECIFICATION.md) — the original PRD and technical specification (unchanged copy).
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — review of the specification, the revised architecture, database
  design, processing workflow, API strategy and phased plan.
- [`METHODOLOGY.md`](METHODOLOGY.md) — the factual validation method: claims, evidence requirements,
  source tiers and origins, how disagreements are classified, verdict rules, worked examples from the editions.
- [`prompts/`](prompts/) — the prompt and JSON output schema for every model stage, each with a dataset example.

## Relationship to the game

- Reads the same CSV format as `game_editions/<id>/questions.csv`
  (`id,question,type,answer,opt_a..opt_d,difficulty,category,subcategory,topic,note`).
- **Never writes into `game_editions/`.** It exports a corrected CSV containing only changes a human
  approved; you copy it in and run `npm run build:content` as usual.
- It is a separate Python program. The game stays vanilla HTML/CSS/JS + Node, and `server.js` does
  not serve this folder (it is not in `PUBLIC_DIRS`).
