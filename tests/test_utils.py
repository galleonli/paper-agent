"""Tests for core text matching utilities."""

from paper_agent.core.utils import text_matches_any


def test_text_matches_any_uses_word_boundaries_for_single_word_phrases() -> None:
    """Single-word phrases should not match inside larger words."""
    text = "We propose a novel method."
    assert not text_matches_any(text, ["pose"])
    assert text_matches_any(text, ["propose"])


def test_text_matches_any_keeps_phrase_matching_for_multi_word_phrases() -> None:
    """Multi-word phrases still match as normalized substrings."""
    text = "This paper studies continual learning under distribution shift."
    assert text_matches_any(text, ["continual learning"])
