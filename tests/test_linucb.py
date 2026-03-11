"""LinUCB sanity tests: mocked features, preferences load/save, predicted reward + uncertainty."""

from pathlib import Path

import numpy as np
import pytest

from paper_agent.config import (
    Config,
    DirectionConfig,
    FeedbackConfig,
    InterestsConfig,
    PolicyConfig,
    SelectionConfig,
)
from paper_agent.core.config import DeliveryConfig
from paper_agent.core.preferences import (
    load_preferences,
    save_preferences,
    update_preferences,
)
from paper_agent.core.topic_stats import (
    load_topic_stats,
    novelty_from_counts,
    save_topic_stats,
    update_topic_stats_from_papers,
)
from paper_agent.features.encoder import encode_paper, get_feature_names
from paper_agent.models import Paper
from paper_agent.policy.base import PolicyContext
from paper_agent.policy.linucb import LinUCBPolicy


def _paper(
    id_: str = "2301.12345",
    title: str = "Contrastive learning",
    summary: str = "We use contrastive learning.",
    categories: list[str] | None = None,
) -> Paper:
    return Paper(
        id=id_,
        title=title,
        summary=summary,
        authors=["Alice"],
        categories=categories or ["cs.LG"],
        updated="2023-01-15T12:00:00Z",
        link_abs=f"https://arxiv.org/abs/{id_}",
        link_pdf=None,
    )


def _config(
    keyphrases: list[str] | None = None,
    allow_categories: list[str] | None = None,
    policy_type: str = "linucb",
    state_dir: str = "./state",
) -> Config:
    return Config(
        interests=InterestsConfig(seeds=[]),
        direction=DirectionConfig(
            max_papers_per_day=10,
            lookback_days=2,
            allow_categories=allow_categories or ["cs.LG", "cs.CL"],
            include_keywords=keyphrases or ["contrastive", "learning"],
            exclude_keywords=[],
        ),
        delivery=DeliveryConfig(state_dir=state_dir),
        feedback=FeedbackConfig(),
        selection=SelectionConfig(),
        policy=PolicyConfig(type=policy_type, alpha=0.5, lambda_ucb=1.0, mu_novelty=0.3, ridge=1.0),
    )


def test_features_encode_paper_consistent_dim() -> None:
    """Feature vector dimension matches get_feature_names length."""
    config = _config()
    names = get_feature_names(config)
    paper = _paper(title="Contrastive learning for NLP", summary="Learning.")
    x, names_out, matched = encode_paper(paper, config)
    assert len(x) == len(names)
    assert names == names_out
    assert "contrastive" in (m.lower() for m in matched) or "learning" in (m.lower() for m in matched)


def test_preferences_save_and_load(tmp_path: Path) -> None:
    """Save A, b to preferences.json; load returns correct theta and A_inv."""
    d = 4
    ridge = 1.0
    A = np.eye(d) * ridge + np.outer([1, 0, 0, 0], [1, 0, 0, 0])
    b = np.array([0.5, 0.1, 0.0, 0.0])
    save_preferences(tmp_path, A, b, ["bias", "f1", "f2", "f3"])
    theta, A_inv, names = load_preferences(tmp_path, d, ridge=ridge)
    np.testing.assert_allclose(theta, np.linalg.solve(A, b))
    np.testing.assert_allclose(A_inv, np.linalg.inv(A))
    assert names == ["bias", "f1", "f2", "f3"]


def test_preferences_cold_start_returns_zeros_and_ridge_inv(tmp_path: Path) -> None:
    """When preferences.json is missing, load_preferences returns theta=0, A_inv = I/ridge."""
    theta, A_inv, names = load_preferences(tmp_path, d=3, ridge=2.0, feature_names=[])
    np.testing.assert_allclose(theta, [0, 0, 0])
    np.testing.assert_allclose(A_inv, np.eye(3) / 2.0)
    assert names == []


def test_update_preferences_increments_A_and_b(tmp_path: Path) -> None:
    """update_preferences adds x x^T to A and reward*x to b."""
    names = ["bias", "f1", "f2"]
    x = np.array([1.0, 1.0, 0.0])
    update_preferences(tmp_path, names, x, reward=1.0, ridge=1.0)
    theta, A_inv, _ = load_preferences(tmp_path, d=3, ridge=1.0, feature_names=names)
    # A = I + x x^T, b = x
    A = np.eye(3) + np.outer(x, x)
    b = x.copy()
    expected_theta = np.linalg.solve(A, b)
    np.testing.assert_allclose(theta, expected_theta, atol=1e-6)


def test_linucb_cold_start_high_uncertainty(tmp_path: Path) -> None:
    """LinUCB with no preferences (cold start) gives non-zero uncertainty for non-zero features."""
    config = _config(state_dir=str(tmp_path))
    paper = _paper("1", title="Contrastive learning", summary="Learning.")
    context = PolicyContext(config)
    policy = LinUCBPolicy()
    result = policy.score([paper], context)
    assert len(result) == 1
    s = result[0]
    assert s.paper.id == "1"
    assert s.uncertainty >= 0
    # Cold start: theta=0 so predicted_reward=0; score = 0 + lambda_ucb*unc + mu_novelty*novelty
    expected_score = (
        config.policy.lambda_ucb * s.uncertainty + config.policy.mu_novelty * s.novelty
    )
    assert s.score == pytest.approx(expected_score, abs=0.01)
    assert s.uncertainty > 0.1


def test_linucb_why_this_paper_includes_phrases_or_exploration(tmp_path: Path) -> None:
    """LinUCB why_this_paper mentions keyphrases or exploration/novelty."""
    config = _config(state_dir=str(tmp_path))
    paper = _paper("1", title="Contrastive representation learning", summary="We use contrastive learning.")
    context = PolicyContext(config)
    policy = LinUCBPolicy()
    result = policy.score([paper], context)
    assert len(result) == 1
    why = result[0].why_this_paper
    assert why != "—"
    assert "contrastive" in why.lower() or "learning" in why.lower() or "Exploration" in why or "Novel" in why


def test_topic_stats_novelty_rare_phrase_high(tmp_path: Path) -> None:
    """Novelty is higher when phrase/topic counts are low (rare)."""
    save_topic_stats(tmp_path, phrase_counts={"common": 100}, topic_counts={"cs.LG": 50})
    phrase_counts, topic_counts = load_topic_stats(tmp_path)
    nov_rare = novelty_from_counts(["rare_phrase"], "cs.OTHER", phrase_counts, topic_counts)
    nov_common = novelty_from_counts(["common"], "cs.LG", phrase_counts, topic_counts)
    assert nov_rare > nov_common


def test_topic_stats_update_from_papers(tmp_path: Path) -> None:
    """update_topic_stats_from_papers merges counts and saves."""
    update_topic_stats_from_papers(
        tmp_path,
        phrase_counts={},
        topic_counts={},
        papers_phrases=[["contrastive", "learning"], ["learning"]],
        papers_topics=["cs.LG", "cs.CL"],
    )
    phrase_counts, topic_counts = load_topic_stats(tmp_path)
    assert phrase_counts.get("contrastive") == 1
    assert phrase_counts.get("learning") == 2
    assert topic_counts.get("cs.LG") == 1
    assert topic_counts.get("cs.CL") == 1
