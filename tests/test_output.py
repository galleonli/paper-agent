"""Minimal tests for local output (notes and digest)."""

from datetime import date
from pathlib import Path

from paper_agent.filter_papers import RankedPaper
from paper_agent.models import Paper
from paper_agent.output.local import write_local_note, write_daily_digest


def _ranked(paper_id: str = "2301.12345", title: str = "Test Paper", why: str | None = "Keyphrase matched") -> RankedPaper:
    return RankedPaper(
        paper=Paper(
            id=paper_id,
            title=title,
            summary="Abstract here.",
            authors=["Alice", "Bob"],
            categories=["cs.LG"],
            updated="2023-01-15T12:00:00Z",
            link_abs=f"https://arxiv.org/abs/{paper_id}",
            link_pdf=f"https://arxiv.org/pdf/{paper_id}.pdf",
        ),
        why_this_paper=why,
    )


def test_write_local_note(tmp_path: Path) -> None:
    """write_local_note creates library_dir/{id}.md with title, summary, why_this_paper."""
    r = _ranked()
    path = write_local_note(r, tmp_path, date(2024, 1, 15))
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Test Paper" in text
    assert "Keyphrase matched" in text
    assert "arxiv.org/abs/2301.12345" in text


def test_write_daily_digest(tmp_path: Path) -> None:
    """write_daily_digest creates daily_dir/YYYY-MM-DD.md with run date and paper list."""
    ranked_list = [_ranked("1", "First"), _ranked("2", "Second")]
    path = write_daily_digest(ranked_list, tmp_path, date(2024, 1, 15))
    assert path.exists()
    assert path.name == "2024-01-15.md"
    text = path.read_text(encoding="utf-8")
    assert "2024-01-15" in text
    assert "First" in text
    assert "Second" in text
