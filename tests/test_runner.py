"""Run the real macOS shell runner against an isolated fake Python executable."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RUNNER = Path(__file__).parents[1] / "scripts" / "run_paper_agent.sh"
pytestmark = pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is required for the macOS runner")


@pytest.mark.parametrize("exit_code", [0, 7])
def test_runner_records_exit_status_and_releases_lock(tmp_path: Path, exit_code: int):
    executable = tmp_path / "fake-python"
    executable.write_text(f"#!/bin/sh\necho 'Processed 2 new papers'\nexit {exit_code}\n")
    executable.chmod(0o700)
    state = tmp_path / "state"
    result = subprocess.run([
        shutil.which("zsh"), str(RUNNER), "--mode", "manual", "--agent-root", str(tmp_path),
        "--python", str(executable), "--config", str(tmp_path / "config.yaml"),
        "--state-dir", str(state), "--log-dir", str(tmp_path / "logs"),
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode == exit_code
    record = json.loads((state / "last_run_status.json").read_text())
    assert record["status"] == ("success" if exit_code == 0 else "failed")
    assert record["exit_code"] == str(exit_code)
    assert Path(record["log_path"]).exists()
    assert not (state / "run.lock").exists()
    assert (state / "last_success_date").exists() == (exit_code == 0)


def test_active_lock_prevents_a_second_pipeline(tmp_path: Path):
    executable = tmp_path / "fake-python"
    marker = tmp_path / "started"
    executable.write_text(f'#!/bin/sh\ntouch "{marker}"\nsleep 1\nexit 0\n')
    executable.chmod(0o700)
    args = [shutil.which("zsh"), str(RUNNER), "--agent-root", str(tmp_path), "--python", str(executable),
            "--config", str(tmp_path / "config.yaml"), "--state-dir", str(tmp_path / "state"), "--log-dir", str(tmp_path / "logs")]
    first = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        import time
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists()
        second = subprocess.run(args, capture_output=True, text=True, timeout=5)
        assert second.returncode == 0
        assert "another Paper Agent process is active" in second.stdout
        first.communicate(timeout=5)
        assert first.returncode == 0
    finally:
        if first.poll() is None:
            first.terminate()
            first.communicate(timeout=5)
