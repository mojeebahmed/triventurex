"""S8 rules engine (pure) and origin clustering — METHODOLOGY.md §4, §5.2, §9."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from qv.domain.stages import BlindAnswer, Quality, Verification
from qv.pipeline.evidence import EvidencePassage, assign_clusters, number_passages
from qv.pipeline.rules import PremiseInfo, RulesInput, judge, load_requirements, strength

REQ = load_requirements()
WORDS = ["zero", "Alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo.",
         "Lima mike november oscar papa quebec romeo sierra tango uniform.",
         "Victor whiskey x-ray yankee zulu one two three four five six seven.",
         "Red orange yellow green blue indigo violet black white grey brown.",
         "Monday tuesday wednesday thursday friday saturday sunday january."]


def ev(pid: str, tier: str = "S", publisher: str = "pub", *, mode: str = "A", target: str = "need",
       origin: str | None = None, option: str | None = None, frame: bool = False, quote: str | None = None,
       as_of: str | None = None, domain: str | None = None) -> EvidencePassage:
    return EvidencePassage(pid=pid, passage_id=int(pid[1:]), mode=mode, target=target,
                           quote=quote or WORDS[int(pid[1:]) % len(WORDS)], tier=tier,
                           frame_authority=frame, publisher=publisher, domain=domain or f"{publisher}.org",
                           page_kind="reference_work", matches_option=option, attributed_origin=origin, as_of=as_of)


def blind(status: str = "answered", answer: str | None = "Tanzania", option: str | None = "B",
          supporting: list[str] | None = None, alternatives: list[dict] | None = None) -> BlindAnswer:
    return BlindAnswer(status=status, answer=answer, option=option, supporting_passages=supporting or ["P1"],
                       conflicting_passages=[], alternative_answers=alternatives or [], presupposition_findings=[],
                       missing_evidence=None, reasoning="r")


def verification(accuracy: str = "CORRECT", supporting: list[str] | None = None,
                 contradicting: list[str] | None = None, match: str = "same", **extra: Any) -> Verification:
    data: dict[str, Any] = {
        "key_assessment": {"factual_accuracy": accuracy, "match_with_blind": match,
                           "supporting_passages": supporting if supporting is not None else ["P1", "P2"],
                           "contradicting_passages": contradicting or []},
        "component_assessments": [],
        "evidence_requirement_met": {"met": True, "independent_origins_supporting": 2,
                                     "highest_tier_supporting": "S", "explanation": "e"},
        "option_assessments": [], "acceptable_alternatives": [], "disagreements": [],
        "presupposition_findings": [], "note_findings": [],
        "temporal": {"time_sensitive": False, "judged_as_of": None, "outdated": False,
                     "previously_true_passages": [], "change_passages": []},
        "frame": {"depends_on_frame": False, "within_frame": "not_applicable", "contested_outside_frame": False,
                  "frame_passages": [], "outside_passages": []},
        "suggested_answer": None, "suggested_question": None, "missing_evidence": None, "explanation": "x"}
    data.update(extra)
    return Verification.model_validate(data)


def quality(overall: str = "GOOD") -> Quality:
    return Quality(overall=overall, issues=[], difficulty_estimate="easy", audience_fit="good",
                   suggested_rewrite=None, rewrite_reason=None)


def inp(passages: list[EvidencePassage], **kw: Any) -> RulesInput:
    base: dict[str, Any] = dict(run_id=1, question_id=7, is_multi=True, key_letter="B", key_text="Tanzania",
                                claim_type="geography_fact", frame_class="universal", as_of_in_question=None,
                                premises=[], note_claim_ids=[], passages=assign_clusters(passages),
                                blind=blind(), verification=verification(), quality=quality(), audit_percent=0)
    base.update(kw)
    return RulesInput(**base)


TWO_SOURCES = [ev("P1", "S", "britannica", option="B"), ev("P2", "T", "wikipedia", option="B")]


# --- strength and clustering ------------------------------------------------------------

def test_five_sites_quoting_one_origin_are_one_origin() -> None:
    """World Tour #102: pages that all credit Ethnologue are one cluster, so never STRONG for a superlative."""
    ps = assign_clusters([ev(f"P{i}", "T", f"site{i}", origin="Ethnologue") for i in range(1, 6)])
    assert {p.cluster for p in ps} == {"C1"}
    st = strength([p.pid for p in ps], {p.pid: p for p in ps}, "measurement_or_superlative", REQ)
    assert (st.level, st.clusters) == ("WEAK", 1)


