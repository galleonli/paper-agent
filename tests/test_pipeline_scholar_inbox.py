import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from paper_agent.core.models import Paper
from paper_agent.core.utils import safe_paper_id_for_path
from paper_agent.pipeline import run as pipeline_run
from paper_agent.filter_papers import RankedPaper
from paper_agent.selection import select_topk as real_select_topk


def _config_with_scholar(tmp_path: Path) -> Path:
    """Build a config with small discovery quota and Scholar Inbox enabled."""
    cfg = f"""
interests:
  seeds: []
  keyphrases: []
  negative_keyphrases: []
direction:
  max_papers_per_day: 2
  lookback_days: 7
  allow_categories: ["cs.LG"]
  deny_categories: []
  queries: []
  include_keywords: []
  exclude_keywords: []
  exclude_authors: []
delivery:
  slack:
    enabled: false
    webhook_url: ""
  library_dir: "{(tmp_path / "library").as_posix()}"
  daily_dir: "{(tmp_path / "daily").as_posix()}"
  state_dir: "{(tmp_path / "state").as_posix()}"
  logs_dir: "{(tmp_path / "logs").as_posix()}"
summarize:
  enabled: false
  brief_summary: true
export:
  formats: ["bibtex", "ris"]
sources:
  arxiv:
    enabled: true
  scholar_alerts:
    enabled: true
    mode: "email"
    email:
      provider: "eml_dir"
      eml_dir: ""
      mbox_path: ""
      from_addresses: []
    max_items_per_run: 10
    push_to_slack: true
    light_filter:
      include_keywords: []
      exclude_keywords: []
      exclude_authors: []
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
  type: "deterministic"
  alpha: 0.5
  lambda_ucb: 1.0
  mu_novelty: 0.3
  ridge: 1.0
advanced:
  request_timeout_seconds: 30
  max_retries: 3
  max_results_per_query: 50
"""
    path = tmp_path / "config.yaml"
    path.write_text(cfg, encoding="utf-8")
    return path


def test_quota_semantics(tmp_path: Path) -> None:
    """
    max_papers_per_day=2 applies ONLY to discovery: 5 discovery -> 2 shown.
    Scholar has 5 -> shows 5 (or max_items_per_run); never consumes max_papers_per_day.
    """
    config_path = _config_with_scholar(tmp_path)

    # Discovery candidates: 5 papers, but policy/selection should cap at 2.
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    discovery_papers = [
        Paper(
            id=f"disc-{i}",
            title=f"Discovery {i}",
            summary="Abstract",
            authors=["Alice"],
            categories=["cs.LG"],
            updated=now_iso,
            link_abs=f"https://arxiv.org/abs/disc-{i}",
            link_pdf=None,
        )
        for i in range(5)
    ]

    # Scholar Inbox: 5 papers, treated separately.
    scholar_papers = [
        Paper(
            id=f"scholar-{i}",
            title=f"Scholar {i}",
            summary="",
            authors=["Bob"],
            categories=[],
            updated=now_iso,
            link_abs=f"https://example.com/scholar/{i}",
            link_pdf=None,
        )
        for i in range(5)
    ]

    def fake_fetch_arxiv(*args, **kwargs):
        return discovery_papers

    def fake_fetch_scholar(now, lookback_days, config):
        return scholar_papers

    with (
        patch("paper_agent.pipeline.fetch_arxiv", side_effect=fake_fetch_arxiv),
        patch(
            "paper_agent.pipeline.scholar_alerts_source.fetch",
            side_effect=fake_fetch_scholar,
        ),
    ):
        result = pipeline_run(config_path)

    # result contains both discovery + scholar newly processed items.
    assert isinstance(result, list)
    assert all(isinstance(r, RankedPaper) for r in result)
    assert len(result) == 7

    # Daily digest file must contain both sections with correct counts.
    digest_path = tmp_path / "daily" / f"{datetime.now().date().isoformat()}.md"
    assert digest_path.exists()
    text = digest_path.read_text(encoding="utf-8")
    assert "## Daily Precision" in text
    assert "## Scholar Inbox" in text
    # Scholar section should list all 5 scholar items.
    for i in range(5):
        assert f"Scholar {i}" in text


def test_scholar_bypass_constraints(tmp_path: Path) -> None:
    """
    Scholar items do NOT go through constrained selector or policy scorer.
    Pipeline return list includes both discovery and scholar newly processed items.
    """
    config_path = _config_with_scholar(tmp_path)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    discovery_papers = [
        Paper(
            id="disc-1",
            title="Discovery 1",
            summary="Abstract",
            authors=["Alice"],
            categories=["cs.LG"],
            updated=now_iso,
            link_abs="https://arxiv.org/abs/disc-1",
            link_pdf=None,
        )
    ]
    scholar_papers = [
        Paper(
            id="scholar-1",
            title="Scholar 1",
            summary="",
            authors=["Bob"],
            categories=[],
            updated=now_iso,
            link_abs="https://example.com/scholar/1",
            link_pdf=None,
        )
    ]

    with (
        patch("paper_agent.pipeline.fetch_arxiv", return_value=discovery_papers),
        patch(
            "paper_agent.pipeline.scholar_alerts_source.fetch",
            return_value=scholar_papers,
        ),
        patch("paper_agent.pipeline.select_topk", side_effect=real_select_topk) as select_mock,
    ):
        result = pipeline_run(config_path)

    assert len(result) == 2
    ids = {r.paper.id for r in result}
    assert "disc-1" in ids
    assert "scholar-1" in ids
    assert select_mock.call_count == 1
    # select_topk input is discovery-scored items only; scholar IDs must not appear there.
    scored_input = select_mock.call_args.args[0]
    assert all("scholar-" not in s.paper.id for s in scored_input)


