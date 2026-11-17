# Knowledge base — plan

*2026-11-17. One plan for the question validator's knowledge base: what exists, what was decided (after two review
rounds with ChatGPT), and the phased roadmap. Phase 1 is built (branch `feat/qv-kb-index`, result note below); each
phase is meant to be built in its own session and branch.*

## 1. What exists

### 1.1 What it is

A local tool that fact-checks the questions of a family quiz board game (Triventurex). Each game edition is a CSV
file of questions: Swab Quest (Islamic / Ahmadiyya, 432 questions), Prophets' Stories (221), World Tour (220),
Animal Safari (220), Football Quest (92). For each question it finds real sources, reads them, and gives a verdict
(VERIFIED, INCORRECT, OUTDATED, CONTESTED, AMBIGUOUS, UNVERIFIED) with quotes and reasons. A person reviews what
needs a person in a small web app and exports a corrected CSV.

**Hard constraints**

- **$0 budget**: only free tiers. LLM = Gemini API free tier (Flash-Lite ≈ 500 requests/day per model, Flash ≈ 20/day);
  search = free tiers (Parallel, Tavily, Exa); Wikipedia, alislam.org and alhakam.org directly. Local models via
  Ollama on a Mac M2 Pro, 32 GB (qwen3 14b/8b, gemma3 12b, mistral-nemo): free but slow (1–4 min per long document).
- **Python + SQLite** (SQLAlchemy/Alembic), Streamlit web page, everything runs on one Mac. No server, no cloud DB.
- **Answer-blind research**: the stages that search and read never see the expected answer (see §2).
- **Only verbatim stored text is evidence**: a quote counts only if it is an exact substring of a document we
  fetched and stored. Models refer to passages by id; they can never introduce a URL, title or quote.
- **Quotes stay in the original language**: translations may help *find* text, never count as evidence.
- **Frames**: some editions declare a frame of reference (e.g. the Ahmadiyya understanding, Qur'an numbering with
  Bismillah = verse 1). Claims inside the frame are judged against the frame's authorities (alislam.org,
  alhakam.org, reviewofreligions.org, books published by them).

### 1.2 The pipeline (per question)

