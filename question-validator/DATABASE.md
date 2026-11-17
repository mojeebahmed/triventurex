# The database — what is stored and how to look at it

Everything the validator imports, searches, fetches and decides is kept in one SQLite file:

```
question-validator/data/validation.db      (+ validation.db-wal / -shm while it is open)
```

`data/` is git-ignored: the database lives only on this Mac. Copy the file to back it up (close `qv ui` first,
or copy all three files together). Deleting it starts from zero; the next `qv` command creates an empty one.

## Four ways to look inside

| Way | Best for | How |
|---|---|---|
| **Web page** | progress, review, the detailed views under *Advanced* | `Start Question Validator.command` or `.venv/bin/qv ui` → http://localhost:8501 |
| **`qv` commands** | quick answers in the terminal | see the table below |
| **DB Browser for SQLite** (free app, sqlitebrowser.org) | clicking through tables, filtering, searching | open `data/validation.db`; use *Browse Data* and *Execute SQL*. Open it **read-only** (File → Open Database Read Only) so nothing is changed by accident |
| **`sqlite3`** (built into macOS) | your own queries | `sqlite3 -header -column data/validation.db "select …"` |

The database protects itself: imported questions, stored pages and passages cannot be changed (triggers refuse
it). Still, change nothing by hand — use `qv` for everything that writes.

### `qv` commands that read the database

| Command | Shows |
|---|---|
| `qv datasets` | imported files and their versions, with structural error / warning counts |
| `qv issues swab-quest` | structural problems found on import |
| `qv status` | every file: verified, to look at, still to check — and what to do next |
| `qv runs` | every research / validate run: dataset, status, how many questions |
| `qv verdicts 3` | one line per question of run 3: verdict, evidence strength, next step |
| `qv verdict 3 127` | why question #127 got its verdict: claims, blind answer, quality, every rule that fired |
| `qv evidence 3 127` | what research found for #127: claims, search queries, pages (tier, publisher), the exact quotes |
| `qv metrics 3` | totals for a run: quotes dropped, questions with evidence, pages per tier |
| `qv usage` | calls, tokens and errors per provider and model |
| `qv quota` | free quota left today / this month |
| `qv eval score 5` | how a run on an eval dataset compares with the expected verdicts |
| `qv kb status` / `qv kb search "first Jalsa Salana"` | the knowledge index: what it holds; search every stored page and book page |
| `qv kb benchmark` | how well that search finds the pages research found useful (saved in `data/kb/benchmarks/`) |

## The tables in plain words

How the pieces connect, from a CSV to a verdict:

```
datasets ─ dataset_versions ─ questions ─┐          (what was imported)
                                         │
runs ─ run_questions ────────────────────┤          (what we worked on, and how far each question got)
                                         │
search_queries ─▶ fetches ─▶ documents ──┤          (what we searched and the pages we saved)
                                         │
question_documents ─ passages ───────────┤          (which pages belong to which question, and the quotes)
                                         │
stage_outputs ─▶ validations ────────────┤          (each model's answer, and the final verdict)
                                         │
decisions ───────────────────────────────┘          (what you decided in the Review and Prepare steps)
api_calls, quota_usage                              (every call made, and the free quota used)
```

