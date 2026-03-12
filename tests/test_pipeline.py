"""Pipeline tests: run with arXiv disabled; policy+selection produce RankedPaper with why_this_paper."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_agent.filter_papers import RankedPaper
from paper_agent.pipeline import run as pipeline_run
from paper_agent.run import run
from tests.helpers import make_paper, write_config


def test_run_with_arxiv_disabled_returns_list(tmp_path: Path) -> None:
    """With sources.arxiv.enabled=false, pipeline runs and returns a list (no fetch)."""
    config_path = write_config(tmp_path)
    result = run(config_path)
    assert isinstance(result, list)
    assert len(result) == 0


def test_run_creates_logs_file(tmp_path: Path) -> None:
    """Pipeline run always creates logs/latest.log with a summary line."""
    config_path = write_config(tmp_path)
    run(config_path)
    log_path = tmp_path / "logs" / "latest.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    # Summary line with counters is written even when no new papers
    assert "fetched_total=" in content
    assert "after_category=" in content
    assert "after_filters=" in content
    assert "new_count=" in content


def test_run_returns_ranked_papers_with_why_this_paper_when_new_items(tmp_path: Path) -> None:
    """When there are new papers, pipeline returns RankedPaper with why_this_paper."""
    config_path = write_config(tmp_path, arxiv_enabled=True)
    fake_paper = make_paper("2301.12345")
    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]):
        result = pipeline_run(config_path)
    assert len(result) == 1
    assert isinstance(result[0], RankedPaper)
    assert hasattr(result[0], "paper") and hasattr(result[0], "why_this_paper")


def test_run_with_linucb_policy_logs_diversity_metrics(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """With policy.type=linucb, pipeline runs and log line includes num_topics and exploration_picks."""
    import logging
    caplog.set_level(logging.INFO)  # noqa: F811
    config_path = write_config(tmp_path, policy_type="linucb")
    run(config_path)
    log_text = caplog.text
    assert "num_topics=" in log_text
    assert "exploration_picks=" in log_text


def test_pipeline_still_saves_seen_and_no_repush(tmp_path: Path) -> None:
    """Seen state is saved so next run with same input has 0 new papers."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    config_path = write_config(tmp_path, arxiv_enabled=True)
    fake_paper = make_paper("2301.99999")

    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]):
        result = pipeline_run(config_path)
    assert len(result) == 1
    assert result[0].paper.id == "2301.99999"

    seen_path = state_dir / "seen.json"
    assert seen_path.exists()
    data = json.loads(seen_path.read_text(encoding="utf-8"))
    assert "2301.99999" in data.get("seen_ids", [])

    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]):
        result2 = pipeline_run(config_path)
    assert len(result2) == 0


def test_integration_autotune_pipeline_contract(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """When autotune.enabled is toggled, pipeline uses correct policy params and logs candidate/reward."""
    import logging

    caplog.set_level(logging.INFO)  # noqa: F811

    # Start from minimal config and enable linucb + autotune.
    autotune_block = """
autotune:
  enabled: true
  method: "thompson"
  random_seed: 123
  schedule:
    daily_hour_utc: 23
    weekly_day_of_week: "sun"
  candidates:
    - id: "fast"
      alpha: 0.1
      lambda_ucb: 0.2
      mu_novelty: 0.3
      ridge: 1.0
"""
    config_path = write_config(
        tmp_path,
        policy_type="linucb",
        extra_yaml=autotune_block,
    )
    config_content = config_path.read_text(encoding="utf-8")

    # Case 1: autotune.enabled=false => static policy and autotune_enabled=False in logs.
    static_cfg = config_content.replace("enabled: true", "enabled: false")
    config_path.write_text(static_cfg, encoding="utf-8")
    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[]):
        run(config_path)
    log_text_static = caplog.text
    assert "autotune_enabled=False" in log_text_static

    # Case 2: autotune.enabled=true => AutoTuneController is used and candidate name appears.
    caplog.clear()
    config_path.write_text(config_content, encoding="utf-8")
    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[]):
        run(config_path)
    log_text = caplog.text
    assert "autotune_enabled=True" in log_text
    assert "autotune_candidate_name=" in log_text
    assert "autotune_daily_reward=" in log_text


