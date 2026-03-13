"""Minimal tests for local output (notes and digest)."""

import json
from datetime import date
from pathlib import Path

from paper_agent.filter_papers import RankedPaper
from paper_agent.models import Paper
from paper_agent.output.local import write_local_note, write_daily_digest


def _ranked(
    paper_id: str = "2301.12345",
    title: str = "Test Paper",
    why: str | None = "Required keyword matched",
) -> RankedPaper:
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
    """write_local_note creates library_dir/YYYY-MM-DD/{id}.md and matching {id}.json."""
    r = _ranked()
    run_date = date(2024, 1, 15)
    path = write_local_note(r, tmp_path, run_date, source="arxiv")
    assert path.exists()
    assert path.parent.name == run_date.isoformat()
    assert path.name == "2301.12345.md"
    text = path.read_text(encoding="utf-8")
    assert "Test Paper" in text
    assert "Required keyword matched" in text
    assert "arxiv.org/abs/2301.12345" in text
    json_path = path.with_suffix(".json")
    assert json_path.exists()
    metadata = json.loads(json_path.read_text(encoding="utf-8"))
    assert metadata["id"] == "2301.12345"
    assert metadata["title"] == "Test Paper"
    assert metadata["authors"] == ["Alice", "Bob"]
    assert metadata["source"] == "arxiv"
    assert metadata["date"] == "2024-01-15"
    assert metadata["link"] == "https://arxiv.org/abs/2301.12345"
    assert metadata["abstract"] == "Abstract here."
    assert metadata["categories"] == ["cs.LG"]
    assert metadata["note_path"] == "library/2024-01-15/2301.12345.md"
    assert metadata["published"] == "2023-01-15"
    assert metadata["why_this_paper"] == "Required keyword matched"
    assert "summary" not in metadata


def test_write_daily_digest(tmp_path: Path) -> None:
    """write_daily_digest creates paper_dir/YYYY-MM-DD.md with two sections (Daily Precision + Scholar Inbox)."""
    discovery = [_ranked("1", "First"), _ranked("2", "Second")]
    scholar = [_ranked("3", "Third")]
    run_date = date(2024, 1, 15)
    path = write_daily_digest(discovery, scholar, tmp_path, run_date)
    assert path.exists()
    assert path.name == "2024-01-15.md"
    text = path.read_text(encoding="utf-8")
    assert "2024-01-15" in text
    assert "## Daily Precision" in text
    assert "## Scholar Inbox" in text
    assert "First" in text
    assert "Second" in text
    assert "Third" in text
    assert "../library/2024-01-15/1.md" in text
    assert "../library/2024-01-15/2.md" in text
    assert "../library/2024-01-15/3.md" in text
    # Section order: Daily Precision first, then Scholar Inbox.
    assert text.index("## Daily Precision") < text.index("## Scholar Inbox")
    assert "Total papers:" in text or "Daily Precision:" in text or "Scholar Inbox:" in text


def test_digest_two_sections_format(tmp_path: Path) -> None:
    """Digest has exactly two section headers and correct subsection structure."""
    discovery = [_ranked("a", "Discovery A")]
    scholar = [_ranked("b", "Scholar B")]
    path = write_daily_digest(discovery, scholar, tmp_path, date(2025, 1, 1))
    text = path.read_text(encoding="utf-8")
    assert text.count("## Daily Precision") == 1
    assert text.count("## Scholar Inbox") == 1
    assert "Papers: 1" in text  # under each section
    assert "### Discovery A" in text
    assert "### Scholar B" in text
    assert "../library/2025-01-01/" in text


def test_write_local_note_scholar_source_and_placeholder(tmp_path: Path) -> None:
    """Scholar note includes Source: scholar_alerts and placeholder when abstract missing."""
    r = RankedPaper(
        paper=Paper(
            id="scholar-abc123",
            title="Inbox Paper",
            summary="",  # no abstract
            authors=["Author"],
            categories=[],
            updated="2025-01-02T00:00:00Z",
            link_abs="https://example.com/paper",
            link_pdf=None,
        ),
        why_this_paper="From your Scholar Inbox.",
    )
    path = write_local_note(r, tmp_path, date(2025, 1, 2), source="scholar_alerts")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Source" in text and "scholar_alerts" in text
    assert "No abstract in alert email" in text
    assert "Inbox Paper" in text


def test_write_local_note_scholar_json_metadata(tmp_path: Path) -> None:
    """Scholar JSON mirrors the note fields (no research summary, no summary field)."""
    r = RankedPaper(
        paper=Paper(
            id="scholar-xyz",
            title="Scholar JSON Paper",
            summary="",
            authors=["Author"],
            categories=[],
            updated="2025-01-03T00:00:00Z",
            link_abs="https://example.com/scholar-json",
            link_pdf=None,
        ),
        why_this_paper="From your Scholar Inbox.",
    )
    run_date = date(2025, 1, 3)
    path = write_local_note(r, tmp_path, run_date, source="scholar_alerts")
    json_path = path.with_suffix(".json")
    assert json_path.exists()
    metadata = json.loads(json_path.read_text(encoding="utf-8"))
    assert metadata["id"] == "scholar-xyz"
    assert metadata["source"] == "scholar_alerts"
    assert metadata["published"] == "2025-01-03"
    assert metadata["abstract"] == "No abstract in alert email."
    assert metadata["why_this_paper"] == "From your Scholar Inbox."
    assert "summary" not in metadata
    assert "research_summary" not in metadata
