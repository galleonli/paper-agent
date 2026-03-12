"""
Shared helpers: safe filenames, text normalization, phrase matching.
"""

import re


def normalize_text(s: str) -> str:
    """Lowercase and strip; used for case-insensitive matching."""
    return s.lower().strip()


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
        if not p:
            continue
        phrase = normalize_text(p)
        if not phrase:
            continue
        if re.search(r"\s", phrase):
            if phrase in norm_text:
                return True
            continue
        if phrase.isalnum():
            if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", norm_text):
                return True
            continue
        if phrase in norm_text:
            return True
    return False


def safe_paper_id_for_path(paper_id: str) -> str:
    """Sanitize paper ID for use as filename (library/{id}.md, .bib, .ris)."""
    return "".join(c for c in paper_id if c.isalnum() or c in ".-_") or "paper"
