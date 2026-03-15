"""
CLI entrypoint: python -m paper_agent run [--config path]
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List


@dataclass
class DiagnosticFinding:
    severity: str
    check_id: str
    category: str
    message: str
    remediation: str


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


def _path_is_writable(path: Path) -> bool:
    """
    Best-effort writability probe for existing directories.
    Uses a temporary file to avoid false positives on ACL-restricted paths.
    """
    if not path.exists() or not path.is_dir():
        return False
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".paper_agent_diag_", delete=True):
            return True
    except OSError:
        return False


def _run_diagnostics(config_path: Path) -> list[DiagnosticFinding]:
    """Run comprehensive diagnostics checks without early exit."""
    findings: list[DiagnosticFinding] = []

    def add(
        severity: str,
        check_id: str,
        category: str,
        message: str,
        remediation: str,
    ) -> None:
        findings.append(
            DiagnosticFinding(
                severity=severity,
                check_id=check_id,
                category=category,
                message=message,
                remediation=remediation,
            )
        )

    # Runtime checks
    py = sys.version_info
    if (py.major, py.minor) < (3, 10):
        add(
            "ERROR",
            "PYTHON_VERSION_TOO_LOW",
            "runtime",
            f"Detected Python {py.major}.{py.minor}; Paper Agent requires Python 3.10+.",
            "Use Python 3.10+ and re-create the virtual environment.",
        )
    else:
        add(
            "INFO",
            "PYTHON_VERSION_OK",
            "runtime",
            f"Python version is {py.major}.{py.minor}.",
            "No action needed.",
        )

    for module_name in ("yaml", "pydantic", "requests"):
        try:
            __import__(module_name)
            add(
                "INFO",
                f"DEPENDENCY_{module_name.upper()}_OK",
                "runtime",
                f"Dependency '{module_name}' is importable.",
                "No action needed.",
            )
        except Exception:
            add(
                "ERROR",
                f"DEPENDENCY_{module_name.upper()}_MISSING",
                "runtime",
                f"Dependency '{module_name}' cannot be imported.",
                "Install project dependencies (for example: pip install -r requirements.txt).",
            )

    # Config checks
    if not config_path.exists():
        add(
            "ERROR",
            "CONFIG_FILE_MISSING",
            "config",
            f"Config file not found: {config_path}",
            "Copy config.example.yaml to config.yaml (or pass --config with a valid path).",
        )
        add(
            "WARN",
            "CONFIG_DEPENDENT_CHECKS_SKIPPED",
            "config",
            "Config-dependent checks were skipped because config file is missing.",
            "Create a valid config file and rerun diagnostics.",
        )
        add(
            "WARN",
            "DEVELOPER_MAINTENANCE_REMINDER",
            "developer",
            "Developer reminder: keep this diagnostics command updated when adding new failure modes.",
            "When adding new features/sources, update diagnostics checks and tests in the same change.",
        )
        return findings

    from paper_agent.core.config import load_config

    config = None
    try:
        config = load_config(config_path)
        add(
            "INFO",
            "CONFIG_VALID",
            "config",
            f"Config is valid: {config_path}",
            "No action needed.",
        )
    except Exception as e:
        add(
            "ERROR",
            "CONFIG_INVALID",
            "config",
            f"Config validation failed: {e}",
            "Fix YAML/schema errors in config and rerun diagnostics.",
        )
        add(
            "WARN",
            "CONFIG_DEPENDENT_CHECKS_SKIPPED",
            "config",
            "Some checks were skipped because config is invalid.",
            "Fix config validation errors to enable full diagnostics coverage.",
        )

    if config is not None:
        # Delivery path checks
        for key, raw in (
            ("delivery.library_dir", config.delivery.library_dir),
            ("delivery.paper_dir", config.delivery.paper_dir),
            ("delivery.state_dir", config.delivery.state_dir),
            ("delivery.logs_dir", config.delivery.logs_dir),
        ):
            p = Path(raw)
            if p.exists() and not p.is_dir():
                add(
                    "ERROR",
                    "DELIVERY_PATH_NOT_DIRECTORY",
                    "filesystem",
                    f"{key} points to a file, not a directory: {p}",
                    f"Change {key} to a directory path in config.",
                )
                continue
            if p.exists() and p.is_dir():
                if _path_is_writable(p):
                    add(
                        "INFO",
                        "DELIVERY_PATH_WRITABLE",
                        "filesystem",
                        f"{key} exists and is writable: {p}",
                        "No action needed.",
                    )
                else:
                    add(
                        "ERROR",
                        "DELIVERY_PATH_NOT_WRITABLE",
                        "filesystem",
                        f"{key} exists but is not writable: {p}",
                        "Fix directory permissions so the current user can write to it.",
                    )
            else:
                parent = p.parent if p.parent != Path("") else Path(".")
                if parent.exists() and parent.is_dir() and _path_is_writable(parent):
                    add(
                        "WARN",
                        "DELIVERY_PATH_MISSING",
                        "filesystem",
                        f"{key} does not exist yet: {p}",
                        "This is usually fine. The run command creates directories automatically.",
                    )
                else:
                    add(
                        "ERROR",
                        "DELIVERY_PARENT_NOT_WRITABLE",
                        "filesystem",
                        f"{key} does not exist and parent is not writable: {parent}",
                        "Use a path under a writable directory or fix parent directory permissions.",
                    )

        # Summarization provider checks
        if config.summarize.enabled:
            provider = (config.summarize.provider or "").strip().lower()
            if provider == "openai":
                api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
                if api_key:
                    add(
                        "INFO",
                        "OPENAI_API_KEY_PRESENT",
                        "env",
                        "OPENAI_API_KEY is set for OpenAI summarization.",
                        "No action needed.",
                    )
                else:
                    add(
                        "WARN",
                        "OPENAI_API_KEY_MISSING",
                        "env",
                        "Summarization is enabled but OPENAI_API_KEY is not set.",
                        "Set OPENAI_API_KEY if you want LLM research summaries.",
                    )
            else:
                add(
                    "WARN",
                    "SUMMARIZE_PROVIDER_UNRECOGNIZED",
                    "config",
                    f"Summarization provider is '{config.summarize.provider}'.",
                    "Ensure the provider is supported by your summarization implementation.",
                )

        # arXiv query/category checks
        if config.sources.arxiv.enabled:
            if not config.direction.allow_categories and not config.direction.queries:
                add(
                    "WARN",
                    "ARXIV_SCOPE_BROAD",
                    "config",
                    "arXiv source is enabled with empty allow_categories and empty queries.",
                    "Set direction.allow_categories and/or direction.queries to narrow discovery scope.",
                )
            else:
                add(
                    "INFO",
                    "ARXIV_SCOPE_CONFIGURED",
                    "config",
                    "arXiv source scope appears configured.",
                    "No action needed.",
                )

        # Scholar Inbox checks
        scholar = config.sources.scholar_alerts
        if scholar.enabled:
            provider = (scholar.email.provider or "").lower().strip()
            if provider == "mbox":
                mbox_path_raw = (scholar.email.mbox_path or "").strip()
                if not mbox_path_raw:
                    add(
                        "ERROR",
                        "SCHOLAR_MBOX_PATH_MISSING",
                        "provider",
                        "Scholar provider is mbox but mbox_path is empty.",
                        "Set sources.scholar_alerts.email.mbox_path to a valid .mbox file.",
                    )
                else:
                    mbox_path = Path(mbox_path_raw)
                    if not mbox_path.is_file():
                        add(
                            "ERROR",
                            "SCHOLAR_MBOX_PATH_INVALID",
                            "provider",
                            f"Scholar mbox file not found: {mbox_path}",
                            "Set mbox_path to an existing .mbox file path.",
                        )
                    else:
                        add(
                            "INFO",
                            "SCHOLAR_MBOX_PATH_OK",
                            "provider",
                            f"Scholar mbox file found: {mbox_path}",
                            "No action needed.",
                        )
            elif provider == "eml_dir":
                eml_dir_raw = (scholar.email.eml_dir or "").strip()
                if not eml_dir_raw:
                    add(
                        "ERROR",
                        "SCHOLAR_EML_DIR_MISSING",
                        "provider",
                        "Scholar provider is eml_dir but eml_dir is empty.",
                        "Set sources.scholar_alerts.email.eml_dir to a valid directory.",
                    )
                else:
                    eml_dir = Path(eml_dir_raw)
                    if not eml_dir.is_dir():
                        add(
                            "ERROR",
                            "SCHOLAR_EML_DIR_INVALID",
                            "provider",
                            f"Scholar eml_dir not found: {eml_dir}",
                            "Set eml_dir to an existing directory containing .eml files.",
                        )
                    else:
                        eml_count = len(list(eml_dir.glob("*.eml")))
                        if eml_count == 0:
                            add(
                                "WARN",
                                "SCHOLAR_EML_DIR_EMPTY",
                                "provider",
                                f"Scholar eml_dir exists but contains no .eml files: {eml_dir}",
                                "Add alert emails or switch provider if using IMAP/Gmail.",
                            )
                        else:
                            add(
                                "INFO",
                                "SCHOLAR_EML_DIR_OK",
                                "provider",
                                f"Scholar eml_dir contains {eml_count} .eml file(s): {eml_dir}",
                                "No action needed.",
                            )
            elif provider in ("imap", "gmail"):
                host = (scholar.email.imap_host or "").strip()
                user = (scholar.email.imap_user or "").strip()
                pw_env = (scholar.email.imap_password_env or "").strip()
                password = (os.getenv(pw_env) or "").strip() if pw_env else ""
                if not host:
                    add(
                        "ERROR",
                        "SCHOLAR_IMAP_HOST_MISSING",
                        "provider",
                        "Scholar IMAP/Gmail provider requires imap_host.",
                        "Set sources.scholar_alerts.email.imap_host (for example imap.gmail.com).",
                    )
                if not user:
                    add(
                        "ERROR",
                        "SCHOLAR_IMAP_USER_MISSING",
                        "provider",
                        "Scholar IMAP/Gmail provider requires imap_user.",
                        "Set sources.scholar_alerts.email.imap_user to your mailbox account.",
                    )
                if not pw_env:
                    add(
                        "ERROR",
                        "SCHOLAR_IMAP_PASSWORD_ENV_MISSING",
                        "provider",
                        "Scholar IMAP/Gmail provider requires imap_password_env.",
                        "Set sources.scholar_alerts.email.imap_password_env.",
                    )
                elif not password:
                    add(
                        "ERROR",
                        "SCHOLAR_IMAP_PASSWORD_NOT_SET",
                        "provider",
                        f"Environment variable {pw_env} is not set.",
                        f"Export {pw_env} in your shell/session before running.",
                    )
                if host and user and pw_env and password:
                    add(
                        "INFO",
                        "SCHOLAR_IMAP_CREDENTIALS_PRESENT",
                        "provider",
                        "Scholar IMAP/Gmail credentials look present.",
                        "No action needed.",
                    )

        # Legacy mode check
        if config.policy.type in ("deterministic", "linucb"):
            add(
                "WARN",
                "LEGACY_POLICY_TYPE",
                "config",
                f"policy.type='{config.policy.type}' is legacy and not active in the default pipeline.",
                "Prefer policy.type='off' unless you are testing compatibility behavior.",
            )

    add(
        "WARN",
        "DEVELOPER_MAINTENANCE_REMINDER",
        "developer",
        "Developer reminder: keep this diagnostics command updated when adding new failure modes.",
        "When adding new features/sources, update diagnostics checks and tests in the same change.",
    )
    return findings


def _emit_diagnostics_text(findings: list[DiagnosticFinding]) -> None:
    severity_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    ordered = sorted(
        findings,
        key=lambda f: (severity_order.get(f.severity, 99), f.category, f.check_id),
    )
    for f in ordered:
        print(
            f"[{f.severity}] {f.check_id} ({f.category})\n"
            f"  - {f.message}\n"
            f"  - Fix: {f.remediation}"
        )
    errors = sum(1 for f in findings if f.severity == "ERROR")
    warns = sum(1 for f in findings if f.severity == "WARN")
    infos = sum(1 for f in findings if f.severity == "INFO")
    status = "FAILED" if errors > 0 else "PASSED_WITH_WARNINGS" if warns > 0 else "PASSED"
    print(
        f"\nDiagnostics status: {status} | "
        f"errors={errors}, warnings={warns}, infos={infos}, total={len(findings)}"
    )


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

    diag_parser = sub.add_parser(
        "diagnostics",
        help="Run comprehensive diagnostics and report all findings",
    )
    diag_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: config.yaml)",
    )
    diag_parser.add_argument(
        "--json",
        action="store_true",
        help="Return diagnostics findings as JSON",
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

    elif args.command == "diagnostics":
        findings = _run_diagnostics(args.config)
        if args.json:
            json.dump(
                [
                    {
                        "severity": f.severity,
                        "check_id": f.check_id,
                        "category": f.category,
                        "message": f.message,
                        "remediation": f.remediation,
                    }
                    for f in findings
                ],
                sys.stdout,
                indent=2,
            )
            sys.stdout.write("\n")
        else:
            _emit_diagnostics_text(findings)
        if any(f.severity == "ERROR" for f in findings):
            sys.exit(1)


if __name__ == "__main__":
    main()