def test_copied_wording_across_sites_joins_clusters() -> None:
    text = "Mount Kilimanjaro is a dormant volcano located in Tanzania, near the border with Kenya."
    ps = assign_clusters([ev("P1", publisher="a", quote=text), ev("P2", publisher="b", quote=text + " Wow."),
                          ev("P3", publisher="c")])
    assert ps[0].cluster == ps[1].cluster != ps[2].cluster


def test_generic_origin_falls_back_to_publisher() -> None:
    ps = assign_clusters([ev("P1", publisher="x", origin="not specified"), ev("P2", publisher="x")])
    assert ps[0].cluster == ps[1].cluster


def test_numbering_puts_question_passages_first() -> None:
    ps = number_passages([replace(ev("P1", mode="B"), passage_id=1), replace(ev("P2"), passage_id=2)])
    assert [(p.pid, p.mode) for p in ps] == [("P1", "A"), ("P2", "B")]


@pytest.mark.parametrize("claim_type,tiers,level", [
    ("scripture_content", ["P"], "STRONG"),
    ("scripture_content", ["S", "S"], "MODERATE"),     # websites about the verse are not the verse
    ("geography_fact", ["T", "T"], "STRONG"),          # two independent tertiary origins (low-risk facts)
    ("historical_event", ["T", "T"], "MODERATE"),      # needs at least one S
    ("historical_event", ["S", "T"], "STRONG"),
    ("sports_record", ["S"], "MODERATE"),
    ("sports_record", ["T"], "WEAK"),
    ("doctrine", ["P"], "MODERATE"),                   # not a frame authority
])
def test_evidence_requirements(claim_type: str, tiers: list[str], level: str) -> None:
    ps = assign_clusters([ev(f"P{i + 1}", t, f"pub{i}") for i, t in enumerate(tiers)])
    assert strength([p.pid for p in ps], {p.pid: p for p in ps}, claim_type, REQ).level == level


def test_doctrine_needs_a_frame_authority() -> None:
    ps = assign_clusters([ev("P1", "S", "alislam", frame=True)])
    assert strength(["P1"], {"P1": ps[0]}, "doctrine", REQ).level == "STRONG"


def test_current_statistic_needs_a_dated_primary_source() -> None:
    undated = assign_clusters([ev("P1", "P", "un")])
    dated = assign_clusters([ev("P1", "P", "un", as_of="2023")])
    assert strength(["P1"], {"P1": undated[0]}, "statistic_current", REQ).level == "MODERATE"
    assert strength(["P1"], {"P1": dated[0]}, "statistic_current", REQ).level == "STRONG"


# --- verdicts (§9.2) -------------------------------------------------------------------

def test_verified_needs_strong_support_and_a_matching_blind_answer() -> None:
    j = judge(inp(TWO_SOURCES), REQ)
    assert (j.verdict, j.evidence_strength, j.review_status) == ("VERIFIED", "STRONG", "auto_ok")


def test_blind_answer_on_another_option_blocks_verified_and_goes_to_review() -> None:
    j = judge(inp(TWO_SOURCES, blind=blind(answer="Kenya", option="D")), REQ)
    assert j.verdict == "UNVERIFIED" and "needs_review" in j.routes
    assert any("differs from the expected answer" in r for r in j.reasons)


def test_key_contradicted_by_stronger_evidence_is_incorrect() -> None:
    """Football Quest #66: the key says 34, P and independent S sources say 36."""
    ps = [ev("P1", "T", "quizsite"), ev("P2", "P", "premierleague"), ev("P3", "S", "bbc")]
    j = judge(inp(ps, is_multi=False, key_letter=None, key_text="34", claim_type="sports_record",
                  blind=blind(answer="36", option=None, supporting=["P2"]),
                  verification=verification("PARTIALLY_CORRECT", ["P1"], ["P2", "P3"], "partially_overlapping",
                                            suggested_answer="36 goals")), REQ)
    assert (j.verdict, j.defect_location) == ("INCORRECT", "answer")
    assert j.claim_statuses["K"] == "contradicted" and j.suggested_answer == "36 goals"
    assert j.review_status == "needs_review"


