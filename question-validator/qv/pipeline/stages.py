"""Model stages S1a, S1b and S3: prompt rendering, code checks and cached execution.

What each stage may see is enforced here, by what the render functions put in the
prompt (METHODOLOGY.md §3): S1a and S3 never receive the key; S1a never receives
the note; S3 mode A never receives note claims.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import select

from qv.config import Profile
from qv.db.models import StageOutput
from qv.db.session import Database
from qv.domain.question import OPTION_LETTERS, Question
from qv.domain.stages import SCHEMA_VERSION, ClaimFormulation, Decomposition, Extraction
from qv.providers.llm.base import LLMRefusal, LLMSchemaError, ModelPool
from qv.providers.usage import CallContext

T = TypeVar("T", bound=BaseModel)

PROMPT_VERSIONS = {"s1a": "s1a.v1", "s1b": "s1b.v1", "s3": "s3.v1", "s4": "s4.v1", "s5": "s5.v1", "s6": "s6.v1"}
CLAIM_TYPES = ("scripture_content | hadith_or_tradition | attribution | doctrine | historical_event | biography |\n"
               "            measurement_or_superlative | statistic_current | sports_record | "
               "definition_or_meaning |\n            classification_or_list | geography_fact | science_fact | other")


@cache
def system_prompt(version: str) -> str:
    """Text of a versioned system prompt (qv/prompts/<version>.system.txt)."""
    return resources.files("qv.prompts").joinpath(f"{version}.system.txt").read_text(encoding="utf-8").strip()


_IF_BLOCK = re.compile(r"\{\{#if (\w+)\}\}(.*?)\{\{/if\}\}", re.S)
_VAR = re.compile(r"\{\{(\w+)\}\}")


def fill_template(text: str, values: dict[str, Any]) -> str:
    """Fill `{{name}}` and `{{#if name}}…{{/if}}` in a system prompt; an unknown name is an error."""
    text = _IF_BLOCK.sub(lambda m: m.group(2) if values.get(m.group(1)) else "", text)

    def var(m: re.Match[str]) -> str:
        if m.group(1) not in values:
            raise KeyError(f"System prompt placeholder {{{{{m.group(1)}}}}} has no value")
        return str(values[m.group(1)])

    return _VAR.sub(var, text)


# --- rendering ----------------------------------------------------------------

def _frame_summary(profile: Profile) -> tuple[str, str]:
    frame = f"{profile.frame.name}" if profile.frame else "none"
    conventions = "; ".join(f"{k}: {v}" for k, v in profile.conventions.items()) or "none"
    return frame, conventions


def _options_block(q: Question) -> str:
    return "\n".join(f"{OPTION_LETTERS[i]}. {o}" for i, o in enumerate(q.options) if o)


def render_s1a(q: Question, profile: Profile) -> str:
    """S1a user message: question and UNMARKED options only — no key, no note."""
    frame, conventions = _frame_summary(profile)
    lines = [
        f"Edition: {profile.edition} — frame: {frame}; conventions: {conventions}",
        f"Category: {q.category} > {q.subcategory} > {q.topic}    Difficulty: {q.difficulty}    Type: {q.type}",
        "",
        f"Question: {q.question}",
    ]
    if q.is_multi:
        lines += ["Options (unmarked, the correct one is not indicated):", _options_block(q)]
    lines += ["", "Definitions:", f"claim_type: {CLAIM_TYPES}",
              "frame_class: universal | tradition_general | attribution_to_frame | frame_specific"]
    return "\n".join(lines)


def render_s1b(q: Question, profile: Profile, s1a: Decomposition) -> str:
    """S1b user message: sees the key and the note (no evidence)."""
    frame, conventions = _frame_summary(profile)
    lines = [f"Edition: {profile.edition} — frame: {frame}; conventions: {conventions}",
             f"Question: {q.question}"]
    if q.is_multi:
        opts = "  ".join(f"{OPTION_LETTERS[i]}. {o}" for i, o in enumerate(q.options) if o)
        idx = q.answer_index
        lines += [f"Options: {opts}",
                  f"Expected answer: {OPTION_LETTERS[idx] if idx is not None else '?'}. {q.resolved_answer_text}"]
    else:
        lines.append(f"Expected answer: {q.resolved_answer_text}")
    lines += [f"Note: {q.note or '(none)'}", "", "Decomposition (from an answer-blind step):",
              s1a.model_dump_json(indent=2)]
    return "\n".join(lines)


@dataclass(frozen=True)
class DocMeta:
    """Document metadata shown to S3."""

    doc_id: int
    final_url: str
    title: str
    publisher: str
    fetched_at: str


def render_s3(q: Question, s1a: Decomposition, *, mode: str, doc: DocMeta, window: str,
              note_claims: list[tuple[str, str]] | None = None, feedback: str | None = None) -> str:
    """S3 user message for one document window. Mode A: presuppositions; mode B: note claims. Never the key."""
    lines = [f"Research question (information need): {s1a.information_need}",
             f"Answer type: {s1a.answer_type}"]
    if q.is_multi:
        lines.append("Options (unmarked): " + "  ".join(f"{OPTION_LETTERS[i]}. {o}"
                                                        for i, o in enumerate(q.options) if o))
    if mode == "A":
        if s1a.presuppositions:
            lines.append("Presuppositions to check:")
            lines += [f"{p.id}: {p.text}" for p in s1a.presuppositions]
    else:
        lines.append("Note claims to check:")
        lines += [f"{cid}: {text}" for cid, text in (note_claims or [])]
    lines += ["", f"Document metadata: id {doc.doc_id} · {doc.final_url} · title \"{doc.title}\" · "
                  f"publisher {doc.publisher} · fetched {doc.fetched_at}", "", "<document>", window, "</document>"]
    if feedback:
        lines += ["", feedback]
    return "\n".join(lines)


def windows(text: str, size: int, overlap: int, max_windows: int) -> list[str]:
    """Split long text into overlapping windows (at most `max_windows`)."""
    if len(text) <= size:
        return [text]
    out, start = [], 0
    while start < len(text) and len(out) < max_windows:
        out.append(text[start:start + size])
        start += size - overlap
    return out


# --- code checks ---------------------------------------------------------------

def check_s1a(out: Decomposition, q: Question) -> list[str]:
    """Problems with an S1a output that code can see (prompts/s1a 'Code checks')."""
    problems: list[str] = []
    queries = [x.q.lower() for x in out.queries]
    if not 3 <= len(out.queries) <= 6:
        problems.append(f"expected 3-6 queries, got {len(out.queries)}")
    if q.is_multi:
        options = [o for o in q.options if o and len(o) >= 3]
        named = [o for o in options if any(o.lower() in qq for qq in queries)]
        if named and len(named) < len(options):
            problems.append("queries name some options but not all (biased): " + ", ".join(named))
    for p in out.presuppositions:
        if p.material and not any(x.target == p.id for x in out.queries):
            problems.append(f"no query targets material presupposition {p.id}")
    if out.superlative.competitor_check_needed and not any(x.purpose == "competitor" for x in out.queries):
        problems.append("competitor check needed but no competitor query")
    return problems


def check_s1b(out: ClaimFormulation, q: Question) -> list[str]:
    """Direct lookups must use references written in the note (never invented)."""
    problems: list[str] = []
    note_refs = set(re.findall(r"\d{1,3}\s*:\s*\d{1,3}", q.note))
    note_refs = {r.replace(" ", "") for r in note_refs}
    for lk in out.direct_lookups:
        refs = {r.replace(" ", "") for r in re.findall(r"\d{1,3}\s*:\s*\d{1,3}", lk.ref)}
        if not refs or not refs <= note_refs:
            problems.append(f"lookup {lk.ref!r} is not a reference written in the note")
    return problems


def filter_s1b_lookups(out: ClaimFormulation, q: Question) -> ClaimFormulation:
    """Drop invented lookups (kept out of the pipeline even if the model insists)."""
    note_refs = {r.replace(" ", "") for r in re.findall(r"\d{1,3}\s*:\s*\d{1,3}", q.note)}
    kept = [lk for lk in out.direct_lookups
            if (refs := {r.replace(" ", "") for r in re.findall(r"\d{1,3}\s*:\s*\d{1,3}", lk.ref)})
            and refs <= note_refs]
    return out.model_copy(update={"direct_lookups": kept})


# --- execution ------------------------------------------------------------------

def input_hash(stage: str, prompt_version: str, inputs: Any) -> str:
    """Hash of everything that determines a stage's output (model excluded: pools may switch models)."""
    payload = json.dumps({"stage": stage, "prompt": prompt_version, "schema": SCHEMA_VERSION, "inputs": inputs},
                         sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class StageRun:
    """A stage output and where it came from."""

    output: BaseModel
    stage_output_id: int
    reused: bool
    model: str
    checks: list[str]


class StageRunner:
    """Runs a stage once per input hash; reuses stored valid outputs (resume, revalidation)."""

    def __init__(self, db: Database, pools: dict[str, ModelPool]) -> None:
        """`pools` maps stage name → ModelPool."""
        self.db = db
        self.pools = pools

    def run(self, *, stage: str, user: str, schema_cls: type[T], hash_inputs: Any, ctx: CallContext,
            checks: Callable[[T], list[str]] | None = None, retry_on_check_failure: bool = True,
            system_values: dict[str, Any] | None = None) -> StageRun:
        """Return a validated output for this input, from storage or from the model.

        `system_values` fill the system prompt's placeholders (S5, S6); they are part of the input hash.
        """
        version = PROMPT_VERSIONS[stage]
        h = input_hash(stage, version, {"in": hash_inputs, "sys": system_values} if system_values else hash_inputs)
        with self.db.session() as s:
            row = s.scalar(select(StageOutput).where(StageOutput.stage == stage, StageOutput.input_hash == h,
                                                     StageOutput.valid.is_(True))
                           .order_by(StageOutput.id.desc()).limit(1))
            if row is not None:
                return StageRun(schema_cls.model_validate(row.output_json), row.id, True, row.model,
                                row.checks_json)

        pool = self.pools[stage]
        system = fill_template(system_prompt(version), system_values or {})
        try:
            result = pool.complete(system=system, user=user, schema_cls=schema_cls, ctx=ctx)
            problems = checks(result.output) if checks else []
            if problems and retry_on_check_failure:
                feedback = ("\n\nA previous answer to this request had these problems; avoid them:\n- "
                            + "\n- ".join(problems))
                retry = pool.complete(system=system, user=user + feedback, schema_cls=schema_cls, ctx=ctx)
                retry_problems = checks(retry.output) if checks else []
                if len(retry_problems) <= len(problems):
                    result, problems = retry, retry_problems
        except (LLMSchemaError, LLMRefusal) as exc:
            self._store(ctx, stage, version, h, pool.last_provider, "", None, [], False, str(exc))
            raise
        sid = self._store(ctx, stage, version, h, result.provider, result.model,
                          result.output.model_dump(mode="json"), problems, True, None)
        return StageRun(result.output, sid, False, result.model, problems)

    def _store(self, ctx: CallContext, stage: str, version: str, h: str, provider: str, model: str,
               output: dict | None, checks: list[str], valid: bool, error: str | None) -> int:
        with self.db.session() as s:
            row = StageOutput(run_id=ctx.run_id, question_id=ctx.question_id, stage=stage, prompt_version=version,
                              schema_version=SCHEMA_VERSION, input_hash=h, provider=provider, model=model,
                              output_json=output, checks_json=checks, valid=valid, error=error)
            s.add(row)
            s.flush()
            return row.id


def s3_target_ids(s1a: Decomposition, mode: str, note_claim_ids: list[str]) -> set[str]:
    """Valid passage targets for a mode."""
    return {"need", *[p.id for p in s1a.presuppositions]} if mode == "A" else set(note_claim_ids)


__all__ = ["DocMeta", "StageRun", "StageRunner", "check_s1a", "check_s1b", "filter_s1b_lookups", "input_hash",
           "render_s1a", "render_s1b", "render_s3", "s3_target_ids", "system_prompt", "windows", "Extraction"]
