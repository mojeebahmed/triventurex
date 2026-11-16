"""Typed outputs of the model stages S1a, S1b, S3, S4, S5 and S6 (prompts/ s1a … s6).

These Pydantic models are the source of truth for the JSON schemas sent to the
model (structured output) and are used again to validate every response.
`tests/test_stage_models.py` checks that they match the schemas in prompts/.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Bump when a stage output model changes shape (part of every input hash).
SCHEMA_VERSION = "1"


class _Strict(BaseModel):
    """Base: unknown fields are an error (mirrors additionalProperties: false)."""

    model_config = ConfigDict(extra="forbid")


class ClaimType(StrEnum):
    """What kind of fact a claim is (METHODOLOGY.md §2)."""

    SCRIPTURE_CONTENT = "scripture_content"
    HADITH_OR_TRADITION = "hadith_or_tradition"
    ATTRIBUTION = "attribution"
    DOCTRINE = "doctrine"
    HISTORICAL_EVENT = "historical_event"
    BIOGRAPHY = "biography"
    MEASUREMENT_OR_SUPERLATIVE = "measurement_or_superlative"
    STATISTIC_CURRENT = "statistic_current"
    SPORTS_RECORD = "sports_record"
    DEFINITION_OR_MEANING = "definition_or_meaning"
    CLASSIFICATION_OR_LIST = "classification_or_list"
    GEOGRAPHY_FACT = "geography_fact"
    SCIENCE_FACT = "science_fact"
    OTHER = "other"


class FrameClass(StrEnum):
    """How a claim relates to an edition's frame of reference."""

    UNIVERSAL = "universal"
    TRADITION_GENERAL = "tradition_general"
    ATTRIBUTION_TO_FRAME = "attribution_to_frame"
    FRAME_SPECIFIC = "frame_specific"


AnswerType = Literal[
    "person", "place", "organisation", "date_or_year", "number", "quantity_with_unit", "name_or_term",
    "meaning_or_translation", "list", "description", "event", "yes_no_or_choice", "other",
]
QueryPurpose = Literal["core", "presupposition", "competitor", "definition", "primary_source"]
LookupSource = Literal["quran", "hadith", "wikidata"]


# --- S1a ---------------------------------------------------------------------

class Presupposition(_Strict):
    """A fact the question takes for granted."""

    id: str = Field(description="PR1, PR2, …")
    text: str = Field(description="the presupposition as a standalone factual statement")
    claim_type: str
    frame_class: str
    material: bool = Field(description="true if the question is wrong when this is false")


class TimeSensitivity(_Strict):
    """Whether the answer can change over time."""

    is_time_sensitive: bool
    as_of_in_question: str | None
    reason: str


class Convention(_Strict):
    """A convention or definition the answer depends on."""

    topic: str
    stated_in_question: bool
    detail: str


class Interpretation(_Strict):
    """Another reasonable reading of the question."""

    reading: str
    could_change_answer: bool


class Superlative(_Strict):
    """Superlative analysis (first / most / largest …)."""

    is_superlative: bool
    dimension: str | None
    competitor_check_needed: bool


class BlindQuery(_Strict):
    """A research query written without knowing the key."""

    q: str
    purpose: QueryPurpose
    target: str = Field(description='"need" or a presupposition id')


class DirectLookup(_Strict):
    """A primary-source lookup named by the question itself."""

    source: LookupSource
    ref: str


class Decomposition(_Strict):
    """S1a output — answer-blind decomposition of a question."""

    information_need: str
    answer_type: AnswerType
    subject_entities: list[str]
    claim_type: ClaimType
    frame_class: FrameClass
    presuppositions: list[Presupposition]
    time_sensitivity: TimeSensitivity
    conventions: list[Convention]
    interpretations: list[Interpretation]
    superlative: Superlative
    queries: list[BlindQuery]
    direct_lookups: list[DirectLookup]
    researchable: bool
    researchable_note: str | None


# --- S1b ---------------------------------------------------------------------

