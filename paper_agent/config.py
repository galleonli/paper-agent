"""
Load and validate config from YAML. Fail fast with clear errors.
Schema aligned with config.example.yaml.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class InterestsConfig(BaseModel):
    """Interest model: seeds, keyphrases, negative_keyphrases."""

    seeds: list[str] = Field(default_factory=list, description="Paper URLs/IDs that define your taste")
    keyphrases: list[str] = Field(default_factory=list, description="Phrases that align with your interests")
    negative_keyphrases: list[str] = Field(default_factory=list, description="Phrases that exclude papers")


class DirectionConfig(BaseModel):
    """Direction constraints: categories, queries, keywords, limits."""

    max_papers_per_day: int = Field(ge=1, le=500, description="Cap papers per run")
    lookback_days: int = Field(ge=1, le=31, description="Days back to consider for catch-up")
    allow_categories: list[str] = Field(default_factory=list, description="arXiv categories to include")
    deny_categories: list[str] = Field(default_factory=list, description="Categories to exclude")
    queries: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    exclude_authors: list[str] = Field(default_factory=list)


class SlackConfig(BaseModel):
    """Slack delivery options."""

    enabled: bool = False
    webhook_url: str = Field(default="", description="Set in config or env; never commit real URL")
    max_message_chars: int = Field(default=4000, ge=100, le=50000)
    show_brief_summary: bool = True
    show_full_summary: bool = False


class DeliveryConfig(BaseModel):
    """Delivery and output directories."""

    slack: SlackConfig = Field(default_factory=SlackConfig)
    library_dir: str = "./library"
    daily_dir: str = "./daily"
    state_dir: str = "./state"
    logs_dir: str = "./logs"


class SummarizeConfig(BaseModel):
    """Summarization options (provider/model; brief_one_liner for Slack)."""

    enabled: bool = True
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    brief_summary: bool = True
    brief_one_liner_enabled: bool = True


class ExportConfig(BaseModel):
    """Reference export formats (BibTeX, RIS, EndNote-compatible)."""

    formats: list[str] = Field(default_factory=lambda: ["bibtex", "ris"])

    @field_validator("formats")
    @classmethod
    def validate_formats(cls, v: list[str]) -> list[str]:
        allowed = {"bibtex", "ris"}
        for f in v:
            if f.lower() not in allowed:
                raise ValueError(f"Unknown export format: {f}. Allowed: {allowed}")
        return [x.lower() for x in v]


class AdvancedConfig(BaseModel):
    """Advanced: timeouts, retries, API limits."""

    request_timeout_seconds: int = Field(default=30, ge=5, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    max_results_per_query: int = Field(default=100, ge=1, le=500)


class ArxivSourceConfig(BaseModel):
    """arXiv source (v0.1)."""

    enabled: bool = True


class ScholarAlertsSourceConfig(BaseModel):
    """Google Scholar alerts inbox (v0.2 placeholder; no scraping implemented)."""

    enabled: bool = False
    input: str = "rss"
    rss_urls: list[str] = Field(default_factory=list)


class SourcesConfig(BaseModel):
    """Sources: arxiv + placeholder for scholar_alerts."""

    arxiv: ArxivSourceConfig = Field(default_factory=ArxivSourceConfig)
    scholar_alerts: ScholarAlertsSourceConfig = Field(default_factory=ScholarAlertsSourceConfig)


class Config(BaseModel):
    """Root config; single source of truth for user-customizable behavior."""

    timezone: str = "UTC"
    interests: InterestsConfig = Field(default_factory=InterestsConfig)
    direction: DirectionConfig = Field(default_factory=DirectionConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    summarize: SummarizeConfig = Field(default_factory=SummarizeConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)


def load_config(path: str | Path) -> Config:
    """
    Load YAML from path and validate. Raises with clear message on missing keys or invalid types.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config: {e}") from e

    if raw is None:
        raise ValueError("Config file is empty or invalid YAML")

    try:
        return Config.model_validate(raw)
    except Exception as e:
        # Pydantic gives field paths; re-raise with hint
        raise ValueError(f"Invalid config: {e}") from e
