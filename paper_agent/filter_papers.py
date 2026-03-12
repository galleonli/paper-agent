"""
Filter and rank papers per config (case-insensitive).
Keyphrases/negative from direction.include_keywords / direction.exclude_keywords; interest gate uses seeds.
When include_keywords is non-empty, require at least one match OR paper in seeds.
Every recommended paper gets a human-readable why_this_paper.
"""

from dataclasses import dataclass
from typing import Optional

from paper_agent.core.config import Config
from paper_agent.core.models import Paper
from paper_agent.core.state import paper_id_in_seeds
from paper_agent.core.utils import normalize_text, text_matches_any


@dataclass
class RankedPaper:
    """Paper with why_this_paper explanation (which keyphrase/seed matched)."""

    paper: Paper
    why_this_paper: Optional[str] = None


def count_after_category(
    papers: list[Paper],
    allow_categories: list[str],
    deny_categories: list[str],
) -> int:
    """Count papers that pass allow_categories/deny_categories only (for logging)."""
    allow_cat = set(normalize_text(c) for c in allow_categories if c)
    deny_cat = set(normalize_text(c) for c in deny_categories if c)
    if not allow_cat and not deny_cat:
        return len(papers)
    n = 0
    for paper in papers:
        paper_cats = set(normalize_text(c) for c in paper.categories)
        if allow_cat and not (paper_cats & allow_cat):
            continue
        if deny_cat and (paper_cats & deny_cat):
            continue
        n += 1
    return n


def build_why_this_paper(
    paper: Paper,
    keyphrases: list[str],
    seeds: list[str],
) -> str:
    """
    Build human-readable explanation: which keyphrases matched and/or that it is in seeds.
    Deterministic; no randomness. Shared by filter_and_rank and deterministic policy.
    """
    parts = []
    combined = normalize_text(paper.title) + " " + normalize_text(paper.summary)
    matched_kw = [p for p in keyphrases if p and normalize_text(p) in combined]
    if matched_kw:
        parts.append(f"Keyphrase(s) matched: {', '.join(matched_kw)}")
    if paper_id_in_seeds(paper.id, seeds):
        parts.append("In your seeds")
    return "; ".join(parts) if parts else "—"


def filter_and_rank(papers: list[Paper], config: Config) -> list[RankedPaper]:
    """
    Filter by direction (categories, include/exclude keywords) and seeds.
    Keyphrases = direction.include_keywords; negative = direction.exclude_keywords.
    When include_keywords is non-empty, include only if at least one match OR paper ID in seeds.
    """
    direction = config.direction
    keyphrases = [k for k in direction.include_keywords if k]
    neg_phrases = [n for n in direction.exclude_keywords if n]
    seeds = [s for s in config.interests.seeds if s]
    exclude_kw = neg_phrases
    allow_cat = set(normalize_text(c) for c in direction.allow_categories if c)
    deny_cat = set(normalize_text(c) for c in direction.deny_categories if c)

    # First pass: category + exclude only; record keyphrase/seed match per candidate.
    candidates: list[tuple[Paper, bool, bool]] = []
    for paper in papers:
        if allow_cat or deny_cat:
            paper_cats = set(normalize_text(c) for c in paper.categories)
            if allow_cat and not (paper_cats & allow_cat):
                continue
            if deny_cat and (paper_cats & deny_cat):
                continue

        combined = normalize_text(paper.title) + " " + normalize_text(paper.summary)
        combined_with_authors = combined + " " + " ".join(normalize_text(a) for a in paper.authors)
        if text_matches_any(combined_with_authors, exclude_kw):
            continue

        keyphrase_match = bool(keyphrases) and text_matches_any(combined, keyphrases)
        seed_match = paper_id_in_seeds(paper.id, seeds)
        candidates.append((paper, keyphrase_match, seed_match))

    # Interest gate: when keyphrases set, require keyphrase or seed match *only if*
    # at least one candidate in this batch matches. Otherwise allow all candidates
    # through so the run is not empty when keyphrases are too narrow for today's feed.
    any_hit = any(kp or sd for _, kp, sd in candidates)
    enforce_gate = bool(keyphrases) and any_hit

    ranked: list[RankedPaper] = []
    for paper, keyphrase_match, seed_match in candidates:
        if enforce_gate and not keyphrase_match and not seed_match:
            continue
        why = build_why_this_paper(paper, keyphrases, seeds)
        ranked.append(RankedPaper(paper=paper, why_this_paper=why))

    # Rank: keyphrase match first, then seed match, then rest; within tier, newer first
    def tier_key(r: RankedPaper) -> int:
        why = (r.why_this_paper or "").lower()
        if "keyphrase" in why:
            return 0
        if "seed" in why:
            return 1
        return 2

    ranked.sort(key=lambda r: r.paper.updated, reverse=True)  # newer first
    ranked.sort(key=tier_key)  # tier 0, 1, 2 (stable: keeps newer-first within tier)
    return ranked
