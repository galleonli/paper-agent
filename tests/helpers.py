"""Shared test helpers for config, papers, and local JSON artifacts."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Sequence

from paper_agent.core.models import Paper


def make_paper(
    paper_id: str,
    *,
    title: str = "Test Paper",
    days_ago: int = 0,
    summary: str = "Abstract here.",
    authors: Sequence[str] | None = None,
    categories: Sequence[str] | None = None,
    link_abs: str | None = None,
) -> Paper:
    """Build a Paper with sensible defaults and UTC updated time."""
    updated = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Paper(
        id=paper_id,
        title=title,
        summary=summary,
        authors=list(authors if authors is not None else ["Alice"]),
        categories=list(categories if categories is not None else ["cs.LG"]),
        updated=updated,
        link_abs=link_abs or f"https://arxiv.org/abs/{paper_id}",
        link_pdf=None,
    )


def _yaml_inline_list(values: Sequence[str]) -> str:
    """Format a sequence as a YAML flow sequence, escaping quotes and backslashes in values."""
    def escape(v: str) -> str:
        # Escape backslash first so that a literal \\" in the value becomes \\\\"
        # in YAML and parses back to \"; escaping quote first would produce
        # invalid or wrong YAML for values containing both \\ and ".
        return v.replace("\\", "\\\\").replace('"', '\\"')
    return "[" + ", ".join(f'"{escape(v)}"' for v in values) + "]"


def write_config(
    tmp_path: Path,
    *,
    arxiv_enabled: bool = False,
    scholar_enabled: bool = False,
    max_papers_per_day: int = 5,
    lookback_days: int = 3,
    policy_type: str = "deterministic",
    summarize_enabled: bool = False,
    export_formats: Sequence[str] = ("bibtex", "ris"),
    scholar_provider: str = "eml_dir",
    scholar_eml_dir: str = "",
    scholar_mbox_path: str = "",
    scholar_from_addresses: Sequence[str] = (),
    scholar_max_items_per_run: int = 10,
    extra_yaml: str = "",
) -> Path:
    """Write a test config.yaml with overridable toggles."""
    cfg = f"""
interests:
  seeds: []
direction:
  max_papers_per_day: {max_papers_per_day}
  lookback_days: {lookback_days}
  allow_categories: ["cs.LG"]
  deny_categories: []
  queries: []
  include_keywords: []
  exclude_keywords: []
delivery:
  library_dir: "{(tmp_path / "library").as_posix()}"
  paper_dir: "{(tmp_path / "daily").as_posix()}"
  state_dir: "{(tmp_path / "state").as_posix()}"
  logs_dir: "{(tmp_path / "logs").as_posix()}"
summarize:
  enabled: {"true" if summarize_enabled else "false"}
  provider: "openai"
  model: "gpt-4o-mini"
  language: "en"
export:
  formats: {_yaml_inline_list(export_formats)}
sources:
  arxiv:
    enabled: {"true" if arxiv_enabled else "false"}
  scholar_alerts:
    enabled: {"true" if scholar_enabled else "false"}
    mode: "email"
    email:
      provider: "{scholar_provider}"
      eml_dir: "{scholar_eml_dir}"
      mbox_path: "{scholar_mbox_path}"
      from_addresses: {_yaml_inline_list(scholar_from_addresses)}
    max_items_per_run: {scholar_max_items_per_run}
    light_filter:
      include_keywords: []
      exclude_keywords: []
    ordering: "arrival"
feedback:
  blocked_phrases: []
  blocked_authors: []
  boosted_phrases: []
selection:
  explore_ratio: 0.2
  topic_cap: 3
  min_topics: 1
policy:
  type: "{policy_type}"
  alpha: 0.5
  lambda_ucb: 1.0
  mu_novelty: 0.3
  ridge: 1.0
advanced:
  request_timeout_seconds: 30
  max_retries: 3
  max_results_per_query: 50
""".strip()
    if extra_yaml.strip():
        cfg = f"{cfg}\n{extra_yaml.strip()}\n"
    else:
        cfg = f"{cfg}\n"
    path = tmp_path / "config.yaml"
    path.write_text(cfg, encoding="utf-8")
    return path


def write_paper_json(
    day_dir: Path,
    filename: str,
    *,
    paper_id: str,
    title: str,
    published: str | None,
    abstract: str = "",
    categories: Sequence[str] | None = None,
    authors: Sequence[str] | None = None,
) -> None:
    """Write one paper metadata JSON file under a day directory."""
    payload = {
        "id": paper_id,
        "title": title,
        "date": day_dir.name,
        "published": published,
        "abstract": abstract,
        "categories": list(categories or []),
        "authors": list(authors or []),
        "link": f"https://example.com/{paper_id}",
        "note_path": f"library/{day_dir.name}/{paper_id}.md",
    }
    (day_dir / filename).write_text(json.dumps(payload), encoding="utf-8")
