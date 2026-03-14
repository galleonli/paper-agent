"""
Pipeline orchestration: load config -> fetch -> lookback -> filter/rank -> state (unseen)
-> write local notes + daily digest.
Catch-up safe and idempotent: seen state is persisted after local output.
"""

from pathlib import Path

from paper_agent.core.config import Config, load_config
from paper_agent.core.dates import get_now, get_run_date, within_lookback
from paper_agent.core.logging import setup_run_logging
from paper_agent.core.models import Paper
from paper_agent.core.state import filter_unseen, save_seen
from paper_agent.core.summarize import build_research_summary
from paper_agent.filter_papers import RankedPaper, count_after_category, filter_and_rank
from paper_agent.policy.base import ScoredPaper
from paper_agent.output.local import (
    enrich_related_local_papers,
    write_daily_digest,
    write_local_note,
    write_weekly_digest,
)
from paper_agent.export import write_bibtex, write_ris
from paper_agent.sources import fetch_arxiv
from paper_agent.sources import scholar_alerts_source
from paper_agent.selection import select_topk
from paper_agent.core.topic_stats import (
    load_topic_stats,
    update_topic_stats_from_papers,
)
from paper_agent.features.encoder import encode_paper
from paper_agent.autotune import AutoTuneController, TunedPolicyParams
from paper_agent.autotune.base import AutoTuneContext
from paper_agent.autotune.reward import compute_reward
from paper_agent.core.utils import normalize_text, text_matches_any
import json
from typing import Any, Dict, List


