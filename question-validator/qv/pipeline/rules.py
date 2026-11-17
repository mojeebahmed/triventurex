"""S8 — the rules engine (METHODOLOGY.md §4, §9): structured findings in, verdict out. Pure code.

Models describe (S4 blind answer, S5 verification, S6 quality); this module decides.
It recounts origin clusters and tiers itself from the passages the verifier cites and
never trusts the model's own count. Every rule that fires adds a plain-words reason.

Interpretations of the methodology made here (rules version 1):
- One P cluster is STRONG where §4 says "1 P"; the single-origin cap of §5.2 is applied
  through the "≥ 2 clusters" alternatives, which one origin can never meet.
- For frame-specific claims and attributions to the frame, contradicting passages that
  are not frame authorities are context ("outside the frame"), not contradiction.
- A presupposition or key that S5 calls contradicted with evidence below the bar is not
  `contradicted` (no INCORRECT), but the question goes to review.
- Questions that end UNVERIFIED with no other flag are routed `needs_evidence`
  (candidates for the escalation round, §3 rule 5).

Rules version 2 (2026-11-17) — key components (S1b K1, K2 …, judged one by one by S5):
- VERIFIED needs every component `supported` with at least one grounded passage; the key as a
  whole still needs STRONG support. A component without an assessment, or `unclear`, is
  `unverified` (→ UNVERIFIED).
- A component S5 calls `supported` while its `evidence_value` carries numbers that differ from the
  asserted value (2003 vs 2006) is counted as `contradicted` — the model's own value wins over its
  label (swab seeded #20). Only numbers are compared; words are left to the model.
- Only components whose value is written in the expected answer count (`written_in`): S1b v1
  sometimes listed the note's verse reference as a component; the note is judged as a note.
- A `contradicted` component with STRONG evidence (for the question's claim type; outside-frame
  passages dropped as for the key) makes the answer INCORRECT; below the bar it goes to review.
  A definitional / convention disagreement about it makes it `definition_dependent` (→ AMBIGUOUS).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from qv.config import CONFIG_DIR
from qv.domain.stages import BlindAnswer, Quality, Verification
from qv.pipeline.evidence import TIER_ORDER, EvidencePassage

RULES_VERSION = "2"
LEVELS = ["NONE", "WEAK", "MODERATE", "STRONG"]
FRAME_CLASSES_JUDGED_IN_FRAME = {"frame_specific", "attribution_to_frame"}
REVIEW_VERDICTS = {"INCORRECT", "AMBIGUOUS", "CONTESTED", "OUTDATED"}


def load_requirements(path: Path = CONFIG_DIR / "evidence_requirements.yaml") -> dict[str, list[dict]]:
    """config/evidence_requirements.yaml: claim type → alternatives that count as STRONG."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --- strength ----------------------------------------------------------------------

@dataclass(frozen=True)
class Strength:
    """How well a set of passages supports something, counted by origin cluster."""

    level: str
    clusters: int
    p: int
    s_or_better: int
    frame_authority: int
    best_tier: str | None
    passages: tuple[str, ...]

    def at_least(self, level: str) -> bool:
        """True when this strength is `level` or better."""
        return LEVELS.index(self.level) >= LEVELS.index(level)

    def describe(self) -> str:
        """e.g. 'STRONG (2 independent origins, best tier P)'."""
        if not self.clusters:
            return "NONE"
        origins = f"{self.clusters} independent origin{'s' if self.clusters != 1 else ''}"
        return f"{self.level} ({origins}, best tier {self.best_tier})"


