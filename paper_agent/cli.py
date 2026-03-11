"""
CLI entrypoint: python -m paper_agent run [--config path]
"""

import argparse
import json
import platform
import re
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


def _safe_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_safe_string(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


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

    search_parser = sub.add_parser(
        "search", help="Search recent papers from local outputs"
    )
    search_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: config.yaml)",
    )
    search_parser.add_argument(
        "--query",
        type=str,
        required=True,
        help='Search query (e.g. "continual learning")',
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        help="Return matched entries as JSON (recommended for automation)",
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

        if entries:
            def _sort_key(e: Any) -> str:
                if isinstance(e, dict):
                    published = str(e.get("published") or "")
                    date_str = str(e.get("date") or today)
                    return published or date_str
                return ""

            entries.sort(key=_sort_key, reverse=True)

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

        if entries:
            def _sort_key(e: Any) -> str:
                if isinstance(e, dict):
                    published = str(e.get("published") or "")
                    date_str = str(e.get("date") or "")
                    return published or date_str
                return ""

            entries.sort(key=_sort_key, reverse=True)
            if limit is not None:
                entries = entries[:limit]

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

    elif args.command == "search":
        config_path = args.config
        if not config_path.exists():
            print(f"Config not found: {config_path}", file=sys.stderr)
            print("Copy config.example.yaml to config.yaml and edit.", file=sys.stderr)
            sys.exit(1)

        delivery = _load_config_delivery(config_path)
        library_dir = Path(delivery.library_dir)
        query_text = str(args.query or "").strip()

        # Load all paper JSON entries from library_dir/YYYY-MM-DD/*.json (newest first).
        entries: List[Any] = []
        for json_path in _iter_paper_json_files(library_dir):
            data = _read_json_safely(json_path)
            if data is not None:
                entries.append(data)

        # Normalize query into tokens, including short date pattern expansion (e.g. 2603.11 -> 2026-03-11).
        def _normalize_query_tokens(text: str) -> list[str]:
            tokens: list[str] = []
            for raw in text.strip().split():
                lower = raw.lower()
                m = re.match(r"^(\d{2})(\d{2})\.(\d{1,2})$", lower)
                if m:
                    year = f"20{m.group(1)}"
                    month = m.group(2)
                    day = m.group(3).zfill(2)
                    tokens.append(f"{year}-{month}-{day}")
                else:
                    tokens.append(lower)
            return tokens

        def _build_search_blob(e: Any) -> str:
            if not isinstance(e, dict):
                return ""
            parts = [
                _safe_string(e.get("title")),
                _safe_string(e.get("authors")),
                _safe_string(e.get("abstract")),
                _safe_string(e.get("categories")),
                _safe_string(e.get("id")),
                _safe_string(e.get("date")),
                _safe_string(e.get("published")),
            ]
            return " ".join(parts).lower()

        def _has_all_tokens(blob: str, tokens: list[str]) -> bool:
            if not tokens:
                return True
            return all(t in blob for t in tokens if t)

        def _score_entry(e: Any, tokens: list[str], full_query: str) -> int:
            if not isinstance(e, dict) or not tokens:
                return 0
            title = _safe_string(e.get("title")).lower()
            authors = _safe_string(e.get("authors")).lower()
            abstract = _safe_string(e.get("abstract")).lower()
            categories = _safe_string(e.get("categories")).lower()
            pid = _safe_string(e.get("id")).lower()
            date_str = _safe_string(e.get("date")).lower()
            published = _safe_string(e.get("published")).lower()

            score = 0
            for t in tokens:
                if not t:
                    continue
                if t in title or t in authors:
                    score += 4
                elif t in abstract:
                    score += 2
                elif t in categories:
                    score += 1
                elif t in pid or t in date_str or t in published:
                    score += 1

            phrase = full_query.lower()
            if phrase:
                if phrase in title or phrase in authors:
                    score += 10
                elif phrase in abstract:
                    score += 5
                elif phrase in categories:
                    score += 2
            return score

        def _date_key(e: Any) -> str:
            if not isinstance(e, dict):
                return ""
            published = _safe_string(e.get("published"))
            date_str = _safe_string(e.get("date"))
            return published or date_str

        tokens = _normalize_query_tokens(query_text)
        full_query = " ".join(tokens)

        if not tokens:
            # No query tokens: just sort by date key descending (same as list).
            entries.sort(key=_date_key, reverse=True)
            results = entries
        else:
            results_scored: list[tuple[Any, int]] = []
            for e in entries:
                blob = _build_search_blob(e)
                if not _has_all_tokens(blob, tokens):
                    continue
                score = _score_entry(e, tokens, full_query)
                if score > 0:
                    results_scored.append((e, score))
            results_scored.sort(
                key=lambda pair: (pair[1], _date_key(pair[0])), reverse=True
            )
            results = [e for (e, _score) in results_scored]

        if args.json:
            json.dump(results, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"{len(results)} paper(s) matched query")  # pragma: no cover


if __name__ == "__main__":
    main()
