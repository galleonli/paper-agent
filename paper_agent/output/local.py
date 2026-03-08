"""
Local output: per-paper notes in library_dir and daily digest in daily_dir.
Contract: library/YYYY-MM-DD/{arxiv_id}.md (Title, arXiv ID, Published, Authors, Link, Categories, Abstract, Summary);
daily/YYYY-MM-DD.md listing papers with arXiv link and local note path.
"""

from datetime import date
from pathlib import Path
from typing import Optional

from paper_agent.core.models import Paper
from paper_agent.core.utils import safe_paper_id_for_path
from paper_agent.filter_papers import RankedPaper


def _brief_summary_for_note(paper: Paper, one_liner: Optional[str] = None) -> str:
    """Summary section: use provided one-liner or first 300 chars of abstract."""
    if one_liner and one_liner.strip():
        return one_liner.strip()
    if paper.summary:
        return (paper.summary[:300] + "…") if len(paper.summary) > 300 else paper.summary
    return "No summary available."


def write_local_note(
    ranked: RankedPaper,
    library_dir: str | Path,
    run_date: date,
    brief_one_liner: Optional[str] = None,
    research_summary: Optional[tuple[str, str]] = None,
    source: str | None = None,
) -> Path:
    """
    Write one markdown note to library_dir/YYYY-MM-DD/{arxiv_id}.md.
    Header: Title, arXiv ID, Published, Authors, Link, Categories; then Abstract; then Summary.
    """
    paper = ranked.paper
    run_subdir = Path(library_dir) / run_date.isoformat()
    run_subdir.mkdir(parents=True, exist_ok=True)
    name = safe_paper_id_for_path(paper.id)
    path = run_subdir / f"{name}.md"

    why = ranked.why_this_paper or "—"
    summary_text = _brief_summary_for_note(paper, brief_one_liner)
    authors_str = "; ".join(paper.authors) if paper.authors else "—"
    cats_str = ", ".join(paper.categories) if paper.categories else "—"
    published = (
        paper.updated[:10]
        if paper.updated and len(paper.updated) >= 10
        else (paper.updated or "—")
    )
    source_str = source or "arxiv"

    research_section = ""
    if research_summary is not None:
        heading, body_text = research_summary
        research_section = f"""

## {heading}

{body_text}
"""

    abstract_body = paper.summary or ("No abstract in alert email." if source == "scholar_alerts" else "—")

    body = f"""# {paper.title}

- **Title**: {paper.title}
- **ID**: {paper.id}
- **Published**: {published}
- **Authors**: {authors_str}
- **Link**: {paper.link_abs}
- **Categories**: {cats_str}
- **Source**: {source_str}

## Abstract

{abstract_body}

## Summary

{summary_text}

## Why this paper

{why}{research_section}

## Key points

(TODO: add your notes)
"""

    path.write_text(body, encoding="utf-8")
    return path


def write_daily_digest(
    discovery: list[RankedPaper],
    scholar_inbox: list[RankedPaper],
    daily_dir: str | Path,
    run_date: date,
) -> Path:
    """
    Write daily digest to daily_dir/YYYY-MM-DD.md (single file per day).
    Sections:
    - Daily Precision: discovery feed (capped by max_papers_per_day).
    - Scholar Inbox: Scholar Alerts items (uncapped or max_items_per_run capped).
    """
    Path(daily_dir).mkdir(parents=True, exist_ok=True)
    path = Path(daily_dir) / f"{run_date.isoformat()}.md"

    total = len(discovery) + len(scholar_inbox)
    lines: list[str] = [
        f"# Daily digest — {run_date.isoformat()}",
        "",
        f"Total papers: {total} (Daily Precision: {len(discovery)}, Scholar Inbox: {len(scholar_inbox)})",
        "",
        "---",
        "",
        "## Daily Precision",
        "",
        f"Papers: {len(discovery)}",
        "",
    ]

    for r in discovery:
        p = r.paper
        note_name = safe_paper_id_for_path(p.id)
        note_label = f"{note_name}.md"
        note_href = f"../library/{run_date.isoformat()}/{note_name}.md"
        why = r.why_this_paper or "—"
        lines.append(f"### {p.title}")
        lines.append("")
        lines.append(f"- **Why**: {why}")
        lines.append(f"- **Link**: {p.link_abs}")
        lines.append(f"- **Local note**: [{note_label}]({note_href})")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Scholar Inbox")
    lines.append("")
    lines.append(f"Papers: {len(scholar_inbox)}")
    lines.append("")

    for r in scholar_inbox:
        p = r.paper
        note_name = safe_paper_id_for_path(p.id)
        note_label = f"{note_name}.md"
        note_href = f"../library/{run_date.isoformat()}/{note_name}.md"
        lines.append(f"### {p.title}")
        lines.append("")
        lines.append(f"- **Link**: {p.link_abs}")
        lines.append(f"- **Local note**: [{note_label}]({note_href})")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
