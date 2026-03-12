"""Tests for shared test helpers (config writing, YAML escaping)."""

from pathlib import Path

import pytest

from paper_agent.config import load_config
from tests.helpers import write_config


def test_write_config_escapes_quotes_and_backslashes_in_inline_lists(tmp_path: Path) -> None:
    """Values with quotes and backslashes in scholar_from_addresses produce valid YAML that round-trips."""
    addresses = [
        'normal@example.com',
        'test"quote@example.com',
        'path\\with\\backslash@example.com',
        'both\\"mixed@example.com',
    ]
    config_path = write_config(tmp_path, scholar_from_addresses=addresses)
    cfg = load_config(config_path)
    assert cfg.sources.scholar_alerts.email.from_addresses == addresses
