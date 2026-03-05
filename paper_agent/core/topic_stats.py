"""
Topic/phrase exposure stats for novelty: state_dir/topic_stats.json.
Rarity of phrases/topics over recent exposures (e.g. last 30 days) -> novelty bonus.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TOPIC_STATS_FILENAME = "topic_stats.json"


def _stats_path(state_dir: str | Path) -> Path:
    return Path(state_dir) / TOPIC_STATS_FILENAME


def load_topic_stats(state_dir: str | Path) -> tuple[dict[str, int], dict[str, int]]:
    """
    Load phrase_counts and topic_counts from state_dir/topic_stats.json.
    Returns (phrase_counts, topic_counts). Empty dicts if missing/invalid.
    """
    path = _stats_path(state_dir)
    if not path.exists():
        return {}, {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}, {}

    phrase_counts = data.get("phrase_counts")
    topic_counts = data.get("topic_counts")
    if not isinstance(phrase_counts, dict):
        phrase_counts = {}
    if not isinstance(topic_counts, dict):
        topic_counts = {}
    phrase_counts = {k: int(v) for k, v in phrase_counts.items() if isinstance(v, (int, float))}
    topic_counts = {k: int(v) for k, v in topic_counts.items() if isinstance(v, (int, float))}
    return phrase_counts, topic_counts


def save_topic_stats(
    state_dir: str | Path,
    phrase_counts: dict[str, int],
    topic_counts: dict[str, int],
) -> None:
    """Persist phrase_counts and topic_counts to state_dir/topic_stats.json."""
    path = _stats_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "phrase_counts": phrase_counts,
        "topic_counts": topic_counts,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def update_topic_stats_from_papers(
    state_dir: str | Path,
    phrase_counts: dict[str, int],
    topic_counts: dict[str, int],
    papers_phrases: list[list[str]],
    papers_topics: list[str],
) -> None:
    """
    Merge counts from this run's selected papers and save.
    papers_phrases[i] = list of normalized phrases that appeared in paper i.
    papers_topics[i] = topic_id (e.g. category) for paper i.
    """
    for phrases in papers_phrases:
        for p in phrases:
            if p:
                phrase_counts[p] = phrase_counts.get(p, 0) + 1
    for t in papers_topics:
        if t:
            topic_counts[t] = topic_counts.get(t, 0) + 1
    save_topic_stats(state_dir, phrase_counts, topic_counts)


def novelty_from_counts(
    phrases_in_paper: list[str],
    topic_id: str,
    phrase_counts: dict[str, int],
    topic_counts: dict[str, int],
) -> float:
    """
    Novelty score: higher when phrases/topic are rare in recent exposures.
    Formula: mean over (1 / (count+1)) for each phrase, plus 1/(topic_count+1).
    Normalized to [0, 1] range; 0 = very common, 1 = never seen.
    """
    if not phrases_in_paper and not topic_id:
        return 0.0
    total = 0.0
    n = 0
    for p in phrases_in_paper:
        if p:
            c = phrase_counts.get(p, 0)
            total += 1.0 / (c + 1)
            n += 1
    if topic_id:
        tc = topic_counts.get(topic_id, 0)
        total += 1.0 / (tc + 1)
        n += 1
    if n == 0:
        return 0.0
    raw = total / n
    return min(1.0, raw)
