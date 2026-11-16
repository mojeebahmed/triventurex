"""Model stages S4 (blind answer), S5 (verification) and S6 (quality): prompts and code checks.

What each stage may see (METHODOLOGY.md §3) is enforced by these render functions:
- S4 gets the question, unmarked options, information need, presuppositions and mode-A
  passages — never the key, the note or note-claim passages.
- S5 gets everything, including S4's answer (S5b, later, will not).
- S6 gets the question, options, key and note — never evidence.
"""

from __future__ import annotations

import json

from qv.config import Profile
from qv.domain.question import OPTION_LETTERS, Question
from qv.domain.stages import BlindAnswer, ClaimFormulation, Decomposition, Quality, Verification
from qv.pipeline.evidence import EvidencePassage, passage_line
from qv.pipeline.stages import _frame_summary


def key_letter(q: Question) -> str | None:
    """The key as an option letter (multiple choice), else None."""
    idx = q.answer_index
    return OPTION_LETTERS[idx] if idx is not None else None


def present_letters(q: Question) -> list[str]:
    """Letters of the options that are filled in."""
    return [OPTION_LETTERS[i] for i, o in enumerate(q.options) if o]


def _options_line(q: Question) -> str:
    return "  ".join(f"{OPTION_LETTERS[i]}. {o}" for i, o in enumerate(q.options) if o)


# --- S4 -----------------------------------------------------------------------------

def blind_passages(passages: list[EvidencePassage]) -> list[EvidencePassage]:
    """The passages S4 may see: mode A only (note-claim passages could leak the answer)."""
    return [p for p in passages if p.mode == "A"]


def render_s4(q: Question, s1a: Decomposition, passages: list[EvidencePassage]) -> str:
    """S4 user message — no key, no note."""
    lines = [f"Question: {q.question}"]
    if q.is_multi:
        lines.append(f"Options (unmarked): {_options_line(q)}")
    lines.append(f"Information need: {s1a.information_need}")
    lines.append("Presuppositions:")
    lines += [f"{p.id}: {p.text}" for p in s1a.presuppositions] or ["(none)"]
    lines.append("Evidence passages:")
    lines += [passage_line(p) for p in blind_passages(passages)]
    return "\n".join(lines)


def _cited_s4(out: BlindAnswer) -> list[str]:
    ids = [*out.supporting_passages, *out.conflicting_passages]
    ids += [p for a in out.alternative_answers for p in a.passages]
    ids += [p for f in out.presupposition_findings for p in f.passages]
    return ids


def check_s4(out: BlindAnswer, q: Question, passages: list[EvidencePassage]) -> list[str]:
    """Code checks from prompts/s4: cited ids exist, an answer cites support, option fits."""
    shown = {p.pid for p in blind_passages(passages)}
    problems = []
    unknown = sorted(set(_cited_s4(out)) - shown)
    if unknown:
        problems.append(f"Cited passage ids that were not provided: {unknown}")
    if out.status == "answered" and not out.supporting_passages:
        problems.append("status 'answered' needs at least one supporting passage")
    if out.status == "answered" and q.is_multi and out.option not in present_letters(q):
        problems.append(f"multiple choice answer needs an option letter among {present_letters(q)}")
    if not q.is_multi and out.option is not None:
        problems.append("open question: option must be null")
    return problems


# --- S5 -----------------------------------------------------------------------------

def s4_summary(s4: BlindAnswer | None) -> str:
    """One line describing the blind answer, for the S5 system prompt."""
    if s4 is None:
        return "not available"
    if s4.status == "answered":
        opt = f" (option {s4.option})" if s4.option else ""
        return f"answered \"{s4.answer}\"{opt}, citing {', '.join(s4.supporting_passages)}"
    alts = "; ".join(f"\"{a.answer}\"" for a in s4.alternative_answers)
    return s4.status.replace("_", " ") + (f" — alternatives: {alts}" if alts else "")


def requirement_text(claim_type: str, requirements: dict[str, list[dict]]) -> str:
    """The §4 requirement in words, for the S5 system prompt."""
    words = {"p": "primary (P) origin", "s_or_better": "independent origins of tier S or better",
             "clusters": "independent origins", "frame_authority": "frame-authority origin"}
    alts = []
    for alt in requirements.get(claim_type) or requirements["other"]:
        parts = [f"{v} {words[k]}{'s' if v != 1 and k in ('p', 'frame_authority') else ''}"
                 for k, v in alt.items() if k in words]
        if alt.get("as_of"):
            parts.append("with an as-of date")
        alts.append(" and ".join(parts))
    return "at least " + " — or — at least ".join(alts)


def s5_system_values(q: Question, s1a: Decomposition, profile: Profile, s4: BlindAnswer | None,
                     requirements: dict[str, list[dict]]) -> dict[str, object]:
    """Values for the S5 system prompt's placeholders."""
    frame, conventions = _frame_summary(profile)
    if profile.frame and profile.frame.authorities:
        frame += f" (authorities: {', '.join(profile.frame.authorities)})"
    return {"blind": s4 is not None, "s4_summary": s4_summary(s4),
            "evidence_requirement": requirement_text(s1a.claim_type, requirements),
            "conventions_summary": conventions, "frame_summary": frame}


