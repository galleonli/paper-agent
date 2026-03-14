"""
Local output: per-paper notes in library_dir and daily digest in paper_dir.
Contract: library/YYYY-MM-DD/{arxiv_id}.md (Title, arXiv ID, Published, Authors, Link, Categories, Abstract, Why this paper, optional Research summary);
daily/YYYY-MM-DD.md listing papers with arXiv link and local note path.
"""

import json
import os
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from paper_agent.core.models import Paper
from paper_agent.core.utils import safe_paper_id_for_path
from paper_agent.filter_papers import RankedPaper


def _paper_metadata(
    *,
    paper: Paper,
    run_date: date,
    note_name: str,
    source: str,
    published: str,
    abstract_body: str,
    why: str,
    research_summary: Optional[tuple[str, str]],
) -> dict[str, object]:
    """
    Build JSON metadata that mirrors the Markdown note content.

    This function reuses the same derived strings used for the Markdown body, so
    JSON stays consistent even if why/research sections change upstream.
    """
    data: dict[str, object] = {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors or [],
        "source": source,
        "date": run_date.isoformat(),
        "link": paper.link_abs,
        "published": published,
        "abstract": abstract_body,
        "why_this_paper": why,
        "categories": paper.categories or [],
        "note_path": f"library/{run_date.isoformat()}/{note_name}.md",
        "related_local_papers": [],
    }
    if research_summary is not None:
        heading, body_text = research_summary
        data["research_summary"] = {
            "heading": heading,
            "body": body_text,
        }
    return data


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
    Header: Title, arXiv ID, Published, Authors, Link, Categories; then Abstract; then Why this paper (and optional Research summary).
    """
    paper = ranked.paper
    run_subdir = Path(library_dir) / run_date.isoformat()
    run_subdir.mkdir(parents=True, exist_ok=True)
    name = safe_paper_id_for_path(paper.id)
    path = run_subdir / f"{name}.md"
    metadata_path = run_subdir / f"{name}.json"

    why = ranked.why_this_paper or "—"
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

## Why this paper

{why}{research_section}

## Key points

(TODO: add your notes)
"""

    path.write_text(body, encoding="utf-8")
    metadata = _paper_metadata(
        paper=paper,
        run_date=run_date,
        note_name=name,
        source=source_str,
        published=published,
        abstract_body=abstract_body,
        why=why,
        research_summary=research_summary,
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+_-]*")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "we",
    "with",
}

_TOPIC_STOPWORDS = {
    "paper",
    "papers",
    "matched",
    "keyword",
    "keywords",
    "study",
    "studies",
    "method",
    "methods",
    "approach",
    "approaches",
    "model",
    "models",
    "task",
    "tasks",
    "result",
    "results",
    "analysis",
    "using",
    "based",
    "system",
    "systems",
    "local",
    "notes",
    "note",
    "summary",
    "google",
    "scholar",
    "inbox",
    "alert",
    "alerts",
    "arxiv",
}


def _iter_library_metadata_paths(library_dir: str | Path) -> list[Path]:
    base = Path(library_dir)
    if not base.exists():
        return []
    dated_dirs = [p for p in base.iterdir() if p.is_dir()]
    paths: list[Path] = []
    for day_dir in sorted(dated_dirs, key=lambda p: p.name, reverse=True):
        paths.extend(sorted(day_dir.glob("*.json"), key=lambda p: p.name))
    return paths