def run(config_path: str | Path) -> list[RankedPaper]:
    """
    Run the full pipeline. Returns all newly processed RankedPaper items
    (discovery + Scholar Inbox).
    State is saved after local notes and daily digest.
    """
    config = load_config(config_path)
    direction = config.direction
    delivery = config.delivery
    advanced = config.advanced
    log = setup_run_logging(delivery.logs_dir)

    # Fetch from sources (discovery: arXiv; inbox: Scholar Alerts email).
    papers_raw: list[Paper] = []
    if config.sources.arxiv.enabled:
        papers_raw = fetch_arxiv(
            allow_categories=direction.allow_categories,
            deny_categories=direction.deny_categories,
            queries=direction.queries or None,
            max_results=advanced.max_results_per_query,
            timeout_seconds=advanced.request_timeout_seconds,
            delay_between_requests_seconds=3.0,
        )
    fetched_total = len(papers_raw)

    # Scholar Inbox (Google Scholar Alerts via email; never counts toward max_papers_per_day)
    scholar_new: list[Paper] = []
    scholar_provider = "off"
    if config.sources.scholar_alerts.enabled:
        scholar_provider = config.sources.scholar_alerts.email.provider
        now = get_now()
        scholar_new = scholar_alerts_source.fetch(
            now=now,
            lookback_days=direction.lookback_days,
            config=config,
        )

    # Lookback filter: keep only papers updated within last lookback_days (system local)
    papers_raw = [p for p in papers_raw if within_lookback(p.updated, direction.lookback_days)]
    after_lookback = len(papers_raw)
    after_category = count_after_category(
        papers_raw, direction.allow_categories, direction.deny_categories
    )

    # Filter and rank (direction + interest)
    ranked_all = filter_and_rank(papers_raw, config)
    after_filters = len(ranked_all)
    include_keywords = [k.strip() for k in direction.include_keywords if (k or "").strip()]
    exclude_keywords = [k.strip() for k in direction.exclude_keywords if (k or "").strip()]
    include_match_count = 0
    exclude_match_count = 0
    for p in papers_raw:
        combined_with_authors = (
            normalize_text(p.title) + " " + normalize_text(p.summary)
            + " " + " ".join(normalize_text(a) for a in p.authors)
        )
        # Match filter logic: include = title OR abstract (not combined), so debug count is accurate.
        if include_keywords and (
            text_matches_any(normalize_text(p.title), include_keywords)
            or text_matches_any(normalize_text(p.summary), include_keywords)
        ):
            include_match_count += 1
        if exclude_keywords and text_matches_any(combined_with_authors, exclude_keywords):
            exclude_match_count += 1
    if fetched_total > 0 and after_filters == 0:
        sample_titles = [p.title[:80] + ("..." if len(p.title) > 80 else "") for p in papers_raw[:3]]
        log.warning(
            "filter_debug after_lookback=%d include_keywords=%s include_match_count=%d "
            "exclude_keywords=%s exclude_match_count=%d lookback_days=%d sample_titles=%s",
            after_lookback,
            include_keywords,
            include_match_count,
            exclude_keywords,
            exclude_match_count,
            direction.lookback_days,
            sample_titles,
        )

    # Selection: build ScoredPaper from filter rank (policy off = required-keyword match only).
    # Score by tier: title match > abstract match > seed > other; then select_topk.
    scored: list[ScoredPaper] = []
    for r in ranked_all:
        topic_id = r.paper.categories[0] if r.paper.categories else "default"
        why_lower = (r.why_this_paper or "").lower()
        if "title" in why_lower and "required keyword" in why_lower:
            score = 1.5
        elif "abstract" in why_lower and "required keyword" in why_lower:
            score = 1.2
        elif "seed" in why_lower:
            score = 1.1
        else:
            score = 1.0
        scored.append(
            ScoredPaper(
                paper=r.paper,
                score=score,
                uncertainty=0.0,
                novelty=0.0,
                why_this_paper=r.why_this_paper or "—",
                topic_id=topic_id,
            )
        )
    autotune_enabled = False
    autotune_controller = None
    autotune_params = None
    autotune_candidate_name = "static"
    autotune_method = "off"
    autotune_daily_reward = 0.0
    run_date = get_run_date()

    selected_scored = select_topk(
        scored,
        k=direction.max_papers_per_day,
        explore_ratio=config.selection.explore_ratio,
        topic_cap=config.selection.topic_cap,
        min_topics=config.selection.min_topics,
    )
    ranked_all = [
        RankedPaper(paper=s.paper, why_this_paper=s.why_this_paper or "—")
        for s in selected_scored
    ]
    selected = len(ranked_all)
    discovery_selected = selected  # same count; explicit for log field alignment

    # Diversity metrics for anti-collapse evidence (computed on all selected)
    num_topics = len({s.topic_id for s in selected_scored})
    exploration_picks = sum(1 for s in selected_scored if getattr(s, "exploration_pick", False))

    # State: only process unseen (discovery feed)
    paper_ids = [r.paper.id for r in ranked_all]
    unseen_ids, seen_cache = filter_unseen(delivery.state_dir, paper_ids)
    if not unseen_ids and not scholar_new:
        log.info(
            "fetched_total=%d after_category=%d after_filters=%d selected=%d new_count=0 num_topics=%d exploration_picks=%d autotune_enabled=%s autotune_method=%s autotune_candidate_name=%s autotune_daily_reward=%.4f discovery_selected=%d scholar_new=%d scholar_provider=%s",
            fetched_total,
            after_category,
            after_filters,
            selected,
            num_topics,
            exploration_picks,
            autotune_enabled,
            autotune_method,
            autotune_candidate_name,
            autotune_daily_reward,
            discovery_selected,
            len(scholar_new),
            scholar_provider,
        )
        return []

    unseen_set = set(unseen_ids)
    ranked_unseen = [r for r in ranked_all if r.paper.id in unseen_set]
    new_count = len(ranked_unseen)

    # Update topic/phrase stats for novelty (next run), using only newly processed papers.
    # This ensures novelty is based on what the user actually saw, not already-seen papers.
    phrase_counts, topic_counts = load_topic_stats(delivery.state_dir)
    id_to_scored = {s.paper.id: s for s in selected_scored}
    papers_phrases: list[list[str]] = []
    papers_topics: list[str] = []
    for r in ranked_unseen:
        scored_item = id_to_scored.get(r.paper.id)
        if scored_item is None:
            continue
        _, _, matched = encode_paper(scored_item.paper, config)
        papers_phrases.append([p.lower().strip() for p in matched])
        papers_topics.append(scored_item.topic_id)
    update_topic_stats_from_papers(
        delivery.state_dir,
        phrase_counts,
        topic_counts,
        papers_phrases,
        papers_topics,
    )

    Path(delivery.library_dir).mkdir(parents=True, exist_ok=True)
    Path(delivery.paper_dir).mkdir(parents=True, exist_ok=True)

    # Build RankedPaper wrappers for Scholar Inbox (no bandit why/selection semantics).
    scholar_ranked: list[RankedPaper] = []
    for p in scholar_new:
        scholar_ranked.append(
            RankedPaper(
                paper=p,
                why_this_paper="From your Scholar Inbox (Google Scholar Alert).",
            )
        )

    discovery_note_paths: list[str] = []
    new_metadata_paths: list[Path] = []
    for r in ranked_unseen:
        # Optional LLM-generated research-focused summary (language-controlled).
        research_summary = build_research_summary(r.paper, r.why_this_paper, config)
        note_path = write_local_note(
            r,
            delivery.library_dir,
            run_date,
            brief_one_liner=None,
            research_summary=research_summary,
            source="arxiv",
        )
        discovery_note_paths.append(str(note_path.relative_to(delivery.library_dir)))
        new_metadata_paths.append(note_path.with_suffix(".json"))

    # Export discovery papers to BibTeX/RIS when configured (library_dir/YYYY-MM-DD/{id}.bib, .ris).
    for r in ranked_unseen:
        if "bibtex" in config.export.formats:
            write_bibtex(r.paper, delivery.library_dir, run_date)
        if "ris" in config.export.formats:
            write_ris(r.paper, delivery.library_dir, run_date)

    scholar_note_paths: list[str] = []
    for r in scholar_ranked:
        # Scholar items: no research summary; may lack abstract.
        note_path = write_local_note(
            r,
            delivery.library_dir,
            run_date,
            brief_one_liner=None,
            research_summary=None,
            source="scholar_alerts",
        )
        scholar_note_paths.append(str(note_path.relative_to(delivery.library_dir)))
        new_metadata_paths.append(note_path.with_suffix(".json"))

    if new_metadata_paths:
        enrich_related_local_papers(delivery.library_dir, new_metadata_paths)

    digest_path = write_daily_digest(
        ranked_unseen,
        scholar_ranked,
        delivery.paper_dir,
        run_date,
    )
    weekly_digest_path = write_weekly_digest(
        delivery.library_dir,
        delivery.paper_dir,
        run_date,
    )

    # Persist seen after local output for discovery feed (Scholar Inbox already persisted in source).
    save_seen(delivery.state_dir, seen_cache)

    if autotune_controller and autotune_params:
        diversity_metrics = {
            "num_topics": float(num_topics),
            "exploration_picks": float(exploration_picks),
        }
        avg_novelty = float(
            sum(s.novelty for s in selected_scored) / len(selected_scored)
        ) if selected_scored else 0.0
        novelty_metrics = {"avg_novelty": avg_novelty}

        # Feedback events are read from state_dir; if feedback_log.jsonl exists,
        # it is preferred. Otherwise, fall back to feedback.yaml when present.
        feedback_events = _load_feedback_events(delivery.state_dir, run_date)

        autotune_daily_reward = compute_reward(
            feedback_events,
            diversity_metrics,
            novelty_metrics,
            config,
        )

        at_update_ctx = AutoTuneContext(
            run_date=run_date,
            num_papers=new_count,
            num_topics=num_topics,
            exploration_picks=exploration_picks,
            avg_novelty=avg_novelty,
        )
        autotune_controller.update(
            reward=autotune_daily_reward,
            context=at_update_ctx,
            chosen_config=autotune_params,
        )

    log.info(
        "fetched_total=%d after_category=%d after_filters=%d selected=%d new_count=%d num_topics=%d exploration_picks=%d digest_path=%s weekly_digest_path=%s autotune_enabled=%s autotune_method=%s autotune_candidate_name=%s autotune_daily_reward=%.4f discovery_selected=%d scholar_new=%d scholar_provider=%s",
        fetched_total,
        after_category,
        after_filters,
        selected,
        new_count,
        num_topics,
        exploration_picks,
        str(digest_path),
        str(weekly_digest_path),
        autotune_enabled,
        autotune_method,
        autotune_candidate_name,
        autotune_daily_reward,
        discovery_selected,
        len(scholar_new),
        scholar_provider,
    )
    return ranked_unseen + scholar_ranked


