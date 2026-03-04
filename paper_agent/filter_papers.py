"""
Filter and rank papers per config (case-insensitive).
Interest model: seeds, keyphrases, negative_keyphrases; direction: categories, include/exclude keywords/authors.
When keyphrases is non-empty, require at least one keyphrase match OR paper in seeds.
Every recommended paper gets a human-readable why_this_paper (keyphrases and/or seed).
"""

from dataclasses import dataclass
from typing import Optional

from paper_agent.config import Config
from paper_agent.models import Paper
from paper_agent.state import normalize_paper_id


@dataclass
class RankedPaper:
    """Paper with why_this_paper explanation (which keyphrase/seed matched)."""

    paper: Paper
    why_this_paper: Optional[str] = None


def _normalize(s: str) -> str:
    return s.lower().strip()


def _text_matches_any(text: str, phrases: list[str]) -> bool:
    """True if any phrase appears in text (case-insensitive)."""
    if not phrases:
        return False
    norm_text = _normalize(text)
    for p in phrases:
        if p and _normalize(p) in norm_text:
            return True
    return False


def _author_matches_exclude(paper: Paper, exclude_authors: list[str]) -> bool:
    """True if any excluded author substring matches a paper author (case-insensitive)."""
    if not exclude_authors:
        return False
    for ex in exclude_authors:
        if not ex:
            continue
        ex_norm = _normalize(ex)
        for a in paper.authors:
            if ex_norm in _normalize(a):
                return True
    return False


def _paper_id_in_seeds(paper_id: str, seeds: list[str]) -> bool:
    """True if paper ID (normalized) is in the seeds list (normalized)."""
    norm_id = normalize_paper_id(paper_id)
    for s in seeds:
        if s and normalize_paper_id(s) == norm_id:
            return True
    return False


def _build_why_this_paper(
    paper: Paper,
    keyphrases: list[str],
    seeds: list[str],
) -> str:
    """
    Build human-readable explanation: which keyphrases matched and/or that it is in seeds.
    Deterministic; no randomness.
    """
    parts = []
    combined = _normalize(paper.title) + " " + _normalize(paper.summary)
    matched_kw = [p for p in keyphrases if p and _normalize(p) in combined]
    if matched_kw:
        parts.append(f"Keyphrase(s) matched: {', '.join(matched_kw)}")
    if _paper_id_in_seeds(paper.id, seeds):
        parts.append("In your seeds")
    return "; ".join(parts) if parts else "—"


def filter_and_rank(papers: list[Paper], config: Config) -> list[RankedPaper]:
    """
    Filter by direction (categories, include/exclude keywords/authors) and interest model.
    When keyphrases is non-empty, include only if at least one keyphrase matches OR paper ID in seeds.
    Case-insensitive throughout. Every included paper gets why_this_paper set.
    """
    interests = config.interests
    direction = config.direction
    keyphrases = [k for k in interests.keyphrases if k]
    seeds = [s for s in interests.seeds if s]
    neg_phrases = [n for n in interests.negative_keyphrases if n]
    include_kw = [k for k in direction.include_keywords if k]
    exclude_kw = [k for k in direction.exclude_keywords if k]
    exclude_auth = [k for k in direction.exclude_authors if k]
    allow_cat = set(_normalize(c) for c in direction.allow_categories if c)
    deny_cat = set(_normalize(c) for c in direction.deny_categories if c)

    ranked: list[RankedPaper] = []
    for paper in papers:
        # Category filter: allow_categories and deny_categories (case-insensitive)
        if allow_cat or deny_cat:
            paper_cats = set(_normalize(c) for c in paper.categories)
            if allow_cat and not (paper_cats & allow_cat):
                continue
            if deny_cat and (paper_cats & deny_cat):
                continue

        combined = _normalize(paper.title) + " " + _normalize(paper.summary)
        combined_with_authors = combined + " " + " ".join(_normalize(a) for a in paper.authors)

        # Direction: include_keywords (must match at least one if non-empty)
        if include_kw and not _text_matches_any(combined_with_authors, include_kw):
            continue
        if _text_matches_any(combined_with_authors, exclude_kw):
            continue
        if _author_matches_exclude(paper, exclude_auth):
            continue

        # Negative keyphrases: exclude if any match
        if _text_matches_any(combined_with_authors, neg_phrases):
            continue

        # Interest gate: when keyphrases non-empty, require keyphrase match OR seed match
        keyphrase_match = bool(keyphrases) and _text_matches_any(combined, keyphrases)
        seed_match = _paper_id_in_seeds(paper.id, seeds)
        if keyphrases and not keyphrase_match and not seed_match:
            continue

        why = _build_why_this_paper(paper, keyphrases, seeds)
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
