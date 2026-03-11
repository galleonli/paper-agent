"""CLI tests for `python -m paper_agent search --query ... --json`."""

import json
from contextlib import redirect_stdout
from pathlib import Path
from io import StringIO

from paper_agent.cli import main as cli_main
from tests.test_pipeline import _minimal_config


def _write_config(tmp_path: Path) -> Path:
    cfg_text = _minimal_config(tmp_path)
    path = tmp_path / "config.yaml"
    path.write_text(cfg_text, encoding="utf-8")
    return path


def _write_paper_json(
    day_dir: Path,
    filename: str,
    *,
    paper_id: str,
    title: str,
    abstract: str = "",
    categories: list[str] | None = None,
    authors: list[str] | None = None,
    published: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "id": paper_id,
        "title": title,
        "date": day_dir.name,
        "abstract": abstract,
        "categories": categories or [],
        "authors": authors or [],
        "published": published,
        "note_path": f"library/{day_dir.name}/{paper_id}.md",
    }
    (day_dir / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_search_empty_query_sorts_by_date_key(tmp_path: Path, monkeypatch) -> None:
    """search --query \"\" sorts all entries by published/date descending when no tokens."""
    config_path = _write_config(tmp_path)
    library_dir = tmp_path / "library"
    d1 = library_dir / "2025-01-02"
    d2 = library_dir / "2025-01-03"
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)

    _write_paper_json(d1, "a.json", paper_id="p-old", title="Old", published="2025-01-01")
    _write_paper_json(d2, "b.json", paper_id="p-new", title="New", published="2025-01-10")

    monkeypatch.setattr(
        "sys.argv",
        ["paper_agent", "search", "--query", "", "--json", "--config", str(config_path)],
        raising=False,
    )
    buf = StringIO()
    with redirect_stdout(buf):
        cli_main()

    out = buf.getvalue().strip()
    data = json.loads(out)
    assert isinstance(data, list)
    assert [p["id"] for p in data] == ["p-new", "p-old"]


def test_search_prioritizes_title_phrase_over_abstract(tmp_path: Path, monkeypatch) -> None:
    """search ranks title/author phrase matches higher than abstract-only matches."""
    config_path = _write_config(tmp_path)
    library_dir = tmp_path / "library"
    d = library_dir / "2025-01-02"
    d.mkdir(parents=True)

    # Title match (should rank highest).
    _write_paper_json(
        d,
        "title.json",
        paper_id="p-title",
        title="Continual Learning with Sparse Experts",
        abstract="Some abstract.",
        authors=["Alice"],
        published="2025-01-02",
    )
    # Abstract-only match.
    _write_paper_json(
        d,
        "abs.json",
        paper_id="p-abs",
        title="Unrelated Title",
        abstract="This work studies continual learning in depth.",
        authors=["Bob"],
        published="2025-01-03",
    )
    # Irrelevant.
    _write_paper_json(
        d,
        "none.json",
        paper_id="p-none",
        title="Completely Different Topic",
        abstract="No relation.",
        authors=["Carol"],
        published="2025-01-04",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "paper_agent",
            "search",
            "--query",
            "continual learning",
            "--json",
            "--config",
            str(config_path),
        ],
        raising=False,
    )
    buf = StringIO()
    with redirect_stdout(buf):
        cli_main()

    out = buf.getvalue().strip()
    data = json.loads(out)
    ids = [p["id"] for p in data]
    # Title match first, abstract-only match second; irrelevant paper excluded.
    assert ids[0] == "p-title"
    assert "p-abs" in ids
    assert "p-none" not in ids

