"""
State management for idempotency and catch-up.
Persists seen paper IDs (and optional last run time) in state_dir/seen.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


SEEN_FILENAME = "seen.json"


def normalize_paper_id(paper_id: str) -> str:
    """Normalize to a canonical ID (e.g. strip arXiv URL prefix)."""
    s = paper_id.strip()
    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/"):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :].strip()
    if s.lower().startswith("arxiv:"):
        s = s[6:].strip()
    return s or paper_id


def paper_id_in_seeds(paper_id: str, seeds: list[str]) -> bool:
    """True if paper_id (normalized) equals any normalized seed."""
    norm_id = normalize_paper_id(paper_id)
    for s in seeds:
        if s and normalize_paper_id(s) == norm_id:
            return True
    return False


def state_path(state_dir: str | Path) -> Path:
    """Path to seen.json inside state_dir."""
    return Path(state_dir) / SEEN_FILENAME


def load_seen(state_dir: str | Path) -> set[str]:
    """
    Load set of seen paper IDs from state_dir/seen.json.
    Returns empty set if file missing or invalid.
    """
    path = state_path(state_dir)
    if not path.exists():
        return set()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return set()
    ids = data.get("seen_ids", [])
    if not isinstance(ids, list):
        return set()
    return {normalize_paper_id(str(x)) for x in ids}


def save_seen(state_dir: str | Path, seen_ids: set[str]) -> None:
    """
    Persist seen paper IDs to state_dir/seen.json.
    Creates state_dir if needed. Optionally stores last_run_utc for debugging.
    """
    path = state_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "seen_ids": sorted(seen_ids),
        "last_run_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_seen(state_dir: str | Path, paper_id: str, seen_cache: set[str] | None = None) -> bool:
    """
    Return True if paper_id is in the seen set.
    If seen_cache is provided, use it; otherwise load from disk.
    """
    norm = normalize_paper_id(paper_id)
    if seen_cache is not None:
        return norm in seen_cache
    seen = load_seen(state_dir)
    return norm in seen


def mark_seen(seen_cache: set[str], paper_id: str) -> None:
    """Add paper_id to the in-memory seen set (call save_seen to persist)."""
    seen_cache.add(normalize_paper_id(paper_id))


def filter_unseen(
    state_dir: str | Path, paper_ids: list[str], seen_cache: set[str] | None = None
) -> tuple[list[str], set[str]]:
    """
    Return (unseen_ids, updated_seen_cache).
    If seen_cache is None, load from state_dir; updated_seen_cache is the set
    that should be saved after processing (includes previously seen + newly seen).
    """
    if seen_cache is None:
        seen_cache = load_seen(state_dir).copy()
    else:
        seen_cache = set(seen_cache)
    unseen = []
    for pid in paper_ids:
        norm = normalize_paper_id(pid)
        if norm not in seen_cache:
            unseen.append(pid)
            seen_cache.add(norm)
    return unseen, seen_cache
