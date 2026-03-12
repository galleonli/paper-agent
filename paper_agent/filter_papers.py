"""
Filter and rank papers per config (case-insensitive).
Required keywords = direction.include_keywords: OR match — paper must contain at least one of them;
  match in title OR abstract is enough (not all keywords, not both title and abstract).
Exclude = direction.exclude_keywords. Seeds allow inclusion without keyword match.
Every recommended paper gets a human-readable why_this_paper.
"""

from dataclasses import dataclass
from typing import Optional

from paper_agent.core.config import Config
from paper_agent.core.models import Paper
from paper_agent.core.state import paper_id_in_seeds
from paper_agent.core.utils import normalize_text, phrases_matching_text, text_matches_any


@dataclass
class RankedPaper:
    """Paper with why_this_paper explanation (which keyphrase/seed matched, title vs abstract)."""

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
    title_match: bool = False,
    abstract_match: bool = False,
) -> str:
    """
    Build human-readable explanation: which keyphrases matched (title vs abstract) and/or seeds.
    Uses the same matching rules as the filter (phrases_matching_text / word boundaries) so the
    explanation and tier scoring stay consistent.
    """
    parts = []
    matched_in_title = phrases_matching_text(paper.title, keyphrases) if title_match else []
    matched_in_abstract = phrases_matching_text(paper.summary, keyphrases) if abstract_match else []
    if matched_in_title:
        parts.append(f"Keyphrase(s) in title: {', '.join(matched_in_title)}")
    if matched_in_abstract and not matched_in_title:
        parts.append(f"Keyphrase(s) in abstract: {', '.join(matched_in_abstract)}")
    elif matched_in_abstract:
        others = [p for p in matched_in_abstract if p not in matched_in_title]
        if others:
            parts.append(f"Also in abstract: {', '.join(others)}")
    if paper_id_in_seeds(paper.id, seeds):
        parts.append("In your seeds")
    return "; ".join(parts) if parts else "—"


def filter_and_rank(papers: list[Paper], config: Config) -> list[RankedPaper]:
    """
    Filter by direction (categories, required/exclude keywords) and seeds.
    Required keywords: OR — match at least one keyword; match in title OR abstract is enough (not all keywords).
    Seeds: paper in seeds passes without keyword match. Exclude = direction.exclude_keywords.
    Ranking: title match > abstract match > seed > rest.
    """
    direction = config.direction
    keyphrases = [k for k in direction.include_keywords if k]
    neg_phrases = [n for n in direction.exclude_keywords if n]
    seeds = [s for s in config.interests.seeds if s]
    exclude_kw = neg_phrases
    allow_cat = set(normalize_text(c) for c in direction.allow_categories if c)
    deny_cat = set(normalize_text(c) for c in direction.deny_categories if c)

    # First pass: category + exclude; record title match, abstract match, seed per candidate.
    candidates: list[tuple[Paper, bool, bool, bool]] = []
    for paper in papers:
        if allow_cat or deny_cat:
            paper_cats = set(normalize_text(c) for c in paper.categories)
            if allow_cat and not (paper_cats & allow_cat):
                continue
            if deny_cat and (paper_cats & deny_cat):
                continue

        combined_with_authors = (
            normalize_text(paper.title) + " " + normalize_text(paper.summary)
            + " " + " ".join(normalize_text(a) for a in paper.authors)
        )
        if text_matches_any(combined_with_authors, exclude_kw):
            continue

        title_match = bool(keyphrases) and text_matches_any(normalize_text(paper.title), keyphrases)
        abstract_match = bool(keyphrases) and text_matches_any(normalize_text(paper.summary), keyphrases)
        keyphrase_match = title_match or abstract_match
        seed_match = paper_id_in_seeds(paper.id, seeds)
        candidates.append((paper, title_match, abstract_match, seed_match))

    # Required-keywords gate: when keyphrases set, include only if keyphrase match or seed.
    enforce_gate = bool(keyphrases)

    ranked: list[RankedPaper] = []
    for paper, title_match, abstract_match, seed_match in candidates:
        if enforce_gate and not (title_match or abstract_match) and not seed_match:
            continue
        why = build_why_this_paper(paper, keyphrases, seeds, title_match=title_match, abstract_match=abstract_match)
        ranked.append(RankedPaper(paper=paper, why_this_paper=why))

    # Rank: title match first, then abstract match, then seed, then rest; within tier, newer first
    def tier_key(r: RankedPaper) -> int:
        why = (r.why_this_paper or "").lower()
        if "title" in why and "keyphrase" in why:
            return 0
        if "abstract" in why and "keyphrase" in why:
            return 1
        if "seed" in why:
            return 2
        return 3

    ranked.sort(key=lambda r: r.paper.updated, reverse=True)
    ranked.sort(key=tier_key)
    return ranked
