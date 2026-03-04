"""Tests for lookback date filter (UTC)."""

from datetime import datetime, timedelta, timezone

import pytest

from paper_agent.dates import parse_arxiv_updated, within_lookback


def test_parse_arxiv_updated() -> None:
    """Parse ISO date from arXiv updated string."""
    assert parse_arxiv_updated("2023-01-15T12:00:00Z") is not None
    assert parse_arxiv_updated("") is None
    assert parse_arxiv_updated("invalid") is None


def test_within_lookback_recent() -> None:
    """Paper updated today is within 7 days lookback."""
    now = datetime.now(timezone.utc)
    s = now.isoformat().replace("+00:00", "Z")
    assert within_lookback(s, 7) is True


def test_within_lookback_old() -> None:
    """Paper updated 10 days ago is outside 3 days lookback."""
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    assert within_lookback(old, 3) is False