def _load_feedback_events(state_dir: str | Path, run_date: date) -> List[Dict[str, Any]]:
    """Load feedback events for the given run_date from JSONL or YAML state files.

    Preference order:
    1) state/feedback_log.jsonl (append-only event log)
    2) state/feedback.yaml (manual entries)
    """
    state_path = Path(state_dir)
    jsonl_path = state_path / "feedback_log.jsonl"
    yaml_path = state_path / "feedback.yaml"

    events: List[Dict[str, Any]] = []
    target_prefix = run_date.isoformat()

    if jsonl_path.exists():
        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = str(record.get("timestamp", ""))
                    if ts.startswith(target_prefix):
                        events.append(
                            {
                                "event_type": record.get("event_type"),
                                "paper_id": record.get("paper_id"),
                                "timestamp": ts,
                            }
                        )
        except OSError:
            # Fall back to YAML if reading JSONL fails.
            pass

    # Fallback: if no events from JSONL (or file missing / unreadable), try YAML.
    if not events and yaml_path.exists():
        try:
            import yaml

            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return events

        raw_events = data.get("events", []) if isinstance(data, dict) else []
        for record in raw_events:
            if not isinstance(record, dict):
                continue
            ts = str(record.get("timestamp", ""))
            if ts.startswith(target_prefix):
                events.append(
                    {
                        "event_type": record.get("event_type"),
                        "paper_id": record.get("paper_id"),
                        "timestamp": ts,
                    }
                )

    return events
