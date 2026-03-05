"""Tests for filter and rank (case-insensitive, why_this_paper)."""

from paper_agent.config import Config, InterestsConfig, DirectionConfig
from paper_agent.filter_papers import count_after_category, filter_and_rank, RankedPaper
from paper_agent.models import Paper


def _paper(
    id_: str = "2301.12345",
    title: str = "Contrastive learning for proteins",
    summary: str = "We use contrastive learning.",
    authors: list[str] | None = None,
    categories: list[str] | None = None,
) -> Paper:
    return Paper(
        id=id_,
        title=title,
        summary=summary,
        authors=authors or ["Alice"],
        categories=categories or ["cs.LG"],
        updated="2023-01-15T12:00:00Z",
        link_abs=f"https://arxiv.org/abs/{id_}",
        link_pdf=None,
    )


def test_filter_negative_keyphrase() -> None:
    """Papers matching negative_keyphrases are excluded (case-insensitive)."""
    config = Config(
        interests=InterestsConfig(keyphrases=["contrastive"], negative_keyphrases=["survey"]),
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=2, allow_categories=[]),
    )
    papers = [
        _paper("1", title="A Survey of ML", summary="This is a survey."),
        _paper("2", title="Contrastive Methods", summary="We propose X."),
    ]
    result = filter_and_rank(papers, config)
    assert len(result) == 1
    assert result[0].paper.id == "2"


def test_filter_exclude_authors() -> None:
    """Papers by exclude_authors are excluded (case-insensitive)."""
    config = Config(
        interests=InterestsConfig(keyphrases=[], negative_keyphrases=[]),
        direction=DirectionConfig(
            max_papers_per_day=10,
            lookback_days=2,
            allow_categories=["cs.LG"],
            exclude_authors=["Bob"],
        ),
    )
    papers = [
        _paper("1", authors=["Alice", "Bob"]),
        _paper("2", authors=["Alice", "Charlie"]),
    ]
    result = filter_and_rank(papers, config)
    assert len(result) == 1
    assert result[0].paper.id == "2"


def test_why_this_paper_set_when_keyphrase_matches() -> None:
    """When a keyphrase matches title/summary, why_this_paper is set."""
    config = Config(
        interests=InterestsConfig(keyphrases=["contrastive", "protein"], negative_keyphrases=[]),
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=2, allow_categories=[]),
    )
    papers = [_paper(title="Contrastive Representation Learning for Protein Folding")]
    result = filter_and_rank(papers, config)
    assert len(result) == 1
    assert result[0].why_this_paper is not None
    assert "contrastive" in result[0].why_this_paper.lower()
    assert "protein" in result[0].why_this_paper.lower()


def test_ranking_keyphrase_matches_first() -> None:
    """Papers with keyphrase match are ranked before seed-only; when keyphrases set, non-matching excluded."""
    config = Config(
        interests=InterestsConfig(
            keyphrases=["contrastive"],
            negative_keyphrases=[],
            seeds=["https://arxiv.org/abs/1"],
        ),
        direction=DirectionConfig(max_papers_per_day=10, lookback_days=2, allow_categories=[]),
    )
    papers = [
        _paper("1", title="Other topic", summary="We study something else."),
        _paper("2", title="Contrastive learning", summary="We use contrastive learning."),
    ]
    result = filter_and_rank(papers, config)
    assert len(result) == 2
    assert result[0].paper.id == "2"
    assert "keyphrase" in (result[0].why_this_paper or "").lower()
    assert result[1].paper.id == "1"
    assert "seed" in (result[1].why_this_paper or "").lower()


def test_count_after_category() -> None:
    """count_after_category returns count of papers passing allow/deny categories only."""
    papers = [
        _paper("1", categories=["cs.LG"]),
        _paper("2", categories=["cs.AI"]),
        _paper("3", categories=["cs.Other"]),
    ]
    # allow cs.LG, cs.CL; deny cs.AI -> only id 1 passes
    n = count_after_category(papers, ["cs.LG", "cs.CL"], ["cs.AI"])
    assert n == 1
    # no filter -> all pass
    assert count_after_category(papers, [], []) == 3


def test_allow_deny_categories() -> None:
    """allow_categories: paper must have at least one allowed; deny_categories: exclude if any match."""
    config = Config(
        interests=InterestsConfig(keyphrases=[], negative_keyphrases=[]),
        direction=DirectionConfig(
            max_papers_per_day=10,
            lookback_days=2,
            allow_categories=["cs.LG", "cs.CL"],
            deny_categories=["cs.AI"],
        ),
    )
    papers = [
        _paper("1", title="A", summary="B", categories=["cs.LG"]),
        _paper("2", title="C", summary="D", categories=["cs.AI"]),
        _paper("3", title="E", summary="F", categories=["cs.Other"]),
    ]
    result = filter_and_rank(papers, config)
    assert len(result) == 1
    assert result[0].paper.id == "1"
    # Paper 2 denied (cs.AI); paper 3 has no allowed category (cs.Other not in allow list)


def test_include_keywords_must_match() -> None:
    """When include_keywords is non-empty, paper must match at least one (case-insensitive)."""
    config = Config(
        interests=InterestsConfig(keyphrases=[], negative_keyphrases=[]),
        direction=DirectionConfig(
            max_papers_per_day=10,
            lookback_days=2,
            allow_categories=[],
            include_keywords=["transformer", "BERT"],
        ),
    )
    papers = [
        _paper("1", title="Random paper", summary="Nothing here."),
        _paper("2", title="Transformers for NLP", summary="We use BERT."),
    ]
    result = filter_and_rank(papers, config)
    assert len(result) == 1
    assert result[0].paper.id == "2"


def test_exclude_keywords_case_insensitive() -> None:
    """Papers matching exclude_keywords are excluded (case-insensitive, title+abstract+authors)."""
    config = Config(
        interests=InterestsConfig(keyphrases=[], negative_keyphrases=[]),
        direction=DirectionConfig(
            max_papers_per_day=10,
            lookback_days=2,
            allow_categories=[],
            exclude_keywords=["survey", "tutorial"],
        ),
    )
    papers = [
        _paper("1", title="A Survey of ML", summary="We review methods."),
        _paper("2", title="TUTORIAL on Deep Learning", summary="Step-by-step."),
        _paper("3", title="Novel method", summary="We propose X."),
    ]
    result = filter_and_rank(papers, config)
    assert len(result) == 1
    assert result[0].paper.id == "3"
