# Backward compatibility: re-export from core

from paper_agent.core.dates import get_now, get_run_date, parse_arxiv_updated, within_lookback

__all__ = ["get_now", "get_run_date", "parse_arxiv_updated", "within_lookback"]