def test_weak_contradiction_does_not_make_it_incorrect_but_is_reviewed() -> None:
    ps = [*TWO_SOURCES, ev("P3", "T", "blog")]
    j = judge(inp(ps, verification=verification("INCORRECT", ["P1", "P2"], ["P3"])), REQ)
    assert j.verdict != "INCORRECT" and "needs_review" in j.routes


def test_false_premise_is_incorrect_even_with_the_right_answer() -> None:
    """Football Quest #70: Brazil is right for the years listed, but the wins were not consecutive."""
    ps = [ev("P1", "S", "fifa"), ev("P2", "S", "bbc"), ev("P3", "T", "wikipedia", target="PR1")]
    pr = PremiseInfo("PR1", "Brazil won three consecutive World Cups", "historical_event", "universal", True)
    v = verification(presupposition_findings=[{"id": "PR1", "status": "contradicted", "passages": ["P2", "P3"],
                                               "explanation": "England won in 1966"}])
    j = judge(inp(ps, is_multi=False, key_letter=None, key_text="Brazil", premises=[pr],
                  blind=blind(answer="Brazil", option=None), verification=v), REQ)
    assert (j.verdict, j.defect_location) == ("INCORRECT", "question_premise")


def test_unsupported_material_premise_blocks_verified() -> None:
    pr = PremiseInfo("PR1", "p", "geography_fact", "universal", True)
    assert judge(inp(TWO_SOURCES, premises=[pr]), REQ).verdict == "UNVERIFIED"
    not_material = replace(pr, material=False)
    assert judge(inp(TWO_SOURCES, premises=[not_material]), REQ).verdict == "VERIFIED"


def test_two_supported_options_are_ambiguous() -> None:
    """Football Quest #86-like: two answers both supported."""
    opts = [{"option": "B", "status": "correct", "passages": ["P1"], "reason": "r"},
            {"option": "C", "status": "defensible", "passages": ["P2"], "reason": "r"}]
    j = judge(inp(TWO_SOURCES, verification=verification(option_assessments=opts)), REQ)
    assert (j.verdict, j.defect_location) == ("AMBIGUOUS", "options")


def test_open_question_with_another_defensible_answer_is_ambiguous() -> None:
    alts = [{"answer": "Arsenal", "option": None, "passages": ["P2"], "why_defensible": "also 3"}]
    j = judge(inp(TWO_SOURCES, is_multi=False, key_letter=None, key_text="Manchester United",
                  blind=blind("multiple_defensible", None, None, alternatives=alts)), REQ)
    assert j.verdict == "AMBIGUOUS"


def test_definitional_disagreement_is_ambiguous_not_incorrect() -> None:
    """World Tour #56: tallest waterfall depends on how height is measured."""
    dis = [{"about": "key", "kind": "definitional", "side_a_passages": ["P1"], "side_b_passages": ["P2"],
            "explanation": "uninterrupted vs total drop"}]
    j = judge(inp(TWO_SOURCES, verification=verification("UNCERTAIN", disagreements=dis)), REQ)
    assert j.verdict == "AMBIGUOUS" and j.claim_statuses["K"] == "definition_dependent"


def test_outdated_answer_unless_the_question_gives_a_date() -> None:
    t = {"time_sensitive": True, "judged_as_of": None, "outdated": True, "previously_true_passages": ["P1"],
         "change_passages": ["P2"]}
    assert judge(inp(TWO_SOURCES, verification=verification(temporal=t)), REQ).verdict == "OUTDATED"
    assert judge(inp(TWO_SOURCES, verification=verification(temporal=t), as_of_in_question="2010"),
                 REQ).verdict == "VERIFIED"


def test_disagreement_from_outside_the_frame_is_not_contradiction() -> None:
    """Prophets' Stories #140: non-frame sources disagree with a frame-specific claim."""
    ps = [ev("P1", "S", "alislam", frame=True), ev("P2", "S", "othersite")]
    frame = {"depends_on_frame": True, "within_frame": "supported", "contested_outside_frame": True,
             "frame_passages": ["P1"], "outside_passages": ["P2"]}
    j = judge(inp(ps, is_multi=False, key_letter=None, key_text="Srinagar", claim_type="doctrine",
                  frame_class="frame_specific", blind=blind(answer="Srinagar", option=None),
                  verification=verification(supporting=["P1"], contradicting=["P2"], frame=frame),
                  specialist_for=["doctrine"]), REQ)
    assert j.verdict == "VERIFIED" and j.within_frame and j.contested_outside_frame
    assert j.claim_statuses["K"] == "supported"


