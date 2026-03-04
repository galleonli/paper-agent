"""Tests for state management (seen.json, idempotency, catch-up)."""

from pathlib import Path

import pytest

from paper_agent.state import (
    load_seen,
    save_seen,
    is_seen,
    mark_seen,
    filter_unseen,
    normalize_paper_id,
    state_path,
)


def test_normalize_paper_id() -> None:
    """Paper IDs are normalized (arXiv URL and prefix stripped)."""
    assert normalize_paper_id("2301.12345") == "2301.12345"
    assert normalize_paper_id("https://arxiv.org/abs/2301.12345") == "2301.12345"
    assert normalize_paper_id("arXiv:2301.12345") == "2301.12345"
    assert normalize_paper_id("  arXiv:2302.00001  ") == "2302.00001"


def test_save_and_load_seen(tmp_path: Path) -> None:
    """Saving and loading seen IDs round-trips correctly."""
    seen = {"2301.12345", "2302.00001"}
    save_seen(tmp_path, seen)
    path = state_path(tmp_path)
    assert path.exists()
    loaded = load_seen(tmp_path)
    assert loaded == seen


def test_load_seen_missing_file(tmp_path: Path) -> None:
    """Missing seen.json returns empty set."""
    assert load_seen(tmp_path) == set()


def test_load_seen_invalid_json(tmp_path: Path) -> None:
    """Invalid JSON in seen.json returns empty set (no crash)."""
    path = state_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ invalid }", encoding="utf-8")
    assert load_seen(tmp_path) == set()


def test_is_seen(tmp_path: Path) -> None:
    """is_seen uses persisted state or provided cache."""
    save_seen(tmp_path, {"2301.12345"})
    assert is_seen(tmp_path, "2301.12345") is True
    assert is_seen(tmp_path, "2302.00001") is False
    assert is_seen(tmp_path, "https://arxiv.org/abs/2301.12345") is True
    # With cache
    assert is_seen(tmp_path, "2303.00000", seen_cache=set()) is False
    assert is_seen(tmp_path, "2303.00000", seen_cache={"2303.00000"}) is True


def test_mark_seen() -> None:
    """mark_seen adds normalized ID to set in place."""
    cache = set()
    mark_seen(cache, "https://arxiv.org/abs/2301.12345")
    assert "2301.12345" in cache


def test_filter_unseen(tmp_path: Path) -> None:
    """filter_unseen returns only IDs not in state; updates cache for persistence."""
    save_seen(tmp_path, {"2301.12345"})
    ids = ["2301.12345", "2302.00001", "2303.00001"]
    unseen, updated = filter_unseen(tmp_path, ids)
    assert unseen == ["2302.00001", "2303.00001"]
    assert "2301.12345" in updated
    assert "2302.00001" in updated
    assert "2303.00001" in updated
    # Persist and re-run: all should be seen (idempotency)
    save_seen(tmp_path, updated)
    unseen2, _ = filter_unseen(tmp_path, ids)
    assert unseen2 == []


def test_state_idempotency_second_run_no_duplicates(tmp_path: Path) -> None:
    """Second run with same paper IDs returns empty unseen (no duplicate deliveries)."""
    ids = ["2301.12345", "2302.00001"]
    unseen1, cache1 = filter_unseen(tmp_path, ids)
    assert len(unseen1) == 2
    save_seen(tmp_path, cache1)
    unseen2, _ = filter_unseen(tmp_path, ids)
    assert len(unseen2) == 0
