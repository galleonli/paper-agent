"""
Shared helpers: safe filenames, text normalization, phrase matching.
"""


def normalize_text(s: str) -> str:
    """Lowercase and strip; used for case-insensitive matching."""
    return s.lower().strip()


def text_matches_any(text: str, phrases: list[str]) -> bool:
    """True if any non-empty phrase appears in text (case-insensitive)."""
    if not phrases:
        return False
    norm_text = normalize_text(text)
    for p in phrases:
        if p and normalize_text(p) in norm_text:
            return True
    return False


def safe_paper_id_for_path(paper_id: str) -> str:
    """Sanitize paper ID for use as filename (library/{id}.md, .bib, .ris)."""
    return "".join(c for c in paper_id if c.isalnum() or c in ".-_") or "paper"
