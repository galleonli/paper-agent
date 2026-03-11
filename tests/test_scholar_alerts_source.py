"""Tests for Scholar Inbox email ingestion (mbox, eml_dir). No network; deterministic."""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_agent.core.config import (
    Config,
    DeliveryConfig,
    DirectionConfig,
    ScholarAlertsEmailConfig,
    ScholarAlertsLightFilterConfig,
    ScholarAlertsSourceConfig,
    SourcesConfig,
)
from paper_agent.core.models import Paper
from paper_agent.core.state import load_seen
from paper_agent.sources import scholar_alerts_source


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _base_config(tmp_path: Path, provider: str = "eml_dir", eml_dir: str = "", mbox_path: str = "") -> Config:
    """Minimal Config with Scholar Alerts (email)."""
    return Config(
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=7),
        delivery=DeliveryConfig(
            library_dir=str(tmp_path / "library"),
            daily_dir=str(tmp_path / "daily"),
            state_dir=str(tmp_path / "state"),
            logs_dir=str(tmp_path / "logs"),
        ),
        sources=SourcesConfig(
            scholar_alerts=ScholarAlertsSourceConfig(
                enabled=True,
                mode="email",
                email=ScholarAlertsEmailConfig(
                    provider=provider,
                    eml_dir=eml_dir or str(tmp_path / "eml"),
                    mbox_path=mbox_path,
                ),
                light_filter=ScholarAlertsLightFilterConfig(),
                max_items_per_run=200,
            )
        ),
    )


def test_parse_eml_extract_items() -> None:
    """Parse .eml fixture; extract items; assert (paper_id, received_ts, title, link)."""
    eml_bytes = (FIXTURE_DIR / "sample_scholar_alert.eml").read_bytes()
    items = scholar_alerts_source.parse_eml_extract_items(eml_bytes)
    assert len(items) == 3
    # Evidence: (paper_id, received_ts, title, link)
    by_id = {it[0]: (it[1], it[2], it[3]) for it in items}
    assert "scholar:arxiv:2501.00001" in by_id
    assert any(k.startswith("scholar:doi:") for k in by_id)
    assert any(k.startswith("scholar:urlhash:") for k in by_id)
    received, title, link = by_id["scholar:arxiv:2501.00001"]
    assert received is not None
    assert received.year == 2025 and received.month == 1 and received.day == 2
    assert "Continual Learning" in title
    assert "arxiv.org/abs/2501.00001" in link
    for paper_id, received_ts, title, link in items:
        assert paper_id.startswith("scholar:")
        assert title
        assert link.startswith("http")


def test_parse_html_eml_extract_items() -> None:
    """Parse HTML Scholar alert email and unwrap scholar redirect URLs."""
    eml_bytes = (FIXTURE_DIR / "sample_scholar_alert_html.eml").read_bytes()
    items = scholar_alerts_source.parse_eml_extract_items(eml_bytes)
    assert len(items) == 2
    links = [it[3] for it in items]
    assert "https://arxiv.org/abs/2602.00001" in links
    assert "https://example.com/manipulation-paper" in links
    titles = [it[2] for it in items]
    assert any("Continual Learning with Sparse Experts" in t for t in titles)


def test_parse_mbox_extract_items() -> None:
    """Parse .mbox fixture; extract items; assert same structure as EML."""
    mbox_path = str(FIXTURE_DIR / "sample_scholar_alert.mbox")
    items = scholar_alerts_source.parse_mbox_extract_items(mbox_path)
    assert len(items) >= 3
    paper_ids = [it[0] for it in items]
    assert "scholar:arxiv:2501.00001" in paper_ids
    for paper_id, received_ts, title, link in items:
        assert paper_id.startswith("scholar:")
        assert title
        assert link.startswith("http")


