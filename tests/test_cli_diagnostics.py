"""CLI tests for `python -m paper_agent diagnostics`."""

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from paper_agent.cli import main as cli_main
from tests.helpers import write_config


def test_diagnostics_missing_config_reports_all_and_exits_nonzero(
    tmp_path: Path, monkeypatch
) -> None:
    """Missing config should report the error and still print maintenance reminder."""
    missing = tmp_path / "missing-config.yaml"
    monkeypatch.setattr(
        "sys.argv",
        ["paper_agent", "diagnostics", "--config", str(missing)],
        raising=False,
    )

    buf = StringIO()
    with pytest.raises(SystemExit) as ex:
        with redirect_stdout(buf):
            cli_main()

    assert ex.value.code == 1
    out = buf.getvalue()
    assert "CONFIG_FILE_MISSING" in out
    assert "CONFIG_DEPENDENT_CHECKS_SKIPPED" in out
    assert "DEVELOPER_MAINTENANCE_REMINDER" in out


def test_diagnostics_json_returns_findings(tmp_path: Path, monkeypatch) -> None:
    """diagnostics --json returns structured findings with no hard errors for minimal valid config."""
    config_path = write_config(tmp_path, summarize_enabled=False)
    monkeypatch.setattr(
        "sys.argv",
        ["paper_agent", "diagnostics", "--json", "--config", str(config_path)],
        raising=False,
    )

    buf = StringIO()
    with redirect_stdout(buf):
        cli_main()

    findings = json.loads(buf.getvalue())
    assert isinstance(findings, list)
    assert any(f["check_id"] == "CONFIG_VALID" for f in findings)
    assert any(f["check_id"] == "DEVELOPER_MAINTENANCE_REMINDER" for f in findings)
    assert not any(f["severity"] == "ERROR" for f in findings)


def test_diagnostics_scholar_empty_mbox_path_reported_as_missing(
    tmp_path: Path, monkeypatch
) -> None:
    """Scholar provider mbox with empty mbox_path must report SCHOLAR_MBOX_PATH_MISSING."""
    config_path = write_config(
        tmp_path,
        scholar_enabled=True,
        scholar_provider="mbox",
        scholar_mbox_path="",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["paper_agent", "diagnostics", "--config", str(config_path)],
        raising=False,
    )
    buf = StringIO()
    with pytest.raises(SystemExit) as ex:
        with redirect_stdout(buf):
            cli_main()
    assert ex.value.code == 1
    assert "SCHOLAR_MBOX_PATH_MISSING" in buf.getvalue()


def test_diagnostics_scholar_empty_eml_dir_reported_as_missing(
    tmp_path: Path, monkeypatch
) -> None:
    """Scholar provider eml_dir with empty eml_dir must report SCHOLAR_EML_DIR_MISSING."""
    config_path = write_config(
        tmp_path,
        scholar_enabled=True,
        scholar_provider="eml_dir",
        scholar_eml_dir="",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["paper_agent", "diagnostics", "--config", str(config_path)],
        raising=False,
    )
    buf = StringIO()
    with pytest.raises(SystemExit) as ex:
        with redirect_stdout(buf):
            cli_main()
    assert ex.value.code == 1
    assert "SCHOLAR_EML_DIR_MISSING" in buf.getvalue()


def test_diagnostics_scholar_eml_dir_error_is_reported(
    tmp_path: Path, monkeypatch
) -> None:
    """Scholar eml_dir misconfiguration should be reported as ERROR and command exits nonzero."""
    missing_eml_dir = tmp_path / "no-eml-dir"
    config_path = write_config(
        tmp_path,
        scholar_enabled=True,
        scholar_provider="eml_dir",
        scholar_eml_dir=str(missing_eml_dir),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["paper_agent", "diagnostics", "--config", str(config_path)],
        raising=False,
    )

    buf = StringIO()
    with pytest.raises(SystemExit) as ex:
        with redirect_stdout(buf):
            cli_main()

    assert ex.value.code == 1
    out = buf.getvalue()
    assert "SCHOLAR_EML_DIR_INVALID" in out
    assert "DEVELOPER_MAINTENANCE_REMINDER" in out
