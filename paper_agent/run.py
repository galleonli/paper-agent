"""
Entrypoint that delegates to pipeline. Kept for backward compatibility (CLI and tests).
"""

from pathlib import Path

from paper_agent.filter_papers import RankedPaper
from paper_agent.pipeline import run as _run


def run(config_path: str | Path) -> list[RankedPaper]:
    """Run the full pipeline. Delegates to pipeline.run()."""
    return _run(config_path)
