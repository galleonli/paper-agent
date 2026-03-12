"""CLI tests for `python -m paper_agent today --json` and list --json."""

import json
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path

from paper_agent.cli import main as cli_main
from tests.helpers import write_config, write_paper_json


def test_today_json_sorts_by_published_then_date(tmp_path: Path, monkeypatch) -> None:
    """today --json returns today's papers sorted by published (or date) descending."""
    # Prepare config and library structure.
    config_path = write_config(tmp_path)
    library_dir = tmp_path / "library"
    today_str = date.today().isoformat()
    day_dir = library_dir / today_str
    day_dir.mkdir(parents=True)

    # Older published date but higher lexicographically smaller id.
    write_paper_json(
        day_dir,
        "a.json",
        paper_id="paper-old",
        title="Old Paper",
        published="2024-01-01",
    )
    # Newer published date should come first.
    write_paper_json(
        day_dir,
        "b.json",
        paper_id="paper-new",
        title="New Paper",
        published="2024-03-10",
    )
    # No published date: falls back to date; should come after both.
    write_paper_json(
        day_dir,
        "c.json",
        paper_id="paper-nopub",
        title="No Published Date",
        published=None,
    )

    # Invoke CLI: python -m paper_agent today --json --config config.yaml
    monkeypatch.setattr(
        "sys.argv",
        [
            "paper_agent",
            "today",
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

    # Should be a list of three entries sorted by published/date desc.
    # Missing published falls back to today's date, so comes first.
    assert isinstance(data, list)
    assert [p["id"] for p in data] == ["paper-nopub", "paper-new", "paper-old"]


def test_list_json_sorts_by_published_then_date_and_respects_limit(tmp_path: Path, monkeypatch) -> None:
    """list --json [--limit] returns recent papers sorted by published (or date) descending."""
    config_path = write_config(tmp_path)
    library_dir = tmp_path / "library"

    # Two days of data: 2025-01-03 (newer) and 2025-01-02 (older).
    d_new = library_dir / "2025-01-03"
    d_old = library_dir / "2025-01-02"
    d_new.mkdir(parents=True)
    d_old.mkdir(parents=True)

    # Newer published date on newer day.
    write_paper_json(
        d_new,
        "a.json",
        paper_id="p-new",
        title="New Paper",
        published="2025-01-10",
    )
    # Older published date on newer day.
    write_paper_json(
        d_new,
        "b.json",
        paper_id="p-mid",
        title="Mid Paper",
        published="2025-01-05",
    )
    # Published on older day, should come last.
    write_paper_json(
        d_old,
        "c.json",
        paper_id="p-old",
        title="Old Paper",
        published="2025-01-01",
    )

    # First, without limit: should return all 3, sorted by published desc.
    monkeypatch.setattr(
        "sys.argv",
        [
            "paper_agent",
            "list",
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
    assert isinstance(data, list)
    assert [p["id"] for p in data] == ["p-new", "p-mid", "p-old"]

    # Then, with limit=2: only the top two remain.
    monkeypatch.setattr(
        "sys.argv",
        [
            "paper_agent",
            "list",
            "--json",
            "--limit",
            "2",
            "--config",
            str(config_path),
        ],
        raising=False,
    )
    buf2 = StringIO()
    with redirect_stdout(buf2):
        cli_main()

    out2 = buf2.getvalue().strip()
    data2 = json.loads(out2)
    assert isinstance(data2, list)
    assert [p["id"] for p in data2] == ["p-new", "p-mid"]

