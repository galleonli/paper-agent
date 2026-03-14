"""Minimal tests for local output (notes and digest)."""

import json
from datetime import date
from pathlib import Path

from paper_agent.filter_papers import RankedPaper
from paper_agent.models import Paper
from paper_agent.output.local import (
    _score_related_candidate,
    enrich_related_local_papers,
    write_daily_digest,
    write_local_note,
)


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


def test_enrich_related_local_papers_scans_entire_library(tmp_path: Path) -> None:
    """Related-paper enrichment scans library across dates, not just the current day."""
    old = RankedPaper(
        paper=Paper(
            id="2401.00001",
            title="Continual Learning with Replay Buffers",
            summary="Replay methods for continual learning with memory buffers.",
            authors=["Alice Smith"],
            categories=["cs.LG"],
            updated="2024-01-10T00:00:00Z",
            link_abs="https://arxiv.org/abs/2401.00001",
            link_pdf=None,
        ),
        why_this_paper="Matched continual learning keyword.",
    )
    new = RankedPaper(
        paper=Paper(
            id="2402.00002",
            title="Memory Replay for Continual Learning Systems",
            summary="A replay-based continual learning method with adaptive memory.",
            authors=["Alice Smith", "Bob"],
            categories=["cs.LG"],
            updated="2024-02-11T00:00:00Z",
            link_abs="https://arxiv.org/abs/2402.00002",
            link_pdf=None,
        ),
        why_this_paper="Matched replay keyword.",
    )
    unrelated = RankedPaper(
        paper=Paper(
            id="2402.99999",
            title="Protein Folding with Diffusion",
            summary="Diffusion models for proteins.",
            authors=["Carol"],
            categories=["q-bio.BM"],
            updated="2024-02-12T00:00:00Z",
            link_abs="https://arxiv.org/abs/2402.99999",
            link_pdf=None,
        ),
        why_this_paper="Matched biology keyword.",
    )

    write_local_note(old, tmp_path, date(2024, 1, 10), source="arxiv")
    target_path = write_local_note(new, tmp_path, date(2024, 2, 11), source="arxiv")
    write_local_note(unrelated, tmp_path, date(2024, 2, 11), source="arxiv")

    enrich_related_local_papers(tmp_path, [target_path.with_suffix(".json")], max_related=3)

    metadata = json.loads(target_path.with_suffix(".json").read_text(encoding="utf-8"))
    related = metadata["related_local_papers"]
    assert related
    assert related[0]["id"] == "2401.00001"
    assert related[0]["date"] == "2024-01-10"
    assert "score" not in related[0]
    assert any("same author" in reason for reason in related[0]["reasons"])
    assert any("same arXiv categories" in reason for reason in related[0]["reasons"])
    assert all(item["id"] != "2402.00002" for item in related)


def test_related_category_reason_matches_scoring_cap() -> None:
    """Displayed shared categories should match the number that contributes to score."""
    target = {
        "authors": [],
        "categories": ["cs.AI", "cs.CL", "cs.LG"],
        "title": "",
        "abstract": "",
        "why_this_paper": "",
        "source": "arxiv",
    }
    candidate = {
        "authors": [],
        "categories": ["cs.AI", "cs.CL", "cs.LG"],
        "title": "",
        "abstract": "",
        "why_this_paper": "",
        "source": "arxiv",
    }

    score, reasons = _score_related_candidate(target, candidate)

    assert score == 5.25
    assert "same arXiv categories: cs.AI, cs.CL" in reasons
    assert all("cs.LG" not in reason for reason in reasons)


def test_related_reasons_use_human_friendly_labels() -> None:
    """Reasons should read naturally and include the source bonus explanation."""
    target = {
        "authors": ["Alice Smith"],
        "categories": ["cs.LG"],
        "title": "Replay for Continual Learning",
        "abstract": "Adaptive replay buffers for lifelong learning.",
        "why_this_paper": "Matched replay keyword.",
        "source": "scholar_alerts",
    }
    candidate = {
        "authors": ["Alice Smith"],
        "categories": ["cs.LG"],
        "title": "Continual Learning with Replay Buffers",
        "abstract": "Replay buffers for continual learning.",
        "why_this_paper": "Matched continual learning keyword.",
        "source": "scholar_alerts",
    }

    score, reasons = _score_related_candidate(target, candidate)

    assert score > 0
    assert "same author: Alice Smith" in reasons
    assert "same arXiv categories: cs.LG" in reasons
    assert any(reason.startswith("similar topics: ") for reason in reasons)
    assert "same source: Scholar Inbox" in reasons


