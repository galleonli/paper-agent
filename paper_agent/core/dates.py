"""
Date helpers for lookback filtering (UTC-based).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


def parse_arxiv_updated(updated_str: str) -> Optional[datetime]:
    """Parse arXiv updated string (ISO 8601) to naive UTC datetime for comparison."""
    if not updated_str or not updated_str.strip():
        return None
    s = updated_str.strip()
    try:
        # Handle Z suffix and +00:00
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def within_lookback(updated_str: str, lookback_days: int) -> bool:
    """True if paper updated date is within the last lookback_days (UTC)."""
    dt = parse_arxiv_updated(updated_str)
    if dt is None:
        return True  # Include if we can't parse (don't drop)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return dt >= cutoff
