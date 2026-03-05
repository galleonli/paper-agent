# Backward compatibility: re-export from core

from paper_agent.core.dates import parse_arxiv_updated, within_lookback

__all__ = ["parse_arxiv_updated", "within_lookback"]
