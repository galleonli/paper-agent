"""Tests for AutoTuneController (discrete candidates + Thompson Sampling)."""

from datetime import date, timedelta
from pathlib import Path

from paper_agent.autotune import AutoTuneController, TunedPolicyParams
from paper_agent.autotune.base import AutoTuneContext
from paper_agent.core.config import Config


def _config_with_autotune(tmp_path: Path) -> Config:
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
  random_seed: 123
  schedule:
    daily_hour_utc: 23
    weekly_day_of_week: "sun"
  candidates:
    - id: "baseline"
      alpha: 0.5
      lambda_ucb: 1.0
      mu_novelty: 0.3
      ridge: 1.0
    - id: "explore"
      alpha: 0.8
      lambda_ucb: 1.2
      mu_novelty: 0.5
      ridge: 1.0
"""
    from paper_agent.core.config import load_config

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_text, encoding="utf-8")
    return load_config(cfg_path)


def test_choose_config_returns_candidate_params(tmp_path: Path) -> None:
    """AutoTuneController.choose_config returns one of the configured candidates."""
    cfg = _config_with_autotune(tmp_path)
    controller = AutoTuneController(cfg, cfg.delivery.state_dir)
    ctx = AutoTuneContext(run_date=date.today())
    params = controller.choose_config(ctx)

    assert isinstance(params, TunedPolicyParams)
    assert params.candidate_id in {"baseline", "explore"}
    # Parameters should match the chosen candidate definition or fall back to policy config.
    if params.candidate_id == "baseline":
        assert params.alpha == 0.5
    elif params.candidate_id == "explore":
        assert params.alpha == 0.8


def test_update_persists_state_and_daily_history(tmp_path: Path) -> None:
    """AutoTuneController.update stores reward statistics and daily history."""
    cfg = _config_with_autotune(tmp_path)
    controller = AutoTuneController(cfg, cfg.delivery.state_dir)
    ctx = AutoTuneContext(run_date=date(2026, 3, 5), num_papers=3, num_topics=2, exploration_picks=1, avg_novelty=0.4)
    params = controller.choose_config(ctx)

    controller.update(reward=2.5, context=ctx, chosen_config=params)

    # Reload controller to ensure state was persisted.
    controller2 = AutoTuneController(cfg, cfg.delivery.state_dir)
    state = controller2._state  # type: ignore[attr-defined]
    assert "daily_history" in state
    assert any(entry["reward"] == 2.5 for entry in state["daily_history"])


def test_autotune_choose_and_update(tmp_path: Path) -> None:
    """choose_config returns a valid candidate and update increments count and mean_reward."""
    cfg = _config_with_autotune(tmp_path)
    controller = AutoTuneController(cfg, cfg.delivery.state_dir)
    ctx = AutoTuneContext(run_date=date(2026, 3, 5))

    params1 = controller.choose_config(ctx)
    params2 = controller.choose_config(ctx)

    # With fixed seed and symmetric priors, both picks should be from the configured pool.
    assert params1.candidate_id in {"baseline", "explore"}
    assert params2.candidate_id in {"baseline", "explore"}

    # After one update, exposure count and statistics should change.
    controller.update(reward=1.0, context=ctx, chosen_config=params1)
    state = controller._state  # type: ignore[attr-defined]
    c_entry = state["candidates"][params1.candidate_id]
    ts_state = c_entry["ts_state"]
    assert ts_state["count"] == 1
    assert ts_state["mean_reward"] == 1.0


def test_autotune_thompson_converges_basic(tmp_path: Path) -> None:
    """Simulate rounds where candidate 'A' always gets higher reward; it should be chosen more often."""
    # Three candidates: A (best), B, C.
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
  random_seed: 123
  schedule:
    daily_hour_utc: 23
    weekly_day_of_week: "sun"
  candidates:
    - id: "A"
      alpha: 0.5
      lambda_ucb: 1.0
      mu_novelty: 0.3
      ridge: 1.0
    - id: "B"
      alpha: 0.5
      lambda_ucb: 1.0
      mu_novelty: 0.3
      ridge: 1.0
    - id: "C"
      alpha: 0.5
      lambda_ucb: 1.0
      mu_novelty: 0.3
      ridge: 1.0
"""
    from paper_agent.core.config import load_config

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_text, encoding="utf-8")
    cfg = load_config(cfg_path)

    controller = AutoTuneController(cfg, cfg.delivery.state_dir)

    picks: dict[str, int] = {"A": 0, "B": 0, "C": 0}
    today = date(2026, 3, 1)
    total_rounds = 200

    for i in range(total_rounds):
        ctx = AutoTuneContext(run_date=today + timedelta(days=i))
        params = controller.choose_config(ctx)
        cid = params.candidate_id
        picks[cid] = picks.get(cid, 0) + 1

        # Candidate A always receives higher reward.
        if cid == "A":
            r = 2.0
        else:
            r = 0.5
        controller.update(reward=r, context=ctx, chosen_config=params)

    # After warmup, A should be picked much more often than others.
    assert picks["A"] > picks["B"]
    assert picks["A"] > picks["C"]
    assert picks["A"] > total_rounds * 0.5


def test_autotune_rollback(tmp_path: Path) -> None:
    """If current candidate underperforms best-known config, controller rolls back."""
    cfg = _config_with_autotune(tmp_path)
    controller = AutoTuneController(cfg, cfg.delivery.state_dir)

    # Simulate that "baseline" has good historical reward.
    state = controller._state  # type: ignore[attr-defined]
    state["candidates"]["baseline"]["ts_state"] = {
        "count": 10,
        "mean_reward": 5.0,
        "reward_sq_sum": 250.0,
    }
    state["candidates"]["explore"]["ts_state"] = {
        "count": 0,
        "mean_reward": 0.0,
        "reward_sq_sum": 0.0,
    }
    controller._current_candidate_id = "explore"  # type: ignore[attr-defined]
    state["current_candidate_id"] = "explore"

    # Force guardrails to trigger rollback quickly.
    cfg.autotune.guardrails.rollback_days = 1
    cfg.autotune.guardrails.max_daily_delta_reward = -0.1

    ctx = AutoTuneContext(run_date=date(2026, 3, 10))
    # Give "explore" a very bad reward.
    controller.update(reward=-10.0, context=ctx, chosen_config=TunedPolicyParams(
        alpha=0.5,
        lambda_ucb=1.0,
        mu_novelty=0.3,
        ridge=1.0,
        candidate_id="explore",
    ))

    # After update, controller should have rolled back to "baseline".
    new_state = controller._state  # type: ignore[attr-defined]
    assert new_state["current_candidate_id"] == "baseline"

