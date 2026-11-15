"""Evaluation set: labelled cases, seeded errors and a sampler for labelling.

METHODOLOGY.md §12: the tool is only trusted as far as it is measured. This
module manages the inputs of that measurement; scoring runs against verdicts
arrive with the judgement phase.

- `eval/cases.yaml`         hand-written expectations (methodology §11 + known errors)
- `eval/known_errors.csv`   real errors from the editions' history (before they were fixed)
- `eval/seeded.csv` + `eval/seeded_labels.yaml`
                            deliberate errors made by editing correct questions,
                            generated deterministically by `generate_seeded_errors`
"""

from __future__ import annotations

import random
import re
from collections import defaultdict
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from qv.config import PROJECT_ROOT
from qv.domain.question import OPTION_COLUMNS, STANDARD_COLUMNS, Question
from qv.io.csv_format import js_trim, parse_csv, quote_value

EVAL_DIR = PROJECT_ROOT / "eval"
EDITIONS_DIR = PROJECT_ROOT.parent / "game_editions"
KNOWN_ERRORS_DATASET = "eval-known-errors"
VERDICTS = ("VERIFIED", "INCORRECT", "AMBIGUOUS", "CONTESTED", "OUTDATED", "UNVERIFIED")


class Expectation(BaseModel):
    """Expected outcome for one case. Either `verdict` or `any_of` is set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: str | None = None
    any_of: tuple[str, ...] = ()
    defect: str | None = None
    review: str | None = None
    note_status: str | None = None
    within_frame: bool | None = None
    contested_outside_frame: bool | None = None

    @model_validator(mode="after")
    def _check(self) -> "Expectation":
        """Exactly one of verdict / any_of, using known verdict names."""
        if (self.verdict is None) == (not self.any_of):
            raise ValueError("set exactly one of 'verdict' or 'any_of'")
        for v in ((self.verdict,) if self.verdict else self.any_of):
            if v not in VERDICTS:
                raise ValueError(f"unknown verdict {v!r}")
        return self

    def accepts(self, verdict: str) -> bool:
        """True when `verdict` meets this expectation."""
        return verdict == self.verdict if self.verdict else verdict in self.any_of


class EvalCase(BaseModel):
    """One labelled question."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: str
    id: str
    question_starts_with: str
    status: str = Field(pattern="^(hypothesis|confirmed)$")
    expect: Expectation
    why: str = ""


def load_cases(path: Path = EVAL_DIR / "cases.yaml") -> list[EvalCase]:
    """Load and validate the hand-written cases."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [EvalCase.model_validate(c) for c in data.get("cases", [])]


def dataset_path(dataset: str) -> Path:
    """CSV file behind a case's dataset name."""
    if dataset == KNOWN_ERRORS_DATASET:
        return EVAL_DIR / "known_errors.csv"
    return EDITIONS_DIR / dataset / "questions.csv"


def load_questions(path: Path) -> dict[str, Question]:
    """Questions of a CSV keyed by id (first occurrence)."""
    parsed = parse_csv(path.read_bytes())
    out: dict[str, Question] = {}
    for row in parsed.rows:
        q = Question.from_row(row, parsed.header)
        out.setdefault(q.ext_id, q)
    return out


def check_case_targets(cases: list[EvalCase]) -> list[str]:
    """Problems with cases whose row is missing or whose text no longer matches the guard."""
    problems: list[str] = []
    cache: dict[str, dict[str, Question]] = {}
    for c in cases:
        path = dataset_path(c.dataset)
        if not path.is_file():
            problems.append(f"{c.dataset}#{c.id}: no file {path}")
            continue
        questions = cache.setdefault(c.dataset, load_questions(path))
        q = questions.get(c.id)
        if q is None:
            problems.append(f"{c.dataset}#{c.id}: id not found")
        elif not q.question.startswith(c.question_starts_with):
            problems.append(f"{c.dataset}#{c.id}: question now reads {q.question[:60]!r}")
    return problems


# ---------------------------------------------------------------------------
# Seeded errors
# ---------------------------------------------------------------------------

