"""Grounding check: only verbatim (normalised) quotes count; offsets map to the stored text."""

from __future__ import annotations

from qv.pipeline.grounding import DocumentIndex, normalise

TEXT = ("The Quran contains 540 ruku (paragraph divisions).\n\n  Some editions count 558 — "
        "the “exact figure” shifts between printings.")


def test_exact_quote_offsets_point_at_original_text() -> None:
    g = DocumentIndex(TEXT).find("The Quran contains 540 ruku (paragraph divisions).")
    assert g is not None
    assert TEXT[g.start:g.end] == "The Quran contains 540 ruku (paragraph divisions)."


def test_whitespace_quotes_and_dashes_are_normalised() -> None:
    quote = 'Some editions count 558 - the "exact figure" shifts'
    g = DocumentIndex(TEXT).find(quote)
    assert g is not None
    assert g.text.startswith("Some editions count 558 — the “exact")
    assert TEXT[g.start:g.end] == g.text


def test_quote_across_line_breaks() -> None:
    assert DocumentIndex(TEXT).find("divisions). Some editions") is not None


def test_changed_word_is_not_grounded() -> None:
    assert DocumentIndex(TEXT).find("The Quran contains 558 ruku (paragraph divisions).") is None


def test_no_fuzzy_matching_of_ellipsis_or_joins() -> None:
    idx = DocumentIndex(TEXT)
    assert idx.find("The Quran contains 540 ruku … shifts between printings.") is None
    assert idx.find("540 ruku. Some editions count 558") is None


def test_too_short_quotes_are_rejected() -> None:
    assert DocumentIndex(TEXT).find("540") is None


def test_nfkc_and_zero_width() -> None:
    text = "Ligature ﬁne text with zero​width inside it, long enough."
    g = DocumentIndex(text).find("Ligature fine text with zerowidth inside")
    assert g is not None and text[g.start:g.end].startswith("Ligature ﬁne")


def test_normalise() -> None:
    assert normalise("  a’b \n\t c–d  ") == "a'b c-d"


def test_footnote_markers_are_ignored() -> None:
    text = "The word 'Ramadan' is derived from Ramdh, meaning 'burning'.[24] It is named so for three reasons."
    g = DocumentIndex(text).find("meaning 'burning'. It is named so for three reasons.")
    assert g is not None and "[24]" in g.text and text[g.start:g.end] == g.text
    assert DocumentIndex(text).find("meaning 'burning'.[24] It is named so") is not None


def test_prompt_delimiters_at_the_edges_are_removed() -> None:
    """Local models copy render_s3's <document> tags into quotes; only those edge tags are removed."""
    g = DocumentIndex(TEXT).find("<document>\nThe Quran contains 540 ruku (paragraph divisions).\n</document>")
    assert g is not None and g.text == "The Quran contains 540 ruku (paragraph divisions)."
    assert DocumentIndex(TEXT).find("The Quran <document>contains 540 ruku") is None
