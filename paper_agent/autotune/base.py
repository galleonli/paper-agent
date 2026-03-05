"""AutoTuneController: discrete hyperparameter tuning with Thompson Sampling.

This module implements a meta-controller that selects one configuration from a
finite candidate pool and updates candidate statistics from scalar run-level
rewards. It does NOT change paper-level scoring logic; it only suggests
policy-layer parameters for the current run.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from paper_agent.core.config import AutotuneConfig, Config


AUTOTUNE_STATE_FILENAME = "autotune.json"


@dataclass
class TunedPolicyParams:
    """Resolved policy parameters for a single run."""

    alpha: float
    lambda_ucb: float
    mu_novelty: float
    ridge: float
    candidate_id: str


@dataclass
class AutoTuneContext:
    """Minimal context for AutoTune decisions."""

    run_date: date
    num_papers: int = 0
    num_topics: int = 0
    exploration_picks: int = 0
    avg_novelty: float = 0.0


class AutoTuneController:
    """Discrete AutoTune controller with Thompson Sampling over candidates.

    The controller is responsible for:
    - choosing a candidate configuration for the current run (choose_config)
    - updating candidate statistics from run-level reward (update)
    - applying rollback rules when a candidate underperforms consistently
    """

    def __init__(self, config: Config, state_dir: str | Path) -> None:
        self._config: Config = config
        self._autotune_cfg: AutotuneConfig = config.autotune
        self._state_dir = Path(state_dir)
        self._state_path = self._state_dir / AUTOTUNE_STATE_FILENAME
        seed = self._autotune_cfg.random_seed
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._state: Dict[str, Any] = self._load_state()
        self._current_candidate_id: Optional[str] = self._state.get("current_candidate_id")

    def choose_config(self, context: AutoTuneContext) -> TunedPolicyParams:
        """Select one candidate config for this run and return policy params.

        When AutoTune is disabled or method is "off", this returns the static
        policy parameters from config.policy and does not modify state.
        """
        if not self._autotune_cfg.enabled or self._autotune_cfg.method == "off":
            policy_cfg = self._config.policy
            return TunedPolicyParams(
                alpha=policy_cfg.alpha,
                lambda_ucb=policy_cfg.lambda_ucb,
                mu_novelty=policy_cfg.mu_novelty,
                ridge=policy_cfg.ridge,
                candidate_id="static",
            )

        candidates = self._state.get("candidates", {})
        if not candidates:
            # Fallback to static if configuration is empty.
            policy_cfg = self._config.policy
            return TunedPolicyParams(
                alpha=policy_cfg.alpha,
                lambda_ucb=policy_cfg.lambda_ucb,
                mu_novelty=policy_cfg.mu_novelty,
                ridge=policy_cfg.ridge,
                candidate_id="static",
            )

        # Thompson Sampling over candidate-level mean rewards.
        best_sample = -math.inf
        best_id: Optional[str] = None
        for cid, data in candidates.items():
            stats = data.get("ts_state", {})
            count = max(0, int(stats.get("count", 0)))
            mean_reward = float(stats.get("mean_reward", 0.0))
            if count <= 0:
                # No data yet: wide prior.
                sample = self._rng.gauss(0.0, 1.0)
            else:
                # Simple Normal posterior: variance shrinks with count.
                std = 1.0 / math.sqrt(count)
                sample = self._rng.gauss(mean_reward, std)
            if sample > best_sample:
                best_sample = sample
                best_id = cid

        assert best_id is not None
        self._current_candidate_id = best_id
        self._state["current_candidate_id"] = best_id
        self._state["last_choose_date"] = context.run_date.isoformat()
        self._ensure_candidate_entry(best_id)
        self._save_state()

        chosen = self._state["candidates"][best_id]
        return TunedPolicyParams(
            alpha=float(chosen.get("alpha", self._config.policy.alpha)),
            lambda_ucb=float(chosen.get("lambda_ucb", self._config.policy.lambda_ucb)),
            mu_novelty=float(chosen.get("mu_novelty", self._config.policy.mu_novelty)),
            ridge=float(chosen.get("ridge", self._config.policy.ridge)),
            candidate_id=best_id,
        )

    def update(
        self,
        reward: float,
        context: AutoTuneContext,
        chosen_config: TunedPolicyParams,
    ) -> None:
        """Update candidate statistics from run-level reward and maybe rollback."""
        if not self._autotune_cfg.enabled or self._autotune_cfg.method == "off":
            return

        cid = chosen_config.candidate_id
        self._ensure_candidate_entry(cid)
        c_entry = self._state["candidates"][cid]
        ts_state = c_entry.setdefault("ts_state", {})

        count = max(0, int(ts_state.get("count", 0)))
        mean = float(ts_state.get("mean_reward", 0.0))
        reward_sq_sum = float(ts_state.get("reward_sq_sum", 0.0))

        count += 1
        new_mean = mean + (reward - mean) / count
        reward_sq_sum += reward * reward

        ts_state["count"] = count
        ts_state["mean_reward"] = new_mean
        ts_state["reward_sq_sum"] = reward_sq_sum

        # Append daily history for auditability.
        history: List[Dict[str, Any]] = self._state.setdefault("daily_history", [])
        history.append(
            {
                "date": context.run_date.isoformat(),
                "candidate_id": cid,
                "reward": reward,
                "num_papers": context.num_papers,
                "num_topics": context.num_topics,
                "exploration_picks": context.exploration_picks,
                "avg_novelty": context.avg_novelty,
            }
        )

        # Rollback logic based on rolling average vs best candidate.
        self._maybe_rollback()
        self._save_state()

    def maybe_weekly_update(self, today: date) -> None:
        """Placeholder for weekly tuning; no-op in this implementation."""
        # Weekly meta-bandit is intentionally left for a later phase.
        self._state.setdefault("last_weekly_update", today.isoformat())
        self._save_state()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _load_state(self) -> Dict[str, Any]:
        if not self._state_path.exists():
            return self._initial_state_from_config()
        try:
            with open(self._state_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return self._initial_state_from_config()

        # Ensure candidates from config exist in state.
        if "candidates" not in data:
            data["candidates"] = {}
        for c in self._autotune_cfg.candidates:
            if c.id not in data["candidates"]:
                data["candidates"][c.id] = {
                    "alpha": c.alpha,
                    "lambda_ucb": c.lambda_ucb,
                    "mu_novelty": c.mu_novelty,
                    "ridge": c.ridge,
                    "ts_state": {"count": 0, "mean_reward": 0.0, "reward_sq_sum": 0.0},
                }
        return data

    def _initial_state_from_config(self) -> Dict[str, Any]:
        candidates_state: Dict[str, Any] = {}
        for c in self._autotune_cfg.candidates:
            candidates_state[c.id] = {
                "alpha": c.alpha,
                "lambda_ucb": c.lambda_ucb,
                "mu_novelty": c.mu_novelty,
                "ridge": c.ridge,
                "ts_state": {"count": 0, "mean_reward": 0.0, "reward_sq_sum": 0.0},
            }
        return {
            "version": 1,
            "current_candidate_id": None,
            "candidates": candidates_state,
            "daily_history": [],
            "weekly_history": [],
            "rollback": {
                "last_stable_candidate_id": None,
                "rollback_events": [],
            },
        }

    def _ensure_candidate_entry(self, candidate_id: str) -> None:
        if "candidates" not in self._state:
            self._state["candidates"] = {}
        if candidate_id not in self._state["candidates"]:
            # If not defined in config, fall back to current policy values.
            policy_cfg = self._config.policy
            self._state["candidates"][candidate_id] = {
                "alpha": policy_cfg.alpha,
                "lambda_ucb": policy_cfg.lambda_ucb,
                "mu_novelty": policy_cfg.mu_novelty,
                "ridge": policy_cfg.ridge,
                "ts_state": {"count": 0, "mean_reward": 0.0, "reward_sq_sum": 0.0},
            }

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, sort_keys=True)

    def _maybe_rollback(self) -> None:
        """Apply rollback if current candidate underperforms best one."""
        guard = self._autotune_cfg.guardrails
        candidates = self._state.get("candidates", {})
        if not candidates:
            return

        # Compute average reward per candidate.
        best_id: Optional[str] = None
        best_avg = -math.inf
        current_id = self._current_candidate_id or self._state.get("current_candidate_id")

        for cid, data in candidates.items():
            stats = data.get("ts_state", {})
            count = int(stats.get("count", 0))
            if count <= 0:
                continue
            mean_reward = float(stats.get("mean_reward", 0.0))
            if mean_reward > best_avg:
                best_avg = mean_reward
                best_id = cid

        if not current_id or not best_id:
            # Nothing to compare.
            return

        current_stats = candidates.get(current_id, {}).get("ts_state", {})
        current_count = int(current_stats.get("count", 0))
        current_avg = float(current_stats.get("mean_reward", 0.0))

        # Require enough observations on current candidate.
        if current_count < guard.rollback_days:
            return

        delta = current_avg - best_avg
        if delta < guard.max_daily_delta_reward:
            # Trigger rollback to best candidate.
            rollback_state = self._state.setdefault("rollback", {})
            rollback_state["last_stable_candidate_id"] = best_id
            events: List[Dict[str, Any]] = rollback_state.setdefault("rollback_events", [])
            events.append(
                {
                    "date": date.today().isoformat(),
                    "from_candidate_id": current_id,
                    "to_candidate_id": best_id,
                    "reason": "rolling_average_drop",
                    "delta_reward": delta,
                }
            )
            self._state["current_candidate_id"] = best_id
            self._current_candidate_id = best_id

