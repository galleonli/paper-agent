"""Minimal tests for BibTeX and RIS export."""

from datetime import date
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


def test_write_exports_with_run_date_subdir(tmp_path: Path) -> None:
    """Exports can be written under library_dir/YYYY-MM-DD when run_date is provided."""
    p = _paper()
    run_date = date(2025, 1, 2)
    bib_path = write_bibtex(p, tmp_path, run_date=run_date)
    ris_path = write_ris(p, tmp_path, run_date=run_date)

    assert bib_path.exists() and ris_path.exists()
    assert bib_path.parent == tmp_path / "2025-01-02"
    assert ris_path.parent == tmp_path / "2025-01-02"
    assert bib_path.name == "2301.12345.bib"
    assert ris_path.name == "2301.12345.ris"