class Mutation(StrEnum):
    """Kinds of deliberate error (METHODOLOGY.md §12)."""

    WRONG_KEY = "wrong_key"              # multi: key moved to a distractor
    WRONG_YEAR_ANSWER = "wrong_year_answer"
    WRONG_YEAR_QUESTION = "wrong_year_question"   # false premise
    WRONG_NUMBER_ANSWER = "wrong_number_answer"
    WRONG_VERSE_IN_NOTE = "wrong_verse_in_note"


class SeededLabel(BaseModel):
    """Label of one seeded question: where it came from and what must be caught."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    eval_id: str
    source_dataset: str
    source_id: str
    mutation: Mutation
    field: str
    original: str
    seeded: str
    expect: Expectation


_YEAR = re.compile(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)")
_NUMBER = re.compile(r"(?<![\d:.,])(\d{1,3})(?![\d:])")
_VERSE = re.compile(r"(\d{1,3}):(\d{1,3})(?![\d\-–])")


def _shift_year(text: str, rng: random.Random) -> str | None:
    """Change the first plausible year by 1–9 years; None when there is no year."""
    m = _YEAR.search(text)
    if not m:
        return None
    year = int(m.group(1))
    new = year + rng.choice([-1, 1]) * rng.randint(1, 9)
    return text[:m.start()] + str(new) + text[m.end():]


def _shift_number(text: str, rng: random.Random) -> str | None:
    """Change the first small non-year number; None when there is none."""
    if _YEAR.search(text):
        return None
    m = _NUMBER.search(text)
    if not m:
        return None
    n = int(m.group(1))
    new = n + rng.randint(1, 3) if n < 10 else n + rng.choice([-1, 1]) * rng.randint(2, max(3, n // 5))
    return text[:m.start()] + str(max(new, 0)) + text[m.end():]


def _mutations_for(q: Question, rng: random.Random) -> list[tuple[Mutation, str, str, str, Expectation]]:
    """Possible (mutation, field, original, seeded, expectation) edits of one question."""
    out: list[tuple[Mutation, str, str, str, Expectation]] = []
    incorrect_answer = Expectation(verdict="INCORRECT", defect="answer", review="needs_review")
    if q.is_multi and q.answer_index is not None:
        others = [i for i, o in enumerate(q.options) if o and i != q.answer_index]
        if others:
            new = str(rng.choice(others) + 1)
            out.append((Mutation.WRONG_KEY, "answer", q.answer, new, incorrect_answer))
    key_field = OPTION_COLUMNS[q.answer_index] if q.is_multi and q.answer_index is not None else "answer"
    key_text = q.resolved_answer_text or ""
    if (new := _shift_year(key_text, rng)) is not None:
        out.append((Mutation.WRONG_YEAR_ANSWER, key_field, key_text, new, incorrect_answer))
    elif (new := _shift_number(key_text, rng)) is not None and new != key_text:
        out.append((Mutation.WRONG_NUMBER_ANSWER, key_field, key_text, new, incorrect_answer))
    if (new := _shift_year(q.question, rng)) is not None:
        out.append((Mutation.WRONG_YEAR_QUESTION, "question", q.question, new,
                    # A changed year can falsify the premise or make the key wrong for that date.
                    Expectation(verdict="INCORRECT", review="needs_review")))
    m = _VERSE.search(q.note)
    if m:
        verse = int(m.group(2)) + rng.randint(3, 9)
        new = q.note[:m.start(2)] + str(verse) + q.note[m.end(2):]
        # The question can stay right; the note must be flagged.
        out.append((Mutation.WRONG_VERSE_IN_NOTE, "note", q.note, new,
                    Expectation(any_of=("VERIFIED", "UNVERIFIED"), note_status="contradicted",
                                review="needs_review")))
    return out


def generate_seeded_errors(sources: dict[str, dict[str, Question]], *, seed: int = 20261115,
                           per_mutation: int = 10) -> tuple[bytes, list[SeededLabel]]:
    """Build a seeded-error CSV (game format) and its labels.

    `sources` maps dataset name → questions. Only questions without known
    problems should be passed in. Deterministic for a given seed and input.
    Eval ids are 1..N in this file only (game ids are never changed).
    """
    rng = random.Random(seed)
    candidates: dict[Mutation, list[tuple[str, Question, str, str, str, Expectation]]] = defaultdict(list)
    for dataset in sorted(sources):
        for ext_id in sorted(sources[dataset], key=lambda i: (len(i), i)):
            q = sources[dataset][ext_id]
            for mutation, field, original, seeded, expect in _mutations_for(q, rng):
                candidates[mutation].append((dataset, q, field, original, seeded, expect))

    lines = [",".join(STANDARD_COLUMNS)]
    labels: list[SeededLabel] = []
    for mutation in Mutation:
        pool = candidates.get(mutation, [])
        chosen = rng.sample(pool, min(per_mutation, len(pool)))
        for dataset, q, field, original, seeded, expect in chosen:
            eval_id = str(len(labels) + 1)
            values = {c: js_trim(q.raw.get(c, "")) for c in STANDARD_COLUMNS}
            values["id"] = eval_id
            values[field] = seeded
            lines.append(",".join(quote_value(values[c]) for c in STANDARD_COLUMNS))
            labels.append(SeededLabel(eval_id=eval_id, source_dataset=dataset, source_id=q.ext_id,
                                      mutation=mutation, field=field, original=original, seeded=seeded,
                                      expect=expect))
    return ("\n".join(lines) + "\n").encode("utf-8"), labels


def labels_to_yaml(labels: list[SeededLabel]) -> str:
    """Serialise seeded labels as YAML (stable order)."""
    return yaml.safe_dump({"seeded": [lb.model_dump(mode="json", exclude_none=True) for lb in labels]},
                          sort_keys=False, allow_unicode=True, width=120)


def load_seeded_labels(path: Path = EVAL_DIR / "seeded_labels.yaml") -> list[SeededLabel]:
    """Load seeded labels written by `labels_to_yaml`."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [SeededLabel.model_validate(x) for x in data.get("seeded", [])]