def test_seen_merge_preserves_scholar_ids_after_pipeline_save(tmp_path: Path) -> None:
    """
    Scholar source writes seen IDs first; pipeline.save_seen must preserve them
    when persisting discovery seen cache.
    """
    config_path = _config_with_scholar(tmp_path)

    # Use real scholar source with fixture email so scholar IDs are persisted by source.fetch().
    fixture_eml = Path(__file__).parent / "fixtures" / "sample_scholar_alert.eml"
    eml_dir = tmp_path / "eml"
    eml_dir.mkdir(parents=True, exist_ok=True)
    eml_text = fixture_eml.read_text(encoding="utf-8")
    fresh_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    eml_text = eml_text.replace("Date: Thu, 02 Jan 2025 10:00:00 +0000", f"Date: {fresh_date}")
    (eml_dir / "sample_scholar_alert.eml").write_text(eml_text, encoding="utf-8")

    cfg_text = config_path.read_text(encoding="utf-8")
    cfg_text = cfg_text.replace('eml_dir: ""', f'eml_dir: "{eml_dir.as_posix()}"')
    cfg_text = cfg_text.replace("from_addresses: []", 'from_addresses: ["scholaralerts-noreply@google.com"]')
    config_path.write_text(cfg_text, encoding="utf-8")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    discovery_papers = [
        Paper(
            id="disc-merge-1",
            title="Discovery Merge 1",
            summary="Abstract",
            authors=["Alice"],
            categories=["cs.LG"],
            updated=now_iso,
            link_abs="https://arxiv.org/abs/disc-merge-1",
            link_pdf=None,
        )
    ]

    with patch("paper_agent.pipeline.fetch_arxiv", return_value=discovery_papers):
        first = pipeline_run(config_path)
    assert len(first) >= 2  # 1 discovery + >=1 scholar from fixture

    seen_path = tmp_path / "state" / "seen.json"
    assert seen_path.exists()
    seen_data = json.loads(seen_path.read_text(encoding="utf-8"))
    seen_ids = set(seen_data.get("seen_ids", []))
    assert "disc-merge-1" in seen_ids
    assert any(pid.startswith("scholar:") for pid in seen_ids)

    # Second run with same inputs should be fully idempotent.
    with patch("paper_agent.pipeline.fetch_arxiv", return_value=discovery_papers):
        second = pipeline_run(config_path)
    assert second == []


def test_bibtex_ris_only_for_discovery_not_scholar(tmp_path: Path) -> None:
    """
    When export.formats includes bibtex/ris, pipeline writes .bib/.ris for discovery
    papers only; Scholar Inbox items get .md/.json but no .bib/.ris.
    """
    config_path = _config_with_scholar(tmp_path)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    discovery_papers = [
        Paper(
            id="disc-export-1",
            title="Discovery Export 1",
            summary="Abstract",
            authors=["Alice"],
            categories=["cs.LG"],
            updated=now_iso,
            link_abs="https://arxiv.org/abs/disc-export-1",
            link_pdf=None,
        )
    ]
    scholar_papers = [
        Paper(
            id="scholar:arxiv:2501.00001",
            title="Scholar Export Check",
            summary="",
            authors=["Bob"],
            categories=[],
            updated=now_iso,
            link_abs="https://arxiv.org/abs/2501.00001",
            link_pdf=None,
        )
    ]

    with (
        patch("paper_agent.pipeline.fetch_arxiv", return_value=discovery_papers),
        patch("paper_agent.pipeline.scholar_alerts_source.fetch", return_value=scholar_papers),
    ):
        result = pipeline_run(config_path)

    assert len(result) == 2
    library = tmp_path / "library"
    run_subdir = library / datetime.now().date().isoformat()
    discovery_name = safe_paper_id_for_path(discovery_papers[0].id)
    scholar_name = safe_paper_id_for_path(scholar_papers[0].id)

    # Both get notes.
    assert (run_subdir / f"{discovery_name}.md").exists()
    assert (run_subdir / f"{scholar_name}.md").exists()
    # Discovery gets BibTeX/RIS; Scholar Inbox does not.
    assert (run_subdir / f"{discovery_name}.bib").exists()
    assert (run_subdir / f"{discovery_name}.ris").exists()
    assert not (run_subdir / f"{scholar_name}.bib").exists()
    assert not (run_subdir / f"{scholar_name}.ris").exists()


def test_research_summary_is_discovery_only_not_scholar(tmp_path: Path) -> None:
    """Pipeline should call research-summary builder only for discovery items."""
    config_path = _config_with_scholar(tmp_path)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    discovery_papers = [
        Paper(
            id="disc-summary-1",
            title="Discovery Summary 1",
            summary="Abstract",
            authors=["Alice"],
            categories=["cs.LG"],
            updated=now_iso,
            link_abs="https://arxiv.org/abs/disc-summary-1",
            link_pdf=None,
        )
    ]
    scholar_papers = [
        Paper(
            id="scholar:arxiv:2601.00001",
            title="Scholar Summary Check",
            summary="",
            authors=["Bob"],
            categories=[],
            updated=now_iso,
            link_abs="https://arxiv.org/abs/2601.00001",
            link_pdf=None,
        )
    ]

    with (
        patch("paper_agent.pipeline.fetch_arxiv", return_value=discovery_papers),
        patch("paper_agent.pipeline.scholar_alerts_source.fetch", return_value=scholar_papers),
        patch(
            "paper_agent.pipeline.build_research_summary",
            return_value=("Research-focused summary", "LLM output"),
        ) as summary_mock,
    ):
        result = pipeline_run(config_path)

    assert len(result) == 2
    assert summary_mock.call_count == 1
    assert summary_mock.call_args.args[0].id == "disc-summary-1"

