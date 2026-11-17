"""Same fact, different result — question pairs about the same fact (KNOWLEDGE_BASE_PLAN.md phase 5). Pure code.

Pairs are found within and across the editions' question files (latest version of each; eval-… sets are left
out) and **recomputed every time** (< 1 s for ~1,200 questions), so they follow every new version. Only the
person's decisions are stored (`fact_pair_decisions`, append-only; the newest per pair wins, `clear` takes one
back). A decision belongs to both questions' exact wording (content hash), like review decisions.

How a pair is found:
1. **Wording**: TF-IDF cosine over the question texts (accents, punctuation and honorifics removed). Where both
   questions were researched, S1a's *information need* is compared too and the higher similarity counts.
2. **Answer**: the normalised answers are equal or nearly so (same numbers and ≥ 90 % similar; or one inside the
   other when it is ≥ 40 % of it, or a year inside a short date), or one is among the other's accepted equivalents
   from S1b (stored research).
3. A pair = same answer and wording ≥ `SAME_ANSWER_MIN`; or the **same question with another answer** (the most
   important case): wording ≥ `SAME_QUESTION_MIN` and the same meaningful words — one different word ("mother",
   "second", "when" / "where") already makes it another fact.
4. **What differs**: the answers, the verdicts (both checked), the claim types (both researched).
Nothing here calls a model; nothing changes a result.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from rapidfuzz import fuzz
from sqlalchemy import select

from qv.db.models import Dataset, FactPairDecision, RunQuestion, StageOutput, Validation
from qv.db.session import Database
from qv.pipeline.structural import normalise_text
from qv.services import workflow

#: Minimum wording similarity (0–1) for a pair with the same answer / with different answers.
SAME_ANSWER_MIN = 0.45
SAME_QUESTION_MIN = 0.8
#: Answers count as the same at this token-set similarity (0–100), when their numbers are equal.
ANSWER_MIN = 90
ACTIONS = ("same_fact", "different_fact", "ignore", "clear")
ACTION_LABEL = {"same_fact": "same fact", "different_fact": "different facts", "ignore": "ignored", "": "—"}

#: Words that never decide whether two questions are about the same fact.
#: Question words (who, when, where, how …) are kept: "When did he die?" and "Where did he die?" are two facts.
_STOP = set("""a an the of in on at to for from by with and or is are was were be been which whom whose what did
does do this that these those it its his her their he she they as into than then there one name named called""".split())
#: Honorifics and titles, written in many ways in the editions.
_HONORIFIC = set("""hadhrat hazrat hz as ra sa saw rh aba pbuh alaihis salam alaihissalam radiallahu anhu anha
sallallahu alaihi wasallam rahimahullah ayyadahullah""".split())


def tokens(text: str) -> list[str]:
    """Words that carry meaning: normalised, without stop words and honorifics; plural -s removed."""
    out = []
    for w in normalise_text(text).split():
        if w in _STOP or w in _HONORIFIC:
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def normalise_answer(text: str) -> str:
    """An answer for comparing: normalised, honorifics and articles removed."""
    return " ".join(w for w in normalise_text(text).split() if w not in _HONORIFIC and w not in {"a", "an", "the"})


def answers_match(a: str, b: str, equivalents: tuple[set[str], set[str]] = (set(), set())) -> bool:
    """True when two answers say the same: equal after normalising, an accepted equivalent of the other, or nearly
    equal with the same numbers."""
    na, nb = normalise_answer(a), normalise_answer(b)
    if not na or not nb:
        return False
    if na == nb or na in equivalents[1] or nb in equivalents[0]:
        return True
    same_numbers = re.findall(r"\d+", na) == re.findall(r"\d+", nb)
    if same_numbers and fuzz.token_sort_ratio(na, nb) >= ANSWER_MIN:
        return True
    short, long_ = sorted((na, nb), key=len)
    if (len(short) < 3 and not short.isdigit()) or re.search(rf"\b{re.escape(short)}\b", long_) is None:
        return False
    # one answer inside the other: only when it is a good part of it ("Hawwa" in "Hawwa Eve"), or a year / date
    # inside a short date ("1908" in "26 May 1908") — not a word inside a long description
    n_short, n_long = len(short.split()), len(long_.split())
    if same_numbers and n_short / n_long >= 0.4:
        return True
    return all(w.isdigit() for w in short.split()) and n_long <= 6


def _tfidf(docs: list[list[str]]) -> list[dict[str, float]]:
    """Unit-length TF-IDF vectors (smoothed idf)."""
    df = Counter(w for d in docs for w in set(d))
    n = len(docs)
    out = []
    for d in docs:
        tf = Counter(d)
        v = {w: (1 + math.log(c)) * (math.log((1 + n) / (1 + df[w])) + 1) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        out.append({w: x / norm for w, x in v.items()})
    return out


def _cos(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


# --- data ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QRef:
    """One question in one file, by its exact wording."""

    dataset: str
    dataset_id: int
    ext_id: str
    content_hash: str

    @property
    def label(self) -> str:
        """e.g. 'swab-quest #127'"""
        return f"{self.dataset} #{self.ext_id}"


@dataclass
class QInfo:
    """A question with what is known about it."""

    ref: QRef
    question: str
    answer: str
    status: str
    verdict: str
    claim_type: str = ""
    information_need: str = ""
    equivalents: set[str] = field(default_factory=set)


@dataclass
class FactPair:
    """Two questions that are probably about the same fact."""

    a: QInfo
    b: QInfo
    similarity: float
    same_answer: bool
    differences: list[str]
    decision: str = ""
    decision_reason: str = ""
    decided_at: datetime | None = None

    @property
    def key(self) -> str:
        """Stable id of the pair (both questions' exact wording)."""
        return pair_key(self.a.ref, self.b.ref)

    @property
    def kind(self) -> str:
        """'same answer' or 'other answer'."""
        return "same answer" if self.same_answer else "other answer"

    @property
    def differs(self) -> bool:
        """True when the answers, verdicts or claim types differ."""
        return bool(self.differences)


def pair_key(a: QRef, b: QRef) -> str:
    """Order-independent key of two question refs."""
    x, y = sorted((f"{a.dataset}#{a.ext_id}@{a.content_hash}", f"{b.dataset}#{b.ext_id}@{b.content_hash}"))
    return f"{x}|{y}"


def _research_extras(db: Database, validation_ids: list[int]) -> dict[int, tuple[str, str, set[str]]]:
    """validation id → (claim type, S1a information need, S1b answer equivalents) from stored research."""
    if not validation_ids:
        return {}
    out: dict[int, tuple[str, str, set[str]]] = {}
    with db.session() as s:
        rows = list(s.execute(select(Validation.id, Validation.claim_type, RunQuestion.stats_json)
                              .join(RunQuestion, (RunQuestion.run_id == Validation.run_id)
                                    & (RunQuestion.question_id == Validation.question_id))
                              .where(Validation.id.in_(validation_ids))))
        ids = {i for _, _, st in rows for i in (st.get("s1a_output_id"), st.get("s1b_output_id")) if i}
        outputs = {o.id: o.output_json or {} for o in s.scalars(select(StageOutput).where(StageOutput.id.in_(ids)))}
    for vid, claim_type, st in rows:
        s1a = outputs.get(st.get("s1a_output_id"), {})
        s1b = outputs.get(st.get("s1b_output_id"), {})
        eq = {normalise_answer(e) for e in s1b.get("answer_equivalents") or [] if e}
        out[vid] = (claim_type or s1a.get("claim_type") or "", s1a.get("information_need") or "", eq)
    return out


def load_questions(db: Database, datasets: list[str] | None = None) -> list[QInfo]:
    """The latest version's questions of every edition file (or the named ones), with result and research."""
    names = datasets if datasets is not None else workflow.dataset_names(db)
    with db.session() as s:
        ids = {d.name: d.id for d in s.scalars(select(Dataset).where(Dataset.name.in_(names)))}
    out: list[tuple[QInfo, int | None]] = []
    for name in names:
        for st in workflow.question_states(db, name):
            if st.status == "format_error" or not st.question:
                continue
            out.append((QInfo(QRef(name, ids[name], st.ext_id, st.content_hash), st.question, st.answer_text,
                              st.status, st.verdict), st.validation_id))
    extras = _research_extras(db, [v for _, v in out if v])
    for q, vid in out:
        if vid in extras:
            q.claim_type, q.information_need, q.equivalents = extras[vid]
    return [q for q, _ in out]


def decisions(db: Database) -> dict[str, dict]:
    """Newest decision per pair key (a `clear` removes it): {key: {action, reason, who, when}}."""
    out: dict[str, dict] = {}
    with db.session() as s:
        names = _dataset_names(s)
        for d in s.scalars(select(FactPairDecision).order_by(FactPairDecision.id)):
            key = _decision_key(names, d)
            if d.action == "clear":
                out.pop(key, None)
            else:
                out[key] = {"action": d.action, "reason": d.reason, "who": d.who, "when": d.created_at}
    return out


def _decision_key(names: dict[int, str], d: FactPairDecision) -> str:
    return pair_key(QRef(names[d.a_dataset_id], d.a_dataset_id, d.a_ext_id, d.a_content_hash),
                    QRef(names[d.b_dataset_id], d.b_dataset_id, d.b_ext_id, d.b_content_hash))


def _dataset_names(s) -> dict[int, str]:  # noqa: ANN001
    return {d.id: d.name for d in s.scalars(select(Dataset))}


def differences(a: QInfo, b: QInfo, same_answer: bool) -> list[str]:
    """What differs between two questions about the same fact, in words."""
    out = []
    if not same_answer:
        out.append(f"answers: “{a.answer}” vs “{b.answer}”")
    if a.verdict and b.verdict and a.verdict != b.verdict:
        out.append(f"results: {a.verdict} vs {b.verdict}")
    if a.claim_type and b.claim_type and a.claim_type != b.claim_type:
        out.append(f"kind of fact: {a.claim_type.replace('_', ' ')} vs {b.claim_type.replace('_', ' ')}")
    return out


def find_pairs(db: Database, datasets: list[str] | None = None, *,
               questions: list[QInfo] | None = None) -> list[FactPair]:
    """Every probable same-fact pair, most similar first, with the person's newest decision."""
    qs = questions if questions is not None else load_questions(db, datasets)
    if len(qs) < 2:
        return []
    vec_q = _tfidf([tokens(q.question) for q in qs])
    has_need = [i for i, q in enumerate(qs) if q.information_need]
    vec_n: dict[int, dict[str, float]] = dict(zip(has_need, _tfidf([tokens(qs[i].information_need)
                                                                    for i in has_need]), strict=True))
    index: dict[str, set[int]] = {}
    for i, v in enumerate(vec_q):
        for w in v:
            index.setdefault(w, set()).add(i)
    decided = decisions(db)
    pairs: list[FactPair] = []
    for i, a in enumerate(qs):
        near = sorted({j for w in vec_q[i] for j in index[w] if j > i})
        for j in near:
            b = qs[j]
            sim = _cos(vec_q[i], vec_q[j])
            if i in vec_n and j in vec_n:
                sim = max(sim, _cos(vec_n[i], vec_n[j]))
            if sim < SAME_ANSWER_MIN:
                continue
            same = answers_match(a.answer, b.answer, (a.equivalents, b.equivalents))
            if not same and (sim < SAME_QUESTION_MIN or set(vec_q[i]) != set(vec_q[j])):
                continue
            p = FactPair(a, b, round(sim, 3), same, differences(a, b, same))
            d = decided.get(p.key)
            if d:
                p.decision, p.decision_reason, p.decided_at = d["action"], d["reason"], d["when"]
            pairs.append(p)
    pairs.sort(key=lambda p: (-p.similarity, p.a.ref.label, p.b.ref.label))
    return pairs


#: Groups on the page: key → label.
GROUPS = {
    "differ": "Different result",
    "undecided": "Not decided yet",
    "same_fact": "Same fact (you)",
    "set_aside": "Different facts / ignored",
    "all": "All pairs",
}
GROUP_HELP = {
    "differ": "Pairs about the same fact whose answers, results or kind of fact differ — and that you have not "
              "called different facts or ignored. Look at these first.",
    "undecided": "Every pair you have not decided on yet.",
    "same_fact": "Pairs you decided are about the same fact.",
    "set_aside": "Pairs you decided are different facts, or chose to ignore.",
    "all": "Every pair found.",
}


def in_group(p: FactPair, group: str) -> bool:
    """True when a pair belongs to a page group."""
    return {"differ": p.differs and p.decision in ("", "same_fact"), "undecided": not p.decision,
            "same_fact": p.decision == "same_fact", "set_aside": p.decision in ("different_fact", "ignore"),
            "all": True}[group]


def record_decision(db: Database, a: QRef, b: QRef, action: str, *, reason: str = "", who: str = "you") -> int:
    """Store a decision about a pair (append-only). Returns its id."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown action {action!r}; one of {ACTIONS}")
    x, y = sorted((a, b), key=lambda r: (r.dataset, r.ext_id, r.content_hash))
    with db.session() as s:
        row = FactPairDecision(a_dataset_id=x.dataset_id, a_ext_id=x.ext_id, a_content_hash=x.content_hash,
                               b_dataset_id=y.dataset_id, b_ext_id=y.ext_id, b_content_hash=y.content_hash,
                               action=action, reason=reason.strip(), who=who)
        s.add(row)
        s.flush()
        return row.id


def decision_history(db: Database, a: QRef, b: QRef) -> list[dict]:
    """Every decision about this pair, oldest first."""
    key = pair_key(a, b)
    with db.session() as s:
        names = _dataset_names(s)
        rows = list(s.scalars(select(FactPairDecision).where(
            FactPairDecision.a_ext_id.in_((a.ext_id, b.ext_id)), FactPairDecision.b_ext_id.in_((a.ext_id, b.ext_id)))
            .order_by(FactPairDecision.id)))
        return [{"action": d.action, "reason": d.reason, "who": d.who,
                 "when": d.created_at.strftime("%Y-%m-%d %H:%M")} for d in rows if _decision_key(names, d) == key]


def counts(pairs: list[FactPair]) -> dict[str, int]:
    """Pairs per page group."""
    return {g: sum(1 for p in pairs if in_group(p, g)) for g in GROUPS}
