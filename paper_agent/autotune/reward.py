"""Reward computation for AutoTune.

compute_reward is a pure function that maps feedback events and diversity/novelty
metrics to a scalar run-level reward using weights from config.autotune.reward.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, Mapping

from paper_agent.core.config import Config


FeedbackEvent = Mapping[str, Any]


def compute_reward(
    events: Iterable[FeedbackEvent],
    diversity_metrics: Mapping[str, float],
    novelty_metrics: Mapping[str, float],
    config: Config,
) -> float:
    """Compute scalar run-level reward from feedback events and diversity/novelty.

    Parameters
    ----------
    events:
        Iterable of feedback events. Each event is a mapping with at least:
        - event_type: one of {"click", "open_note", "star", "export", "skip", "mute"}
        - paper_id: string identifier for the paper
        - timestamp: ISO-8601 string (not used in this function)
    diversity_metrics:
        Mapping with optional keys:
        - "num_topics": number of distinct topics among selected papers.
        - "exploration_picks": number of exploration picks in the run.
    novelty_metrics:
        Mapping with optional keys:
        - "avg_novelty": average novelty across selected papers.
    config:
        Full Config object; this function uses config.autotune.reward.* weights.
    """
    reward_cfg = config.autotune.reward

    # Aggregate per-paper event flags (0/1) for each type.
    # If multiple events of the same type occur for the same paper in a run,
    # they are treated as a single positive (clipped at 1).
    paper_events: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ev in events:
        etype = str(ev.get("event_type", "")).lower()
        pid = str(ev.get("paper_id", "")).strip()
        if not pid or etype not in {
            "click",
            "open_note",
            "star",
            "export",
            "skip",
            "mute",
        }:
            continue
        paper_events[pid][etype] = 1

    papers_reward = 0.0
    s = reward_cfg.signals
    for _, flags in paper_events.items():
        r_i = (
            s.click * flags.get("click", 0)
            + s.open_note * flags.get("open_note", 0)
            + s.star * flags.get("star", 0)
            + s.export * flags.get("export", 0)
            + s.skip * flags.get("skip", 0)
            + s.mute * flags.get("mute", 0)
        )
        papers_reward += r_i

    d_cfg = reward_cfg.diversity
    num_topics = float(diversity_metrics.get("num_topics", 0.0))
    exploration_picks = float(diversity_metrics.get("exploration_picks", 0.0))
    avg_novelty = float(novelty_metrics.get("avg_novelty", 0.0))

    diversity_reward = (
        d_cfg.num_topics * num_topics
        + d_cfg.exploration_picks * exploration_picks
        + d_cfg.avg_novelty * avg_novelty
    )

    return papers_reward + diversity_reward


__all__ = ["compute_reward", "FeedbackEvent"]