def test_dedup_idempotency(tmp_path: Path) -> None:
    """Second run with same eml_dir yields 0 new papers; seen contains scholar IDs."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert.eml", eml_dir / "a.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    first = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    second = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    assert len(first) >= 3
    assert len(second) == 0
    seen = load_seen(cfg.delivery.state_dir)
    for p in first:
        assert p.id in seen


def test_ordering_arrival_desc(tmp_path: Path) -> None:
    """Two emails with different dates: order is by received time descending (newest first)."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert.eml", eml_dir / "newer.eml")
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert_2.eml", eml_dir / "older.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    now = datetime(2025, 1, 5, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    # Newer email (02 Jan) has arxiv 2501.00001; older (31 Dec) has 2412.99999. Newest first.
    ids = [p.id for p in result]
    idx_2501 = next((i for i, pid in enumerate(ids) if "2501.00001" in pid), None)
    idx_2412 = next((i for i, pid in enumerate(ids) if "2412.99999" in pid), None)
    assert idx_2501 is not None and idx_2412 is not None
    assert idx_2501 < idx_2412


def test_fetch_disabled_returns_empty(tmp_path: Path) -> None:
    """When scholar_alerts.enabled=false, fetch returns []."""
    cfg = _base_config(tmp_path, eml_dir=str(tmp_path / "eml"))
    cfg.sources.scholar_alerts.enabled = False
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    assert result == []


def test_fetch_empty_eml_dir_returns_empty(tmp_path: Path) -> None:
    """When eml_dir is empty, fetch returns []."""
    (tmp_path / "eml").mkdir(exist_ok=True)
    cfg = _base_config(tmp_path, eml_dir=str(tmp_path / "eml"))
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    assert result == []


def test_fetch_mbox_from_fixture(tmp_path: Path) -> None:
    """Fetch from mbox path (fixture); returns papers with scholar IDs."""
    mbox_path = str(FIXTURE_DIR / "sample_scholar_alert.mbox")
    cfg = _base_config(tmp_path, provider="mbox", mbox_path=mbox_path, eml_dir="")
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    assert len(result) >= 3
    for p in result:
        assert p.id.startswith("scholar:")
        assert p.title
        assert p.link_abs.startswith("http")


def test_scholar_seen_namespace(tmp_path: Path) -> None:
    """Scholar IDs in state/seen.json are namespaced (scholar:...) so they do not collide with discovery."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert.eml", eml_dir / "a.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    assert len(result) > 0
    seen = load_seen(cfg.delivery.state_dir)
    for p in result:
        assert p.id in seen
        assert p.id.startswith("scholar:"), f"Scholar ID must be namespaced: {p.id}"


def test_light_filter_exclude_keywords_filters_items(tmp_path: Path) -> None:
    """exclude_keywords: items whose title or snippet contains a keyword are excluded (case-insensitive)."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert.eml", eml_dir / "a.eml")
    # Fixture has: "Continual Learning...", "Lifelong Representation...", "Incremental Learning in Robotics..."
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    cfg.sources.scholar_alerts.light_filter.exclude_keywords = ["continual"]
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    # "Continual Learning with Sparse Experts" should be excluded; 2 items remain
    assert len(result) == 2
    titles = [p.title for p in result]
    assert not any("Continual" in t for t in titles)
    assert any("Lifelong" in t or "Representation" in t for t in titles)
    assert any("Incremental" in t or "Robotics" in t for t in titles)


def test_light_filter_include_keywords_filters_items(tmp_path: Path) -> None:
    """include_keywords: only items whose title or snippet matches at least one keyword are kept."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert.eml", eml_dir / "a.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    cfg.sources.scholar_alerts.light_filter.include_keywords = ["robotics"]
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    # Only "Incremental Learning in Robotics" contains "robotics"
    assert len(result) == 1
    assert "Robotics" in result[0].title or "robotics" in result[0].title.lower()


def test_max_items_per_run_caps_results(tmp_path: Path) -> None:
    """max_items_per_run caps the number of Scholar Inbox papers returned (before unseen filter)."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert.eml", eml_dir / "a.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    cfg.sources.scholar_alerts.max_items_per_run = 2
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    assert len(result) == 2


def test_fetch_missing_mbox_path_returns_empty(tmp_path: Path) -> None:
    """When provider=mbox and mbox_path points to a non-existent file, fetch returns [] (no crash)."""
    cfg = _base_config(tmp_path, provider="mbox", mbox_path="/nonexistent/path/to/file.mbox", eml_dir="")
    now = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    assert result == []


def test_html_email_with_exclude_keyword_does_not_drop_all(tmp_path: Path) -> None:
    """
    With HTML alerts, exclude_keywords should only remove matching items, not all items
    due to HTML pollution in parsed text.
    """
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert_html.eml", eml_dir / "a.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    cfg.sources.scholar_alerts.light_filter.exclude_keywords = ["manipulation"]
    now = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)
    with patch("paper_agent.sources.scholar_alerts_source.arxiv_source.fetch_arxiv_by_id", return_value=None):
        result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)
    assert len(result) == 1
    assert "Continual Learning with Sparse Experts" in result[0].title


def test_fetch_imap_provider_uses_env_password_and_parses_items(tmp_path: Path) -> None:
    """provider=imap uses env password and returns parsed Scholar papers (no real network)."""
    eml_bytes = (FIXTURE_DIR / "sample_scholar_alert_html.eml").read_bytes()

    class _FakeIMAP:
        def __init__(self, host: str) -> None:
            assert host == "imap.gmail.com"
            self._selected = None
            self.logged_out = False

        def login(self, user: str, password: str):
            assert user == "user@example.com"
            assert password == "fake-app-password"
            return ("OK", [b"logged in"])

        def select(self, mailbox: str):
            self._selected = mailbox
            return ("OK", [b"1"])

        def search(self, _charset, _criteria: str):
            assert self._selected == "scholar-alerts"
            return ("OK", [b"1"])

        def fetch(self, _msg_id, _what: str):
            meta = b'1 (RFC822 {2048} INTERNALDATE "06-Mar-2026 10:00:00 +0000")'
            return ("OK", [(meta, eml_bytes), b")"])

        def logout(self):
            self.logged_out = True
            return ("BYE", [b"LOGOUT"])

    cfg = _base_config(tmp_path, provider="imap", eml_dir="", mbox_path="")
    cfg.sources.scholar_alerts.email.imap_host = "imap.gmail.com"
    cfg.sources.scholar_alerts.email.imap_user = "user@example.com"
    cfg.sources.scholar_alerts.email.imap_password_env = "IMAP_PASSWORD"
    cfg.sources.scholar_alerts.email.gmail_label = "scholar-alerts"
    cfg.sources.scholar_alerts.email.from_addresses = []

    now = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)
    with (
        patch.dict(os.environ, {"IMAP_PASSWORD": "fake-app-password"}, clear=False),
        patch("paper_agent.sources.scholar_alerts_source.imaplib.IMAP4_SSL", _FakeIMAP),
        patch("paper_agent.sources.scholar_alerts_source.arxiv_source.fetch_arxiv_by_id", return_value=None),
        patch(
            "paper_agent.sources.scholar_alerts_source._fetch_title_abstract_from_url",
            return_value=(None, None),
        ),
    ):
        result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)

    assert len(result) == 2
    assert result[0].id.startswith("scholar:")
    assert all(p.link_abs.startswith("http") for p in result)