def strength(pids: list[str], passages: dict[str, EvidencePassage], claim_type: str,
             requirements: dict[str, list[dict]]) -> Strength:
    """Count clusters among the cited passages and compare with the claim type's requirement."""
    cited = [passages[p] for p in dict.fromkeys(pids) if p in passages]
    best: dict[str, str] = {}
    frame: set[str] = set()
    dated_p: set[str] = set()
    for p in cited:
        if p.cluster not in best or TIER_ORDER[p.tier] < TIER_ORDER[best[p.cluster]]:
            best[p.cluster] = p.tier
        if p.frame_authority and p.tier in ("P", "S"):
            frame.add(p.cluster)
        if p.tier == "P" and p.as_of:
            dated_p.add(p.cluster)
    n = len(best)
    p_count = sum(1 for t in best.values() if t == "P")
    s_count = sum(1 for t in best.values() if t in ("P", "S"))
    best_tier = min(best.values(), key=TIER_ORDER.__getitem__) if best else None

    def meets(alt: dict) -> bool:
        return ((len(dated_p) if alt.get("as_of") else p_count) >= alt.get("p", 0)
                and s_count >= alt.get("s_or_better", 0) and n >= alt.get("clusters", 0)
                and len(frame) >= alt.get("frame_authority", 0))

    alts = requirements.get(claim_type) or requirements["other"]
    if n and any(meets(a) for a in alts):
        level = "STRONG"
    elif n >= 2 or s_count:
        level = "MODERATE"
    elif n:
        level = "WEAK"
    else:
        level = "NONE"
    return Strength(level, n, p_count, s_count, len(frame), best_tier, tuple(p.pid for p in cited))


# --- inputs and outputs ---------------------------------------------------------------

@dataclass(frozen=True)
class PremiseInfo:
    """A presupposition from S1a."""

    id: str
    text: str
    claim_type: str
    frame_class: str
    material: bool


@dataclass(frozen=True)
class ComponentInfo:
    """A key component from S1b: one separately checkable part of the expected answer."""

    id: str
    text: str
    value: str


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_SEASON = re.compile(r"\b(\d{2})(\d{2})\s*[-–—/]\s*(\d{2})\b")


def numbers_in(text: str | None) -> set[str]:
    """Numbers written in a text, normalised: '1,000' → '1000', '8,5' → '8.5', '2022–23' → 2022 and 2023."""
    text = _SEASON.sub(lambda m: f"{m.group(1)}{m.group(2)} {m.group(1)}{m.group(3)}", text or "")
    out = set()
    for raw in _NUMBER.findall(text):
        if re.fullmatch(r"\d{1,3}(,\d{3})+", raw):
            raw = raw.replace(",", "")
        raw = raw.replace(",", ".")
        try:
            out.add(f"{float(raw):g}" if "." in raw else str(int(raw)))
        except ValueError:
            continue
    return out


def values_differ(asserted: str, evidence_value: str | None) -> bool:
    """True when the evidence's value names numbers and the asserted value's numbers are not among them."""
    mine, theirs = numbers_in(asserted), numbers_in(evidence_value)
    return bool(mine and theirs and not mine <= theirs)


def written_in(value: str, answer: str) -> bool:
    """True when a component's value is part of the expected answer: its numbers all appear there, or (without
    numbers) one of its words of 4+ letters does, or the whole value does. S1b sometimes lists the note's verse
    reference as a component; such a part is the note's, not the answer's."""
    mine = numbers_in(value)
    if mine:
        return mine <= numbers_in(answer)
    words = {w for w in re.findall(r"[^\W\d_]{4,}", value.casefold())}
    have = set(re.findall(r"[^\W\d_]{4,}", answer.casefold()))
    return bool(words & have) or value.strip().casefold() in answer.casefold()


@dataclass
class RulesInput:
    """Everything S8 needs; all model outputs are already validated."""

    run_id: int
    question_id: int
    is_multi: bool
    key_letter: str | None
    key_text: str
    claim_type: str
    frame_class: str
    as_of_in_question: str | None
    premises: list[PremiseInfo]
    note_claim_ids: list[str]
    passages: list[EvidencePassage]
    blind: BlindAnswer | None
    verification: Verification | None
    quality: Quality | None
    specialist_for: list[str] = field(default_factory=list)
    audit_percent: float = 3.0
    key_components: list[ComponentInfo] = field(default_factory=list)


