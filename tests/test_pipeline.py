"""Pipeline tests: run with arXiv disabled; policy+selection produce RankedPaper with why_this_paper."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_agent.core.models import Paper
from paper_agent.filter_papers import RankedPaper
from paper_agent.pipeline import run as pipeline_run
from paper_agent.run import run


def _minimal_config(tmp_path: Path, **kwargs: str) -> str:
    base = """
timezone: "UTC"
interests:
  seeds: []
  keyphrases: []
  negative_keyphrases: []
direction:
  max_papers_per_day: 5
  lookback_days: 3
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
  library_dir: "{library_dir}"
  daily_dir: "{daily_dir}"
  state_dir: "{state_dir}"
  logs_dir: "{logs_dir}"
summarize:
  enabled: false
  brief_summary: true
export:
  formats: ["bibtex", "ris"]
sources:
  arxiv:
    enabled: false
  scholar_alerts:
    enabled: false
feedback:
  blocked_phrases: []
  blocked_authors: []
  boosted_phrases: []
selection:
  explore_ratio: 0.2
  topic_cap: 3
  min_topics: 1
policy:
  type: "deterministic"
  alpha: 0.5
  lambda_ucb: 1.0
  mu_novelty: 0.3
  ridge: 1.0
advanced:
  request_timeout_seconds: 30
  max_retries: 3
  max_results_per_query: 50
"""
    return base.format(
        library_dir=(tmp_path / "library").as_posix(),
        daily_dir=(tmp_path / "daily").as_posix(),
        state_dir=(tmp_path / "state").as_posix(),
        logs_dir=(tmp_path / "logs").as_posix(),
        **kwargs,
    )


def test_run_with_arxiv_disabled_returns_list(tmp_path: Path) -> None:
    """With sources.arxiv.enabled=false, pipeline runs and returns a list (no fetch)."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_minimal_config(tmp_path), encoding="utf-8")
    result = run(config_path)
    assert isinstance(result, list)
    assert len(result) == 0


def test_run_creates_logs_file(tmp_path: Path) -> None:
    """Pipeline run always creates logs/latest.log with a summary line."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_minimal_config(tmp_path), encoding="utf-8")
    result = run(config_path)
    assert isinstance(result, list)
    log_path = tmp_path / "logs" / "latest.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    # Summary line with counters is written even when no new papers
    assert "fetched_total=" in content
    assert "after_category=" in content
    assert "after_filters=" in content
    assert "new_count=" in content


def test_run_returns_ranked_papers_with_why_this_paper(tmp_path: Path) -> None:
    """Pipeline returns list of RankedPaper; when non-empty, items have why_this_paper (policy)."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_minimal_config(tmp_path), encoding="utf-8")
    result = run(config_path)
    assert all(isinstance(r, RankedPaper) for r in result)
    for r in result:
        assert hasattr(r, "paper") and hasattr(r, "why_this_paper")


def test_run_with_linucb_policy_logs_diversity_metrics(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """With policy.type=linucb, pipeline runs and log line includes num_topics and exploration_picks."""
    import logging
    caplog.set_level(logging.INFO)  # noqa: F811
    config_path = tmp_path / "config.yaml"
    config_content = _minimal_config(tmp_path)
    config_content = config_content.replace('type: "deterministic"', 'type: "linucb"')
    config_path.write_text(config_content, encoding="utf-8")
    run(config_path)
    log_text = caplog.text
    assert "num_topics=" in log_text
    assert "exploration_picks=" in log_text


def test_slack_failure_still_saves_seen_no_repush(tmp_path: Path) -> None:
    """When Slack raises, pipeline logs warning and does not re-raise; seen is saved so next run has 0 new."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    config_content = _minimal_config(tmp_path)
    config_content = config_content.replace(
        "sources:\n  arxiv:\n    enabled: false",
        "sources:\n  arxiv:\n    enabled: true",
    )
    config_content = config_content.replace('webhook_url: ""', 'webhook_url: "https://hooks.slack.com/fake"')
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content, encoding="utf-8")

    # Use a date within lookback_days=3 so the paper is not filtered out
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fake_paper = Paper(
        id="2301.99999",
        title="Test Paper",
        summary="Abstract here.",
        authors=["Alice"],
        categories=["cs.LG"],
        updated=now_iso,
        link_abs="https://arxiv.org/abs/2301.99999",
        link_pdf=None,
    )

    with (
        patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]),
        patch("paper_agent.pipeline.send_slack_brief", side_effect=RuntimeError("Slack failed")),
    ):
        result = pipeline_run(config_path)
    assert len(result) == 1
    assert result[0].paper.id == "2301.99999"

    seen_path = state_dir / "seen.json"
    assert seen_path.exists()
    data = json.loads(seen_path.read_text(encoding="utf-8"))
    assert "2301.99999" in data.get("seen_ids", [])

    with (
        patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]),
        patch("paper_agent.pipeline.send_slack_brief"),
    ):
        result2 = pipeline_run(config_path)
    assert len(result2) == 0


def test_integration_autotune_pipeline_contract(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """When autotune.enabled is toggled, pipeline uses correct policy params and logs candidate/reward."""
    import logging

    caplog.set_level(logging.INFO)  # noqa: F811

    # Start from minimal config and enable linucb + autotune.
    base_cfg = _minimal_config(tmp_path)
    base_cfg = base_cfg.replace('type: "deterministic"', 'type: "linucb"')
    autotune_block = """
autotune:
  enabled: true
  method: "thompson"
  random_seed: 123
  schedule:
    daily_hour_utc: 23
    weekly_day_of_week: "sun"
  candidates:
    - id: "fast"
      alpha: 0.1
      lambda_ucb: 0.2
      mu_novelty: 0.3
      ridge: 1.0
"""
    config_content = base_cfg + autotune_block
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content, encoding="utf-8")

    # Case 1: autotune.enabled=false => static policy and autotune_enabled=False in logs.
    static_cfg = config_content.replace("enabled: true", "enabled: false")
    config_path.write_text(static_cfg, encoding="utf-8")
    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[]):
        run(config_path)
    log_text_static = caplog.text
    assert "autotune_enabled=False" in log_text_static

    # Case 2: autotune.enabled=true => AutoTuneController is used and candidate name appears.
    caplog.clear()
    config_path.write_text(config_content, encoding="utf-8")
    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[]):
        run(config_path)
    log_text = caplog.text
    assert "autotune_enabled=True" in log_text
    assert "autotune_candidate_name=" in log_text
    assert "autotune_daily_reward=" in log_text


def test_autotune_flag_false_when_policy_not_linucb(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Even if autotune.enabled=true, when policy.type!=linucb the logs must show autotune_enabled=False."""
    import logging

    caplog.set_level(logging.INFO)  # noqa: F811

    base_cfg = _minimal_config(tmp_path)
    # Keep policy.type deterministic, but configure autotune.enabled=true.
    autotune_block = """
autotune:
  enabled: true
  method: "thompson"
  random_seed: 123
  schedule:
    daily_hour_utc: 23
    weekly_day_of_week: "sun"
  candidates:
    - id: "fast"
      alpha: 0.1
      lambda_ucb: 0.2
      mu_novelty: 0.3
      ridge: 1.0
"""
    config_content = base_cfg + autotune_block
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content, encoding="utf-8")

    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[]):
        run(config_path)
    log_text = caplog.text
    # AutoTune is configured but not active because policy.type != linucb.
    assert "autotune_enabled=False" in log_text
