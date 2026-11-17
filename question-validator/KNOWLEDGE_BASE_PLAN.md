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