def test_fetch_imap_missing_env_password_returns_empty(tmp_path: Path) -> None:
    """provider=imap without env password returns [] and does not connect."""
    cfg = _base_config(tmp_path, provider="imap", eml_dir="", mbox_path="")
    cfg.sources.scholar_alerts.email.imap_host = "imap.gmail.com"
    cfg.sources.scholar_alerts.email.imap_user = "user@example.com"
    cfg.sources.scholar_alerts.email.imap_password_env = "IMAP_PASSWORD"
    cfg.sources.scholar_alerts.email.gmail_label = "scholar-alerts"

    now = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "paper_agent.sources.scholar_alerts_source.imaplib.IMAP4_SSL",
            side_effect=AssertionError("should not connect without password"),
        ),
    ):
        result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)

    assert result == []


def test_scholar_arxiv_enrichment_uses_full_abstract_when_fetch_returns_paper(tmp_path: Path) -> None:
    """When fetch_arxiv_by_id returns a Paper, Scholar item gets full abstract and title from arXiv."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert_html.eml", eml_dir / "a.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    cfg.sources.scholar_alerts.light_filter.exclude_keywords = ["manipulation"]
    now = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)

    enriched = Paper(
        id="2602.00001",
        title="Enriched Title From arXiv",
        summary="Full abstract from arXiv API.",
        authors=["Alice", "Bob"],
        categories=["cs.LG"],
        updated="2026-02-01T00:00:00Z",
        link_abs="https://arxiv.org/abs/2602.00001",
        link_pdf="https://arxiv.org/pdf/2602.00001.pdf",
    )
    with patch(
        "paper_agent.sources.scholar_alerts_source.arxiv_source.fetch_arxiv_by_id",
        return_value=enriched,
    ):
        result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)

    assert len(result) == 1
    assert result[0].summary == "Full abstract from arXiv API."
    assert result[0].title == "Enriched Title From arXiv"
    assert result[0].authors == ["Alice", "Bob"]
    assert result[0].link_pdf == "https://arxiv.org/pdf/2602.00001.pdf"


def test_scholar_no_crash_when_arxiv_fetch_raises(tmp_path: Path) -> None:
    """When fetch_arxiv_by_id raises, fetch still returns papers with snippet (no crash)."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert_html.eml", eml_dir / "a.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    cfg.sources.scholar_alerts.light_filter.exclude_keywords = ["manipulation"]
    now = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)

    with patch(
        "paper_agent.sources.scholar_alerts_source.arxiv_source.fetch_arxiv_by_id",
        side_effect=RuntimeError("network error"),
    ):
        result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)

    assert len(result) == 1
    assert "Continual Learning with Sparse Experts" in result[0].title
    assert result[0].summary  # snippet from email; no crash


def test_fetch_title_abstract_from_url_returns_none_for_invalid_url() -> None:
    """Generic fetcher never raises; returns (None, None) for invalid or non-http URL."""
    from paper_agent.sources.scholar_alerts_source import _fetch_title_abstract_from_url

    assert _fetch_title_abstract_from_url("") == (None, None)
    assert _fetch_title_abstract_from_url("not-a-url") == (None, None)
    assert _fetch_title_abstract_from_url("ftp://example.com/x") == (None, None)


def test_scholar_generic_fetch_enriches_non_arxiv_when_fetcher_returns_title_and_abstract(
    tmp_path: Path,
) -> None:
    """When link is not arXiv, generic fetcher can enrich title/abstract; no crash when it fails."""
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "sample_scholar_alert_html.eml", eml_dir / "a.eml")
    cfg = _base_config(tmp_path, eml_dir=str(eml_dir))
    cfg.sources.scholar_alerts.light_filter.exclude_keywords = ["continual"]
    now = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)

    with patch(
        "paper_agent.sources.scholar_alerts_source._fetch_title_abstract_from_url",
        return_value=("Fetched Page Title", "Fetched abstract from page meta."),
    ):
        result = scholar_alerts_source.fetch(now, lookback_days=10, config=cfg)

    assert len(result) == 1
    assert "example.com" in result[0].link_abs
    assert result[0].summary == "Fetched abstract from page meta."
