"""
LinUCB policy: predicted reward + uncertainty from state/preferences.json; novelty from topic_stats.
Score = predicted_reward + lambda_ucb * uncertainty + mu_novelty * novelty.
why_this_paper: top contributing phrases + exploration/novelty when relevant.
"""

import numpy as np

from paper_agent.core.config import Config
from paper_agent.core.models import Paper
from paper_agent.core.preferences import load_preferences
from paper_agent.core.topic_stats import load_topic_stats, novelty_from_counts
from paper_agent.core.utils import normalize_text, text_matches_any
from paper_agent.features.encoder import encode_paper, get_feature_names
from paper_agent.policy.base import PolicyContext, ScoredPaper


def _build_why_linucb(
    feature_names: list[str],
    x: list[float],
    theta: np.ndarray,
    matched_phrases: list[str],
    uncertainty: float,
    novelty: float,
    lambda_ucb: float,
    mu_novelty: float,
) -> str:
    """Build why_this_paper: top contributing phrases; add exploration/novelty if they contribute."""
    parts = []
    if matched_phrases:
        parts.append(f"Keyphrase(s): {', '.join(matched_phrases[:3])}")
    # Top contributing features (by |theta_i * x_i|), excluding bias
    if len(feature_names) > 1 and len(theta) == len(x):
        contribs = []
        for i in range(1, min(len(theta), len(x), len(feature_names))):
            if x[i] > 0:
                contribs.append((feature_names[i], theta[i] * x[i]))
        contribs.sort(key=lambda t: abs(t[1]), reverse=True)
        top = [name for name, _ in contribs[:3] if name != "default"]
        if top and not matched_phrases:
            parts.append(f"Features: {', '.join(top)}")
    if uncertainty > 0.1 and lambda_ucb > 0:
        parts.append("Exploration (high uncertainty)")
    if novelty > 0.2 and mu_novelty > 0:
        parts.append("Novel topic")
    return "; ".join(parts) if parts else "—"


class LinUCBPolicy:
    """LinUCB: predicted reward + uncertainty; novelty from topic_stats; why_this_paper explains."""

    def score(self, papers: list[Paper], context: PolicyContext) -> list[ScoredPaper]:
        config = context.config
        state_dir = config.delivery.state_dir
        feedback = config.feedback
        policy_cfg = config.policy
        keyphrases_norm = [normalize_text(k) for k in config.direction.include_keywords if k]
        blocked_phrases = [p for p in feedback.blocked_phrases if p]
        blocked_authors = [a for a in feedback.blocked_authors if a]

        feature_names = get_feature_names(config)
        d = len(feature_names)
        theta, A_inv, _ = load_preferences(
            state_dir, d, ridge=policy_cfg.ridge, feature_names=feature_names
        )
        phrase_counts, topic_counts = load_topic_stats(state_dir)

        alpha = policy_cfg.alpha
        lambda_ucb = policy_cfg.lambda_ucb
        mu_novelty = policy_cfg.mu_novelty

        result: list[ScoredPaper] = []
        for paper in papers:
            combined = normalize_text(paper.title) + " " + normalize_text(paper.summary)
            authors_text = " ".join(normalize_text(a) for a in paper.authors)
            if text_matches_any(combined + " " + authors_text, blocked_phrases):
                continue
            if blocked_authors and any(
                ex and normalize_text(ex) in authors_text for ex in blocked_authors
            ):
                continue

            x_list, _, matched_phrases = encode_paper(paper, config)
            x = np.array(x_list, dtype=np.float64)
            if len(x) != d:
                continue
            pred = float(np.dot(x, theta))
            xAinv = x @ A_inv
            unc_sq = max(0.0, float(np.dot(xAinv, x)))
            uncertainty = alpha * (np.sqrt(unc_sq) if unc_sq > 0 else 0.0)

            phrases_for_novelty = [p for p in matched_phrases if p]
            topic_id = paper.categories[0] if paper.categories else "default"
            novelty = novelty_from_counts(
                [normalize_text(p) for p in phrases_for_novelty],
                topic_id,
                phrase_counts,
                topic_counts,
            )

            score = pred + lambda_ucb * uncertainty + mu_novelty * novelty
            why = _build_why_linucb(
                feature_names, x_list, theta, matched_phrases,
                uncertainty, novelty, lambda_ucb, mu_novelty,
            )
            result.append(
                ScoredPaper(
                    paper=paper,
                    score=score,
                    uncertainty=uncertainty,
                    novelty=novelty,
                    why_this_paper=why,
                    topic_id=topic_id,
                    exploration_pick=False,
                )
            )
        return result