# ---------------------------------------------------------------------------
# Sampling questions for human labelling
# ---------------------------------------------------------------------------

def stratified_sample(sources: dict[str, dict[str, Question]], *, n: int = 150, seed: int = 20261115,
                      always: set[tuple[str, str]] | None = None) -> list[tuple[str, Question]]:
    """Pick about `n` questions spread over (dataset, category, type).

    Every stratum gets at least one question while the budget allows; the rest
    is allocated in proportion to stratum size. `always` (dataset, id) pairs
    are included first (e.g. the cases in cases.yaml).
    """
    rng = random.Random(seed)
    always = always or set()
    picked: list[tuple[str, Question]] = []
    taken: set[tuple[str, str]] = set()
    for ds, ext_id in sorted(always):
        if ext_id in sources.get(ds, {}):
            picked.append((ds, sources[ds][ext_id]))
            taken.add((ds, ext_id))

    strata: dict[tuple[str, str, str], list[Question]] = defaultdict(list)
    for ds in sorted(sources):
        for q in sources[ds].values():
            if (ds, q.ext_id) not in taken:
                strata[(ds, q.category, q.type)].append(q)
    budget = max(0, n - len(picked))
    total = sum(len(v) for v in strata.values()) or 1
    keys = sorted(strata)
    rng.shuffle(keys)
    quota = {k: (1 if i < budget else 0) for i, k in enumerate(keys)}
    remaining = budget - sum(quota.values())
    for k in sorted(keys):
        quota[k] += int(remaining * len(strata[k]) / total)
    leftover = budget - sum(quota.values())
    for k in sorted(keys, key=lambda k: -len(strata[k])):
        if leftover <= 0:
            break
        if quota[k] < len(strata[k]):
            quota[k] += 1
            leftover -= 1
    for k in sorted(keys):
        pool = sorted(strata[k], key=lambda q: (len(q.ext_id), q.ext_id))
        for q in rng.sample(pool, min(quota[k], len(pool))):
            picked.append((k[0], q))
    return picked
