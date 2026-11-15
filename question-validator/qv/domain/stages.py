"""Typed outputs of the model stages S1a, S1b and S3 (prompts/ s1a, s1b, s3).

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
