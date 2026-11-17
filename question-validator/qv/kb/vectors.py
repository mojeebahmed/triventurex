"""KB phase 4 — embeddings for the retrieval experiments (KNOWLEDGE_BASE_PLAN.md → Phase 4). Local and free only.

- `OllamaEmbedder`: a multilingual embedding model in the local Ollama (`/api/embed`; e.g. `bge-m3`,
  `qwen3-embedding` — pulled by the person, never by this code). No cloud model is ever used here.
- `HashingEmbedder`: pure code (hashed word + character-trigram counts) — the test double, and a floor to compare with.
- `VectorStore`: `<data_dir>/kb/vectors.sqlite`, a **cache** next to the index: one float16 vector per (model, chunk
  text sha256). Keyed by the text, not the chunk id, so `qv kb rebuild` (or re-chunking unchanged text) keeps the
  vectors — embedding everything again takes hours locally. Never anything a person decided.
- `VectorSearch`: brute-force cosine in numpy over the current chunks (≤ 100 k chunks fit easily in memory), one result
  per document group (`canon_key`, best chunk) — the same unit BM25 search and the benchmark use.

Adopt embeddings (hybrid) in research **only** if the decision rule (`benchmark.compare`) says so; until then this
module is used by `qv kb embed` and `qv kb benchmark --vectors <model>` only.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
import numpy as np

from qv.kb.index import KnowledgeIndex

DEFAULT_OLLAMA = "http://localhost:11434"


class Embedder(Protocol):
    """Turns texts into vectors (one row per text)."""

    name: str

    def embed(self, texts: list[str]) -> np.ndarray:
        """Vectors, shape (len(texts), dim)."""
        ...


class EmbedderUnavailable(RuntimeError):
    """The local embedding model cannot be used (Ollama not running, model not pulled)."""


class OllamaEmbedder:
    """An embedding model in the local Ollama."""

    def __init__(self, model: str, *, base_url: str = DEFAULT_OLLAMA, client: httpx.Client | None = None,
                 timeout_s: float = 600.0, keep_alive: str = "10m") -> None:
        """`model` as Ollama names it, e.g. `bge-m3`."""
        self.model = model
        self.name = f"ollama/{model}"
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_s)
        self._keep_alive = keep_alive

    def embed(self, texts: list[str]) -> np.ndarray:
        """One `/api/embed` request for a batch of texts."""
        try:
            resp = self._client.post(f"{self._base}/api/embed",
                                     json={"model": self.model, "input": texts, "keep_alive": self._keep_alive})
        except httpx.ConnectError as exc:
            raise EmbedderUnavailable(f"Ollama is not reachable at {self._base} (is it running?)") from exc
        if resp.status_code == 404:
            raise EmbedderUnavailable(f"{self.model} is not pulled (run: ollama pull {self.model})")
        resp.raise_for_status()
        vecs = resp.json().get("embeddings") or []
        if len(vecs) != len(texts):
            raise RuntimeError(f"{self.model}: {len(vecs)} vectors for {len(texts)} texts")
        return np.asarray(vecs, dtype=np.float32)


class HashingEmbedder:
    """Pure-code vectors: hashed words and character trigrams (no model). Deterministic; for tests and as a floor."""

    def __init__(self, dim: int = 512) -> None:
        """`dim` buckets."""
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r"\w+", text.casefold())
        grams = [w[i:i + 3] for w in words for i in range(max(1, len(w) - 2))]
        for tok in (*words, *(f"#{g}" for g in grams)):
            h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "little")
            v[h % self.dim] += 1.0 if h & (1 << 63) else -1.0
        return v

    def embed(self, texts: list[str]) -> np.ndarray:
        """One vector per text."""
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), dtype=np.float32)


def _unit(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(n == 0, 1, n)


def text_sha(text: str) -> str:
    """The key a chunk's vector is stored under."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class VectorStore:
    """`<data_dir>/kb/vectors.sqlite`: float16 unit vectors per (model, text sha256). A rebuildable cache."""

    def __init__(self, path: Path) -> None:
        """Open (and create) the file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS kb_vectors (model TEXT, text_sha TEXT, dim INTEGER, vec BLOB, "
                          "PRIMARY KEY (model, text_sha))")

    @classmethod
    def for_data_dir(cls, data_dir: Path) -> VectorStore:
        """The store of a data directory."""
        return cls(data_dir / "kb" / "vectors.sqlite")

    def close(self) -> None:
        """Close the connection."""
        self.conn.close()

    def has(self, model: str) -> set[str]:
        """Text hashes that already have a vector for this model."""
        return {r[0] for r in self.conn.execute("SELECT text_sha FROM kb_vectors WHERE model = ?", (model,))}

    def put(self, model: str, shas: list[str], vecs: np.ndarray) -> None:
        """Store unit vectors as float16."""
        unit = _unit(vecs.astype(np.float32)).astype(np.float16)
        self.conn.executemany("INSERT OR REPLACE INTO kb_vectors VALUES (?, ?, ?, ?)",
                              [(model, s, unit.shape[1], unit[i].tobytes()) for i, s in enumerate(shas)])
        self.conn.commit()

    def get(self, model: str, shas: Iterable[str]) -> dict[str, np.ndarray]:
        """Vectors by text hash (missing ones are left out)."""
        out: dict[str, np.ndarray] = {}
        wanted = list(dict.fromkeys(shas))
        for i in range(0, len(wanted), 900):
            part = wanted[i:i + 900]
            q = f"SELECT text_sha, vec FROM kb_vectors WHERE model = ? AND text_sha IN ({','.join('?' * len(part))})"
            for sha, blob in self.conn.execute(q, (model, *part)):
                out[sha] = np.frombuffer(blob, dtype=np.float16)
        return out

    def models(self) -> dict[str, int]:
        """Models in the store → number of vectors."""
        return dict(self.conn.execute("SELECT model, COUNT(*) FROM kb_vectors GROUP BY model").fetchall())


@dataclass
class EmbedReport:
    """What `embed_index` did."""

    model: str
    chunks: int
    texts: int          # different chunk texts (copies of a page share one vector)
    embedded: int
    already: int
    seconds: float
    vector_bytes: int

    def line(self) -> str:
        """One line for the terminal."""
        rate = self.embedded / self.seconds if self.seconds else 0.0
        return (f"{self.model}: {self.chunks} current chunks ({self.texts} different texts) — {self.embedded} embedded "
                f"now, {self.already} already "
                f"stored; {self.seconds:.0f} s ({rate:.1f} chunks/s); vectors {self.vector_bytes / 1e6:.1f} MB")


def current_chunks(idx: KnowledgeIndex) -> list[tuple[int, str, str]]:
    """(chunk id, canon key, text) of every chunk of a current document."""
    return [(r[0], r[1], r[2]) for r in idx.conn.execute(
        "SELECT c.chunk_id, d.canon_key, c.text FROM kb_chunks c JOIN kb_docs d ON d.doc_key = c.doc_key "
        "WHERE d.is_current = 1 ORDER BY c.chunk_id")]


def embed_index(idx: KnowledgeIndex, store: VectorStore, embedder: Embedder, *, batch: int = 16,
                limit: int | None = None, progress: Callable[[int, int], None] | None = None) -> EmbedReport:
    """Embed every current chunk that has no vector for this model yet (at most `limit`). Resumable: stopping
    halfway keeps what was stored."""
    chunks = current_chunks(idx)
    have = store.has(embedder.name)
    texts = {text_sha(t): t for _, _, t in chunks}
    todo = {sha: t for sha, t in texts.items() if sha not in have}
    items = list(todo.items())[:limit] if limit is not None else list(todo.items())
    t0 = time.monotonic()
    done = 0
    dim = 0
    for i in range(0, len(items), batch):
        part = items[i:i + batch]
        vecs = embedder.embed([t for _, t in part])
        dim = vecs.shape[1]
        store.put(embedder.name, [s for s, _ in part], vecs)
        done += len(part)
        if progress:
            progress(done, len(items))
    n_vec = store.models().get(embedder.name, 0)
    return EmbedReport(embedder.name, len(chunks), len(texts), done, len(texts) - len(todo),
                       round(time.monotonic() - t0, 1),
                       n_vec * (dim or _dim_of(store, embedder.name)) * 2)


def _dim_of(store: VectorStore, model: str) -> int:
    row = store.conn.execute("SELECT dim FROM kb_vectors WHERE model = ? LIMIT 1", (model,)).fetchone()
    return int(row[0]) if row else 0


class VectorSearch:
    """Cosine search over the current chunks' vectors of one model (loaded once)."""

    def __init__(self, idx: KnowledgeIndex, store: VectorStore, embedder: Embedder) -> None:
        """Load the vectors of every current chunk that has one."""
        self.embedder = embedder
        chunks = current_chunks(idx)
        vecs = store.get(embedder.name, (text_sha(t) for _, _, t in chunks))
        rows = [(canon, vecs[text_sha(t)]) for _, canon, t in chunks if text_sha(t) in vecs]
        self.missing = len(chunks) - len(rows)
        self.canon = [c for c, _ in rows]
        self.matrix = (np.stack([v for _, v in rows]).astype(np.float32) if rows
                       else np.zeros((0, 1), dtype=np.float32))

    @property
    def size(self) -> int:
        """Chunks with a vector."""
        return len(self.canon)

    def ranked_keys(self, query: str, limit: int = 100) -> list[str]:
        """Canon keys by their best chunk's cosine similarity, best first."""
        if not self.size or not query.strip():
            return []
        q = _unit(self.embedder.embed([query]).astype(np.float32))[0]
        scores = self.matrix @ q
        best: dict[str, float] = {}
        for i in np.argsort(-scores):
            key = self.canon[int(i)]
            if key not in best:
                best[key] = float(scores[i])
                if len(best) >= limit:
                    break
        return list(best)
