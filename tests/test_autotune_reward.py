"""Tests for AutoTune reward computation."""

from pathlib import Path

from paper_agent.autotune.reward import compute_reward
from paper_agent.core.config import Config, load_config


def _config_for_reward(tmp_path: Path) -> Config:
    yaml_text = f"""
interests:
  seeds: []
direction:
  max_papers_per_day: 5
  lookback_days: 3
  allow_categories: ["cs.LG"]
  deny_categories: []
  queries: []
  include_keywords: []
  exclude_keywords: []
delivery:
  library_dir: "{(tmp_path / "library").as_posix()}"
  paper_dir: "{(tmp_path / "daily").as_posix()}"
  state_dir: "{(tmp_path / "state").as_posix()}"
  logs_dir: "{(tmp_path / "logs").as_posix()}"
summarize:
  enabled: false
  provider: openai
  model: gpt-4o-mini
  language: en
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
  type: "linucb"
  alpha: 0.5
  lambda_ucb: 1.0
  mu_novelty: 0.3
  ridge: 1.0
advanced:
  request_timeout_seconds: 30
  max_retries: 3
  max_results_per_query: 50
autotune:
  enabled: true
  method: "thompson"
  schedule:
    daily_hour_utc: 23
    weekly_day_of_week: "sun"
  candidates:
    - id: "baseline"
      alpha: 0.5
      lambda_ucb: 1.0
      mu_novelty: 0.3
      ridge: 1.0
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_text, encoding="utf-8")
    return load_config(cfg_path)


def test_compute_reward_with_basic_events(tmp_path: Path) -> None:
    """compute_reward matches expected weighted sum for events + diversity/novelty."""
    cfg = _config_for_reward(tmp_path)
    events = [
        {"event_type": "click", "paper_id": "p1", "timestamp": "2026-03-05T10:00:00Z"},
        {"event_type": "open_note", "paper_id": "p1", "timestamp": "2026-03-05T10:05:00Z"},
        {"event_type": "star", "paper_id": "p2", "timestamp": "2026-03-05T10:10:00Z"},
    ]
    diversity = {"num_topics": 3, "exploration_picks": 1}
    novelty = {"avg_novelty": 0.5}

    value = compute_reward(events, diversity, novelty, cfg)

    s = cfg.autotune.reward.signals
    d = cfg.autotune.reward.diversity
    # p1: click + open_note, p2: star
    expected_papers = s.click * 1 + s.open_note * 1 + s.star * 1
    expected_diversity = (
        d.num_topics * diversity["num_topics"]
        + d.exploration_picks * diversity["exploration_picks"]
        + d.avg_novelty * novelty["avg_novelty"]
    )
    assert value == expected_papers + expected_diversity


def test_compute_reward_ignores_unknown_events(tmp_path: Path) -> None:
    """Unknown event types or missing paper_id are ignored."""
    cfg = _config_for_reward(tmp_path)
    events = [
        {"event_type": "unknown", "paper_id": "p1", "timestamp": "2026-03-05T10:00:00Z"},
        {"event_type": "click", "paper_id": "", "timestamp": "2026-03-05T10:01:00Z"},
    ]
    diversity = {"num_topics": 0, "exploration_picks": 0}
    novelty = {"avg_novelty": 0.0}

    value = compute_reward(events, diversity, novelty, cfg)
    assert value == 0.0


def test_load_feedback_events_falls_back_to_yaml(tmp_path: Path) -> None:
    """If jsonl has no events for today, _load_feedback_events should fall back to YAML."""
    from datetime import date
    from paper_agent.pipeline import _load_feedback_events

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)

    # JSONL exists but only has events from a different date.
    jsonl_path = state_dir / "feedback_log.jsonl"
    jsonl_path.write_text(
        '{"event_type":"click","paper_id":"old","timestamp":"2026-03-04T10:00:00Z"}\n',
        encoding="utf-8",
    )

    # YAML has today's event.
    yaml_path = state_dir / "feedback.yaml"
    yaml_path.write_text(
        "events:\n"
        "  - event_type: click\n"
        "    paper_id: p1\n"
        "    timestamp: 2026-03-05T12:00:00Z\n",
        encoding="utf-8",
    )

    today = date(2026, 3, 5)
    events = _load_feedback_events(state_dir, today)
    assert any(e.get("paper_id") == "p1" for e in events)


def test_reward_skip_and_mute_weights(tmp_path: Path) -> None:
    """Skip penalty is weak and mute penalty is strong, controlled by config."""
    cfg = _config_for_reward(tmp_path)
    s = cfg.autotune.reward.signals

    events_skip = [
        {"event_type": "skip", "paper_id": "p1", "timestamp": "2026-03-05T10:00:00Z"},
    ]
    events_mute = [
        {"event_type": "mute", "paper_id": "p1", "timestamp": "2026-03-05T10:00:00Z"},
    ]
    diversity = {"num_topics": 0, "exploration_picks": 0}
    novelty = {"avg_novelty": 0.0}

    reward_skip = compute_reward(events_skip, diversity, novelty, cfg)
    reward_mute = compute_reward(events_mute, diversity, novelty, cfg)

    assert reward_skip == s.skip
    assert reward_mute == s.mute
    assert abs(reward_mute) > abs(reward_skip)