@dataclass
class Judgement:
    """The S8 result for one question."""

    verdict: str
    defect_location: str | None
    evidence_strength: str
    factual_accuracy: str | None
    claim_statuses: dict[str, str]
    note_status: str | None
    note_statuses: dict[str, str]
    blind_status: str | None
    blind_answer: str | None
    blind_matches_key: bool | None
    within_frame: bool
    contested_outside_frame: bool
    quality: str | None
    routes: list[str]
    review_status: str
    reasons: list[str]
    suggested_answer: str | None
    suggested_question: str | None
    acceptable_alternatives: list[dict]
    support: dict[str, dict]
    rules_version: str = RULES_VERSION


# --- the rules ---------------------------------------------------------------------

def _short(text: str | None, n: int = 140) -> str:
    text = text or ""
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def _valid(pids: list[str], passages: dict[str, EvidencePassage]) -> list[str]:
    return [p for p in pids if p in passages]


def _better(a: Strength, b: Strength) -> bool:
    """True when `a` clearly outweighs `b`: better best tier, or same tier and more origins."""
    ta, tb = TIER_ORDER.get(a.best_tier or "", 9), TIER_ORDER.get(b.best_tier or "", 9)
    return ta < tb or (ta == tb and a.clusters > b.clusters)


def _status(sup: Strength, con: Strength) -> str:
    """Claim status from support and contradiction strength (§9.1)."""
    if con.level == "STRONG":
        if sup.level != "STRONG" or _better(con, sup):
            return "contradicted"
        return "supported" if _better(sup, con) else "contested"
    if sup.level == "STRONG":
        return "supported" if not con.at_least("MODERATE") else "supported_weak"
    if sup.at_least("WEAK") and LEVELS.index(sup.level) > LEVELS.index(con.level):
        return "supported_weak"
    return "unverified"


