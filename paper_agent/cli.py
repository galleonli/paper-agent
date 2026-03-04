"""
CLI entrypoint: python -m paper_agent run [--config path]
"""

import argparse
import sys
from pathlib import Path


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


if __name__ == "__main__":
    main()
