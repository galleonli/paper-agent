"""
Shared helpers (e.g. safe filenames from paper IDs).
"""


def safe_paper_id_for_path(paper_id: str) -> str:
    """Sanitize paper ID for use as filename (library/{id}.md, .bib, .ris)."""
    return "".join(c for c in paper_id if c.isalnum() or c in ".-_") or "paper"
