"""
Common data models for papers (used by fetch, filter, output).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Paper:
    """A single paper; normalized ID and metadata from source (e.g. arXiv)."""

    id: str  # Canonical ID (e.g. 2301.12345)
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    updated: str  # ISO date or raw string from source
    link_abs: str  # Abstract page URL
    link_pdf: Optional[str] = None