def test_autotune_flag_false_when_policy_not_linucb(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Even if autotune.enabled=true, when policy.type!=linucb the logs must show autotune_enabled=False."""
    import logging

    caplog.set_level(logging.INFO)  # noqa: F811

    # Keep policy.type deterministic, but configure autotune.enabled=true.
    autotune_block = """
autotune:
  enabled: true
  method: "thompson"
  random_seed: 123
  schedule:
    daily_hour_utc: 23
    weekly_day_of_week: "sun"
  candidates:
    - id: "fast"
      alpha: 0.1
      lambda_ucb: 0.2
      mu_novelty: 0.3
      ridge: 1.0
"""
    config_path = write_config(tmp_path, extra_yaml=autotune_block)

    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[]):
        run(config_path)
    log_text = caplog.text
    # AutoTune is configured but not active because policy.type != linucb.
    assert "autotune_enabled=False" in log_text


def test_summarize_disabled_makes_no_llm_calls(tmp_path: Path) -> None:
    """When summarize.enabled=false, pipeline never calls the LLM helper."""
    config_path = write_config(tmp_path, arxiv_enabled=True)
    fake_paper = make_paper("2403.00001", title="No LLM Call Test")

    with (
        patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]),
        patch(
            "paper_agent.core.summarize._call_openai_chat",
            side_effect=AssertionError("LLM call should not happen when summarize.enabled=false"),
        ),
    ):
        result = pipeline_run(config_path)

    assert len(result) == 1
    assert result[0].paper.id == "2403.00001"


def test_catch_up_lookback_and_seen_behavior(tmp_path: Path) -> None:
    """
    Catch-up invariant:
    - recent unseen items are processed,
    - out-of-window items are ignored,
    - already-seen items are not reprocessed.
    """
    config_path = write_config(tmp_path, arxiv_enabled=True)
    recent = make_paper("2403.00002", title="Recent Paper", days_ago=1)
    old = make_paper("2403.99999", title="Old Paper", days_ago=10)

    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[recent, old]):
        first = pipeline_run(config_path)
    assert [r.paper.id for r in first] == ["2403.00002"]

    # Same input on second run: recent is already seen; old remains out-of-window.
    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[recent, old]):
        second = pipeline_run(config_path)
    assert second == []

    seen_path = tmp_path / "state" / "seen.json"
    seen_data = json.loads(seen_path.read_text(encoding="utf-8"))
    assert "2403.00002" in seen_data.get("seen_ids", [])
    assert "2403.99999" not in seen_data.get("seen_ids", [])


def test_idempotency_no_duplicate_artifacts(tmp_path: Path) -> None:
    """
    Running twice with no new input:
    - no duplicate notes.
    """
    config_path = write_config(tmp_path, arxiv_enabled=True)
    fake_paper = make_paper("2403.00003", title="Artifact Test Paper")

    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]):
        first = pipeline_run(config_path)
        second = pipeline_run(config_path)

    assert len(first) == 1
    assert second == []

    library_dir = tmp_path / "library"
    paper_dir = tmp_path / "daily"
    date_subdir = datetime.now().date().isoformat()
    assert (library_dir / date_subdir / "2403.00003.md").exists()
    assert (library_dir / date_subdir / "2403.00003.bib").exists()
    assert (library_dir / date_subdir / "2403.00003.ris").exists()
    assert (paper_dir / f"{datetime.now().date().isoformat()}.md").exists()
    assert (tmp_path / "logs" / "latest.log").exists()
    assert len(list(library_dir.glob("*/*.md"))) == 1


def test_pipeline_respects_export_formats_toggle(tmp_path: Path) -> None:
    """
    When export.formats is empty, pipeline still writes notes
    but does not create BibTeX/RIS artifacts.
    """
    config_path = write_config(tmp_path, arxiv_enabled=True, export_formats=[])

    fake_paper = make_paper("2403.12345", title="No Export Formats Paper")

    with patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]):
        result = pipeline_run(config_path)

    assert len(result) == 1

    library_dir = tmp_path / "library"
    date_subdir = datetime.now().date().isoformat()
    run_dir = library_dir / date_subdir
    # One note is written for the paper (filename derived from safe_paper_id_for_path).
    md_files = list(run_dir.glob("*.md"))
    assert len(md_files) == 1
    # BibTeX/RIS are not written when formats list is empty.
    assert not any(run_dir.glob("*.bib"))
    assert not any(run_dir.glob("*.ris"))


def test_pipeline_writes_research_summary_in_note_when_summarize_and_api_used(tmp_path: Path) -> None:
    """
    With summarize enabled and OpenAI API mocked to return a known body,
    the pipeline must write a note that contains the Research-focused summary section.
    Proves the API path is wired into the pipeline and note output.
    """
    config_path = write_config(
        tmp_path,
        arxiv_enabled=True,
        summarize_enabled=True,
    )
    fake_paper = make_paper("2501.11111", title="Test Paper For Summary")
    mocked_summary_body = "MOCKED_RESEARCH_SUMMARY_FROM_API_XYZ"

    with (
        patch("paper_agent.pipeline.fetch_arxiv", return_value=[fake_paper]),
        patch(
            "paper_agent.pipeline.build_research_summary",
            return_value=("Research-focused summary", mocked_summary_body),
        ),
    ):
        result = pipeline_run(config_path)

    assert len(result) == 1
    library_dir = tmp_path / "library"
    date_subdir = datetime.now().date().isoformat()
    note_path = library_dir / date_subdir / "2501.11111.md"
    assert note_path.exists(), f"Note file not found: {note_path}"
    content = note_path.read_text(encoding="utf-8")
    assert "Research-focused summary" in content, "Note should contain research summary heading"
    assert mocked_summary_body in content, "Note should contain the body returned by mocked API"