def _read_metadata(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _tokenize_text(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in _TOKEN_RE.findall((part or "").lower()):
            if len(token) >= 3 and token not in _STOPWORDS:
                tokens.add(token)
    return tokens


def _normalized_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(v).strip() for v in values if str(v).strip()]


def _normalized_display_map(values: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in _normalized_list(values):
        key = value.lower()
        if key not in result:
            result[key] = value
    return result


def _metadata_date(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text


def _metadata_sort_date(value: Any) -> tuple[int, str]:
    text = _metadata_date(value)
    if not text or text in {"—", "-", "unknown", "Unknown", "n/a", "N/A"}:
        return (0, "")
    return (1, text)


def _metadata_run_date(value: Any) -> date | None:
    text = _metadata_date(value)
    if not text or text in {"—", "-", "unknown", "Unknown", "n/a", "N/A"}:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _week_bounds(run_date: date) -> tuple[date, date]:
    week_start = run_date - timedelta(days=run_date.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _build_related_entry(candidate: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "id": str(candidate.get("id", "")),
        "title": str(candidate.get("title", "Untitled")),
        "date": _metadata_date(candidate.get("date")),
        "note_path": str(candidate.get("note_path", "")),
        "link": str(candidate.get("link", "")),
        "reasons": reasons,
    }


def _score_related_candidate(target: dict[str, Any], candidate: dict[str, Any]) -> tuple[float, list[str]]:
    target_authors = _normalized_display_map(target.get("authors"))
    candidate_authors = _normalized_display_map(candidate.get("authors"))
    shared_author_keys = sorted(target_authors.keys() & candidate_authors.keys())
    shared_authors = [target_authors[k] for k in shared_author_keys]

    target_categories = _normalized_display_map(target.get("categories"))
    candidate_categories = _normalized_display_map(candidate.get("categories"))
    shared_category_keys = sorted(target_categories.keys() & candidate_categories.keys())
    shared_categories = [target_categories[k] for k in shared_category_keys]

    target_tokens = _tokenize_text(
        str(target.get("title", "")),
        str(target.get("abstract", "")),
        str(target.get("why_this_paper", "")),
    )
    candidate_tokens = _tokenize_text(
        str(candidate.get("title", "")),
        str(candidate.get("abstract", "")),
        str(candidate.get("why_this_paper", "")),
    )
    shared_tokens = sorted(target_tokens & candidate_tokens)

    score = 0.0
    reasons: list[str] = []

    if shared_authors:
        score += min(len(shared_authors), 2) * 4.0
        author_label = "same author" if len(shared_authors) == 1 else "same authors"
        reasons.append(f"{author_label}: {', '.join(shared_authors[:2])}")
    if shared_categories:
        score += min(len(shared_categories), 2) * 2.5
        reasons.append(f"same arXiv categories: {', '.join(shared_categories[:2])}")
    if shared_tokens:
        score += min(len(shared_tokens), 4) * 1.25
        reasons.append(f"similar topics: {', '.join(shared_tokens[:4])}")
    if str(target.get("source", "")).strip() and target.get("source") == candidate.get("source"):
        score += 0.25
        source = str(target.get("source", "")).strip()
        source_label = "Scholar Inbox" if source == "scholar_alerts" else "arXiv" if source == "arxiv" else source
        reasons.append(f"same source: {source_label}")

    return score, reasons


def enrich_related_local_papers(
    library_dir: str | Path,
    target_metadata_paths: list[str | Path],
    *,
    max_related: int = 3,
) -> None:
    all_metadata_by_id: dict[str, dict[str, Any]] = {}
    for metadata_path in _iter_library_metadata_paths(library_dir):
        metadata = _read_metadata(metadata_path)
        if metadata is None:
            continue
        paper_id = str(metadata.get("id", "")).strip()
        if paper_id and paper_id not in all_metadata_by_id:
            all_metadata_by_id[paper_id] = metadata

    for target_path_raw in target_metadata_paths:
        target_path = Path(target_path_raw)
        target = _read_metadata(target_path)
        if target is None:
            continue

        target_id = str(target.get("id", "")).strip()
        candidates: list[tuple[float, dict[str, Any], list[str]]] = []
        for candidate_id, candidate in all_metadata_by_id.items():
            if not candidate_id or candidate_id == target_id:
                continue
            score, reasons = _score_related_candidate(target, candidate)
            if score <= 0:
                continue
            candidates.append((score, candidate, reasons))

        candidates.sort(
            key=lambda item: (
                item[0],
                _metadata_sort_date(item[1].get("published") or item[1].get("date")),
                str(item[1].get("title", "")),
            ),
            reverse=True,
        )
        target["related_local_papers"] = [
            _build_related_entry(candidate, reasons)
            for score, candidate, reasons in candidates[:max_related]
        ]
        target_path.write_text(
            json.dumps(target, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _weekly_note_href(note_path: str, paper_dir: str | Path, digest_dir: Path) -> str:
    if not note_path.strip():
        return ""
    absolute_note = Path(paper_dir).parent / note_path
    return Path(os.path.relpath(absolute_note, start=digest_dir)).as_posix()


def _format_counter(counter: Counter[str], limit: int) -> str:
    items = [(name, count) for name, count in counter.most_common() if name]
    if not items:
        return "None"
    return ", ".join(f"{name} ({count})" for name, count in items[:limit])


def _collect_weekly_topic_counts(entries: list[dict[str, Any]], limit: int = 5) -> list[str]:
    counter: Counter[str] = Counter()
    for entry in entries:
        tokens = _tokenize_text(
            str(entry.get("title", "")),
            str(entry.get("abstract", "")),
            str(entry.get("why_this_paper", "")),
        )
        counter.update(token for token in tokens if token not in _TOPIC_STOPWORDS)
    return [topic for topic, _count in counter.most_common(limit)]


def _collect_weekly_category_counts(entries: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for entry in entries:
        counter.update(_normalized_list(entry.get("categories")))
    return counter


def _collect_weekly_author_counts(entries: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for entry in entries:
        counter.update(_normalized_list(entry.get("authors")))
    return counter


def _weekly_highlight_score(entry: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    source = str(entry.get("source", "")).strip()
    why = str(entry.get("why_this_paper", "")).strip()
    related_count = len(entry.get("related_local_papers", [])) if isinstance(entry.get("related_local_papers"), list) else 0
    has_research_summary = isinstance(entry.get("research_summary"), dict)

    if source != "scholar_alerts":
        score += 3.0
        reasons.append("strong relevance signal")
    else:
        score += 1.0
        reasons.append("useful Scholar Inbox lead")

    if why and why != "—":
        score += 2.0
    if has_research_summary:
        score += 2.0
        reasons.append("has research summary")
    if related_count > 0:
        score += min(related_count, 3)
        reasons.append("links to local reading history")
    if _metadata_sort_date(entry.get("published") or entry.get("date"))[0] == 1:
        score += 0.5

    return score, reasons[:2]


def _select_weekly_highlights(
    discovery_entries: list[dict[str, Any]],
    scholar_entries: list[dict[str, Any]],
    limit: int = 3,
) -> list[tuple[dict[str, Any], list[str]]]:
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for entry in [*discovery_entries, *scholar_entries]:
        score, reasons = _weekly_highlight_score(entry)
        scored.append((score, entry, reasons))

    scored.sort(
        key=lambda item: (
            item[0],
            _metadata_sort_date(item[1].get("published") or item[1].get("date")),
            str(item[1].get("title", "")),
        ),
        reverse=True,
    )
    return [(entry, reasons) for _score, entry, reasons in scored[:limit]]


def _weekly_summary_sentence(
    top_topics: list[str],
    category_counts: Counter[str],
) -> str:
    top_categories = [name for name, _count in category_counts.most_common(2) if name]
    if top_topics and top_categories:
        return (
            f"This week focused on {', '.join(top_topics[:3])}, "
            f"with most papers landing in {', '.join(top_categories)}."
        )
    if top_topics:
        return f"This week focused on {', '.join(top_topics[:3])}."
    if top_categories:
        return f"This week was concentrated in {', '.join(top_categories)}."
    return "This week has no dominant topic or category signal yet."


def _append_weekly_entries(
    lines: list[str],
    entries: list[dict[str, Any]],
    *,
    paper_dir: str | Path,
    digest_dir: Path,
    include_why: bool,
) -> None:
    current_day = None
    for entry in entries:
        entry_day = _metadata_date(entry.get("date")) or "Unknown date"
        if entry_day != current_day:
            lines.append(f"### {entry_day}")
            lines.append("")
            current_day = entry_day

        title = str(entry.get("title", "Untitled"))
        link = str(entry.get("link", "")).strip()
        why = str(entry.get("why_this_paper", "—")).strip() or "—"
        note_path = str(entry.get("note_path", "")).strip()
        note_label = Path(note_path).name if note_path else ""
        note_href = _weekly_note_href(note_path, paper_dir, digest_dir) if note_path else ""

        lines.append(f"#### {title}")
        lines.append("")
        if include_why:
            lines.append(f"- **Why**: {why}")
        if link:
            lines.append(f"- **Link**: {link}")
        if note_label and note_href:
            lines.append(f"- **Local note**: [{note_label}]({note_href})")
        lines.append("")


def write_weekly_digest(
    library_dir: str | Path,
    paper_dir: str | Path,
    run_date: date,
) -> Path:
    """
    Write a weekly digest under paper_dir/weekly/ covering the current local week.

    The digest is rebuilt from library metadata across the full week window, so it
    includes papers from earlier days in the same week, not just the current run.
    """
    week_start, week_end = _week_bounds(run_date)
    weekly_dir = Path(paper_dir) / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    path = weekly_dir / f"{week_start.isoformat()}_to_{week_end.isoformat()}.md"

    weekly_by_id: dict[str, dict[str, Any]] = {}
    for metadata_path in _iter_library_metadata_paths(library_dir):
        metadata = _read_metadata(metadata_path)
        if metadata is None:
            continue
        metadata_day = _metadata_run_date(metadata.get("date"))
        if metadata_day is None or not (week_start <= metadata_day <= week_end):
            continue
        paper_id = str(metadata.get("id", "")).strip()
        if paper_id and paper_id not in weekly_by_id:
            weekly_by_id[paper_id] = metadata

    discovery_entries = sorted(
        [m for m in weekly_by_id.values() if str(m.get("source", "")).strip() != "scholar_alerts"],
        key=lambda item: (
            _metadata_sort_date(item.get("published") or item.get("date")),
            str(item.get("title", "")),
        ),
        reverse=True,
    )
    scholar_entries = sorted(
        [m for m in weekly_by_id.values() if str(m.get("source", "")).strip() == "scholar_alerts"],
        key=lambda item: (
            _metadata_sort_date(item.get("published") or item.get("date")),
            str(item.get("title", "")),
        ),
        reverse=True,
    )

    all_entries = [*discovery_entries, *scholar_entries]
    topic_counts = _collect_weekly_topic_counts(all_entries)
    category_counts = _collect_weekly_category_counts(all_entries)
    author_counts = _collect_weekly_author_counts(all_entries)
    highlights = _select_weekly_highlights(discovery_entries, scholar_entries)

    total = len(discovery_entries) + len(scholar_entries)
    lines: list[str] = [
        f"# Weekly digest — {week_start.isoformat()} to {week_end.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Total papers: {total}",
        f"- Daily Precision: {len(discovery_entries)}",
        f"- Scholar Inbox: {len(scholar_entries)}",
        f"- Top topics: {', '.join(topic_counts) if topic_counts else 'None'}",
        f"- Top categories: {_format_counter(category_counts, 5)}",
        f"- Frequent authors: {_format_counter(author_counts, 5)}",
        f"- Highlights: {'; '.join(str(entry.get('title', 'Untitled')) for entry, _reasons in highlights) if highlights else 'None'}",
        "",
        _weekly_summary_sentence(topic_counts, category_counts),
        "",
        "---",
        "",
        "## Highlights",
        "",
    ]
    for entry, reasons in highlights:
        title = str(entry.get("title", "Untitled"))
        entry_day = _metadata_date(entry.get("date")) or "Unknown date"
        link = str(entry.get("link", "")).strip()
        note_path = str(entry.get("note_path", "")).strip()
        note_label = Path(note_path).name if note_path else ""
        note_href = _weekly_note_href(note_path, paper_dir, weekly_dir) if note_path else ""
        lines.append(f"### {title} ({entry_day})")
        lines.append("")
        if reasons:
            lines.append(f"- **Why highlighted**: {'; '.join(reasons)}")
        if link:
            lines.append(f"- **Link**: {link}")
        if note_label and note_href:
            lines.append(f"- **Local note**: [{note_label}]({note_href})")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
        "## Daily Precision",
        "",
        f"Papers: {len(discovery_entries)}",
        "",
        ]
    )
    _append_weekly_entries(
        lines,
        discovery_entries,
        paper_dir=paper_dir,
        digest_dir=weekly_dir,
        include_why=True,
    )
    lines.append("---")
    lines.append("")
    lines.append("## Scholar Inbox")
    lines.append("")
    lines.append(f"Papers: {len(scholar_entries)}")
    lines.append("")
    _append_weekly_entries(
        lines,
        scholar_entries,
        paper_dir=paper_dir,
        digest_dir=weekly_dir,
        include_why=False,
    )

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_daily_digest(
    discovery: list[RankedPaper],
    scholar_inbox: list[RankedPaper],
    paper_dir: str | Path,
    run_date: date,
) -> Path:
    """
    Write daily digest to paper_dir/YYYY-MM-DD.md (single file per day).
    Sections:
    - Daily Precision: discovery feed (capped by max_papers_per_day).
    - Scholar Inbox: Scholar Alerts items (uncapped or max_items_per_run capped).
    """
    Path(paper_dir).mkdir(parents=True, exist_ok=True)
    path = Path(paper_dir) / f"{run_date.isoformat()}.md"

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
