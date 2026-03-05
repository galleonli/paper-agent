"""
Pipeline orchestration: load config -> fetch -> lookback -> filter/rank -> state (unseen)
-> write local notes + daily digest + export -> deliver (Slack). Log failure on delivery; do not re-push.
Catch-up safe and idempotent: seen state is persisted after local output.
"""

from datetime import date
from pathlib import Path

from paper_agent.core.config import Config, load_config
from paper_agent.core.dates import within_lookback
from paper_agent.core.logging import setup_run_logging
from paper_agent.core.models import Paper
from paper_agent.core.state import filter_unseen, save_seen
from paper_agent.core.summarize import build_research_summary
from paper_agent.export import write_bibtex, write_ris
from paper_agent.filter_papers import RankedPaper, count_after_category, filter_and_rank
from paper_agent.policy.base import ScoredPaper
from paper_agent.output.local import write_daily_digest, write_local_note
from paper_agent.deliver import send_slack_brief
from paper_agent.sources import fetch_arxiv
from paper_agent.policy.base import PolicyContext
from paper_agent.policy.deterministic import DeterministicPolicy
from paper_agent.policy.linucb import LinUCBPolicy
from paper_agent.selection import select_topk
from paper_agent.core.topic_stats import (
    load_topic_stats,
    update_topic_stats_from_papers,
)
from paper_agent.features.encoder import encode_paper
from paper_agent.autotune import AutoTuneController, TunedPolicyParams
from paper_agent.autotune.base import AutoTuneContext
from paper_agent.autotune.reward import compute_reward
import json
from typing import Any, Dict, List


def run(config_path: str | Path) -> list[RankedPaper]:
    """
    Run the full pipeline. Returns list of RankedPaper that were newly processed.
    State is saved after local notes/digest/export; if Slack fails, we log and do not re-push next run.
    """
    config = load_config(config_path)
    direction = config.direction
    delivery = config.delivery
    advanced = config.advanced
    log = setup_run_logging(delivery.logs_dir)

    # Fetch from sources (arXiv if enabled)
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

    # Lookback filter: keep only papers updated within last lookback_days (UTC)
    papers_raw = [p for p in papers_raw if within_lookback(p.updated, direction.lookback_days)]
    after_category = count_after_category(
        papers_raw, direction.allow_categories, direction.deny_categories
    )

    # Filter and rank (direction + interest)
    ranked_all = filter_and_rank(papers_raw, config)
    after_filters = len(ranked_all)

    # Policy + constrained selection (agent logic)
    papers_for_policy = [r.paper for r in ranked_all]
    context = PolicyContext(config)

    # Optional AutoTune: choose policy parameters before scoring.
    autotune_configured = bool(getattr(config, "autotune", None) and config.autotune.enabled)
    autotune_enabled = autotune_configured and config.policy.type == "linucb"
    autotune_candidate_name = "static"
    autotune_method = "off"
    autotune_params: TunedPolicyParams | None = None
    autotune_daily_reward = 0.0

    run_date = date.today()

    autotune_controller: AutoTuneController | None = None
    if autotune_enabled:
        autotune_method = config.autotune.method
        autotune_controller = AutoTuneController(config, delivery.state_dir)
        at_context = AutoTuneContext(
            run_date=run_date,
        )
        autotune_params = autotune_controller.choose_config(at_context)
        autotune_candidate_name = autotune_params.candidate_id
        # Override policy config for this run only.
        config.policy.alpha = autotune_params.alpha
        config.policy.lambda_ucb = autotune_params.lambda_ucb
        config.policy.mu_novelty = autotune_params.mu_novelty
        config.policy.ridge = autotune_params.ridge

    if config.policy.type == "linucb":
        policy = LinUCBPolicy()
    else:
        policy = DeterministicPolicy()
    scored = policy.score(papers_for_policy, context)
    selected_scored = select_topk(
        scored,
        k=direction.max_papers_per_day,
        explore_ratio=config.selection.explore_ratio,
        topic_cap=config.selection.topic_cap,
        min_topics=config.selection.min_topics,
    )
    # Build why_this_paper: append exploration/novelty when selection chose for exploration
    def _why_with_selection(s: ScoredPaper) -> str:
        why = s.why_this_paper or "—"
        if getattr(s, "exploration_pick", False):
            why = f"{why} (exploration)"
        return why

    ranked_all = [
        RankedPaper(paper=s.paper, why_this_paper=_why_with_selection(s))
        for s in selected_scored
    ]
    selected = len(ranked_all)

    # Diversity metrics for anti-collapse evidence (computed on all selected)
    num_topics = len({s.topic_id for s in selected_scored})
    exploration_picks = sum(1 for s in selected_scored if getattr(s, "exploration_pick", False))

    # State: only process unseen
    paper_ids = [r.paper.id for r in ranked_all]
    unseen_ids, seen_cache = filter_unseen(delivery.state_dir, paper_ids)
    if not unseen_ids:
        log.info(
            "fetched_total=%d after_category=%d after_filters=%d selected=%d new_count=0 pushed_count=0 num_topics=%d exploration_picks=%d autotune_enabled=%s autotune_method=%s autotune_candidate_name=%s autotune_daily_reward=%.4f",
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
    Path(delivery.daily_dir).mkdir(parents=True, exist_ok=True)

    note_paths: list[str] = []
    for r in ranked_unseen:
        # Optional LLM-generated research-focused summary (language-controlled).
        research_summary = build_research_summary(r.paper, r.why_this_paper, config)
        note_path = write_local_note(
            r,
            delivery.library_dir,
            run_date,
            brief_one_liner=None,
            research_summary=research_summary,
        )
        note_paths.append(note_path.name)

    digest_path = write_daily_digest(ranked_unseen, delivery.daily_dir, run_date)

    # Export BibTeX / RIS
    for r in ranked_unseen:
        if "bibtex" in config.export.formats:
            write_bibtex(r.paper, delivery.library_dir)
        if "ris" in config.export.formats:
            write_ris(r.paper, delivery.library_dir)

    # Persist seen after local output (so we never re-write or re-push the same papers)
    save_seen(delivery.state_dir, seen_cache)

    pushed_count = 0
    if delivery.slack.enabled:
        try:
            send_slack_brief(ranked_unseen, config, note_paths)
            pushed_count = new_count
        except Exception as e:
            log.warning("Slack push failed (papers already marked seen): %s", e)

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
        "fetched_total=%d after_category=%d after_filters=%d selected=%d new_count=%d pushed_count=%d num_topics=%d exploration_picks=%d digest_path=%s autotune_enabled=%s autotune_method=%s autotune_candidate_name=%s autotune_daily_reward=%.4f",
        fetched_total,
        after_category,
        after_filters,
        selected,
        new_count,
        pushed_count,
        num_topics,
        exploration_picks,
        str(digest_path),
        autotune_enabled,
        autotune_method,
        autotune_candidate_name,
        autotune_daily_reward,
    )
    return ranked_unseen


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