def render_s5(q: Question, s1a: Decomposition, s1b: ClaimFormulation, profile: Profile,
              passages: list[EvidencePassage]) -> str:
    """S5 user message — sees the key, the note and all passages."""
    lines = [f"Edition: {profile.edition}", f"Question ({q.type}, {q.difficulty}): {q.question}"]
    if q.is_multi:
        lines += [f"Options: {_options_line(q)}", f"Expected answer: {key_letter(q)}. {q.resolved_answer_text}"]
    else:
        lines.append(f"Expected answer: {q.resolved_answer_text}")
    ts = s1a.time_sensitivity
    as_of = f"(as of in question: {ts.as_of_in_question})" if ts.as_of_in_question else ""
    lines += [
        f"Key components: {json.dumps([c.model_dump() for c in s1b.key_components], ensure_ascii=False)}",
        f"Accepted equivalents: {', '.join(s1b.answer_equivalents) or '(none)'}",
        f"Claim type: {s1a.claim_type} · frame class: {s1a.frame_class} · time-sensitive: "
        f"{ts.is_time_sensitive} {as_of}".rstrip(),
        f"Presuppositions: {json.dumps([p.model_dump() for p in s1a.presuppositions], ensure_ascii=False)}",
        f"Note: {q.note or '(none)'}",
        "Note claims: " + json.dumps([n.model_dump() for n in s1b.note_claims if n.kind != "explanation"],
                                     ensure_ascii=False),
        "", "Evidence passages:",
    ]
    lines += [passage_line(p, with_target=True) for p in passages]
    return "\n".join(lines)


def _cited_s5(out: Verification) -> list[str]:
    ka = out.key_assessment
    ids = [*ka.supporting_passages, *ka.contradicting_passages]
    ids += [p for c in out.component_assessments for p in c.passages]
    ids += [p for o in out.option_assessments for p in o.passages]
    ids += [p for a in out.acceptable_alternatives for p in a.passages]
    ids += [p for d in out.disagreements for p in (*d.side_a_passages, *d.side_b_passages)]
    ids += [p for f in out.presupposition_findings for p in f.passages]
    ids += [p for f in out.note_findings for p in f.passages]
    ids += [*out.temporal.previously_true_passages, *out.temporal.change_passages]
    ids += [*out.frame.frame_passages, *out.frame.outside_passages]
    return ids


def check_s5(out: Verification, q: Question, passages: list[EvidencePassage]) -> list[str]:
    """Code checks from prompts/s5."""
    shown = {p.pid for p in passages}
    problems = []
    unknown = sorted(set(_cited_s5(out)) - shown)
    if unknown:
        problems.append(f"Cited passage ids that were not provided: {unknown}")
    if out.key_assessment.factual_accuracy == "CORRECT" and not out.key_assessment.supporting_passages:
        problems.append("CORRECT needs at least one supporting passage")
    for f in [*out.presupposition_findings, *out.note_findings, *out.component_assessments]:
        if f.status == "contradicted" and not f.passages:
            problems.append(f"{f.id}: 'contradicted' needs at least one passage")
    for d in out.disagreements:
        if not d.side_a_passages or not d.side_b_passages:
            problems.append(f"disagreement about {d.about}: cite passages on both sides")
    if q.is_multi:
        missing = set(present_letters(q)) - {o.option for o in out.option_assessments}
        if missing:
            problems.append(f"assess every option; missing {sorted(missing)}")
    return problems


# --- S6 -----------------------------------------------------------------------------

def s6_system_values(profile: Profile) -> dict[str, object]:
    """Values for the S6 system prompt's placeholders."""
    style = "; ".join(f"{k}: {v}" for k, v in profile.conventions.items()) or "no special conventions"
    return {"edition_name": profile.edition, "audience": profile.audience, "style_summary": style}


def render_s6(q: Question) -> str:
    """S6 user message — the question as players see it; no evidence."""
    lines = [f"Question ({q.type}, stated difficulty {q.difficulty}): {q.question}"]
    if q.is_multi:
        lines += [f"Options: {_options_line(q)}", f"Expected answer: {key_letter(q)}. {q.resolved_answer_text}"]
    else:
        lines.append(f"Expected answer: {q.resolved_answer_text}")
    lines += [f"Note shown to players after answering: {q.note or '(none)'}",
              f"Category: {q.category} > {q.subcategory} > {q.topic}"]
    return "\n".join(lines)


def check_s6(out: Quality, q: Question) -> list[str]:
    """A rewrite only for NEEDS_IMPROVEMENT / POOR; option letters must exist."""
    problems = []
    if out.overall == "GOOD" and out.suggested_rewrite is not None:
        problems.append("suggest a rewrite only for NEEDS_IMPROVEMENT or POOR")
    letters = present_letters(q) if q.is_multi else []
    bad = [i.option for i in out.issues if i.option is not None and i.option not in letters
           and i.type != "too_few_options"]
    if bad:
        problems.append(f"issues refer to options that do not exist: {bad}")
    return problems