| Stage | Who | Sees the answer? | Does |
|---|---|---|---|
| S1a Decomposition | LLM | no | information need, claim type, frame class, **blind search queries** |
| S1b Claim formulation | LLM | yes | key claim, note claims, direct lookups (e.g. a Qur'an verse), **challenge queries** |
| S2 Retrieval | code | queries only | runs searches, fetches pages (robots.txt respected), stores them; Qur'an verses and book pages directly |
| S3 Evidence extraction | LLM, one document at a time | no | verbatim passages + *what each passage says the answer is* |
| Grounding | code | — | drops any quote not found word for word in the stored text |
| S4 Blind answer | LLM | no | answers the question from the passages alone |
| S5 Verification | LLM | yes | compares key, options and blind answer with the evidence |
| S6 Quality | LLM | yes, no evidence | wording, ambiguity, audience, suggested rewrite |
| S8 Rules | code | — | claim statuses → verdict, evidence strength, review route (deterministic, versioned) |

**Source trust** is per domain (`config/sources.yaml` + the person's own marks): P primary · S expert · T
encyclopaedia · X never evidence (quiz sites, forums). Passages that trace back to the same origin count once
("echo" defence). Every model call goes through a quota ledger; a run stops cleanly when a free limit is reached
and resumes later without repeating finished work (stage outputs are cached by input hash).

**Results so far** (evaluation set with known and seeded errors, Flash-Lite as judge, 51 of 104 questions):
≈ 90 % of errors routed to human review, 0 % of correct questions wrongly marked INCORRECT, 1 false VERIFIED
(probably a bad test label).

### 1.3 The knowledge base today

Everything the research touches is kept, so it can be reused. All stored rows are immutable (DB triggers).

| Store | What it holds | Size now |
|---|---|---|
| `documents` | full extracted text of every page read: web pages, Wikipedia articles, Qur'an verses (Arabic + English), book pages; url, domain, title, fetch date, content hash | 290 documents, ≈ 3.1 M characters |
| `passages` | grounded verbatim quotes per question: char offsets, what the passage says the answer is, stance, qualifiers, "as of" date, attributed origin | 596 passages for 67 questions |
| `question_documents` | which document was read for which question, how it was found (query), trust tier, page kind (quiz / news / official …), on-topic or not | |
| `fetches`, `search_queries` | fetch log incl. failures (403, robots.txt …), search results cache (60 days) | 230 searches |
| Book library | local PDFs (Ahmadiyya books), page by page in **SQLite FTS5** (BM25), cited as *book + page*; a German book also has a machine translation per page indexed **for search only** | 3 books, ≈ 500 pages (an Urdu book needs OCR — not done) |
| Source registry + marks | trust tier per domain; the person can mark sites use / don't use / needs special access | |

**How retrieval works now**: for each question, S1a/S1b produce queries → up to 4 web searches (top 5 results each) +
Wikipedia + alislam.org site search + alhakam.org (sitemap keyword match) + the best 2 book pages from FTS5 (BM25 over
the core query and two blind queries, any shared content word counts) → up to 5 documents (+2 for the note) are read
by S3. Stored documents are reused only when the **same URL** comes up again in a web search.

## 2. Decisions (after two review rounds, 2026-11-17)

**Keep unchanged**: stage separation and what each stage may see; verbatim grounding; immutable imports, documents and
passages; S8 as pure code; origin clusters; quota ledger, resumable runs and input-hash cache; provider pools; SQLite +
Alembic.

**Agreed direction**
- The missing piece is **one search index over everything stored** (today only books are searchable; stored web pages are
  reused only when the same URL comes back from a web search) and the uses built on it: a search page, reuse in research,
  duplicate detection, question generation.
- **Measure before adding**: a retrieval benchmark from data we already have comes first; embeddings, rerankers and local
  models are adopted only when a measurement says they help.
- **LLM stages stay provider-flexible**: Gemini free tier is primary today (local models measured worse at quoting and
  ≈ 40–160× slower on S3), local models are overflow and are re-tested per stage; **search-side AI (embeddings) is local**.
- **Topic exploration without a knowledge graph**: a topic is a saved search; its view lists matching passages, the
  existing questions on it in every edition, and later matching facts. Curated topic links can be added later.
- **Facts are pointers to evidence, never evidence**: a fact has grounded supporting quotes and an append-only status
  history; a question built on it is validated blind from fresh research.

**Risks and how they are handled**

| Risk | Mitigation |
|---|---|
| Answer leakage through reuse (stored passages carry another question's asserted answer) | reuse **documents only**; S3 extracts again, blind |
| Echo / popularity bias (one strong page surfacing everywhere) | origin clusters unchanged; cap stored pages per question; web search still runs |
| Staleness (records, current statistics) | time-sensitive claims skip stored pages older than a set age; older versions never invalidated, only flagged |
| Similarity or translation mistaken for evidence | search only decides what S3 reads; quotes ground against the original text |
| Self-confirmation of generated questions | leave-one-out validation: the generating document and its origin cluster are masked; independent origin required; frame-only facts go to the specialist |
| Misleading benchmark gains from incomplete labels | condensed metrics + judged coverage; sample-judging when a system's top 10 is mostly unjudged |
| Multilingual benchmark bias (questions written from the machine translation favour translation search) | use real quiz questions whose German page a person marked; Urdu only after an OCR quality test |
| Weaker results from local models | a stage moves local only when the evaluation set says it is as good |

## 3. Roadmap

### Ground rules (all phases)

- **Unchanged**: answer-blind research; only verbatim stored text is evidence (grounding code); immutable imports,
  documents and passages; S8 as pure code; origin clusters; quota ledger; SQLite + Alembic; free services only.
- **Two kinds of storage**:
  - *Derived, rebuildable* → `data/kb/index.sqlite` (no Alembic; delete it and it is rebuilt). Chunks, FTS, vectors,
    URL groups, language guesses.
  - *Curated or paid for* → the Alembic database (`data/validation.db`): anything a person decides, anything that
    cost model requests (facts, saved topics, decisions). Book translations stay in the library index, where they are
    already kept across rebuilds.
- **Every phase**: `pytest` green, no network in tests, `USER_GUIDE.md` / `DATABASE.md` / `CLAUDE.md` / page Help updated.
- **Any phase that changes research** re-runs the evaluation set: errors sent to review must not fall, false
  INCORRECT ≤ 3 %, false VERIFIED must not rise, quotes dropped < 2 %, need coverage ≥ 85 %.

### Retrieval metrics (used in phases 1, 3, 4)

Per question, the labels come from data already stored (`question_documents` + `passages`):
**relevant** = read for that question, on the right subject, ≥ 1 grounded passage on the information need ·
**not relevant** = read and off-topic, or read without any quote · **unjudged** = everything else in the index.

| Metric | How |
|---|---|
| Recall@5, Recall@10 | share of the question's relevant documents in the top k |
| MRR | 1 / rank of the first relevant document |
| nDCG@10 | binary gains |
| **Condensed** MRR / nDCG@10 | the same with unjudged results removed from the ranked list first |
| **Judged coverage@10** | share of the top 10 that is judged (relevant or not relevant) |
| **Unjudged share@10** | 1 − judged coverage, reported per system |

**Decision rule**: a system counts as better only if it wins on Recall@10 **and** condensed MRR / nDCG, by more than the
noise level (≈ 10 points with ≈ 70 questions; report a bootstrap interval). If its unjudged share@10 is above 30 %, a
person judges a random sample of 20 of its unjudged results (on the search page, phase 2) before deciding. Labels added
that way are stored and reused.

### Document identity (used from phase 1)

- **Normalised URL** (derived, in the index): lower-case host, no `www.`, http → https, no fragment, tracking parameters
  dropped (`utm_*`, `fbclid`, `gclid`, `ref`, `mc_*`), remaining parameters sorted, trailing slash removed. Redirects are
  already followed (the final URL is stored). For new fetches the page's own **canonical URL** (from trafilatura metadata)
  is stored too.
- **Same content, different URLs** (16 such documents today): grouped by content hash — one search result with "also
  at …". As evidence they already count once (origin clusters).
- **Versions** (9 URLs have more than one today): the newest version per normalised URL is *current*; older ones are
  *older version*, hidden by default in search, **never invalidated**: passages keep pointing at the exact version
  they were quoted from. A newer version only *triggers*: (a) a "newer version exists" note where an old one is cited,
  (b) for time-sensitive claims, a re-check suggestion. Nothing changes a verdict or a fact automatically.

---

### Phase 1 — Unified knowledge index + retrieval baseline

**Delivers**: every stored page (web, Wikipedia, Qur'an, book pages) searchable with one FTS5 index; the first
honest measurement of retrieval quality.
**Depends on**: nothing.

Tasks
1. `qv/kb/index.py`: build/update `data/kb/index.sqlite` — tables `kb_docs` (doc key, source kind, document id or
   book + page, URL, normalised URL, content hash, current/older, language guess, trust tier, editions/categories of
   questions that read it, fetch date, text hash, chunker version), `kb_chunks` (chunk id, doc key, start/end offsets,
   page, text), `kb_fts` (FTS5 over chunks + search-only translation rows, `unicode61 remove_diacritics 2`).
2. Chunker: paragraph-based windows ≈ 1,000–1,500 chars, small overlap, never across a book page; offsets map back
   to the stored text. Versioned (`CHUNKER_VERSION`).
3. Incremental: index only new documents or a changed text hash / chunker version; `qv kb index` (incremental),
   `qv kb rebuild`, `qv kb status`. Runs automatically after each batch.
4. Language guess without new dependencies (script + stopword counts: en, de, ar/ur script).
5. `qv/kb/search.py`: BM25 search returning documents (best chunks as previews), with filters.
6. `qv/kb/benchmark.py` + `qv kb benchmark`: labels as above, BM25 with each question's S1a queries, all metrics,
   results saved as a dated JSON in `data/kb/benchmarks/`.

DB changes: none in the Alembic database (index is a cache). Optional small migration for **new** fetches only:
`documents.canonical_url`, `documents.published` (nullable). ⚠ On SQLite, `batch_alter_table` recreates the table —
the immutability triggers must be re-created in the same migration (`tests/test_db.py` checks models = migrations;
add a test that the triggers exist after upgrade). Existing rows are not back-filled (their raw HTML is not kept).

Acceptance
- Index of today's data builds in < 1 minute; an incremental run with nothing new takes < 2 s.
- Every chunk's offsets reproduce its text from the stored document (test over all chunks).
- Book search results are the same or better than today's library search on 10 known queries.
- Baseline benchmark report exists (all metrics, coverage, bootstrap intervals).

Tests: chunker (boundaries, offsets, pages), URL normalisation table, version/current grouping, content-hash
grouping, incremental indexing, metric functions on hand-made rankings (incl. condensed lists and coverage).

**Result (2026-11-17, branch `feat/qv-kb-index`)** — `qv/kb/` (text, index, search, benchmark), `qv kb index |
rebuild | status | search | benchmark`, `tests/test_kb.py` (24 tests).
- Index of today's data: 787 documents (265 web, 3 Wikipedia, 22 Qur'an, 497 book pages), 762 search results after
  grouping, 9 older versions, 3,833 chunks, 75 search-only translation rows. Full build 0.5 s; an update with nothing
  new 0.2 s. Every chunk's offsets reproduce its stored text (checked on all chunks of the real data and in tests).
- Book search vs today's library search on 10 known queries: 9 of 10 share ≥ 2 of the top 3 pages; where the top
  page differs, the new top page contains the asked words and the old one did not ("Noah ark": old p. 317 has neither
  word, new p. 266 has both; "Promised Messiah birth Qadian": new p. 255 has *born* and *Qadian*, old p. 254 neither)
  → same or better (chunk-level BM25 instead of whole pages).
- **Baseline** (`data/kb/benchmarks/2026-11-17-012320.json`; 61 questions, 54 with a relevant document, 180 relevant /
  93 not-relevant labels):

  | system | Recall@5 | Recall@10 | MRR | nDCG@10 | cond. MRR | cond. nDCG@10 | unjudged@10 |
  |---|---|---|---|---|---|---|---|
  | bm25-need (S1a information need) | 0.63 | 0.79 | 0.68 | 0.65 | 0.93 | 0.91 | 0.70 |
  | bm25-queries (all blind queries as one) | 0.67 | 0.82 | 0.66 | 0.66 | 0.89 | 0.91 | 0.68 |
  | bm25-queries-rrf (each query, fused) | 0.71 | 0.87 | 0.69 | 0.70 | 0.91 | 0.92 | 0.67 |

  RRF wins Recall@10 over the need alone (+0.08, interval 0.02–0.15) but not condensed MRR / nDCG, and its unjudged
  share is ≈ 0.67 > 30 % → by the decision rule nothing is "better" yet; a sample of unjudged results needs judging
  (phase 2's judging tool). For phase 3, per-query search fused with RRF is the natural default.
- Not done (optional in the plan): the `documents.canonical_url / published` migration — new fetches still store
  only the final URL. Normalised URLs + content-hash groups cover today's 16 copies and 9 versions.

### Phase 2 — Knowledge search page

**Delivers**: browse and search everything collected. **Depends on**: phase 1.

Tasks
1. Advanced → **Knowledge**: search box; filters source type, language, trust, edition/category, current/older
   versions; results table (document, best passage with words marked, trust, page, date, "also at"); popup with the
   stored text (words marked, ◀/▶ through results), link to the web page or the PDF page.
2. **Saved searches = topics**: name + query + filters; the topic view also lists matching existing questions
   (FTS over questions of all editions) with their results.
3. Optional judging: on a result, "relevant / not relevant for question #…" — stored as labels for the benchmark.

DB changes (Alembic): `topics` (id, name, query, filters_json, created, updated); `relevance_labels` (question ext id +
content hash, doc key, label, who, created; append-only). Designed so later `topic_links` (topic id, target kind
document | question | fact | passage, target ref, note, who, created; append-only) can be added without changing
`topics`.

Acceptance: any stored page is findable by a distinctive phrase; filters combine; the popup opens the right page and
offsets; a topic can be saved, reopened and renamed. Tests: query building, filters, topic CRUD, label storage.

**Result (built 2026-11-17, branch `claude/qv-kb-search-page-a3ae38`, based on `feat/qv-kb-index`)**
- Advanced → **🧠 Knowledge** (`page_knowledge` in `qv/ui/app.py`); logic in `qv/services/knowledge.py`. Results table
  marks the search words in the cells (new `marks=` option of `data_table` / `qv/ui/table.py`, built from text
  nodes, never HTML). The popup reads the stored text from `documents.text` / the library page (not from the index),
  shows the best passage, marks the words, underlines the hit chunks by their offsets, links only plain `http(s)`
  addresses (a book page links to the book's `source_url#page=N` when known); ◀ / ▶ via `popup_nav`.
- Topics: a **Topic** box above the search (choose = reopen), 📌 Save as topic · 💾 Save changes · ✏️ Rename · 🗑.
  Tab *Questions with these words*: a simple word match (word starts ≥ 4 letters count; quoted phrases must match)
  over the latest version of every non-eval file, with status and verdict (`workflow.question_states`) — no FTS
  table was needed at ≈ 1,200 questions.
- Judging: popup → file + question id → ✅ / ❌ / ↩; `relevance_labels` (migration 0006, append-only triggers).
  `qv kb benchmark` passes the current judgements as `extra_labels` (question key from the version's profile) and the
  report stores `person_labels`.
- DB: `topics` (mutable: rename / change / delete; `topic_links` can later point at `topics.id`), `relevance_labels`.
- Tests: `tests/test_knowledge.py` (filters, combined filters, older versions, every stored page findable by a
  phrase, offsets reproduce the stored text, escaping, safe links, topic CRUD, question matching, labels newest-wins
  + append-only, labels reaching the benchmark). Checked in the browser against a copy of `data/`.
- Not done: a search inside the stored text of one result beyond marking; topic links (not now, as planned).

### Phase 3 — Stored pages first (+ web PDFs)

**Delivers**: research reuses what is stored; fewer free searches. **Depends on**: phase 1 (and its baseline).

Tasks
1. In S2: search the index with the question's blind queries (S1a only) before the web; add up to N stored documents
   (config, default 2) not already read for this question; S3 reads them blind; `found_by: {via: stored}`.
2. **Documents only** — never reuse another question's passages or asserted answers (test).
3. Freshness: for time-sensitive claim types (`statistic_current`, `sports_record`, …) skip stored pages older than
   `stored_max_age_days` (config) and fetch fresh instead.
4. Cap: stored documents never replace the blind web queries at first; a later switch (`stored_first_skip_web`) may skip
   web searches when enough stored pages qualify — off by default.
5. **Web PDFs**: fetched like pages (robots, size cap), read page by page with the library reader, stored as documents per
   page with the **site's** trust tier; "needs OCR" check; appear in the index.
6. Page: "found in stored pages" badge on sources.

DB changes: none required (found_by is JSON). Acceptance: evaluation set rules above hold; searches per question go
down (report); benchmark: stored-page recall reported. Tests: blind queries only, no passage reuse, freshness rule,
PDF page storage and trust.

**Result (2026-11-17, branch `claude/qv-kb-stored-first-aaa96c`, on top of phase 1) — code and tests only.**
- **Stored pages first** in S2 (`qv/services/research.py`): the index is searched with the S1a blind queries only
  (per-query BM25 + RRF, as the phase-1 baseline suggested), up to `stored_pages_per_question` = 2 documents not yet
  read for the question are added in mode A on top of the web budget and read blind by S3 (`found_by: {via: stored,
  query, doc_key, rank}`). Skipped: tier X / "needs special access" sites, books not listed for the edition, a second
  page per site or book, and for time-sensitive questions pages older than `stored_max_age_days` = 365 (or without
  a date). The index is opened read-only; a missing or broken index is noted in the stats and never fails research.
- **Documents only**: a test shows the S3 prompt of a stored page holds no other question's passages or answers and
  that only S1a queries reach the index.
- `stored_first_skip_web` implemented and tested, **off** (skips only the paid-pool web queries).
- **Web PDFs**: fetched like pages (robots.txt, 20 MB cap, ≤ 400 pages), read page by page with the library reader,
  one document per readable page (`<pdf url>#page=N`, `source_kind = pdf`, the site's trust); a PDF without readable
  text → `needs_ocr`, nothing stored. They are in the index (normalised URLs keep `#page=N`). The Book library's
  *Found on the web* now lists every web PDF with what happened to it (*Read* column) — still book candidates.
- Page: 🗄️ *found in stored pages* badge (and *PDF page*) on sources, help text in the legend and the Book library.
- Report: per-question `stored_pages`, `stored_searches`, `searches_total` in the run stats; a "searches per
  question · stored pages added per question" line after every batch; `qv kb benchmark` reports **stored-page
  recall** (hit / recall in the top 2 of bm25-queries-rrf).
- Tests: `tests/test_stored_pages.py` (14), no network.
- **Still to do — the acceptance check on the evaluation set** (uses free Gemini / search quota, so Mojeeb decides
  when; not run). After merging, on the evaluation set: `qv kb index`, then `qv eval import` (it prints the runs to
  start), then `qv validate eval-known-errors --judge-pool cheap` and the same for every other eval dataset it lists
  (seeded per edition and controls; `qv resume <run>` until done), then `qv eval score <new runs…>` and compare with the
  last scores (errors to review must not fall, false INCORRECT ≤ 3 %, false VERIFIED not up, quotes dropped < 2 %,
  need coverage ≥ 85 %), and compare the "Searches per question" lines with earlier runs (`stats_json`
  `searches_total`). `qv kb benchmark` gives the stored-page recall (no quota used).
- **Acceptance result (2026-11-17)** — before = runs 7–17 (stored pages off), after = runs 18–28 (on), Flash-Lite
  judge, compared on the 77 questions done in both: errors to review 31/36 → 32/36 (86.1 → 88.9 %), false
  INCORRECT 0 → 0 %, false VERIFIED 2 → 2 (football seeded #26 fixed; swab seeded #20 new), correct questions
  auto-verified 14/40 → 18/40, verdict as labelled 67.5 → 71.4 %. **Decision: stored pages stay on (2).** Swab
  seeded #20 (Baitul Futuh, 2003 → 2006): the stored book page found the right year, but the judge treated the
  whole key (place + size + year) as one claim and cited that passage as support — a judge / claim-splitting
  weakness, not retrieval. Web searches per question fell to ~0, but mostly from cache, so not a fair saving
  measure. Stored-page recall: hit 0.816 in the top 2. 13 items ran out of Flash-Lite quota (runs 26–28) — resume
  with `qv resume <run>`. Quotes dropped / need coverage are not reported by `qv eval score` (not measured).

### Phase 4 — Retrieval experiments (embeddings) + local models per stage

**Delivers**: a measured decision, not a feature. **Depends on**: phases 1 and 3.

Tasks
1. Pull **one** multilingual embedding model in Ollama (candidates: `bge-m3`, `qwen3-embedding`); embed chunks into
   `kb_vectors` (BLOB, float16) — brute-force cosine in numpy.
2. Compare BM25 / vectors / hybrid (RRF, k = 60) on the phase-1 benchmark.
3. **English → German set**: 30–40 real Swab Quest / Prophets' Stories questions whose answer page in the German book a
   person has marked, + 10 English → English controls. Compare original-text FTS, translation FTS (today), embeddings,
   hybrid; Recall@5 and MRR.
4. Measure embedding time and memory on the M2 Pro; projected full-scale cost.
5. Overnight runs of the evaluation set with local models **per stage** (S1a, S3, S4, S6) — quality vs Gemini.

DB changes: index only. Acceptance: a written result in `data/kb/benchmarks/` + a decision note in this file. Adopt
embeddings (hybrid) **only** if the decision rule says so; otherwise remove `kb_vectors` code paths. A stage moves local
only if its evaluation-set numbers are not worse.

### Phase 5 — Same fact, different result (duplicates)

**Delivers**: consistency across editions. **Depends on**: phase 1 (phase 4 if embeddings were adopted).

Tasks
1. Candidates: compare S1a **information needs** (BM25, or hybrid) within and across editions + same claim type.
2. Confirm: normalised key answers equal / equivalent → *same fact*; then compare claim types and verdicts.
3. Review group **"Same fact, different result"**; the person decides (same fact / different fact / ignore).

DB changes (Alembic): `fact_pairs` (two question refs = ext id + content hash + dataset, similarity, found, status) and
`fact_pair_decisions` (append-only, reason, who, when). Acceptance: the known pair (#127 / #285) is found; on a
hand-checked sample of 30 candidates, ≥ 80 % are real same-fact pairs. Tests: candidate generation, answer
normalisation, decisions history.

**Result (2026-11-17, branch `claude/qv-fact-pairs`) — built, no model calls.**
- `qv/services/fact_pairs.py`: TF-IDF cosine over the question words (honorifics, accents, punctuation and stop words
  removed; **question words kept** — *when* vs *where* is another fact), or over S1a's information need when both
  were researched (the higher counts); answers equal after normalising, ≥ 90 % similar with the same numbers, one
  inside the other only when it is ≥ 40 % of it or a year inside a short date, or an S1b accepted equivalent. A pair
  = same answer and similarity ≥ 0.45, or **the same question with another answer**: similarity ≥ 0.8 and the same
  meaningful words. What differs: answers, verdicts (both checked), claim types (both researched).
- **Deviation from the plan:** no `fact_pairs` table — pairs are recomputed from the latest versions (< 1 s), so they
  follow every new version and nothing stale is stored. Only `fact_pair_decisions` (Alembic 0007, append-only +
  triggers; same_fact / different_fact / ignore / clear; the newest per pair wins; both questions by dataset + id +
  content hash, so a reworded question makes the pair new again).
- Page **Check questions → Same fact** (groups *Different result* · *Not decided yet* · *Same fact (you)* ·
  *Different facts / ignored* · *All*; popup with both questions side by side, what differs, decision + history,
  Help) and `qv pairs [--group …]`.
- **Acceptance:** the known pair swab-quest #127 / #285 is found, and its third copy prophets-stories #133. On the
  editions (2026-11-17 copy of the database): 37 pairs, all hand-checked — 33 real same-fact pairs (89 %, target
  ≥ 80 %). Misses: football #23 / #55 (two Maradona goals of 1986), animal-safari #61 / #76 (biggest bird / biggest
  eggs), prophets #108 / #212 and swab #380 / #384 (same story, other detail). A first version without question
  words and with token-set matching found 59 pairs with ≈ 60 % precision ("when" / "where" pairs, a year inside a
  long description). Only 1 pair has two different verdicts so far — most questions are not checked yet.

### Phase 6 — Facts and question generation

**Delivers**: new questions from collected knowledge, safely. **Depends on**: phases 1, 3, 5.

Tasks
1. Fact extraction run: choose topic / documents / book; LLM proposes statements + passage offsets; **grounded like
   passages**; stored as candidates.
2. Generation run: question + answer + distractors per accepted fact; duplicate check (phase 5); **leave-one-out
   validation** — the generating document and its whole origin cluster are masked from retrieval; VERIFIED needs an
   independent origin; frame-only facts always go to the specialist.
3. **Concentration limits** configurable per edition (profile) and overridable per generation run: max accepted
   questions per document, per book, per domain.
4. Review + export as new rows with new ids (never into `game_editions/`).

DB changes (Alembic): `facts` (statement, subject, claim type, date/as-of, time sensitivity, created by, created);
`fact_support` (fact, document id, offsets, quote, stance, cluster); `fact_events` (**append-only**: fact, new status
candidate/accepted/rejected/stale, reason, evidence refs (passage / document ids), who, when — the current status is the
newest event); `question_facts` (question ref ↔ fact); `generation_runs` (settings incl. limits, model, prompt version,
started, status); generated questions as a new dataset version / dataset (existing import machinery).

Acceptance: every fact has ≥ 1 grounded quote; every status change has a reason; leave-one-out proven by test (the
generating document never appears in the validation's documents); limits enforced; a pilot of 20 generated questions
reviewed by a person. Tests: grounding of facts, events history, masking, limits, export ids.

---

### Explicitly not now

- Separate vector database (Qdrant, Chroma), PostgreSQL, sqlite-vec — brute force is enough at ≤ 100 k chunks.
- Knowledge graph, entity extraction, AI summaries stored as knowledge.
- More than one embedding model; a reranker (unless phase 4 shows ranking, not recall, is the problem).
- Docling; switching to PyMuPDF (AGPL) — only if extraction quality fails.
- Urdu OCR — first a 5-page character-error-rate test, only when an Urdu book is needed.
- "Ask the knowledge base" free-form answers; conversational search.
- Curated topic links (designed in phase 2, built when saved searches are not enough).
- Automatic fact staleness: only flagged for a person, never applied automatically.
- Moving judging stages (S4/S5) to local models without the phase-4 evidence.

### Order and dependencies

```
0 evaluation measurement (running)
1 index + baseline ──► 2 search page ──► (topics, labels)
        │
        └──► 3 stored pages first (+ web PDFs) ──► 4 experiments ──► 5 duplicates ──► 6 facts + generation
```
Phase 2 and phase 3 can be built in either order after phase 1; phase 2 first gives the judging tool phase 4 may need.

### Agreed order from 2026-11-17 (Mojeeb) — code first, quota runs grouped

**First priority: validate the real editions and use the results in the game** — before any question generation.

Model-quota runs (Gemini free tier) — run in the background with the daily run while code is built:
1. **Finish the evaluation set with `stored_pages_per_question: 0`** → a clean "before" (phase 3 code is merged, so
   without this the remaining runs would mix before and after).
2. **Same eval set with `stored_pages_per_question: 2`** → the phase-3 acceptance "after" (both compared with
   `qv eval score`; searches per question compared too).
3. **Full validation of the editions**: Swab Quest first, then the others; review → export.

Code, in parallel:
- **Validated export for the game** (new item, not a KB phase): extra columns in the exported questions CSV that say
  how a question was checked, and the game's 📚 Questions tab + the Academy's Review / Explore lists show them. The
  game's parser keys rows by header and its checker only checks the column count, so extra columns are safe; the
  generated JS / content scripts and both pages need changes (root project rules apply there). Columns to agree first.
- **Phase 5** (duplicates) — little or no model use.
- **Phase 4 code** + embedding tests (local, $0); its local-model eval runs overnight on the Mac, one stage per run.
- **Phase 6 code** with a small sample only (a handful of facts and ~10–20 generated questions to prove grounding,
  leave-one-out masking and limits). **Full generation waits** until Mojeeb asks for it.

The knowledge index is **general** (one index over everything stored, all editions): each stored page carries the
editions / categories of the questions that read it, books carry the editions they are listed for, and search can
filter on these. Phase 6 chooses its source material (edition, topic, book, documents) per generation run, so it can
generate for an existing edition or a new one.
