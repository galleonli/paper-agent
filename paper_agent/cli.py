"""
CLI entrypoint: python -m paper_agent run [--config path]
"""

import argparse
import json
import platform
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List


def _load_config_delivery(config_path: Path) -> Any:
    """Load config and return its delivery section."""
    from paper_agent.core.config import load_config

    config = load_config(config_path)
    return config.delivery


def _iter_paper_json_files(library_dir: Path) -> Iterable[Path]:
    """Yield all per-paper JSON files under library_dir/YYYY-MM-DD/*.json, newest first."""
    if not library_dir.exists():
        return []
    dated_dirs = [p for p in library_dir.iterdir() if p.is_dir()]
    for day_dir in sorted(dated_dirs, key=lambda p: p.name, reverse=True):
        json_files = sorted(day_dir.glob("*.json"), key=lambda p: p.name, reverse=True)
        for jf in json_files:
            yield jf


def _read_json_safely(path: Path) -> Any | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _open_with_default_app(path: Path) -> int:
    """Open path with the OS default application."""
    system = platform.system()
    try:
        if system == "Darwin":
            return subprocess.call(["open", str(path)])
        if system == "Windows":
            # Use start via cmd to respect default associations.
            return subprocess.call(["cmd", "/c", "start", "", str(path)])
        return subprocess.call(["xdg-open", str(path)])
    except Exception as e:
        print(f"Failed to open {path}: {e}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper Intelligence Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Run the pipeline once")
    run_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: config.yaml)",
    )

    today_parser = sub.add_parser(
        "today", help="Return today's papers from local outputs"
    )
    today_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: config.yaml)",
    )
    today_parser.add_argument(
        "--json",
        action="store_true",
        help="Return today's entries as JSON (recommended for automation)",
    )

    list_parser = sub.add_parser(
        "list", help="List recent papers from local outputs"
    )
    list_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: config.yaml)",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Return entries as JSON (recommended for automation)",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of papers to return",
    )

    open_parser = sub.add_parser(
        "open", help="Open the local note for a given paper id"
    )
    open_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: config.yaml)",
    )
    open_parser.add_argument(
        "paper_id",
        help="Paper id or filename stem (e.g. 2403.00003)",
    )

    args = parser.parse_args()

    if args.command == "run":
        config_path = args.config
        if not config_path.exists():
            print(f"Config not found: {config_path}", file=sys.stderr)
            print("Copy config.example.yaml to config.yaml and edit.", file=sys.stderr)
            sys.exit(1)
        from paper_agent.run import run

        try:
            processed = run(config_path)
            print(f"Processed {len(processed)} new paper(s).")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "today":
        config_path = args.config
        if not config_path.exists():
            print(f"Config not found: {config_path}", file=sys.stderr)
            print("Copy config.example.yaml to config.yaml and edit.", file=sys.stderr)
            sys.exit(1)

        delivery = _load_config_delivery(config_path)
        library_dir = Path(delivery.library_dir)
        today = date.today().isoformat()
        day_dir = library_dir / today

        entries: List[Any] = []
        if day_dir.exists():
            for json_path in sorted(day_dir.glob("*.json"), key=lambda p: p.name):
                data = _read_json_safely(json_path)
                if data is not None:
                    entries.append(data)

        if args.json:
            json.dump(entries, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"{len(entries)} paper(s) for {today}")

    elif args.command == "list":
        config_path = args.config
        if not config_path.exists():
            print(f"Config not found: {config_path}", file=sys.stderr)
            print("Copy config.example.yaml to config.yaml and edit.", file=sys.stderr)
            sys.exit(1)

        delivery = _load_config_delivery(config_path)
        library_dir = Path(delivery.library_dir)

        entries: List[Any] = []
        limit = args.limit if args.limit is not None and args.limit > 0 else None

        for json_path in _iter_paper_json_files(library_dir):
            data = _read_json_safely(json_path)
            if data is None:
                continue
            entries.append(data)
            if limit is not None and len(entries) >= limit:
                break

        if args.json:
            json.dump(entries, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"{len(entries)} paper(s) in local library")

    elif args.command == "open":
        config_path = args.config
        if not config_path.exists():
            print(f"Config not found: {config_path}", file=sys.stderr)
            print("Copy config.example.yaml to config.yaml and edit.", file=sys.stderr)
            sys.exit(1)

        delivery = _load_config_delivery(config_path)
        library_dir = Path(delivery.library_dir)
        paper_id = str(args.paper_id).strip()

        # First try: treat paper_id as filename stem under any date directory.
        candidate_json = None
        pattern = f"{paper_id}.json"
        for day_dir in library_dir.iterdir() if library_dir.exists() else []:
            if not day_dir.is_dir():
                continue
            candidate = day_dir / pattern
            if candidate.exists():
                candidate_json = candidate
                break

        # Fallback: scan recent JSON files until a matching id is found.
        if candidate_json is None:
            for json_path in _iter_paper_json_files(library_dir):
                data = _read_json_safely(json_path)
                if not isinstance(data, dict):
                    continue
                if str(data.get("id", "")).strip() == paper_id:
                    candidate_json = json_path
                    break

        if candidate_json is None:
            print(f"No local note found for paper id: {paper_id}", file=sys.stderr)
            sys.exit(1)

        note_path = candidate_json.with_suffix(".md")
        if not note_path.exists():
            print(f"Markdown note not found next to JSON: {note_path}", file=sys.stderr)
            sys.exit(1)

        rc = _open_with_default_app(note_path)
        if rc != 0:
            sys.exit(rc)


if __name__ == "__main__":
    main()