class KeyComponent(_Strict):
    """One separately checkable fact inside the key."""

    id: str = Field(description="K1, K2, …")
    text: str
    value: str = Field(description="the specific value asserted, e.g. '34', 'Erling Haaland'")


class NoteClaim(_Strict):
    """A checkable statement in the note column."""

    id: str = Field(description="N1, N2, …")
    text: str
    kind: Literal["scripture_reference", "hadith_reference", "book_reference", "factual_statement",
                  "explanation"]
    reference: str | None
    scheme: str | None = Field(description="numbering scheme declared by the edition")


class NoteLookup(_Strict):
    """A direct lookup for a note claim."""

    for_claim: str
    source: LookupSource
    ref: str
    scheme: str | None


class ChallengeQuery(_Strict):
    """A query aimed at evidence against the key."""

    q: str
    angle: Literal["previous_or_later_holder", "commonly_confused", "disputed_or_myth", "change_over_time",
                   "definition_variant", "other"]


class NoteQuery(_Strict):
    """A query for a note claim that cannot be looked up directly."""

    q: str
    for_claim: str


class ClaimFormulation(_Strict):
    """S1b output — what the dataset claims (sees the key and the note)."""

    key_claim: str
    key_components: list[KeyComponent]
    answer_equivalents: list[str]
    note_claims: list[NoteClaim]
    direct_lookups: list[NoteLookup]
    challenge_queries: list[ChallengeQuery]
    note_queries: list[NoteQuery]


# --- S3 ----------------------------------------------------------------------

PageKind = Literal[
    "primary_text", "official_record", "authors_own_work", "scholarly", "reference_work", "encyclopedia_wiki",
    "news", "educational", "organisation_page", "quiz_or_trivia", "listicle_or_content_farm",
    "forum_or_social", "machine_generated_suspected", "other",
]


class PageAssessment(_Strict):
    """What kind of page a document is."""

    page_kind: PageKind
    about_right_subject: bool
    publisher: str | None
    author: str | None
    publication_date: str | None
    concerns: list[str]


class ExtractedPassage(_Strict):
    """A verbatim passage as reported by the model (not yet grounded)."""

    quote: str
    target: str
    asserted_answer: str | None
    matches_option: Literal["A", "B", "C", "D", "none"] | None
    stance: Literal["supports", "contradicts", "qualifies", "mentions"] | None
    qualifiers: str | None
    as_of: str | None
    attributed_origin: str | None
    is_primary_for_claim: bool


class Extraction(_Strict):
    """S3 output — evidence from one document."""

    page: PageAssessment
    passages: list[ExtractedPassage]
    no_relevant_content_reason: str | None


# --- S4 ----------------------------------------------------------------------

OptionLetter = Literal["A", "B", "C", "D"]


class AlternativeAnswer(_Strict):
    """Another answer the passages also support."""

    answer: str
    option: OptionLetter | None
    passages: list[str]
    why_defensible: str


class PresuppositionCheck(_Strict):
    """S4's reading of one presupposition."""

    id: str
    status: Literal["supported", "contradicted", "unclear"]
    passages: list[str]


class BlindAnswer(_Strict):
    """S4 output — an answer formed from the evidence without knowing the key."""

    status: Literal["answered", "multiple_defensible", "insufficient_evidence", "unanswerable_as_written"]
    answer: str | None
    option: OptionLetter | None
    supporting_passages: list[str]
    conflicting_passages: list[str]
    alternative_answers: list[AlternativeAnswer]
    presupposition_findings: list[PresuppositionCheck]
    missing_evidence: str | None = Field(description="what evidence would settle it, used for the escalation round")
    reasoning: str


# --- S5 ----------------------------------------------------------------------