def judge(inp: RulesInput, requirements: dict[str, list[dict]]) -> Judgement:
    """Apply METHODOLOGY.md §9 to one question's findings."""
    pas = {p.pid: p for p in inp.passages}
    s4, s5, s6 = inp.blind, inp.verification, inp.quality
    reasons: list[str] = []
    review: list[str] = []
    in_frame = inp.frame_class in FRAME_CLASSES_JUDGED_IN_FRAME

    def drop_outside(pids: list[str], judged_in_frame: bool) -> list[str]:
        return [p for p in pids if pas[p].frame_authority] if judged_in_frame else pids

    # --- key claim
    if s5 is None:
        sup = con = strength([], pas, inp.claim_type, requirements)
        key_status = "unverified"
        reasons.append("No grounded evidence was found, so the answer could not be checked.")
    else:
        sup_ids = _valid(s5.key_assessment.supporting_passages, pas)
        con_ids = _valid(s5.key_assessment.contradicting_passages, pas)
        if inp.is_multi and inp.key_letter:
            dropped = [p for p in sup_ids if pas[p].matches_option not in (None, "none", inp.key_letter)]
            if dropped:
                reasons.append(f"Passages {', '.join(dropped)} were cited as support but point to another option; "
                               "not counted.")
            sup_ids = [p for p in sup_ids if p not in dropped]
            con_ids = [p for p in con_ids if pas[p].matches_option != inp.key_letter]
        con_ids = drop_outside(con_ids, in_frame)
        sup = strength(sup_ids, pas, inp.claim_type, requirements)
        con = strength(con_ids, pas, inp.claim_type, requirements)
        key_dis = [d for d in s5.disagreements if d.about == "key" or d.about.startswith("K")]
        if s5.temporal.outdated and _valid(s5.temporal.change_passages, pas) and not inp.as_of_in_question:
            key_status = "outdated"
            reasons.append("The evidence shows the answer has changed over time "
                           f"(passages {', '.join(_valid(s5.temporal.change_passages, pas))}).")
        elif any(d.kind in ("definitional", "convention") for d in key_dis) \
                and s5.key_assessment.factual_accuracy != "CORRECT":
            key_status = "definition_dependent"
            kinds = sorted({d.kind for d in key_dis if d.kind in ("definitional", "convention")})
            reasons.append(f"Sources disagree because of a {' / '.join(kinds)} difference the question does not "
                           "settle.")
        else:
            key_status = _status(sup, con)
        reasons.append(f"Support for the expected answer: {sup.describe()}"
                       + (f"; against it: {con.describe()}." if con.clusters else "."))
        if s5.key_assessment.factual_accuracy in ("INCORRECT", "PARTIALLY_CORRECT"):
            review.append(f"The verifier rates the expected answer {s5.key_assessment.factual_accuracy}.")
            if key_status not in ("contradicted", "contested", "outdated", "definition_dependent"):
                reasons.append("The verifier doubts the answer, but the evidence against it is below the bar "
                               f"for {inp.claim_type} claims.")
        if s5.evidence_requirement_met.met != (sup.level == "STRONG"):
            reasons.append(f"Note: the verifier's own view of the evidence requirement "
                           f"({'met' if s5.evidence_requirement_met.met else 'not met'}) differs from the "
                           "recount; the recount is used.")
    claim_statuses = {"K": key_status}

    # --- key components (rules v2)
    comp_status: dict[str, str] = {}
    comp_against: dict[str, Strength] = {}
    if s5 is not None and inp.key_components:
        assessed = {c.id: c for c in s5.component_assessments}
        for kc in inp.key_components:
            if not written_in(kc.value, inp.key_text):
                reasons.append(f"{kc.id} ('{_short(kc.text, 90)}': {_short(kc.value, 60)}) is not written in the "
                               "expected answer; not counted as a part of it.")
                continue
            ca = assessed.get(kc.id)
            label = f"{kc.id} ('{_short(kc.text, 90)}')"
            if ca is None:
                comp_status[kc.id] = "unverified"
                reasons.append(f"Part {label} of the expected answer was not assessed.")
                continue
            ids = _valid(ca.passages, pas)
            st = ca.status
            if st == "supported" and values_differ(kc.value, ca.evidence_value):
                st = "contradicted"
                reasons.append(f"Part {label}: the verifier calls it supported, but the value it found "
                               f"({_short(ca.evidence_value, 60)}) differs from the expected answer's "
                               f"({_short(kc.value, 60)}) — counted as contradicted.")
            dis = [d for d in s5.disagreements if d.about == kc.id]
            if st == "supported":
                if inp.is_multi and inp.key_letter:
                    ids = [p for p in ids if pas[p].matches_option in (None, "none", inp.key_letter)]
                status = "supported" if ids else "unverified"
            elif st == "contradicted":
                against = strength(drop_outside(ids, in_frame), pas, inp.claim_type, requirements)
                comp_against[kc.id] = against
                found = f" (the evidence gives {_short(ca.evidence_value, 60)})" if ca.evidence_value else ""
                if any(d.kind in ("definitional", "convention") for d in dis):
                    status = "definition_dependent"
                elif against.level == "STRONG":
                    status = "contradicted"
                    reasons.append(f"Part {label} of the expected answer is contradicted{found}: "
                                   f"{against.describe()}.")
                else:
                    status = "unverified"
                    review.append(f"The verifier finds part {label} of the expected answer contradicted{found}, "
                                  "with evidence below the bar.")
            else:
                status = "unverified"
            comp_status[kc.id] = status
        claim_statuses.update(comp_status)
    parts_contradicted = [k for k, v in comp_status.items() if v == "contradicted"]
    parts_unsupported = [k for k, v in comp_status.items() if v != "supported"]

    # --- presuppositions
    premise_status: dict[str, str] = {}
    findings = {f.id: f for f in s5.presupposition_findings} if s5 else {}
    for pr in inp.premises:
        f = findings.get(pr.id)
        if f is None:
            premise_status[pr.id] = "unverified"
            continue
        ids = _valid(f.passages, pas)
        judged_in_frame = pr.frame_class in FRAME_CLASSES_JUDGED_IN_FRAME
        dis = [d for d in s5.disagreements if d.about == pr.id] if s5 else []
        if f.status == "contradicted":
            st = strength(drop_outside(ids, judged_in_frame), pas, pr.claim_type, requirements)
            if any(d.kind in ("definitional", "convention") for d in dis):
                status = "definition_dependent"
            elif st.level == "STRONG":
                status = "contradicted"
            else:
                status = "unverified"
                review.append(f"The verifier finds {pr.id} ('{pr.text}') contradicted, with evidence below the "
                              "bar.")
            if status == "contradicted":
                reasons.append(f"{pr.id} ('{pr.text}') is contradicted: {st.describe()}.")
        elif f.status == "supported":
            st = strength(ids, pas, pr.claim_type, requirements)
            status = "supported" if st.level == "STRONG" else ("supported_weak" if st.at_least("WEAK")
                                                               else "unverified")
            if any(d.kind == "factual_conflict" for d in dis):
                other = strength(_valid([p for d in dis for p in d.side_b_passages], pas), pas, pr.claim_type,
                                 requirements)
                if status == "supported" and other.level == "STRONG":
                    status = "contested"
        else:
            status = "unverified"
        premise_status[pr.id] = status
    claim_statuses.update(premise_status)
    material = [pr for pr in inp.premises if pr.material]

    # --- note claims
    note_statuses: dict[str, str] = {}
    if s5:
        for nf in s5.note_findings:
            ids = _valid(nf.passages, pas)
            st = nf.status
            if st == "unclear" or (st in ("supported", "contradicted") and not ids):
                st = "unverified"
            note_statuses[nf.id] = st
    for cid in inp.note_claim_ids:
        note_statuses.setdefault(cid, "unverified")
    note_status = None
    for st in ("contradicted", "convention_mismatch", "unverified", "supported"):
        if st in note_statuses.values():
            note_status = st
            break
    if note_status == "contradicted":
        review.append("The note contradicts the evidence.")
        reasons.append("The note's claims " + ", ".join(k for k, v in note_statuses.items() if v == "contradicted")
                       + " are contradicted by the evidence.")

    # --- blind answer
    blind_matches: bool | None = None
    if s4 is not None:
        if s4.status == "answered":
            if inp.is_multi:
                blind_matches = s4.option == inp.key_letter
            else:
                blind_matches = bool(s5 and s5.key_assessment.match_with_blind in ("same", "equivalent"))
            if not blind_matches:
                review.append(f"The answer formed from the evidence without the key ({_short(s4.answer)}"
                              + (f", option {s4.option}" if s4.option else "") + ") differs from the expected "
                              f"answer ({_short(inp.key_text)}).")
        else:
            reasons.append(f"Answer formed from the evidence without the key: {s4.status.replace('_', ' ')}.")

    # --- ambiguity (§9.2 row 5)
    ambiguous = False
    if s5 and inp.is_multi:
        ok = [o.option for o in s5.option_assessments if o.status in ("correct", "defensible")
              and _valid(o.passages, pas)]
        if len(ok) >= 2:
            ambiguous = True
            reasons.append(f"More than one option is supported by the evidence: {', '.join(ok)}.")
    if s4 and not inp.is_multi and s4.status == "multiple_defensible":
        accepted = {a.answer.casefold() for a in (s5.acceptable_alternatives if s5 else [])}
        others = [a.answer for a in s4.alternative_answers if a.answer.casefold() not in accepted
                  and _valid(a.passages, pas)]
        if others:
            ambiguous = True
            reasons.append("The evidence supports more than one answer: " + "; ".join(others) + ".")
    definition_dependent = "definition_dependent" in claim_statuses.values()

    # --- verdict (§9.2, first matching row wins)
    defect = None
    if any(premise_status.get(pr.id) == "contradicted" for pr in inp.premises):
        verdict, defect = "INCORRECT", "question_premise"
    elif key_status == "contradicted":
        verdict, defect = "INCORRECT", "answer"
        reasons.append(f"The evidence against the expected answer outweighs the support ({con.describe()}).")
    elif parts_contradicted and key_status != "outdated":
        verdict, defect = "INCORRECT", "answer"
        reasons.append(f"Part(s) {', '.join(parts_contradicted)} of the expected answer are wrong, so the answer "
                       "is not right as written.")
    elif key_status == "outdated":
        verdict, defect = "OUTDATED", "answer"
    elif key_status == "contested" or "contested" in premise_status.values():
        verdict = "CONTESTED"
        reasons.append("Comparable evidence supports and contradicts the expected answer or a premise.")
    elif ambiguous or definition_dependent:
        verdict, defect = "AMBIGUOUS", ("options" if inp.is_multi and ambiguous else "question_wording")
    elif (key_status == "supported" and blind_matches is True
          and all(premise_status.get(pr.id) == "supported" for pr in material)
          and not parts_unsupported
          and s5 is not None and s5.key_assessment.factual_accuracy == "CORRECT"):
        verdict = "VERIFIED"
    else:
        verdict = "UNVERIFIED"
        if key_status == "supported" and blind_matches is not True:
            reasons.append("Not verified: the answer formed without the key did not independently reach the "
                           "expected answer.")
        weak = [pr.id for pr in material if premise_status.get(pr.id) != "supported"]
        if key_status == "supported" and weak:
            reasons.append(f"Not verified: premise(s) {', '.join(weak)} lack strong support.")
        if key_status == "supported" and parts_unsupported:
            reasons.append(f"Not verified: part(s) {', '.join(parts_unsupported)} of the expected answer are not "
                           "supported by the evidence.")

    # --- frame flags
    within_frame = bool(s5 and s5.frame.depends_on_frame and s5.frame.within_frame == "supported"
                        and (in_frame or inp.claim_type == "doctrine"))
    contested_outside = bool(s5 and s5.frame.contested_outside_frame and inp.frame_class != "attribution_to_frame")
    if within_frame:
        reasons.append("Judged within the edition's frame of reference"
                       + (", contested outside it." if contested_outside else "."))

    # --- quality
    quality = s6.overall if s6 else None
    if quality == "POOR":
        review.append("The question is rated POOR as a quiz question.")

    # --- routing (§9.3)
    routes: list[str] = []
    if verdict in REVIEW_VERDICTS:
        review.insert(0, f"Verdict {verdict}.")
    if review:
        routes.append("needs_review")
        reasons += [r for r in review if not r.startswith("Verdict ")]
    clean = verdict == "VERIFIED" and not review
    if not clean and (in_frame or inp.claim_type in inp.specialist_for or inp.frame_class in inp.specialist_for):
        routes.insert(0, "needs_specialist")
        reasons.append(f"Needs a specialist: {inp.claim_type} / {inp.frame_class} question without a clean "
                       "verification.")
    if clean and sup.level == "STRONG":
        h = int(hashlib.sha256(f"{inp.run_id}:{inp.question_id}".encode()).hexdigest(), 16)
        routes.append("audit_sample" if (h % 10000) < inp.audit_percent * 100 else "auto_ok")
    if not routes:
        routes.append("needs_evidence")
    return Judgement(
        verdict=verdict, defect_location=defect, evidence_strength=sup.level,
        factual_accuracy=s5.key_assessment.factual_accuracy if s5 else None,
        claim_statuses=claim_statuses, note_status=note_status, note_statuses=note_statuses,
        blind_status=s4.status if s4 else None, blind_answer=(s4.answer if s4 else None),
        blind_matches_key=blind_matches, within_frame=within_frame, contested_outside_frame=contested_outside,
        quality=quality, routes=routes, review_status=routes[0], reasons=reasons,
        suggested_answer=s5.suggested_answer if s5 else None,
        suggested_question=s5.suggested_question if s5 else None,
        acceptable_alternatives=[a.model_dump() for a in s5.acceptable_alternatives] if s5 else [],
        support={"key": {"for": sup.describe(), "against": con.describe(), "passages_for": list(sup.passages),
                         "passages_against": list(con.passages)},
                 **{kid: {"against": st.describe(), "passages_against": list(st.passages)}
                    for kid, st in comp_against.items()}},
    )
