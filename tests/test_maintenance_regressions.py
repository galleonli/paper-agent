import json
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

import pytest

from paper_agent.core.config import load_config
from paper_agent.core.state import load_seen, save_seen
from paper_agent.filter_papers import RankedPaper
from paper_agent.output.local import write_daily_digest, write_local_note
from paper_agent.pipeline import run
from paper_agent.sources import scholar_alerts_source
from tests.helpers import make_paper, write_config


@pytest.mark.parametrize("layout", ["nested", "custom"])
def test_daily_links_and_metadata_resolve_to_real_notes(tmp_path: Path, layout: str):
    paper_dir = tmp_path / "Papers"
    library = paper_dir / "library" if layout == "nested" else tmp_path / "Custom Library"
    day = datetime.now().date()
    paper = RankedPaper(paper=make_paper("paper-1"), why_this_paper="Relevant")
    note = write_local_note(paper, library, day, paper_dir=paper_dir)
    metadata = json.loads(note.with_suffix(".json").read_text())
    assert (paper_dir / metadata["note_path"]).resolve() == note.resolve()
    digest = write_daily_digest([paper], [], paper_dir, day, library_dir=library)
    href = re.search(r"\*\*Local note\*\*: \[[^\]]+\]\(([^)]+)\)", digest.read_text()).group(1)
    assert (digest.parent / unquote(href)).resolve() == note.resolve()
    assert " " not in href


def test_a_later_run_keeps_earlier_daily_digest_entries(tmp_path: Path):
    config = write_config(tmp_path, arxiv_enabled=True)
    for paper_id in ["first", "second"]:
        with patch("paper_agent.pipeline.fetch_arxiv", return_value=[make_paper(paper_id, title=paper_id)]):
            assert len(run(config)) == 1
    text = (tmp_path / "daily" / f"{datetime.now().date().isoformat()}.md").read_text()
    assert "### first" in text
    assert "### second" in text
    assert "Total papers: 2" in text


def test_scholar_items_are_retried_after_output_failure(tmp_path: Path):
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    fixture = Path(__file__).parent / "fixtures" / "sample_scholar_alert.eml"
    raw = fixture.read_text().replace("Date: Thu, 02 Jan 2025 10:00:00 +0000", f"Date: {datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}")
    (eml_dir / "alert.eml").write_text(raw)
    config = write_config(tmp_path, scholar_enabled=True, scholar_eml_dir=str(eml_dir), lookback_days=7)
    with (
        patch("paper_agent.sources.scholar_alerts_source.arxiv_source.fetch_arxiv_by_id", return_value=None),
        patch("paper_agent.sources.scholar_alerts_source._fetch_title_abstract_from_url", return_value=(None, None)),
    ):
        with patch("paper_agent.pipeline.write_local_note", side_effect=OSError("disk unavailable")):
            with pytest.raises(OSError, match="disk unavailable"):
                run(config)
        assert load_seen(tmp_path / "state") == set()
        recovered = run(config)
        assert recovered
        assert all(item.paper.id in load_seen(tmp_path / "state") for item in recovered)
        assert run(config) == []


def test_failed_seen_write_preserves_previous_state(tmp_path: Path):
    save_seen(tmp_path, {"first"})
    with patch("paper_agent.core.state.os.replace", side_effect=OSError("disk unavailable")):
        with pytest.raises(OSError):
            save_seen(tmp_path, {"second"})
    assert load_seen(tmp_path) == {"first"}
    assert [p.name for p in tmp_path.iterdir()] == ["seen.json"]


@pytest.mark.parametrize("data", [[], None, "invalid"])
def test_non_object_seen_file_does_not_crash(tmp_path: Path, data):
    (tmp_path / "seen.json").write_text(json.dumps(data))
    assert load_seen(tmp_path) == set()


def test_email_login_failure_is_visible_without_leaking_server_error(tmp_path: Path, monkeypatch):
    config = load_config(write_config(tmp_path, scholar_enabled=True, scholar_provider="gmail"))
    config.sources.scholar_alerts.email.imap_host = "imap.example.com"
    config.sources.scholar_alerts.email.imap_user = "test@example.com"
    config.sources.scholar_alerts.email.imap_password_env = "PAPER_AGENT_TEST_PASSWORD"
    monkeypatch.setenv("PAPER_AGENT_TEST_PASSWORD", "private-password")
    with patch("paper_agent.sources.scholar_alerts_source.imaplib.IMAP4_SSL", side_effect=OSError("private-password")):
        with pytest.raises(RuntimeError, match="connection or login failed") as error:
            scholar_alerts_source.fetch(datetime.now(timezone.utc), 7, config)
    assert "private-password" not in str(error.value)


def test_scholar_deduplicates_before_applying_run_limit(tmp_path: Path):
    config = load_config(write_config(tmp_path, scholar_enabled=True))
    config.sources.scholar_alerts.max_items_per_run = 2
    now = datetime.now(timezone.utc)
    links = ["https://example.com/seen", "https://example.com/new", "https://example.com/new", "https://example.com/older"]
    items = [scholar_alerts_source._RawItem("Paper", link, "Abstract", now, []) for link in links]
    seen_id = scholar_alerts_source._namespaced_id(scholar_alerts_source._stable_paper_id(links[0]))
    save_seen(config.delivery.state_dir, {seen_id})
    with (
        patch.object(scholar_alerts_source, "_raw_items_from_source", return_value=items),
        patch.object(scholar_alerts_source, "_fetch_title_abstract_from_url", return_value=(None, None)) as enrich,
    ):
        papers = scholar_alerts_source.fetch(now, 7, config)
    assert [paper.link_abs for paper in papers] == [links[1], links[3]]
    assert enrich.call_count == 2