def test_enrich_related_local_papers_keeps_newest_duplicate_id(tmp_path: Path) -> None:
    """When a paper id exists on multiple dates, keep the newest metadata entry."""
    target = RankedPaper(
        paper=Paper(
            id="2403.00003",
            title="Replay Methods for Continual Learning",
            summary="Replay methods in continual learning systems.",
            authors=["Dana"],
            categories=["cs.LG"],
            updated="2024-03-15T00:00:00Z",
            link_abs="https://arxiv.org/abs/2403.00003",
            link_pdf=None,
        ),
        why_this_paper="Matched replay keyword.",
    )
    older = RankedPaper(
        paper=Paper(
            id="2401.11111",
            title="Older Replay Paper",
            summary="Replay methods with memory.",
            authors=["Dana"],
            categories=["cs.LG"],
            updated="2024-01-10T00:00:00Z",
            link_abs="https://arxiv.org/abs/2401.11111",
            link_pdf=None,
        ),
        why_this_paper="Older version.",
    )
    newer = RankedPaper(
        paper=Paper(
            id="2401.11111",
            title="Newer Replay Paper",
            summary="Replay methods with adaptive memory.",
            authors=["Dana"],
            categories=["cs.LG"],
            updated="2024-02-10T00:00:00Z",
            link_abs="https://arxiv.org/abs/2401.11111v2",
            link_pdf=None,
        ),
        why_this_paper="Newer version.",
    )

    write_local_note(older, tmp_path, date(2024, 1, 10), source="arxiv")
    write_local_note(newer, tmp_path, date(2024, 2, 10), source="arxiv")
    target_path = write_local_note(target, tmp_path, date(2024, 3, 15), source="arxiv")

    enrich_related_local_papers(tmp_path, [target_path.with_suffix(".json")], max_related=3)

    metadata = json.loads(target_path.with_suffix(".json").read_text(encoding="utf-8"))
    related = metadata["related_local_papers"]
    assert related
    assert related[0]["id"] == "2401.11111"
    assert related[0]["title"] == "Newer Replay Paper"
    assert related[0]["date"] == "2024-02-10"
    assert related[0]["link"] == "https://arxiv.org/abs/2401.11111v2"


def test_enrich_related_local_papers_sorts_unknown_dates_last(tmp_path: Path) -> None:
    """Unknown published dates should not outrank valid recent dates."""
    target = RankedPaper(
        paper=Paper(
            id="2403.00003",
            title="Replay Methods for Continual Learning",
            summary="Replay methods in continual learning systems.",
            authors=["Dana"],
            categories=["cs.LG"],
            updated="2024-03-15T00:00:00Z",
            link_abs="https://arxiv.org/abs/2403.00003",
            link_pdf=None,
        ),
        why_this_paper="Matched replay keyword.",
    )
    unknown_date = RankedPaper(
        paper=Paper(
            id="2401.11111",
            title="Replay Paper With Unknown Date",
            summary="Replay methods with memory.",
            authors=["Dana"],
            categories=["cs.LG"],
            updated="",
            link_abs="https://arxiv.org/abs/2401.11111",
            link_pdf=None,
        ),
        why_this_paper="Older version.",
    )
    known_date = RankedPaper(
        paper=Paper(
            id="2402.22222",
            title="Replay Paper With Known Date",
            summary="Replay methods with adaptive memory.",
            authors=["Dana"],
            categories=["cs.LG"],
            updated="2024-02-10T00:00:00Z",
            link_abs="https://arxiv.org/abs/2402.22222",
            link_pdf=None,
        ),
        why_this_paper="Newer version.",
    )

    write_local_note(unknown_date, tmp_path, date(2024, 1, 10), source="arxiv")
    write_local_note(known_date, tmp_path, date(2024, 2, 10), source="arxiv")
    target_path = write_local_note(target, tmp_path, date(2024, 3, 15), source="arxiv")

    enrich_related_local_papers(tmp_path, [target_path.with_suffix(".json")], max_related=3)

    metadata = json.loads(target_path.with_suffix(".json").read_text(encoding="utf-8"))
    related = metadata["related_local_papers"]
    assert related
    assert related[0]["id"] == "2402.22222"
    assert related[1]["id"] == "2401.11111"
