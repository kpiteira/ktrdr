"""
KTRDR Settings Manager - Runtime configuration management.

This module provides access to configuration settings with environment-specific
overrides and environment variable support.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .. import metadata
from .host_services import (
    ApiServiceSettings,
    get_api_service_settings,
)
from .ib_config import IbConfig, get_ib_config


class APISettings(BaseSettings):
    """API Server Settings."""

    title: str = Field(default=metadata.API_TITLE)
    description: str = Field(default=metadata.API_DESCRIPTION)
    version: str = Field(default=metadata.VERSION)
    host: str = Field(default=metadata.get("api.host", "127.0.0.1"))
    port: int = Field(default=metadata.get("api.port", 8000))
    reload: bool = Field(default=metadata.get("api.reload", True))
    log_level: str = Field(default=metadata.get("api.log_level", "INFO"))
    api_prefix: str = Field(default=metadata.API_PREFIX)
    cors_origins: list = Field(default=metadata.get("api.cors_origins", ["*"]))

    model_config = SettingsConfigDict(env_prefix="KTRDR_API_")


class LoggingSettings(BaseSettings):
    """Logging Settings."""

    level: str = Field(default=metadata.get("logging.level", "INFO"))
    format: str = Field(
        default=metadata.get(
            "logging.format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    )

    model_config = SettingsConfigDict(env_prefix="KTRDR_LOGGING_")


class OrphanDetectorSettings(BaseSettings):
    """Orphan Detector Settings.

    Configures the background orphan detection service that identifies
    RUNNING operations with no worker and marks them as FAILED.

    Environment variables:
        ORPHAN_TIMEOUT_SECONDS: Time (seconds) before an unclaimed operation
            is marked as orphaned. Default: 60
        ORPHAN_CHECK_INTERVAL_SECONDS: How often (seconds) to check for
            orphaned operations. Default: 15
    """

    timeout_seconds: int = Field(
        default=60,
        gt=0,
        description="Time in seconds before an unclaimed operation is marked FAILED",
    )
    check_interval_seconds: int = Field(
        default=15,
        gt=0,
        description="Interval in seconds between orphan detection checks",
    )

    model_config = SettingsConfigDict(env_prefix="ORPHAN_")


class CheckpointSettings(BaseSettings):
    """Checkpoint Settings.

    Configures checkpoint saving for long-running operations like training.
    Settings control checkpoint frequency and storage location.

    Environment variables:
        CHECKPOINT_EPOCH_INTERVAL: Save checkpoint every N epochs. Default: 10
        CHECKPOINT_TIME_INTERVAL_SECONDS: Save checkpoint every M seconds. Default: 300
        CHECKPOINT_DIR: Directory for checkpoint artifacts. Default: /app/data/checkpoints
        CHECKPOINT_MAX_AGE_DAYS: Auto-cleanup checkpoints older than N days. Default: 30
    """

    epoch_interval: int = Field(
        default=10,
        gt=0,
        description="Save checkpoint every N epochs/units",
    )
    time_interval_seconds: int = Field(
        default=300,
        gt=0,
        description="Save checkpoint every M seconds",
    )
    dir: str = Field(
        default="/app/data/checkpoints",
        description="Directory for checkpoint artifact storage",
    )
    max_age_days: int = Field(
        default=30,
        gt=0,
        description="Auto-cleanup checkpoints older than N days",
    )

    model_config = SettingsConfigDict(env_prefix="CHECKPOINT_")


# Cache settings to avoid repeated disk/env access
@lru_cache
def get_api_settings() -> APISettings:
    """Get API settings with caching."""
    return APISettings()


@lru_cache
def get_logging_settings() -> LoggingSettings:
    """Get logging settings with caching."""
    return LoggingSettings()


@lru_cache
def get_orphan_detector_settings() -> OrphanDetectorSettings:
    """Get orphan detector settings with caching."""
    return OrphanDetectorSettings()


@lru_cache
def get_checkpoint_settings() -> CheckpointSettings:
    """Get checkpoint settings with caching."""
    return CheckpointSettings()


# Compatibility aliases for existing code
CLISettings = ApiServiceSettings  # CLI uses API service settings for client connections


def get_cli_settings() -> ApiServiceSettings:
    """Get CLI client settings with caching (compatibility alias)."""
    return get_api_service_settings()


# Clear settings cache (for testing)
def clear_settings_cache() -> None:
    """Clear settings cache."""
    get_api_settings.cache_clear()
    get_logging_settings.cache_clear()
    get_api_service_settings.cache_clear()
    get_orphan_detector_settings.cache_clear()
    get_checkpoint_settings.cache_clear()


# Export IB config for convenience
__all__ = [
    "APISettings",
    "LoggingSettings",
    "OrphanDetectorSettings",
    "CheckpointSettings",
    "ApiServiceSettings",
    "get_api_settings",
    "get_logging_settings",
    "get_orphan_detector_settings",
    "get_checkpoint_settings",
    "get_api_service_settings",
    "clear_settings_cache",
    # Compatibility aliases
    "CLISettings",
    "get_cli_settings",
    "IbConfig",
    "get_ib_config",
]