def test_no_evidence_is_unverified_and_needs_evidence() -> None:
    j = judge(inp([], blind=None, verification=None), REQ)
    assert (j.verdict, j.evidence_strength, j.review_status) == ("UNVERIFIED", "NONE", "needs_evidence")


def test_religious_questions_without_clean_verification_go_to_a_specialist() -> None:
    j = judge(inp([], blind=None, verification=None, claim_type="scripture_content",
                  specialist_for=["scripture_content"]), REQ)
    assert j.review_status == "needs_specialist"


def test_note_contradicted_does_not_change_the_verdict_but_is_reviewed() -> None:
    v = verification(note_findings=[{"id": "N1", "status": "contradicted", "passages": ["P2"], "explanation": "e"}])
    j = judge(inp(TWO_SOURCES, verification=v, note_claim_ids=["N1"]), REQ)
    assert j.verdict == "VERIFIED" and j.note_status == "contradicted" and j.review_status == "needs_review"


def test_note_claim_without_cited_passages_is_unverified() -> None:
    v = verification(note_findings=[{"id": "N1", "status": "supported", "passages": [], "explanation": "e"}])
    assert judge(inp(TWO_SOURCES, verification=v, note_claim_ids=["N1", "N2"]), REQ).note_statuses == {
        "N1": "unverified", "N2": "unverified"}


def test_poor_quality_is_reported_alongside_and_reviewed() -> None:
    j = judge(inp(TWO_SOURCES, quality=quality("POOR")), REQ)
    assert j.verdict == "VERIFIED" and j.quality == "POOR" and j.review_status == "needs_review"


def test_support_pointing_at_another_option_is_not_counted() -> None:
    ps = [ev("P1", "S", "a", option="D"), ev("P2", "T", "b", option="B")]
    j = judge(inp(ps), REQ)
    assert j.evidence_strength == "WEAK" and j.verdict == "UNVERIFIED"


def test_cited_ids_that_do_not_exist_are_ignored() -> None:
    j = judge(inp(TWO_SOURCES[:1], verification=verification(supporting=["P1", "P9"])), REQ)
    assert j.evidence_strength == "MODERATE"


def test_audit_sample_is_deterministic() -> None:
    assert judge(inp(TWO_SOURCES, audit_percent=100), REQ).review_status == "audit_sample"
    assert judge(inp(TWO_SOURCES, audit_percent=0), REQ).review_status == "auto_ok"


def test_no_verified_without_grounded_support() -> None:
    """Phase 3 exit criterion: VERIFIED is impossible when no passage supports the key."""
    for v in (verification(supporting=[]), verification(supporting=["P7"]), None):
        assert judge(inp(TWO_SOURCES, verification=v), REQ).verdict != "VERIFIED"


def test_eval_score_metrics() -> None:
    from qv.evaluation import Expectation, score
    exp = {"1": (Expectation(verdict="INCORRECT"), "seeded"), "2": (Expectation(verdict="VERIFIED"), "hypothesis"),
           "3": (Expectation(any_of=("VERIFIED", "AMBIGUOUS")), "hypothesis"),
           "4": (Expectation(verdict="INCORRECT"), "confirmed")}
    res = score([{"id": "1", "verdict": "UNVERIFIED", "review": "needs_review"},
                 {"id": "2", "verdict": "INCORRECT", "review": "needs_review"},
                 {"id": "3", "verdict": "AMBIGUOUS", "review": "needs_review"},
                 {"id": "4", "verdict": "VERIFIED", "review": "auto_ok"},
                 {"id": "9", "verdict": "VERIFIED", "review": "auto_ok"}], exp)
    assert (res["labelled"], res["errors"], res["error_recall_pct"], res["false_verifications"]) == (4, 2, 50.0, 1)
    assert (res["good"], res["false_incorrect_pct"], res["verdict_agreement_pct"]) == (2, 50.0, 25.0)
