"""
Load and validate config from YAML. Fail fast with clear errors.

Schema and default values are aligned with config.example.yaml:
- direction: max_papers_per_day=15, lookback_days=3
- policy.type: "linucb"
- sources.scholar_alerts: mode=email, email.provider (mbox/eml_dir/gmail/imap), light_filter, ordering=arrival only.
- Scholar Inbox never counts toward max_papers_per_day and never participates in exploration/diversity (hardcoded).
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

    max_papers_per_day: int = Field(default=15, ge=1, le=500, description="Cap papers per run")
    lookback_days: int = Field(default=3, ge=1, le=31, description="Days back to consider for catch-up")
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
    max_message_chars: int = Field(default=10000, ge=100, le=50000)
    show_brief_summary: bool = True


class DeliveryConfig(BaseModel):
    """Delivery and output directories."""

    slack: SlackConfig = Field(default_factory=SlackConfig)
    library_dir: str = "./library"
    daily_dir: str = "./daily"
    state_dir: str = "./state"
    logs_dir: str = "./logs"


class SummarizeConfig(BaseModel):
    """Summarization options (provider/model; brief one-liner + research notes)."""

    enabled: bool = True
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    brief_summary: bool = True
    brief_one_liner_enabled: bool = True
    # Language for LLM-generated content in notes/Slack (“en”, “zh”, etc.).
    language: str = "en"
    # Whether to generate a research-focused structured summary for local notes.
    research_summary_enabled: bool = True


class PromptsConfig(BaseModel):
    """Optional prompt overrides for advanced users."""

    research_summary_template: str = ""


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


class AutotuneRewardSignalsConfig(BaseModel):
    """Weights for per-paper feedback signals used by AutoTune."""

    click: float = 0.2
    open_note: float = 0.5
    star: float = 1.0
    export: float = 1.5
    skip: float = -0.05
    mute: float = -2.0


class AutotuneRewardDiversityConfig(BaseModel):
    """Weights for diversity and novelty components in AutoTune reward."""

    num_topics: float = 0.1
    exploration_picks: float = 0.05
    avg_novelty: float = 0.2


class AutotuneRewardConfig(BaseModel):
    """Reward shaping configuration for AutoTune."""

    signals: AutotuneRewardSignalsConfig = Field(default_factory=AutotuneRewardSignalsConfig)
    diversity: AutotuneRewardDiversityConfig = Field(default_factory=AutotuneRewardDiversityConfig)


class AutotuneGuardrailsConfig(BaseModel):
    """Guardrails and rollback rules for AutoTune."""

    max_daily_delta_reward: float = -5.0
    rollback_days: int = Field(default=3, ge=1, le=30)
    allowed_ranges: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {
            "alpha": (0.0, 5.0),
            "lambda_ucb": (0.0, 5.0),
            "mu_novelty": (0.0, 5.0),
            "ridge": (0.01, 100.0),
        }
    )


class AutotuneCandidateConfig(BaseModel):
    """Discrete candidate for AutoTune to choose from."""

    id: str
    alpha: float
    lambda_ucb: float
    mu_novelty: float
    ridge: float


class AutotuneScheduleConfig(BaseModel):
    """Scheduling configuration for AutoTune updates."""

    daily_hour_utc: int = Field(default=23, ge=0, le=23)
    weekly_day_of_week: str = Field(
        default="sun", description="Three-letter lowercase day name: mon..sun"
    )

    @field_validator("weekly_day_of_week")
    @classmethod
    def validate_day(cls, v: str) -> str:
        allowed = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        v_norm = v.lower()
        if v_norm not in allowed:
            raise ValueError(f"weekly_day_of_week must be one of {sorted(allowed)}")
        return v_norm


class AutotuneConfig(BaseModel):
    """AutoTune meta-controller configuration."""

    enabled: bool = False
    method: str = Field(default="thompson", description="'thompson' or 'off'")
    schedule: AutotuneScheduleConfig = Field(default_factory=AutotuneScheduleConfig)
    candidates: list[AutotuneCandidateConfig] = Field(default_factory=list)
    reward: AutotuneRewardConfig = Field(default_factory=AutotuneRewardConfig)
    guardrails: AutotuneGuardrailsConfig = Field(default_factory=AutotuneGuardrailsConfig)
    random_seed: int | None = Field(
        default=None,
        description="Optional fixed seed for AutoTune randomness (Thompson Sampling).",
    )


class ArxivSourceConfig(BaseModel):
    """arXiv source (v0.1)."""

    enabled: bool = True


class ScholarAlertsLightFilterConfig(BaseModel):
    """Light, source-local filters for Scholar Inbox items."""

    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    exclude_authors: list[str] = Field(default_factory=list)


class ScholarAlertsEmailConfig(BaseModel):
    """Email ingestion: mbox, eml_dir, gmail, or imap. No RSS."""

    provider: str = Field(
        default="mbox",
        description="One of: mbox, eml_dir, gmail, imap.",
    )
    gmail_label: str = Field(
        default="scholar-alerts",
        description="Mailbox/label to select for Gmail IMAP; typically a Gmail label such as 'scholar-alerts'.",
    )
    imap_host: str = Field(default="", description="IMAP host (e.g. imap.gmail.com) when provider=imap.")
    imap_user: str = Field(default="", description="IMAP user/email when provider=imap.")
    imap_password_env: str = Field(
        default="IMAP_PASSWORD",
        description="Env var name for IMAP password (never put password in config).",
    )
    mbox_path: str = Field(default="", description="Path to exported .mbox when provider=mbox.")
    eml_dir: str = Field(default="", description="Directory of .eml files when provider=eml_dir.")
    from_addresses: list[str] = Field(
        default_factory=lambda: ["scholaralerts-noreply@google.com"],
        description="Optional filter: only process messages from these addresses; empty = no filter.",
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"mbox", "eml_dir", "gmail", "imap"}
        v_norm = v.lower().strip()
        if v_norm not in allowed:
            raise ValueError(f"sources.scholar_alerts.email.provider must be one of {sorted(allowed)}")
        return v_norm


class ScholarAlertsSourceConfig(BaseModel):
    """Google Scholar Alerts Inbox: email only (no RSS; no crawling). Never counts toward max_papers_per_day; no bandit constraints."""

    enabled: bool = False
    mode: str = Field(default="email", description="Only 'email' is implemented for Scholar Alerts.")
    email: ScholarAlertsEmailConfig = Field(
        default_factory=ScholarAlertsEmailConfig,
        description="Email source settings: provider, paths, IMAP, from_addresses.",
    )
    max_items_per_run: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Cap on Scholar Inbox items processed per run.",
    )
    push_to_slack: bool = True
    light_filter: ScholarAlertsLightFilterConfig = Field(
        default_factory=ScholarAlertsLightFilterConfig,
        description="Light filters applied only to Scholar Inbox items.",
    )
    ordering: str = Field(
        default="arrival",
        description="Only 'arrival' (email received time) for email inbox semantics.",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v.lower() != "email":
            raise ValueError("sources.scholar_alerts.mode must be 'email' (only email is implemented).")
        return "email"

    @field_validator("ordering")
    @classmethod
    def validate_ordering(cls, v: str) -> str:
        if v.lower() != "arrival":
            raise ValueError("sources.scholar_alerts.ordering must be 'arrival' for email inbox.")
        return "arrival"


class SourcesConfig(BaseModel):
    """Sources: arxiv + scholar_alerts (Scholar Inbox via email only; no crawling)."""

    arxiv: ArxivSourceConfig = Field(default_factory=ArxivSourceConfig)
    scholar_alerts: ScholarAlertsSourceConfig = Field(default_factory=ScholarAlertsSourceConfig)


class FeedbackConfig(BaseModel):
    """Feedback: blocked/boosted phrases and authors (used by deterministic policy)."""

    blocked_phrases: list[str] = Field(default_factory=list, description="Phrases to exclude (strong negative)")
    blocked_authors: list[str] = Field(default_factory=list, description="Author substrings to exclude")
    boosted_phrases: list[str] = Field(default_factory=list, description="Phrases that boost relevance")


class SelectionConfig(BaseModel):
    """Selection: exploration quota and diversity constraints (agent logic)."""

    explore_ratio: float = Field(default=0.2, ge=0.0, le=1.0, description="Epsilon: fraction of K for exploration")
    topic_cap: int = Field(default=3, ge=1, le=20, description="Max papers per topic per day")
    min_topics: int = Field(default=1, ge=1, le=20, description="Minimum distinct topics per day")


class PolicyConfig(BaseModel):
    """Policy: deterministic or LinUCB; UCB/novelty weights for bandit."""

    type: str = Field(default="linucb", description="Policy: 'deterministic' or 'linucb'")
    alpha: float = Field(default=0.5, ge=0.0, le=5.0, description="LinUCB uncertainty scale")
    lambda_ucb: float = Field(default=1.0, ge=0.0, le=5.0, description="Weight for uncertainty in selection score")
    mu_novelty: float = Field(default=0.3, ge=0.0, le=5.0, description="Weight for novelty in selection score")
    ridge: float = Field(default=1.0, ge=0.01, le=100.0, description="Ridge regularization for LinUCB")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"deterministic", "linucb"}
        if v.lower() not in allowed:
            raise ValueError(f"policy.type must be one of {allowed}")
        return v.lower()


class Config(BaseModel):
    """Root config; single source of truth for user-customizable behavior.
    All dates (paths, digest, run date) use system local time; no timezone config."""

    interests: InterestsConfig = Field(default_factory=InterestsConfig)
    direction: DirectionConfig = Field(default_factory=DirectionConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    summarize: SummarizeConfig = Field(default_factory=SummarizeConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    autotune: AutotuneConfig = Field(default_factory=AutotuneConfig)


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
