"""
Policy interface: score(papers, context) -> list of ScoredPaper.
Used by pipeline before constrained selection. No bandit learning in Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from paper_agent.core.config import Config
from paper_agent.core.models import Paper


@dataclass
class ScoredPaper:
    """Paper with score, uncertainty, novelty, why_this_paper, topic_id, and exploration_pick flag."""

    paper: Paper
    score: float
    uncertainty: float
    novelty: float
    why_this_paper: str
    topic_id: str
    exploration_pick: bool = False


class PolicyContext:
    """Context passed to policy.score (config)."""

    def __init__(self, config: Config) -> None:
        self.config = config


class Policy(Protocol):
    """Protocol for scoring candidates."""

    def score(self, papers: list[Paper], context: PolicyContext) -> list[ScoredPaper]:
        """Return scored papers; caller applies constrained selection."""
        ...
