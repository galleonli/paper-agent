"""Tests for policy (deterministic scoring, why_this_paper, feedback)."""

import pytest

from paper_agent.config import (
    Config,
    FeedbackConfig,
    InterestsConfig,
    DirectionConfig,
    SelectionConfig,
)
from paper_agent.models import Paper
from paper_agent.policy.base import PolicyContext, ScoredPaper
from paper_agent.policy.deterministic import DeterministicPolicy


def _paper(
    id_: str = "2301.12345",
    title: str = "Contrastive learning for proteins",
    summary: str = "We use contrastive learning.",
    authors: list[str] | None = None,
    categories: list[str] | None = None,
) -> Paper:
    return Paper(
        id=id_,
        title=title,
        summary=summary,
        authors=authors or ["Alice"],
        categories=categories or ["cs.LG"],
        updated="2023-01-15T12:00:00Z",
        link_abs=f"https://arxiv.org/abs/{id_}",
        link_pdf=None,
    )


def test_deterministic_policy_scores_and_sets_why_this_paper() -> None:
    """Deterministic policy returns ScoredPaper with why_this_paper and score."""
    config = Config(
        interests=InterestsConfig(seeds=[]),
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=2, include_keywords=["contrastive", "protein"], exclude_keywords=[]),
        feedback=FeedbackConfig(),
        selection=SelectionConfig(),
    )
    papers = [
        _paper("1", title="Contrastive Representation Learning", summary="Protein folding."),
    ]
    context = PolicyContext(config)
    policy = DeterministicPolicy()
    result = policy.score(papers, context)
    assert len(result) == 1
    s = result[0]
    assert isinstance(s, ScoredPaper)
    assert s.paper.id == "1"
    assert s.score >= 1.0
    assert s.uncertainty == 0.0
    assert s.novelty == 0.0
    assert s.why_this_paper
    assert "contrastive" in s.why_this_paper.lower()
    assert "protein" in s.why_this_paper.lower()
    assert s.topic_id == "cs.LG"


def test_deterministic_policy_blocked_phrases_excludes() -> None:
    """Papers matching feedback.blocked_phrases are excluded from scored list."""
    config = Config(
        interests=InterestsConfig(seeds=[]),
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=2, include_keywords=["ml"], exclude_keywords=[]),
        feedback=FeedbackConfig(blocked_phrases=["survey", "review"]),
        selection=SelectionConfig(),
    )
    papers = [
        _paper("1", title="A survey of deep learning", summary="We survey the field."),
        _paper("2", title="Novel ML method", summary="We propose X."),
    ]
    context = PolicyContext(config)
    policy = DeterministicPolicy()
    result = policy.score(papers, context)
    ids = [s.paper.id for s in result]
    assert "1" not in ids
    assert "2" in ids


def test_deterministic_policy_blocked_authors_excludes() -> None:
    """Papers with feedback.blocked_authors are excluded."""
    config = Config(
        interests=InterestsConfig(seeds=[]),
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=2, include_keywords=["ml"], exclude_keywords=[]),
        feedback=FeedbackConfig(blocked_authors=["Bob"]),
        selection=SelectionConfig(),
    )
    papers = [
        _paper("1", authors=["Alice", "Bob Smith"]),
        _paper("2", authors=["Alice", "Charlie"]),
    ]
    context = PolicyContext(config)
    policy = DeterministicPolicy()
    result = policy.score(papers, context)
    ids = [s.paper.id for s in result]
    assert "1" not in ids
    assert "2" in ids


def test_deterministic_policy_boosted_phrases_increase_score() -> None:
    """Boosted phrases increase score (relative ordering)."""
    config = Config(
        interests=InterestsConfig(seeds=[]),
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=2, include_keywords=["learning"], exclude_keywords=[]),
        feedback=FeedbackConfig(boosted_phrases=["transformers"]),
        selection=SelectionConfig(),
    )
    papers = [
        _paper("1", title="Learning methods", summary="We study learning."),
        _paper("2", title="Learning with transformers", summary="We use transformers."),
    ]
    context = PolicyContext(config)
    policy = DeterministicPolicy()
    result = policy.score(papers, context)
    assert len(result) == 2
    scores = {s.paper.id: s.score for s in result}
    assert scores["2"] > scores["1"]


def test_deterministic_policy_empty_why_when_no_match() -> None:
    """When no keyphrase/seed matches, why_this_paper is fallback '—'."""
    config = Config(
        interests=InterestsConfig(seeds=[]),
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=2, include_keywords=[], exclude_keywords=[]),
        feedback=FeedbackConfig(),
        selection=SelectionConfig(),
    )
    papers = [_paper("1", title="Other topic", summary="Nothing matches.")]
    context = PolicyContext(config)
    policy = DeterministicPolicy()
    result = policy.score(papers, context)
    assert len(result) == 1
    assert result[0].why_this_paper == "—"
