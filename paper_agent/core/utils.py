"""
Shared helpers: safe filenames, text normalization, phrase matching.
"""

import re


def normalize_text(s: str) -> str:
    """Lowercase and strip; used for case-insensitive matching."""
    return s.lower().strip()


def _phrase_matches_text(phrase: str, norm_text: str) -> bool:
    """
    True if phrase matches norm_text (same rules as text_matches_any).
    Multi-word: substring; single-word alnum: word boundaries.
    """
    if not phrase or not phrase.strip():
        return False
    phrase = normalize_text(phrase)
    if not phrase:
        return False
    if re.search(r"\s", phrase):
        return phrase in norm_text
    if phrase.isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", norm_text))
    return phrase in norm_text


def text_matches_any(text: str, phrases: list[str]) -> bool:
    """
    True if any non-empty phrase matches text (case-insensitive).

    Matching rule:
    - Multi-word phrases use substring match.
    - Single-word alnum phrases use word boundaries to avoid false positives
      (e.g. "pose" should not match "propose").
    """
    if not phrases:
        return False
    norm_text = normalize_text(text)
    for p in phrases:
        if _phrase_matches_text(p, norm_text):
            return True
    return False


def phrases_matching_text(text: str, phrases: list[str]) -> list[str]:
    """
    Return list of phrases that match text (same rules as text_matches_any).
    Use when you need which phrases matched, not just whether any matched.
    """
    norm_text = normalize_text(text)
    return [p for p in phrases if p and _phrase_matches_text(p, norm_text)]


def safe_paper_id_for_path(paper_id: str) -> str:
    """Sanitize paper ID for use as filename (library/{id}.md, .bib, .ris)."""
    return "".join(c for c in paper_id if c.isalnum() or c in ".-_") or "paper"
