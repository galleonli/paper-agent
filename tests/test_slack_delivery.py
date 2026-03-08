"""Slack delivery formatting tests for backward-compatible one-liner semantics."""

from paper_agent.core.config import Config
from paper_agent.core.models import Paper
from paper_agent.filter_papers import RankedPaper
from paper_agent.deliver.slack import _build_slack_message


def _ranked_sample() -> RankedPaper:
    return RankedPaper(
        paper=Paper(
            id="2301.12345",
            title="Test Paper",
            summary="This is a test abstract for slack one-liner behavior.",
            authors=["Alice"],
            categories=["cs.LG"],
            updated="2025-01-01T00:00:00Z",
            link_abs="https://arxiv.org/abs/2301.12345",
            link_pdf=None,
        ),
        why_this_paper="Keyphrase matched",
    )


def test_one_liner_does_not_depend_on_brief_summary_flag() -> None:
    """
    Backward compatibility:
    If Slack brief display and brief_one_liner_enabled are true, one-liner appears
    even when summarize.brief_summary is false.
    """
    cfg = Config()
    cfg.delivery.slack.show_brief_summary = True
    cfg.summarize.brief_one_liner_enabled = True
    cfg.summarize.brief_summary = False  # Should not disable Slack one-liner.

    msg = _build_slack_message(
        discovery=[_ranked_sample()],
        scholar_inbox=[],
        config=cfg,
        discovery_note_paths=["2301.12345.md"],
        scholar_note_paths=[],
    )
    assert "One-liner:" in msg


def test_slack_message_keeps_dated_note_relative_path() -> None:
    """Slack message should preserve dated note path provided by pipeline."""
    cfg = Config()
    cfg.delivery.slack.show_brief_summary = True
    cfg.summarize.brief_one_liner_enabled = True

    note_rel = "2025-01-02/2301.12345.md"
    msg = _build_slack_message(
        discovery=[_ranked_sample()],
        scholar_inbox=[],
        config=cfg,
        discovery_note_paths=[note_rel],
        scholar_note_paths=[],
    )
    assert note_rel in msg

