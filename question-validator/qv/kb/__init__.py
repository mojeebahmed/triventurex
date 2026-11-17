"""Knowledge base: one search index over everything the research has stored (KNOWLEDGE_BASE_PLAN.md).

- `text`      — URL normalisation, chunking, language guess (pure functions)
- `index`     — builds and updates `<data_dir>/kb/index.sqlite`, a rebuildable cache (no Alembic)
- `search`    — BM25 search returning documents with their best chunks
- `benchmark` — retrieval metrics on labels taken from data already stored

Search only decides what is read; evidence is always the stored original text (grounding is unchanged).
"""
