"""
Pipeline: load config -> fetch (arXiv) -> lookback filter -> filter/rank -> state (unseen)
-> write local notes + daily digest + export -> Slack (log failure, do not re-push).
Catch-up safe and idempotent: seen state is persisted after local output; Slack failure is logged.
"""

import logging
from datetime import date
from pathlib import Path

from paper_agent.config import Config, load_config
from paper_agent.dates import within_lookback
from paper_agent.exporters import write_bibtex, write_ris
from paper_agent.fetch.arxiv import fetch_arxiv
from paper_agent.filter_papers import RankedPaper, filter_and_rank
from paper_agent.models import Paper
from paper_agent.output.local import write_local_note, write_daily_digest
from paper_agent.output.slack import send_slack_brief
from paper_agent.state import filter_unseen, save_seen


def _setup_run_logging(logs_dir: str | Path) -> logging.Logger:
    """Configure and return logger that writes to logs_dir/latest.log."""
    log_path = Path(logs_dir) / "latest.log"
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("paper_agent.run")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    return logger


def run(config_path: str | Path) -> list[RankedPaper]:
    """
    Run the full pipeline. Returns list of RankedPaper that were newly processed.
    State is saved after local notes/digest/export; if Slack fails, we log and do not re-push next run.
    """
    config = load_config(config_path)
    direction = config.direction
    delivery = config.delivery
    advanced = config.advanced
    log = _setup_run_logging(delivery.logs_dir)

    # Fetch from arXiv (if enabled)
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
    after_lookback = len(papers_raw)

    # Filter and rank
    ranked_all = filter_and_rank(papers_raw, config)
    after_filters = len(ranked_all)
    ranked_all = ranked_all[: direction.max_papers_per_day]
    selected = len(ranked_all)

    # State: only process unseen
    paper_ids = [r.paper.id for r in ranked_all]
    unseen_ids, seen_cache = filter_unseen(delivery.state_dir, paper_ids)
    if not unseen_ids:
        log.info(
            "fetched_total=%d after_lookback=%d after_filters=%d selected=%d new_count=0 pushed_count=0",
            fetched_total,
            after_lookback,
            after_filters,
            selected,
        )
        return []

    unseen_set = set(unseen_ids)
    ranked_unseen = [r for r in ranked_all if r.paper.id in unseen_set]
    new_count = len(ranked_unseen)

    run_date = date.today()
    Path(delivery.library_dir).mkdir(parents=True, exist_ok=True)
    Path(delivery.daily_dir).mkdir(parents=True, exist_ok=True)

    note_paths: list[str] = []
    for r in ranked_unseen:
        note_path = write_local_note(r, delivery.library_dir, run_date)
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

    log.info(
        "fetched_total=%d after_lookback=%d after_filters=%d selected=%d new_count=%d pushed_count=%d digest_path=%s",
        fetched_total,
        after_lookback,
        after_filters,
        selected,
        new_count,
        pushed_count,
        str(digest_path),
    )
    return ranked_unseen
