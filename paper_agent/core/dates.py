"""
Date helpers: single source of run date and "now" using system local time.
All paths, file names, and date logic use the machine clock; no timezone config.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional


def get_run_date() -> date:
    """Current run date (system local). Used for paths, digest, exports."""
    return date.today()


def get_now() -> datetime:
    """Current time (system local, naive). Used for lookback cutoff and Scholar fetch."""
    return datetime.now()


def parse_arxiv_updated(updated_str: str) -> Optional[datetime]:
    """Parse arXiv updated string (ISO 8601) to timezone-aware UTC datetime."""
    if not updated_str or not updated_str.strip():
        return None
    s = updated_str.strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def within_lookback(updated_str: str, lookback_days: int) -> bool:
    """True if paper updated date is within the last lookback_days (system local date)."""
    dt = parse_arxiv_updated(updated_str)
    if dt is None:
        return True
    cutoff = get_now() - timedelta(days=lookback_days)
    dt_local = dt.astimezone().replace(tzinfo=None)
    return dt_local >= cutoff
