"""Retrieval benchmark on labels taken from data already stored (KNOWLEDGE_BASE_PLAN.md → Retrieval metrics).

Per question (one question = edition + id + content hash; its runs are merged):
- **relevant**: read for that question, on the right subject, with ≥ 1 grounded passage on the information need
- **not relevant**: read and off-topic, or read without any grounded quote
- **unjudged**: everything else in the index

Documents are judged as their search group (`canon_key`: versions and same-content copies together), because that
is what search returns. Queries are the question's own S1a output (answer-blind), so the benchmark never sees the
key either.
"""

from __future__ import annotations

import json
import math
import random
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text as sql

from qv.db.session import Database
from qv.kb.index import KnowledgeIndex
from qv.kb.search import ranked_keys

DEPTH = 100          # ranked list length per question
RRF_K = 60
BOOTSTRAP = 1000
METRICS = ("recall@5", "recall@10", "mrr", "ndcg@10", "condensed_mrr", "condensed_ndcg@10", "judged_coverage@10")


@dataclass
class BenchQuestion:
    """One benchmark question: its blind queries and its labels (canon keys)."""

    key: str                                  # "<edition>#<id>@<hash8>"
    need: str
    queries: list[str]
    relevant: set[str] = field(default_factory=set)
    not_relevant: set[str] = field(default_factory=set)


# --- labels ---------------------------------------------------------------------------------------

def load_questions(db: Database, idx: KnowledgeIndex, extra_labels: list[tuple[str, str, str]] | None = None
                   ) -> list[BenchQuestion]:
    """Benchmark questions from stored research: every question with an S1a output and ≥ 1 document read.
    `extra_labels` = (question key, doc key, 'relevant' | 'not_relevant') from a person (phase 2), applied last."""
    canon = idx.canon_of_document()
    with db.session() as s:
        rq = s.execute(sql("SELECT rq.question_id, rq.stats_json, dv.profile, q.ext_id, q.content_hash "
                           "FROM run_questions rq JOIN questions q ON q.id = rq.question_id "
                           "JOIN dataset_versions dv ON dv.id = q.dataset_version_id "
                           "WHERE rq.status = 'done' ORDER BY rq.id")).all()
        outputs = {r[0]: r[1] for r in s.execute(sql("SELECT id, output_json FROM stage_outputs "
                                                     "WHERE stage = 's1a' AND valid = 1"))}
        reads = s.execute(sql("SELECT qd.id, qd.question_id, qd.document_id, qd.about_right_subject, qd.status "
                              "FROM question_documents qd")).all()
        need_passages = {r[0] for r in s.execute(sql("SELECT DISTINCT question_document_id FROM passages "
                                                     "WHERE target = 'need'"))}
        any_passages = {r[0] for r in s.execute(sql("SELECT DISTINCT question_document_id FROM passages"))}
    qkey_of: dict[int, str] = {}
    questions: dict[str, BenchQuestion] = {}
    for qid, stats, profile, ext_id, chash in rq:
        stats = json.loads(stats) if isinstance(stats, str) else (stats or {})
        out = outputs.get(stats.get("s1a_output_id"))
        if out is None:
            continue
        out = json.loads(out) if isinstance(out, str) else out
        key = f"{profile}#{ext_id}@{chash[:8]}"
        qkey_of[qid] = key
        queries = [q["q"] for q in out.get("queries", []) if q.get("q")]
        questions[key] = BenchQuestion(key, out.get("information_need", ""), list(dict.fromkeys(queries)))
    for qd_id, qid, doc_id, on_subject, status in reads:
        key, ck = qkey_of.get(qid), canon.get(doc_id)
        if key is None or ck is None:
            continue
        bq = questions[key]
        if on_subject and qd_id in need_passages:
            bq.relevant.add(ck)
        elif on_subject is False or on_subject == 0 or (status in ("extracted", "excluded") and qd_id not in any_passages):
            bq.not_relevant.add(ck)
    for key, doc_key, label in extra_labels or []:
        if key in questions:
            d = idx.doc(doc_key)
            ck = d["canon_key"] if d else doc_key
            (questions[key].relevant if label == "relevant" else questions[key].not_relevant).add(ck)
    for bq in questions.values():
        bq.not_relevant -= bq.relevant
    return [q for q in questions.values() if q.relevant or q.not_relevant]


