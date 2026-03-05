"""
Run logging: configures logger that writes to logs_dir/latest.log.
"""

import logging
from pathlib import Path


def setup_run_logging(logs_dir: str | Path) -> logging.Logger:
    """
    Configure and return logger that writes to logs_dir/latest.log.

    Idempotent across multiple calls in the same process: if a FileHandler
    is already attached for a previous run, it is removed so that the new
    call always targets the provided logs_dir. This makes repeated runs
    (and tests using tmp_path) write to the correct per-run directory.
    """
    logs_dir = Path(logs_dir)
    log_path = logs_dir / "latest.log"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("paper_agent.run")
    logger.setLevel(logging.INFO)

    # Remove any existing FileHandlers so we can safely point to a new logs_dir.
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)

    return logger
