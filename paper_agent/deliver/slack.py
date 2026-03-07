"""
Slack delivery: format and send brief digest (title, one-liner, why_this_paper, links).
Respects max_message_chars; truncates or splits if needed.
"""

import requests

from paper_agent.core.config import Config
from paper_agent.core.utils import safe_paper_id_for_path
from paper_agent.filter_papers import RankedPaper
from paper_agent.core.models import Paper


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
    include_why: bool = True,
) -> str:
    """Format a single paper for Slack: title, optional one-liner, why, links."""
    p = ranked.paper
    why = ranked.why_this_paper or "—"
    brief_line = ""
    if show_brief:
        brief = _brief_line(p, ranked.why_this_paper, one_liner)
        brief_line = f"One-liner: {brief}\n"
    why_line = f"Why this paper: {why}\n" if include_why else ""
    return (
        f"*{p.title}*\n"
        f"{brief_line}"
        f"{why_line}"
        f"🔗 Link: {p.link_abs}  |  Note: {note_rel}"
    )


def _format_scholar_block(ranked: RankedPaper, note_rel: str) -> str:
    """Format one Scholar Inbox item: title + link + received timestamp (brief) + note."""
    p = ranked.paper
    received = "—"
    if p.updated:
        # p.updated is ISO (e.g. 2025-01-02T10:00:00Z); show date briefly
        received = p.updated[:10] if len(p.updated) >= 10 else p.updated
    return (
        f"*{p.title}*\n"
        f"Received: {received}\n"
        f"🔗 Link: {p.link_abs}  |  Note: {note_rel}"
    )


def _build_section(
    header: str,
    ranked_list: list[RankedPaper],
    note_paths: list[str],
    show_brief: bool,
    include_why: bool,
    scholar_format: bool = False,
) -> str:
    blocks: list[str] = []
    for i, r in enumerate(ranked_list):
        note_rel = (
            note_paths[i]
            if i < len(note_paths)
            else f"{safe_paper_id_for_path(r.paper.id)}.md"
        )
        if scholar_format:
            block = _format_scholar_block(r, note_rel)
        else:
            one_liner: str | None = (
                _brief_line(r.paper, r.why_this_paper, None) if show_brief else None
            )
            block = _format_slack_block(
                r,
                note_rel,
                one_liner,
                show_brief=show_brief,
                include_why=include_why,
            )
        blocks.append(block)
    if not blocks:
        return f"*{header}* — 0 paper(s)"
    body = f"*{header}* — {len(ranked_list)} paper(s)\n\n" + "\n\n".join(blocks)
    return body


def _build_slack_message(
    discovery: list[RankedPaper],
    scholar_inbox: list[RankedPaper],
    config: Config,
    discovery_note_paths: list[str],
    scholar_note_paths: list[str],
) -> str:
    """
    Build Slack message body with two sections:
    - Daily Precision (discovery feed)
    - Scholar Inbox (Google Scholar Alerts)
    Truncate to max_message_chars.
    """
    delivery = config.delivery
    slack_cfg = delivery.slack
    max_chars = slack_cfg.max_message_chars
    # Backward-compatible gate for Slack one-liner display.
    # Keep semantics stable: one-liner is controlled by Slack display switch
    # plus brief_one_liner_enabled, without introducing new hard gates.
    show_brief = (
        slack_cfg.show_brief_summary
        and config.summarize.brief_one_liner_enabled
    )

    sections: list[str] = []
    sections.append(
        _build_section(
            header="Daily Precision",
            ranked_list=discovery,
            note_paths=discovery_note_paths,
            show_brief=show_brief,
            include_why=True,
        )
    )
    if config.sources.scholar_alerts.enabled and config.sources.scholar_alerts.push_to_slack:
        sections.append(
            _build_section(
                header="Scholar Inbox",
                ranked_list=scholar_inbox,
                note_paths=scholar_note_paths,
                show_brief=False,
                include_why=False,
                scholar_format=True,
            )
        )

    intro = "📄 *Paper digest*\n\n"
    out = intro + "\n\n---\n\n".join(sections)
    if len(out) > max_chars:
        out = out[: max_chars - 20] + "\n\n… (truncated)"
    return out


def send_slack_brief(
    discovery: list[RankedPaper],
    scholar_inbox: list[RankedPaper],
    config: Config,
    discovery_note_paths: list[str],
    scholar_note_paths: list[str],
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

    body = _build_slack_message(
        discovery,
        scholar_inbox,
        config,
        discovery_note_paths,
        scholar_note_paths,
    )
    payload = {"text": body}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Slack webhook failed: {e}") from e
