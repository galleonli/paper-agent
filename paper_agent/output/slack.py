"""
Slack delivery: format and send brief digest (title, one-liner, why_this_paper, links).
Respects max_message_chars; truncates or splits if needed.
"""

import requests

from paper_agent.config import Config
from paper_agent.filter_papers import RankedPaper
from paper_agent.models import Paper
from paper_agent.utils import safe_paper_id_for_path


def _brief_line(paper: Paper, why: str | None, one_liner: str | None) -> str:
    """One line summary for Slack: use one_liner or first 200 chars of abstract."""
    if one_liner and one_liner.strip():
        return one_liner.strip()[:500]
    if paper.summary:
        s = paper.summary.replace("\n", " ").strip()[:300]
        return s + "…" if len(paper.summary) > 300 else s
    return "No summary."


def _format_slack_block(
    ranked: RankedPaper,
    note_rel: str,
    one_liner: str | None,
    show_brief: bool,
) -> str:
    """Format a single paper for Slack: title, optional one-liner, why, links."""
    p = ranked.paper
    why = ranked.why_this_paper or "—"
    brief_line = ""
    if show_brief:
        brief = _brief_line(p, ranked.why_this_paper, one_liner)
        brief_line = f"One-liner: {brief}\n"
    return (
        f"*{p.title}*\n"
        f"{brief_line}"
        f"Why this paper: {why}\n"
        f"🔗 arXiv: {p.link_abs}  |  Note: {note_rel}"
    )


def _build_slack_message(
    ranked_list: list[RankedPaper],
    config: Config,
    note_paths: list[str],
) -> str:
    """
    Build Slack message body. Include title, one-liner (only if show_brief_summary),
    why_this_paper, links. Truncate to max_message_chars.
    """
    delivery = config.delivery
    slack_cfg = delivery.slack
    max_chars = slack_cfg.max_message_chars
    show_brief = slack_cfg.show_brief_summary

    blocks: list[str] = []
    for i, r in enumerate(ranked_list):
        note_rel = note_paths[i] if i < len(note_paths) else f"{safe_paper_id_for_path(r.paper.id)}.md"
        one_liner: str | None = _brief_line(r.paper, r.why_this_paper, None) if show_brief else None
        block = _format_slack_block(r, note_rel, one_liner, show_brief)
        blocks.append(block)

    intro = f"📄 *Paper digest* — {len(ranked_list)} paper(s)\n\n"
    out = intro + "\n\n".join(blocks)
    if len(out) > max_chars:
        out = out[: max_chars - 20] + "\n\n… (truncated)"
    return out


def send_slack_brief(
    ranked_list: list[RankedPaper],
    config: Config,
    note_paths: list[str],
) -> None:
    """
    Send brief digest to Slack webhook if enabled.
    Uses delivery.slack.*; raises on HTTP error if webhook URL looks configured.
    """
    slack_cfg = config.delivery.slack
    if not slack_cfg.enabled:
        return
    url = (slack_cfg.webhook_url or "").strip()
    if not url or "PLACEHOLDER" in url or "YOUR" in url:
        return  # Skip if URL not configured

    body = _build_slack_message(ranked_list, config, note_paths)
    payload = {"text": body}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Slack webhook failed: {e}") from e
