# Backward compatibility: re-export from core

from paper_agent.core.config import (
    Config,
    load_config,
    InterestsConfig,
    DirectionConfig,
    SlackConfig,
    DeliveryConfig,
    SummarizeConfig,
    ExportConfig,
    AdvancedConfig,
    ArxivSourceConfig,
    ScholarAlertsSourceConfig,
    SourcesConfig,
    FeedbackConfig,
    SelectionConfig,
    PolicyConfig,
)

__all__ = [
    "Config",
    "load_config",
    "InterestsConfig",
    "DirectionConfig",
    "SlackConfig",
    "DeliveryConfig",
    "SummarizeConfig",
    "ExportConfig",
    "AdvancedConfig",
    "ArxivSourceConfig",
    "ScholarAlertsSourceConfig",
    "SourcesConfig",
    "FeedbackConfig",
    "SelectionConfig",
    "PolicyConfig",
]