| Table | One row is … | Useful columns |
|---|---|---|
| `datasets` | a named question set (e.g. `swab-quest`) | `name`, `profile` |
| `dataset_versions` | one imported file; never changes | `version_no`, `source_filename`, `row_count`, `error_count`, `original_bytes` (the exact file) |
| `questions` | one CSV row of one version | `ext_id` (the CSV id), `question`, `type`, `answer`, `opt_a…opt_d`, `note`, `resolved_answer_text` (the answer as text) |
| `structural_issues` | a problem found on import | `ext_id`, `severity`, `code`, `message` |
| `runs` | one `qv research` / `qv validate` run | `kind` (research / validate), `status`, `stop_reason`, `config_json` |
| `run_questions` | one question in one run | `status` (pending / done / failed), `step`, `error`, `stats_json` |
| `search_queries` | one search we sent, with its results (kept for reuse) | `provider`, `query`, `results_json` (url, title, snippet), `expires_at` |
| `fetches` | one attempt to download a page | `url`, `status` (ok · error · not_text · empty · robots_disallowed · too_large · needs_ocr (a PDF without readable text)), `http_status`, `error` (for a web PDF read page by page: "pdf: 12 of 14 pages stored, 2 need OCR") |
| `documents` | one saved page — **its full text** | `url`, `final_url`, `domain`, `title`, `source_kind` (web · wikipedia · quran · library (a book page) · pdf (one page of a web PDF: `final_url` = `<pdf url>#page=N`, `url` = the PDF)), `text`, `char_len`, `fetched_at` |
| `question_documents` | a page used for one question in one run, with its rating | `effective_tier` (P primary · S secondary · T tertiary · X excluded), `publisher`, `page_kind`, `frame_authority`, `status`, `grounded_count`, `dropped_count` |
| `passages` | one exact quote from a page | `quote`, `mode` (A = about the question, B = about the note), `target`, `asserted_answer`, `matches_option`, `stance`, `char_start`/`char_end` (where in the page) |
| `stage_outputs` | one model answer (S1a, S1b, S3, S4, S5, S6) | `stage`, `model`, `output_json`, `valid`, `checks_json`, `input_hash` (same input → reused, no new call) |
| `validations` | the verdict for one question in one run (`qv judge <run> --rules-only` recomputes it from the stored answers, in place) | `verdict`, `evidence_strength`, `review_status`, `claim_statuses_json` (K = the whole answer, K1, K2 … = its parts, PR… = premises), `blind_answer`, `blind_matches_key`, `reasons_json`, `suggested_answer`, `passage_map_json` (P1, P2 … → passage), `rules_version` |
| `source_marks` | your mark on a website (use with a trust P/S/T / don't use / needs special access / clear) — never changed, the newest per site counts; applied on top of `config/sources.yaml` | `domain`, `action`, `tier`, `note`, `created_at` |
| `decisions` | your decision about one question (keep / edit / specialist / remove / later; on the Prepare page reword / wording_ok, counted apart from the review decision) — never changed, the newest counts | `ext_id`, `action`, `changes_json` (your edit), `comment`, `content_hash` (the wording it was made for), `created_at` |
| `topics` | a saved search on the Knowledge page: a name, the search words and the filters — can be renamed and changed | `name` (unique), `query`, `filters_json` (`source_kinds`, `languages`, `tiers`, `edition`, `category`, `include_older`), `created_at`, `updated_at` |
| `relevance_labels` | your judgement that a stored page / book page is relevant or not for a question — never changed, the newest per question + page counts (`clear` takes it back); used by `qv kb benchmark` | `dataset_id`, `ext_id`, `content_hash` (the wording it was made for), `doc_key` (`doc:<documents.id>` or `book:<book>/p<page>`), `label` (relevant · not_relevant · clear), `who`, `created_at` |
| `api_calls` | every call to a model, search engine or website | `provider`, `model`, `stage`, `status` (ok / error / quota), `input_tokens`, `output_tokens`, `latency_ms`, `error` |
| `quota_usage` | free quota used per provider and day / month | `used`, `exhausted` |
| `alembic_version` | the database schema version (internal) | — |

Words used in the tables: **tier** and **origin** are explained in [METHODOLOGY.md](METHODOLOGY.md) §5–6,
**verdict** and **review status** in §9, the stages S1a…S8 in §3. The web view's legend explains them too.

## Example queries

Copy one line into the terminal from the `question-validator` folder (or into DB Browser's *Execute SQL* — then
only the part between the quotes).

```bash
# Runs: dataset, kind, status, number of questions
sqlite3 -header -column data/validation.db "select r.id, d.name dataset, r.kind, r.status, count(rq.id) questions from runs r join dataset_versions v on v.id = r.dataset_version_id join datasets d on d.id = v.dataset_id left join run_questions rq on rq.run_id = r.id group by r.id"
```

```bash
# Verdicts of run 3
sqlite3 -header -column data/validation.db "select q.ext_id id, v.verdict, v.evidence_strength strength, v.review_status next_step from validations v join questions q on q.id = v.question_id where v.run_id = 3 order by cast(q.ext_id as int)"
```

```bash
# What we searched for (newest first)
sqlite3 -header -column data/validation.db "select provider, query, json_array_length(results_json) results, fetched_at from search_queries order by id desc limit 20"
```

```bash
# The quotes found for question #127 in run 3, with the website
sqlite3 -header -column data/validation.db "select p.mode, d.domain, substr(p.quote, 1, 100) quote from passages p join documents d on d.id = p.document_id join questions q on q.id = p.question_id where p.run_id = 3 and q.ext_id = '127'"
```

```bash
# Search our own saved pages for a word (simplest way; `qv kb search` ranks results)
sqlite3 -header -column data/validation.db "select id, domain, substr(title, 1, 60) title from documents where text like '%Maryam%'"
```

```bash
# Read one saved page in full (document 12)
sqlite3 data/validation.db "select title || char(10) || url || char(10) || char(10) || text from documents where id = 12" | less
```

```bash
# Pages that could not be downloaded, and why
sqlite3 -header -column data/validation.db "select status, http_status, url from fetches where status != 'ok'"
```

```bash
# Which model answered each stage of question #127 in run 3
sqlite3 -header -column data/validation.db "select stage, model, valid from stage_outputs where run_id = 3 and question_id = (select q.id from questions q join run_questions rq on rq.question_id = q.id where rq.run_id = 3 and q.ext_id = '127')"
```

```bash
# Calls per provider and model, and how many failed
sqlite3 -header -column data/validation.db "select provider, model, status, count(*) calls from api_calls group by 1, 2, 3"
```

```bash
# Your review decisions, newest first
sqlite3 -header -column data/validation.db "select d.created_at, ds.name file, d.ext_id id, d.action, d.comment from decisions d join datasets ds on ds.id = d.dataset_id order by d.id desc limit 20"
```

Stage outputs are reused by input hash, so a question researched in an earlier run keeps its S1a/S1b/S3 outputs
under that earlier run's id — the last query then shows only the stages that were new in run 3.

## Our own knowledge base (what exists today)

Every page we fetch is saved in full in `documents`, and every quote that passed the exact-match check in
`passages`. Search results are kept in `search_queries` (reused until `expires_at`).

**The knowledge index** (`data/kb/index.sqlite`, phase 1 of [KNOWLEDGE_BASE_PLAN.md](KNOWLEDGE_BASE_PLAN.md)) makes
all of it searchable in one place: every stored document plus every page of the searchable library books, cut into
chunks of about 1,200 characters and indexed with SQLite FTS5 (BM25). It is a **cache** — built only from
`validation.db` and `data/library/index.sqlite`, updated after every batch (`qv kb index`), and safe to delete
(`qv kb rebuild` builds it again in about a second). It is not in the Alembic database and has no migrations.

| Table (index.sqlite) | What it holds |
|---|---|
| `kb_docs` | one row per document (`doc:<documents.id>`) or book page (`book:<book>/p<page>`): URL, normalised URL, title, trust tier, language guess, current / older version, `canon_key` (its search group), which editions / categories / how many questions read it |
| `kb_chunks` | the chunks: document, start / end offsets into the stored text (`text == stored[start:end]`), page |
| `kb_fts` | the FTS5 index: chunk text (`kind = original`) and search-only translations of book pages (`kind = en` …) |
| `meta` | schema version, last update, `library://` documents that are indexed as their book page |

Same page, several URLs (tracking parameters, `www.`, http/https …) or the same text at two sites → one search
result with "also at …". A page fetched again with new text keeps the old version (passages still point at it);
search shows the newest unless older versions are asked for.

Your topics and relevance judgements are **not** in this cache: they are in `validation.db` (`topics`,
`relevance_labels`), so rebuilding the index never loses them.

```bash
# Your current relevance judgements (newest per question + page)
sqlite3 -header -column data/validation.db "select d.name file, r.ext_id, r.doc_key, r.label, r.created_at from relevance_labels r join datasets d on d.id = r.dataset_id where r.id in (select max(id) from relevance_labels group by dataset_id, ext_id, content_hash, doc_key) and r.label != 'clear'"
```

**Stored pages first** (phase 3): research searches this index with a question's blind (S1a) queries and reads up to
`stored_pages_per_question` stored documents again. Such a read is an ordinary `question_documents` row whose
`found_by_json` holds `{"via": "stored", "query": …, "doc_key": …, "rank": …}`; a book page becomes the same
`library://` document the library path makes. Nothing new is stored in the database for it. `run_questions.stats_json`
gets `stored_pages`, `stored_searches`, `searches_total` (and `stored_too_old`, `stored_already_read`,
`stored_index_unavailable`, `web_searches_skipped` when they happen).

```bash
# Documents that were read because they were found in stored pages
sqlite3 -header -column data/validation.db "select qd.run_id, qd.question_id, d.id, substr(d.title, 1, 50) title from question_documents qd join documents d on d.id = qd.document_id where qd.found_by_json like '%\"via\": \"stored\"%'"

# Pages of web PDFs
sqlite3 -header -column data/validation.db "select id, final_url, char_len from documents where source_kind = 'pdf'"

# The ten biggest documents in the index
sqlite3 -header -column data/kb/index.sqlite "select doc_key, tier, lang, char_len, substr(title, 1, 50) title from kb_docs order by char_len desc limit 10"
```
