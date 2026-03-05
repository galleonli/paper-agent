"""Tests for constrained top-k selection (topic_cap, k, min_topics, explore_ratio)."""

import pytest

from paper_agent.models import Paper
from paper_agent.policy.base import ScoredPaper
from paper_agent.selection.constrained_topk import select_topk


def _scored(
    paper_id: str,
    score: float,
    topic_id: str = "cs.LG",
    uncertainty: float = 0.0,
    novelty: float = 0.0,
    exploration_pick: bool = False,
) -> ScoredPaper:
    return ScoredPaper(
        paper=Paper(
            id=paper_id,
            title="Title",
            summary="Summary",
            authors=["A"],
            categories=[topic_id],
            updated="2023-01-01T00:00:00Z",
            link_abs=f"https://arxiv.org/abs/{paper_id}",
            link_pdf=None,
        ),
        score=score,
        uncertainty=uncertainty,
        novelty=novelty,
        why_this_paper="—",
        topic_id=topic_id,
        exploration_pick=exploration_pick,
    )


def test_select_topk_respects_k() -> None:
    """select_topk returns at most k papers."""
    scored = [_scored(str(i), 1.0 + i * 0.1) for i in range(10)]
    result = select_topk(scored, k=3, explore_ratio=0.0, topic_cap=10, min_topics=1)
    assert len(result) == 3


def test_select_topk_empty_returns_empty() -> None:
    """Empty scored list or k=0 returns empty."""
    assert select_topk([], k=5) == []
    assert select_topk([_scored("1", 1.0)], k=0) == []


def test_select_topk_topic_cap() -> None:
    """No more than topic_cap papers per topic."""
    scored = [
        _scored("1", 1.0, "cs.LG"),
        _scored("2", 0.9, "cs.LG"),
        _scored("3", 0.8, "cs.LG"),
        _scored("4", 0.7, "cs.CL"),
    ]
    result = select_topk(scored, k=4, explore_ratio=0.0, topic_cap=2, min_topics=1)
    assert len(result) <= 4
    topic_counts: dict[str, int] = {}
    for s in result:
        topic_counts[s.topic_id] = topic_counts.get(s.topic_id, 0) + 1
    assert topic_counts.get("cs.LG", 0) <= 2
    assert topic_counts.get("cs.CL", 0) <= 2


def test_select_topk_min_topics_preference() -> None:
    """When possible, selection includes at least min_topics distinct topics."""
    scored = [
        _scored("1", 1.0, "cs.LG"),
        _scored("2", 0.95, "cs.LG"),
        _scored("3", 0.9, "cs.CL"),
        _scored("4", 0.85, "cs.AI"),
    ]
    result = select_topk(scored, k=3, explore_ratio=0.0, topic_cap=2, min_topics=2)
    topics = {s.topic_id for s in result}
    assert len(topics) >= 2 or len(result) < 3


def test_select_topk_explore_ratio_slots() -> None:
    """With explore_ratio > 0, exploration (uncertainty+novelty) can fill slots after exploit."""
    high_score = _scored("1", 10.0)
    high_score.uncertainty = 0.0
    high_score.novelty = 0.0
    low_score_high_unc = _scored("2", 0.1)
    low_score_high_unc.uncertainty = 5.0
    low_score_high_unc.novelty = 0.0
    scored = [high_score, low_score_high_unc]
    result = select_topk(scored, k=2, explore_ratio=0.5, topic_cap=10, min_topics=1)
    assert len(result) == 2
    ids = [s.paper.id for s in result]
    assert "1" in ids
    assert "2" in ids


def test_select_topk_n_less_than_k_returns_all_capped() -> None:
    """When n < k, returns at most n (and topic_cap still applies)."""
    scored = [_scored("1", 1.0), _scored("2", 0.9)]
    result = select_topk(scored, k=10, explore_ratio=0.0, topic_cap=5, min_topics=1)
    assert len(result) == 2


def test_select_topk_n_le_k_still_marks_exploration_picks() -> None:
    """When n <= k, explore_ratio is still applied: some papers get exploration_pick=True."""
    # 2 papers, k=2, explore_ratio=0.5 -> 1 exploit, 1 explore; both selected, one marked exploration
    scored = [
        _scored("1", 10.0, "cs.LG", uncertainty=0.0, novelty=0.0),
        _scored("2", 0.5, "cs.CL", uncertainty=5.0, novelty=0.0),
    ]
    result = select_topk(scored, k=2, explore_ratio=0.5, topic_cap=10, min_topics=1)
    assert len(result) == 2
    exploration_picks = sum(1 for s in result if s.exploration_pick)
    assert exploration_picks >= 1, "when n<=k with explore_ratio>0, at least one should be exploration_pick"


def test_select_topk_marks_exploration_picks() -> None:
    """Papers chosen in the exploration phase have exploration_pick=True."""
    # Need n > k so exploit/explore slots run: k=2, 3 papers. Paper 1 high score; paper 2 high uncertainty.
    scored = [
        _scored("1", 10.0, "cs.LG", uncertainty=0.0, novelty=0.0),
        _scored("2", 0.1, "cs.CL", uncertainty=5.0, novelty=0.0),
        _scored("3", 0.2, "cs.AI", uncertainty=0.0, novelty=0.0),
    ]
    result = select_topk(scored, k=2, explore_ratio=0.5, topic_cap=10, min_topics=1)
    assert len(result) == 2
    by_id = {s.paper.id: s for s in result}
    assert by_id["1"].exploration_pick is False  # exploit slot
    assert by_id["2"].exploration_pick is True   # exploration slot (high uncertainty)
