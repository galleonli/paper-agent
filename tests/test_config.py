"""Tests for config load and validation (fail fast, clear errors)."""

import tempfile
from pathlib import Path

import pytest

from paper_agent.config import Config, load_config, DirectionConfig, InterestsConfig


def test_load_config_from_example(tmp_path: Path) -> None:
    """Loading valid YAML produces a Config with expected defaults."""
    yaml_content = """
interests:
  seeds: ["https://arxiv.org/abs/2301.12345"]
  keyphrases: ["contrastive learning"]
  negative_keyphrases: []
direction:
  max_papers_per_day: 10
  lookback_days: 2
  allow_categories: ["cs.LG"]
  deny_categories: []
  queries: []
  include_keywords: []
  exclude_keywords: []
  exclude_authors: []
delivery:
  slack:
    enabled: false
    webhook_url: ""
  library_dir: "./library"
  daily_dir: "./daily"
  state_dir: "./state"
  logs_dir: "./logs"
summarize:
  enabled: true
  brief_summary: true
export:
  formats: ["bibtex", "ris"]
advanced:
  request_timeout_seconds: 30
  max_retries: 3
  max_results_per_query: 100
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")

    cfg = load_config(config_path)
    assert isinstance(cfg, Config)
    assert cfg.direction.max_papers_per_day == 10
    assert cfg.direction.lookback_days == 2
    assert cfg.interests.keyphrases == ["contrastive learning"]
    assert cfg.delivery.state_dir == "./state"
    assert "bibtex" in cfg.export.formats and "ris" in cfg.export.formats


def test_load_config_missing_file() -> None:
    """Missing config path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config("/nonexistent/config.yaml")


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    """Invalid YAML raises ValueError with clear message."""
    p = tmp_path / "bad.yaml"
    p.write_text("not: valid: yaml: [", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_config(p)


def test_config_validation_direction_bounds() -> None:
    """Direction limits are validated (max_papers_per_day, lookback_days)."""
    with pytest.raises(ValueError):
        DirectionConfig(max_papers_per_day=0, lookback_days=1)
    with pytest.raises(ValueError):
        DirectionConfig(max_papers_per_day=10, lookback_days=0)
    # Valid
    d = DirectionConfig(max_papers_per_day=15, lookback_days=3)
    assert d.max_papers_per_day == 15


def test_config_validation_export_formats() -> None:
    """Export formats must be bibtex or ris."""
    from paper_agent.config import ExportConfig

    ExportConfig(formats=["bibtex", "ris"])
    ExportConfig(formats=["BibTeX"])  # normalized to lower
    with pytest.raises(ValueError, match="Unknown export format"):
        ExportConfig(formats=["pdf", "bibtex"])


def test_load_config_example_file() -> None:
    """config.example.yaml in repo root loads and has expected structure."""
    from pathlib import Path

    example = Path(__file__).resolve().parent.parent / "config.example.yaml"
    if not example.exists():
        pytest.skip("config.example.yaml not found (run from repo root)")
    cfg = load_config(example)
    assert cfg.direction.max_papers_per_day >= 1
    assert cfg.direction.lookback_days >= 1
    assert cfg.delivery.state_dir
    assert "bibtex" in cfg.export.formats and "ris" in cfg.export.formats
    assert cfg.sources.arxiv.enabled in (True, False)
    assert hasattr(cfg, "feedback") and hasattr(cfg.feedback, "blocked_phrases")
    assert hasattr(cfg, "selection") and hasattr(cfg.selection, "topic_cap")
    assert 0 <= cfg.selection.explore_ratio <= 1
    assert cfg.selection.topic_cap >= 1 and cfg.selection.min_topics >= 1
    assert hasattr(cfg, "policy") and cfg.policy.type in ("deterministic", "linucb")


def test_load_config_supports_scholar_imap_shape(tmp_path: Path) -> None:
    """Scholar Alerts email+imap config shape is accepted and normalized."""
    yaml_content = """
interests:
  seeds: []
  keyphrases: []
  negative_keyphrases: []
direction:
  max_papers_per_day: 12
  lookback_days: 7
  allow_categories: []
  deny_categories: []
  queries: []
  include_keywords: []
  exclude_keywords: []
  exclude_authors: []
delivery:
  slack:
    enabled: false
    webhook_url: ""
  library_dir: "./library"
  daily_dir: "./daily"
  state_dir: "./state"
  logs_dir: "./logs"
summarize:
  enabled: false
  brief_summary: true
export:
  formats: ["bibtex", "ris"]
sources:
  arxiv:
    enabled: true
  scholar_alerts:
    enabled: true
    mode: "email"
    email:
      provider: "imap"
      gmail_label: "scholar-alerts"
      imap_host: "imap.gmail.com"
      imap_user: "user@example.com"
      imap_password_env: "IMAP_PASSWORD"
      mbox_path: ""
      eml_dir: ""
      from_addresses: []
    max_items_per_run: 200
    push_to_slack: true
    ordering: "arrival"
    light_filter:
      include_keywords: []
      exclude_keywords:
        - "point cloud"
        - "humanoid"
        - "manipulation"
        - "survey"
      exclude_authors: []
advanced:
  request_timeout_seconds: 30
  max_retries: 3
  max_results_per_query: 100
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")
    cfg = load_config(config_path)

    sa = cfg.sources.scholar_alerts
    assert sa.enabled is True
    assert sa.mode == "email"
    assert sa.ordering == "arrival"
    assert sa.email.provider == "imap"
    assert sa.email.imap_host == "imap.gmail.com"
    assert sa.email.imap_user == "user@example.com"
    assert sa.email.imap_password_env == "IMAP_PASSWORD"
    assert sa.email.gmail_label == "scholar-alerts"
    assert sa.email.from_addresses == []
    assert sa.light_filter.exclude_keywords == [
        "point cloud",
        "humanoid",
        "manipulation",
        "survey",
    ]
