"""KB phase 4: local embeddings, the vector cache, vector / hybrid systems in the benchmark, the language sets."""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest
import respx

from qv.kb import benchmark as bm
from qv.kb.index import KnowledgeIndex
from qv.kb.search import ranked_keys
from qv.kb.vectors import (
    EmbedderUnavailable, HashingEmbedder, OllamaEmbedder, VectorSearch, VectorStore, current_chunks, embed_index,
    text_sha,
)
from tests.test_kb import build, world  # noqa: F401 — fixture


def test_hashing_embedder_is_deterministic_and_similar_texts_are_close() -> None:
    e = HashingEmbedder(256)
    a, b, c = e.embed(["Kilimanjaro is in Tanzania", "Kilimanjaro lies in Tanzania", "Allah taught Adam the names"])
    assert np.array_equal(a, e.embed(["Kilimanjaro is in Tanzania"])[0])

    def cos(x: np.ndarray, y: np.ndarray) -> float:
        return float(x @ y / np.linalg.norm(x) / np.linalg.norm(y))

    assert cos(a, b) > cos(a, c)


def test_store_keeps_vectors_by_text_across_index_rebuilds(world: dict) -> None:  # noqa: F811
    idx = build(world)
    store = VectorStore.for_data_dir(world["dir"])
    e = HashingEmbedder(64)
    first = embed_index(idx, store, e, batch=2)
    n = len({text_sha(t) for _, _, t in current_chunks(idx)})   # copies of a page share one vector
    assert first.texts == n < first.chunks and first.embedded == n and first.already == 0
    assert store.models() == {e.name: n}
    idx.close()
    idx = build(world, rebuild=True)              # the index is rebuilt (new chunk ids) …
    again = embed_index(idx, store, e)
    assert again.embedded == 0 and again.already == n  # … but nothing is embedded twice
    one = current_chunks(idx)[0]
    vec = store.get(e.name, [text_sha(one[2])])[text_sha(one[2])]
    assert vec.dtype == np.float16 and abs(float(np.linalg.norm(vec.astype(np.float32))) - 1) < 0.01
    idx.close()
    store.close()


def test_embedding_can_stop_and_continue(world: dict) -> None:  # noqa: F811
    idx = build(world)
    store = VectorStore.for_data_dir(world["dir"])
    r1 = embed_index(idx, store, HashingEmbedder(32), limit=2)
    r2 = embed_index(idx, store, HashingEmbedder(32))
    assert r1.embedded == 2 and r1.embedded + r2.embedded == r2.texts and r2.already == 2
    idx.close()
    store.close()


def test_vector_search_returns_one_key_per_document_group(world: dict) -> None:  # noqa: F811
    idx = build(world)
    store = VectorStore.for_data_dir(world["dir"])
    e = HashingEmbedder()
    embed_index(idx, store, e)
    vs = VectorSearch(idx, store, e)
    keys = vs.ranked_keys("what did Allah teach Adam", limit=50)
    assert keys and len(keys) == len(set(keys))
    assert keys[0] == idx.doc(f"doc:{world['docs']['adam']}")["canon_key"]
    assert vs.missing == 0 and VectorSearch(idx, store, HashingEmbedder(99)).size == 0  # other model: nothing
    idx.close()
    store.close()


def test_benchmark_with_vectors_runs_the_decision_rule(world: dict) -> None:  # noqa: F811
    idx = build(world)
    store = VectorStore.for_data_dir(world["dir"])
    e = HashingEmbedder()
    embed_index(idx, store, e)
    vs = VectorSearch(idx, store, e)
    idx.close()
    report, _ = bm.run_benchmark(world["db"], world["dir"], save=False, vectors=vs)
    assert {"vec-need", "vec-queries-rrf", "hybrid-rrf"} <= set(report["systems"])
    assert set(report["decision"]) == {"vec-queries-rrf", "hybrid-rrf"}
    assert all("better" in d for d in report["decision"].values())
    assert report["vectors"]["model"] == e.name
    assert any(line.startswith("Decision rule, hybrid-rrf") for line in bm.summary_lines(report))
    store.close()


def test_english_to_german_set_from_marked_book_pages(world: dict) -> None:  # noqa: F811
    """A person marked the German book page for q3 (and an English page as a control): the language set measures
    finding exactly that page; the original-text search cannot find German from English words, the translation can."""
    idx = build(world)
    qs = bm.load_questions(world["db"], idx)
    k3 = next(q for q in qs if q.key.startswith("world-tour#3@"))
    k3.queries = ["first Jalsa Salana Qadian"]
    labels = [(k3.key, "book:de/p1", "relevant"), (k3.key, "book:basics/p2", "relevant"),
              (k3.key, "doc:999", "relevant")]
    sets = bm.language_sets(qs, idx, labels)
    assert set(sets) == {"en→de", "en→en"}
    [de] = sets["en→de"]
    assert de.relevant == {idx.doc("book:de/p1")["canon_key"]}
    systems = bm.language_systems(idx, None)
    assert set(systems) == {"fts-original", "fts+translation"}
    target = idx.doc("book:de/p1")["canon_key"]
    q = bm.BenchQuestion("x", "", ["Fasting"], {target})
    assert target not in systems["fts-original"](q) and target in systems["fts+translation"](q)
    assert target not in ranked_keys(idx, "Fasting", original_only=True)
    idx.close()


@respx.mock
def test_ollama_embedder_request_and_errors() -> None:
    route = respx.post("http://localhost:11434/api/embed").mock(return_value=httpx.Response(
        200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]}))
    vecs = OllamaEmbedder("bge-m3").embed(["a", "b"])
    assert vecs.shape == (2, 2)
    assert json.loads(route.calls[0].request.content) == {"model": "bge-m3", "input": ["a", "b"], "keep_alive": "10m"}
    respx.post("http://localhost:11434/api/embed").mock(return_value=httpx.Response(404, json={"error": "not found"}))
    with pytest.raises(EmbedderUnavailable, match="ollama pull bge-m3"):
        OllamaEmbedder("bge-m3").embed(["a"])
    respx.post("http://localhost:11434/api/embed").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(EmbedderUnavailable, match="not reachable"):
        OllamaEmbedder("bge-m3").embed(["a"])


def test_cli_embed_and_benchmark_with_hashing(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from typer.testing import CliRunner

    from qv.cli import app
    from qv.config import Settings
    build(world).close()
    monkeypatch.setattr("qv.cli._db", lambda: world["db"])
    monkeypatch.setattr("qv.cli._settings", lambda: Settings(data_dir=world["dir"]))
    monkeypatch.setattr("qv.kb.index.update_index", lambda *a, **k: type("R", (), {"line": lambda self: "ok"})())
    out = CliRunner().invoke(app, ["kb", "embed", "--model", "hashing"]).output
    assert "embedded now" in out
    out = CliRunner().invoke(app, ["kb", "benchmark", "--vectors", "hashing", "--no-save"]).output
    assert "Decision rule, hybrid-rrf" in out and "Vectors (hashing-512)" in out
    assert isinstance(KnowledgeIndex.for_data_dir(world["dir"]), KnowledgeIndex)
