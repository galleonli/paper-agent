"""Minimal tests for BibTeX and RIS export."""

from pathlib import Path

from paper_agent.exporters import write_bibtex, write_ris
from paper_agent.models import Paper


def _paper() -> Paper:
    return Paper(
        id="2301.12345",
        title="Test Paper Title",
        summary="Abstract here.",
        authors=["Alice", "Bob"],
        categories=["cs.LG"],
        updated="2023-01-15T12:00:00Z",
        link_abs="https://arxiv.org/abs/2301.12345",
        link_pdf="https://arxiv.org/pdf/2301.12345.pdf",
    )


def test_write_bibtex(tmp_path: Path) -> None:
    """BibTeX file is created with title, authors, year, url."""
    p = _paper()
    path = write_bibtex(p, tmp_path)
    assert path.exists()
    assert path.suffix == ".bib"
    text = path.read_text(encoding="utf-8")
    assert "Test Paper Title" in text
    assert "2301.12345" in text
    assert "Alice" in text and "Bob" in text


def test_write_ris(tmp_path: Path) -> None:
    """RIS file is created (EndNote-compatible) with title, authors, year, url."""
    p = _paper()
    path = write_ris(p, tmp_path)
    assert path.exists()
    assert path.suffix == ".ris"
    text = path.read_text(encoding="utf-8")
    assert "TY  - GEN" in text
    assert "Test Paper Title" in text
    assert "ER  - " in text
