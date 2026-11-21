import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / "core with spaces"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(Path(__file__).parents[1] / "scripts/bootstrap.sh", root / "scripts/bootstrap.sh")
    (root / "config.example.yaml").write_text("example: true\n")
    (root / "requirements.txt").write_text("")
    (root / "config.yaml").write_text("private: preserved\n")
    # Keep the filesystem recovery real while avoiding package downloads in these tests.
    python = tmp_path / "replacement-python"
    python.write_text('''#!/bin/bash
set -eu
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  mkdir -p "$3/bin"
  cp "$0" "$3/bin/python"
  printf '#!/bin/sh\\nexit 0\\n' > "$3/bin/paper-agent"
  chmod +x "$3/bin/paper-agent"
fi
''')
    python.chmod(0o755)
    return root, python


def bootstrap(root, python):
    return subprocess.run(
        ["bash", str(root / "scripts/bootstrap.sh")],
        env={**os.environ, "PAPER_AGENT_PYTHON": str(python)},
        capture_output=True, text=True, timeout=15,
    )


@pytest.mark.parametrize("layout", ["directory", "external-link", "dangling-link"])
def test_recover_missing_interpreter_without_touching_config_or_old_files(installation, layout):
    root, python = installation
    old = root / ".venv"
    if layout == "dangling-link":
        old.symlink_to(root.parent / "missing-environment")
    else:
        target = old if layout == "directory" else root.parent / "shared-environment"
        (target / "bin").mkdir(parents=True)
        (target / "bin/python").symlink_to(root.parent / "removed-python")
        (target / "keep.txt").write_text("preserve me")
        if layout == "external-link":
            old.symlink_to(target)

    result = bootstrap(root, python)
    assert result.returncode == 0, result.stderr
    assert (root / ".venv/bin/python").is_file()
    assert (root / "config.yaml").read_text() == "private: preserved\n"
    backups = list(root.glob(".venv-backup.*/environment"))
    assert len(backups) == 1
    if layout == "dangling-link":
        assert backups[0].is_symlink()
        assert backups[0].readlink() == root.parent / "missing-environment"
    else:
        assert (backups[0] / "keep.txt").read_text() == "preserve me"
        assert (backups[0] / "bin/python").is_symlink()
        if layout == "external-link":
            assert (target / "keep.txt").read_text() == "preserve me"


def test_invalid_replacement_leaves_broken_environment_in_place(installation):
    root, _ = installation
    (root / ".venv").symlink_to(root.parent / "missing-environment")
    result = bootstrap(root, root.parent / "missing-python")
    assert result.returncode != 0
    assert (root / ".venv").is_symlink()
    assert not list(root.glob(".venv-backup.*"))
    assert (root / "config.yaml").read_text() == "private: preserved\n"


def test_reuses_working_environment(installation):
    root, python = installation
    assert bootstrap(root, python).returncode == 0
    (root / ".venv/keep.txt").write_text("existing environment")
    assert bootstrap(root, root.parent / "unused-python").returncode == 0
    assert (root / ".venv/keep.txt").read_text() == "existing environment"
    assert not list(root.glob(".venv-backup.*"))
