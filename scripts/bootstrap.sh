#!/usr/bin/env bash
# Bootstrap Paper Agent: create venv, install deps, copy config.
# Run from the repository root: ./scripts/bootstrap.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f "config.example.yaml" ]] || [[ ! -f "requirements.txt" ]]; then
  echo "Error: Run this script from the Paper Agent repo root (where config.example.yaml and requirements.txt exist)." >&2
  exit 1
fi

echo "Creating virtual environment at .venv ..."
python3 -m venv .venv

echo "Installing dependencies ..."
.venv/bin/pip install -q -r requirements.txt

if [[ ! -f "config.yaml" ]]; then
  cp config.example.yaml config.yaml
  echo "Created config.yaml from config.example.yaml."
else
  echo "config.yaml already exists; leaving it unchanged."
fi

mkdir -p logs state 2>/dev/null || true

echo ""
echo "Done. Next steps:"
echo "  1. Edit config.yaml (e.g. interests.seeds, delivery.paper_dir)."
echo "  2. If using Raycast: set Config file path and Paper directory in extension Preferences."
echo "  3. Run once: .venv/bin/python -m paper_agent run --config config.yaml"
echo ""
