#!/usr/bin/env bash
# Install or update Paper Agent while preserving local configuration.
# Run from the repository root: ./scripts/bootstrap.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f "config.example.yaml" ]] || [[ ! -f "requirements.txt" ]]; then
  echo "Error: Run this script from the Paper Agent repo root (where config.example.yaml and requirements.txt exist)." >&2
  exit 1
fi

PYTHON_BIN="python3"
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Error: Paper Agent requires Python 3.11 or later. Check $PYTHON_BIN before installing." >&2
  exit 1
fi

if [[ "$PYTHON_BIN" == "python3" ]]; then
  echo "Creating virtual environment at .venv ..."
  python3 -m venv .venv
else
  echo "Using the existing virtual environment at .venv ..."
fi

echo "Installing Paper Agent and its dependencies ..."
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  .venv/bin/python -m ensurepip --upgrade
fi
.venv/bin/python -m pip install -q --upgrade pip setuptools
.venv/bin/python -m pip install -q --upgrade --upgrade-strategy eager .
.venv/bin/paper-agent --help >/dev/null

if [[ ! -f "config.yaml" ]]; then
  cp config.example.yaml config.yaml
  echo "Created config.yaml from config.example.yaml."
else
  echo "config.yaml already exists; leaving it unchanged."
fi

mkdir -p logs state

echo ""
echo "Done. Next steps:"
echo "  1. Edit config.yaml (e.g. interests.seeds, delivery.paper_dir)."
echo "  2. If using Raycast: set Config file path and Paper directory in extension Preferences."
echo "  3. Run once: .venv/bin/python -m paper_agent run --config config.yaml"
echo ""
