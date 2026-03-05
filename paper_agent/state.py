# Backward compatibility: re-export from core

from paper_agent.core.state import (
    SEEN_FILENAME,
    normalize_paper_id,
    paper_id_in_seeds,
    state_path,
    load_seen,
    save_seen,
    is_seen,
    mark_seen,
    filter_unseen,
)

__all__ = [
    "SEEN_FILENAME",
    "normalize_paper_id",
    "paper_id_in_seeds",
    "state_path",
    "load_seen",
    "save_seen",
    "is_seen",
    "mark_seen",
    "filter_unseen",
]