class KeyAssessment(_Strict):
    """The key compared with the evidence."""

    factual_accuracy: Literal["CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "UNCERTAIN"]
    match_with_blind: Literal["same", "equivalent", "partially_overlapping", "different", "blind_insufficient",
                              "not_shown"]
    supporting_passages: list[str]
    contradicting_passages: list[str]


class ComponentAssessment(_Strict):
    """One key component compared with the evidence."""

    id: str
    status: Literal["supported", "contradicted", "unclear"]
    evidence_value: str | None = Field(description="the value the evidence gives, if different")
    passages: list[str]


class RequirementCheck(_Strict):
    """The model's own view of the evidence requirement (S8 recounts it)."""

    met: bool
    independent_origins_supporting: int
    highest_tier_supporting: Literal["P", "S", "T"] | None
    explanation: str


class OptionAssessment(_Strict):
    """One multiple-choice option."""

    option: OptionLetter
    status: Literal["correct", "defensible", "incorrect", "unclear"]
    passages: list[str]
    reason: str


class AcceptableAlternative(_Strict):
    """An answer that should also be accepted."""

    answer: str
    basis: Literal["equivalent_wording", "transliteration", "partial_but_acceptable", "alternative_convention"]
    passages: list[str]


class Disagreement(_Strict):
    """A classified disagreement between passages."""

    about: str = Field(description='"key", a component id, a presupposition id or a note claim id')
    kind: Literal["factual_conflict", "definitional", "convention", "interpretive", "temporal", "source_error"]
    side_a_passages: list[str]
    side_b_passages: list[str]
    explanation: str


class ClaimFinding(_Strict):
    """A presupposition checked against the evidence."""

    id: str
    status: Literal["supported", "contradicted", "unclear"]
    passages: list[str]
    explanation: str


class NoteFinding(_Strict):
    """A note claim checked against the evidence."""

    id: str
    status: Literal["supported", "contradicted", "convention_mismatch", "unclear"]
    passages: list[str]
    explanation: str


class Temporal(_Strict):
    """Time sensitivity of the answer."""

    time_sensitive: bool
    judged_as_of: str | None
    outdated: bool
    previously_true_passages: list[str]
    change_passages: list[str]


class FrameFinding(_Strict):
    """How the answer depends on the edition's frame."""

    depends_on_frame: bool
    within_frame: Literal["supported", "contradicted", "unclear", "not_applicable"]
    contested_outside_frame: bool
    frame_passages: list[str]
    outside_passages: list[str]


class Verification(_Strict):
    """S5 / S5b output — findings about the key, options, premises and note (not the verdict)."""

    key_assessment: KeyAssessment
    component_assessments: list[ComponentAssessment]
    evidence_requirement_met: RequirementCheck
    option_assessments: list[OptionAssessment]
    acceptable_alternatives: list[AcceptableAlternative]
    disagreements: list[Disagreement]
    presupposition_findings: list[ClaimFinding]
    note_findings: list[NoteFinding]
    temporal: Temporal
    frame: FrameFinding
    suggested_answer: str | None
    suggested_question: str | None
    missing_evidence: str | None
    explanation: str


# --- S6 ----------------------------------------------------------------------

QualityIssueType = Literal[
    "ambiguous_wording", "multiple_answers_possible", "missing_context_or_convention", "compound_question",
    "false_precision", "answer_leak", "implausible_distractors", "distractor_possibly_correct", "too_few_options",
    "option_format_inconsistent", "difficulty_mismatch", "age_inappropriate", "culturally_misleading",
    "honorific_or_style_inconsistent", "spelling_or_grammar", "possible_factual_issue",
]


class QualityIssue(_Strict):
    """One wording or quiz-design issue."""

    type: QualityIssueType
    severity: Literal["minor", "major"]
    detail: str
    is_hypothesis: bool
    option: OptionLetter | None


class Rewrite(_Strict):
    """A suggested rewrite of the question."""

    question: str
    options: list[str] | None
    answer: str
    note: str | None


class Quality(_Strict):
    """S6 output — the question judged as a quiz question, without evidence."""

    overall: Literal["GOOD", "NEEDS_IMPROVEMENT", "POOR"]
    issues: list[QualityIssue]
    difficulty_estimate: Literal["easy", "medium", "hard"]
    audience_fit: Literal["good", "too_hard_for_young", "unsuitable"]
    suggested_rewrite: Rewrite | None
    rewrite_reason: str | None
