"""
Run logging: configures logger that writes to logs_dir/latest.log.
"""

import logging
from pathlib import Path


def setup_run_logging(logs_dir: str | Path) -> logging.Logger:
    """Configure and return logger that writes to logs_dir/latest.log."""
    log_path = Path(logs_dir) / "latest.log"
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("paper_agent.run")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    return logger
