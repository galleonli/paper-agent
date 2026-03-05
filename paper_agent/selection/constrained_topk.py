"""
Constrained top-k selection: explore/exploit quota (epsilon), topic cap, min topics.
Greedy selection that satisfies constraints. Marks exploration_pick on ScoredPaper when chosen in explore phase.
"""

from dataclasses import replace

from paper_agent.policy.base import ScoredPaper


def select_topk(
    scored: list[ScoredPaper],
    k: int,
    explore_ratio: float = 0.2,
    topic_cap: int = 3,
    min_topics: int = 1,
) -> list[ScoredPaper]:
    """
    Select up to k papers from scored list.
    - (1 - explore_ratio)*k exploitation slots (highest score).
    - explore_ratio*k exploration slots (highest uncertainty + novelty); marked exploration_pick=True.
    - No more than topic_cap papers per topic_id.
    - At least min_topics distinct topics when possible.
    Greedy: fill by score first (respecting topic_cap), then by uncertainty+novelty, then fill remaining.
    """
    if not scored or k <= 0:
        return []

    n = len(scored)
    n_exploit = max(0, int((1 - explore_ratio) * k))
    n_explore = k - n_exploit

    if n <= k:
        # Apply topic cap and take up to k; still mark explore_ratio*k as exploration_pick
        capped = _apply_topic_cap(scored, topic_cap)[:k]
        n_explore_actual = min(len(capped), n_explore)
        if n_explore_actual <= 0:
            return capped
        # Mark the n_explore_actual papers with highest (uncertainty + novelty) as exploration
        with_expl = [
            (i, s.uncertainty + s.novelty) for i, s in enumerate(capped)
        ]
        with_expl.sort(key=lambda x: x[1], reverse=True)
        explore_indices = {with_expl[j][0] for j in range(n_explore_actual)}
        return [
            replace(s, exploration_pick=(i in explore_indices))
            for i, s in enumerate(capped)
        ]

    by_score = sorted(scored, key=lambda s: s.score, reverse=True)
    by_exploration = sorted(
        scored, key=lambda s: s.uncertainty + s.novelty, reverse=True
    )

    selected: list[ScoredPaper] = []
    topic_counts: dict[str, int] = {}
    used_ids: set[str] = set()

    def add_if_ok(candidate: ScoredPaper, exploration_pick: bool = False) -> bool:
        if candidate.paper.id in used_ids:
            return False
        count = topic_counts.get(candidate.topic_id, 0)
        if count >= topic_cap:
            return False
        out = replace(candidate, exploration_pick=exploration_pick)
        selected.append(out)
        used_ids.add(candidate.paper.id)
        topic_counts[candidate.topic_id] = count + 1
        return True

    for s in by_score:
        if len(selected) >= n_exploit:
            break
        add_if_ok(s, exploration_pick=False)

    for s in by_exploration:
        if len(selected) >= k:
            break
        add_if_ok(s, exploration_pick=True)

    remaining = [s for s in by_score if s.paper.id not in used_ids]
    while len(selected) < k and remaining:
        added = False
        for s in remaining:
            if add_if_ok(s, exploration_pick=False):
                remaining = [x for x in remaining if x.paper.id not in used_ids]
                added = True
                break
        if not added:
            break

    topics_seen = set(topic_counts)
    if len(topics_seen) < min_topics and len(selected) < k:
        for s in remaining:
            if len(selected) >= k or len(topics_seen) >= min_topics:
                break
            if s.topic_id in topics_seen:
                continue
            if add_if_ok(s, exploration_pick=False):
                topics_seen.add(s.topic_id)

    return selected[:k]


def _apply_topic_cap(scored: list[ScoredPaper], topic_cap: int) -> list[ScoredPaper]:
    """Return list with at most topic_cap papers per topic (order preserved)."""
    topic_counts: dict[str, int] = {}
    out: list[ScoredPaper] = []
    for s in scored:
        count = topic_counts.get(s.topic_id, 0)
        if count < topic_cap:
            out.append(s)
            topic_counts[s.topic_id] = count + 1
    return out