# --- metrics --------------------------------------------------------------------------------------

def recall_at(ranking: list[str], relevant: set[str], k: int) -> float:
    """Share of the relevant documents in the top k."""
    return len(set(ranking[:k]) & relevant) / len(relevant) if relevant else 0.0


def mrr(ranking: list[str], relevant: set[str]) -> float:
    """1 / rank of the first relevant document (0 when none is ranked)."""
    for i, key in enumerate(ranking, start=1):
        if key in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at(ranking: list[str], relevant: set[str], k: int) -> float:
    """nDCG@k with binary gains."""
    dcg = sum(1.0 / math.log2(i + 1) for i, key in enumerate(ranking[:k], start=1) if key in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return dcg / ideal if ideal else 0.0


def condensed(ranking: list[str], judged: set[str]) -> list[str]:
    """The ranking with unjudged documents removed."""
    return [k for k in ranking if k in judged]


def judged_coverage_at(ranking: list[str], judged: set[str], k: int) -> float:
    """Share of the top k that is judged (0 for an empty ranking)."""
    top = ranking[:k]
    return sum(1 for key in top if key in judged) / len(top) if top else 0.0


def question_metrics(ranking: list[str], q: BenchQuestion) -> dict[str, float]:
    """All metrics for one ranked list."""
    judged = q.relevant | q.not_relevant
    cond = condensed(ranking, judged)
    return {"recall@5": recall_at(ranking, q.relevant, 5), "recall@10": recall_at(ranking, q.relevant, 10),
            "mrr": mrr(ranking, q.relevant), "ndcg@10": ndcg_at(ranking, q.relevant, 10),
            "condensed_mrr": mrr(cond, q.relevant), "condensed_ndcg@10": ndcg_at(cond, q.relevant, 10),
            "judged_coverage@10": judged_coverage_at(ranking, judged, 10), "n_relevant": len(q.relevant)}


def rrf(rankings: list[list[str]], k: int = RRF_K, depth: int = DEPTH) -> list[str]:
    """Reciprocal-rank fusion of several rankings."""
    score: dict[str, float] = defaultdict(float)
    for r in rankings:
        for i, key in enumerate(r, start=1):
            score[key] += 1.0 / (k + i)
    return [key for key, _ in sorted(score.items(), key=lambda kv: -kv[1])][:depth]


def bootstrap_ci(values: list[float], *, n: int = BOOTSTRAP, seed: int = 0) -> tuple[float, float]:
    """95 % percentile interval of the mean (resampling questions)."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n))
    return (means[int(0.025 * n)], means[int(0.975 * n) - 1])


# --- systems --------------------------------------------------------------------------------------

def default_systems(idx: KnowledgeIndex) -> dict[str, Callable[[BenchQuestion], list[str]]]:
    """BM25 baselines: the information need alone, all blind queries as one query, each query fused (RRF)."""
    return {
        "bm25-need": lambda q: ranked_keys(idx, q.need, limit=DEPTH),
        "bm25-queries": lambda q: ranked_keys(idx, " ".join(q.queries) or q.need, limit=DEPTH),
        "bm25-queries-rrf": lambda q: rrf([ranked_keys(idx, x, limit=DEPTH) for x in (q.queries or [q.need])]),
    }


def evaluate(questions: list[BenchQuestion], systems: dict[str, Callable[[BenchQuestion], list[str]]]) -> dict:
    """Metrics per system (mean + bootstrap interval), unjudged share, and per-question numbers.
    Recall / MRR / nDCG are averaged over questions with ≥ 1 relevant document; coverage over all."""
    with_rel = [q for q in questions if q.relevant]
    report: dict = {"questions": len(questions), "with_relevant": len(with_rel),
                    "relevant_labels": sum(len(q.relevant) for q in questions),
                    "not_relevant_labels": sum(len(q.not_relevant) for q in questions), "systems": {}}
    for name, fn in systems.items():
        per_q = {q.key: question_metrics(fn(q), q) for q in questions}
        out: dict = {}
        for m in METRICS:
            vals = [per_q[q.key][m] for q in (questions if m == "judged_coverage@10" else with_rel)]
            mean = sum(vals) / len(vals) if vals else 0.0
            out[m] = {"mean": round(mean, 4), "ci95": [round(x, 4) for x in bootstrap_ci(vals)]}
        out["unjudged_share@10"] = round(1 - out["judged_coverage@10"]["mean"], 4)
        report["systems"][name] = {"metrics": out, "per_question": per_q}
    return report


def compare(report: dict, a: str, b: str, *, n: int = BOOTSTRAP, seed: int = 0) -> dict:
    """The plan's decision rule for "is `b` better than `a`": b must win on Recall@10 AND on condensed MRR or
    condensed nDCG@10, each with the 95 % interval of the paired difference above 0. When b's unjudged share@10 is
    above 30 %, a person judges a sample first (`needs_judging`)."""
    pa, pb = report["systems"][a]["per_question"], report["systems"][b]["per_question"]
    keys = [k for k in pa if k in pb and pa[k]["n_relevant"]]
    rng = random.Random(seed)
    result: dict = {}
    for m in ("recall@10", "condensed_mrr", "condensed_ndcg@10"):
        diffs = [pb[k][m] - pa[k][m] for k in keys]
        if not diffs:
            result[m] = {"diff": 0.0, "ci95": [0.0, 0.0], "wins": False}
            continue
        means = sorted(sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(n))
        lo, hi = means[int(0.025 * n)], means[int(0.975 * n) - 1]
        result[m] = {"diff": round(sum(diffs) / len(diffs), 4), "ci95": [round(lo, 4), round(hi, 4)], "wins": lo > 0}
    unjudged = report["systems"][b]["metrics"]["unjudged_share@10"]
    result["needs_judging"] = unjudged > 0.30
    result["better"] = (result["recall@10"]["wins"]
                        and (result["condensed_mrr"]["wins"] or result["condensed_ndcg@10"]["wins"])
                        and not result["needs_judging"])
    return result


def run_benchmark(db: Database, data_dir: Path, *, save: bool = True,
                  extra_labels: list[tuple[str, str, str]] | None = None) -> tuple[dict, Path | None]:
    """Build the labels, evaluate the default systems, save `<data_dir>/kb/benchmarks/<date-time>.json`."""
    idx = KnowledgeIndex.for_data_dir(data_dir)
    try:
        questions = load_questions(db, idx, extra_labels)
        t0 = time.monotonic()
        report = evaluate(questions, default_systems(idx))
        report["seconds"] = round(time.monotonic() - t0, 1)
        report["index"] = idx.status()
    finally:
        idx.close()
    report["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
    report["person_labels"] = len(extra_labels or [])
    report["labels_rule"] = ("relevant = read, on the right subject, >= 1 grounded passage on the need; "
                             "not relevant = read and off-topic, or read without a grounded quote")
    path = None
    if save:
        out_dir = data_dir / "kb" / "benchmarks"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{time.strftime('%Y-%m-%d-%H%M%S')}.json"
        path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return report, path


def summary_lines(report: dict) -> list[str]:
    """A small table for the terminal."""
    lines = [f"{report['questions']} questions ({report['with_relevant']} with a relevant document), "
             f"{report['relevant_labels']} relevant / {report['not_relevant_labels']} not-relevant labels"]
    head = f"{'system':<20}" + "".join(f"{m:>20}" for m in METRICS) + f"{'unjudged@10':>14}"
    lines.append(head)
    for name, sysr in report["systems"].items():
        m = sysr["metrics"]
        cells = "".join(f"{m[k]['mean']:>7.3f} [{m[k]['ci95'][0]:.2f}-{m[k]['ci95'][1]:.2f}]" for k in METRICS)
        lines.append(f"{name:<20}{cells}{m['unjudged_share@10']:>14.2f}")
    return lines
