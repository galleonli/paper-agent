"""
Export selected papers to BibTeX and RIS (EndNote-compatible).
Writes to library_dir/YYYY-MM-DD: {id}.bib and {id}.ris.
"""

import re
from datetime import date
from pathlib import Path

from paper_agent.core.models import Paper
from paper_agent.core.utils import safe_paper_id_for_path


def _bibtex_escape(s: str) -> str:
    """Escape special chars for BibTeX."""
    return s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("&", "\\&")


def _ris_escape(s: str) -> str:
    """RIS format: no leading/trailing spaces; newlines as \\n in some fields."""
    return s.strip().replace("\r\n", " ").replace("\n", " ")


def _year_from_updated(updated: str) -> str:
    """Extract 4-digit year from ISO date string."""
    if not updated:
        return ""
    m = re.search(r"(\d{4})", updated)
    return m.group(1) if m else ""


def write_bibtex(paper: Paper, library_dir: str | Path, run_date: date | None = None) -> Path:
    """Write one paper to library_dir[/YYYY-MM-DD]/{id}.bib. Returns path."""
    target_dir = Path(library_dir) / run_date.isoformat() if run_date is not None else Path(library_dir)
    path = target_dir / f"{safe_paper_id_for_path(paper.id)}.bib"
    path.parent.mkdir(parents=True, exist_ok=True)
    key = paper.id.replace(".", "_").replace(":", "_")[:64]
    authors_bt = " and ".join(_bibtex_escape(a) for a in paper.authors) if paper.authors else ""
    year = _year_from_updated(paper.updated)
    body = f"""@misc{{{key},
  title = {{{_bibtex_escape(paper.title)}}},
  author = {{{authors_bt}}},
  year = {{{year}}},
  url = {{{paper.link_abs}}},
  note = {{arXiv:{paper.id}}}
}}
"""
    path.write_text(body, encoding="utf-8")
    return path


def write_ris(paper: Paper, library_dir: str | Path, run_date: date | None = None) -> Path:
    """Write one paper to library_dir[/YYYY-MM-DD]/{id}.ris (EndNote-compatible). Returns path."""
    target_dir = Path(library_dir) / run_date.isoformat() if run_date is not None else Path(library_dir)
    path = target_dir / f"{safe_paper_id_for_path(paper.id)}.ris"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "TY  - GEN",
        f"TI  - {_ris_escape(paper.title)}",
        f"UR  - {paper.link_abs}",
        f"PY  - {_year_from_updated(paper.updated)}",
        "ER  - ",
    ]
    for a in (paper.authors or [])[:50]:
        lines.insert(-1, f"AU  - {_ris_escape(a)}")
    lines.insert(-1, f"N1  - arXiv:{paper.id}")
    body = "\n".join(lines)
    path.write_text(body, encoding="utf-8")
    return path
