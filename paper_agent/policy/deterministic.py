"""
Deterministic policy: score from phrase matches and penalties; why_this_paper; uncertainty=0, novelty=0.
"""

from paper_agent.core.config import Config
from paper_agent.core.models import Paper
from paper_agent.core.state import paper_id_in_seeds
from paper_agent.core.utils import normalize_text, text_matches_any
from paper_agent.filter_papers import build_why_this_paper
from paper_agent.policy.base import PolicyContext, ScoredPaper


class DeterministicPolicy:
    """Score papers by phrase matches and penalties; uncertainty and novelty are 0."""

    def score(self, papers: list[Paper], context: PolicyContext) -> list[ScoredPaper]:
        config = context.config
        feedback = config.feedback
        keyphrases = [k for k in config.direction.include_keywords if k]
        seeds = [s for s in config.interests.seeds if s]
        blocked_phrases = [p for p in feedback.blocked_phrases if p]
        blocked_authors = [a for a in feedback.blocked_authors if a]
        boosted_phrases = [p for p in feedback.boosted_phrases if p]

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

            why = build_why_this_paper(paper, keyphrases, seeds)
            score = 1.0
            matched = [p for p in keyphrases if p and normalize_text(p) in combined]
            score += 0.1 * len(matched)
            for p in boosted_phrases:
                if p and normalize_text(p) in combined:
                    score += 0.05
            if paper_id_in_seeds(paper.id, seeds):
                score += 0.2

            topic_id = paper.categories[0] if paper.categories else "default"
            result.append(
                ScoredPaper(
                    paper=paper,
                    score=score,
                    uncertainty=0.0,
                    novelty=0.0,
                    why_this_paper=why,
                    topic_id=topic_id,
                )
            )
        return result
