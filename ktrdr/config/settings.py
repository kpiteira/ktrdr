"""
KTRDR Settings Manager - Runtime configuration management.

This module provides access to configuration settings with environment-specific
overrides and environment variable support.
"""

from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache
from .. import metadata
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

    model_config = ConfigDict(env_prefix="KTRDR_API_")


class LoggingSettings(BaseSettings):
    """Logging Settings."""

    level: str = Field(default=metadata.get("logging.level", "INFO"))
    format: str = Field(
        default=metadata.get(
            "logging.format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    )

    model_config = ConfigDict(env_prefix="KTRDR_LOGGING_")


class TrainingHostSettings(BaseSettings):
    """Training Host Service Settings."""

    enabled: bool = Field(
        default=metadata.get("training_host.enabled", False),
        alias="USE_TRAINING_HOST_SERVICE",
    )
    base_url: str = Field(
        default=metadata.get("training_host.base_url", "http://localhost:5002"),
        alias="TRAINING_HOST_SERVICE_URL",
    )
    timeout: float = Field(default=metadata.get("training_host.timeout", 30.0))
    health_check_interval: float = Field(
        default=metadata.get("training_host.health_check_interval", 10.0)
    )
    max_retries: int = Field(default=metadata.get("training_host.max_retries", 3))
    retry_delay: float = Field(default=metadata.get("training_host.retry_delay", 1.0))
    progress_poll_interval: float = Field(
        default=metadata.get("training_host.progress_poll_interval", 2.0)
    )
    session_timeout: float = Field(
        default=metadata.get("training_host.session_timeout", 3600.0)
    )

    model_config = ConfigDict(env_prefix="KTRDR_TRAINING_HOST_")


class CLISettings(BaseSettings):
    """CLI Client Settings."""

    api_base_url: str = Field(
        default="http://localhost:8000", description="Base URL for API client"
    )
    timeout: float = Field(default=30.0, description="Default timeout for API requests")
    max_retries: int = Field(
        default=3, description="Maximum retry attempts for failed requests"
    )
    retry_delay: float = Field(default=1.0, description="Delay between retry attempts")

    model_config = ConfigDict(env_prefix="KTRDR_CLI_")

    @property
    def base_url(self) -> str:
        """Get base URL (alias for api_base_url)."""
        return self.api_base_url


# Cache settings to avoid repeated disk/env access
@lru_cache()
def get_api_settings() -> APISettings:
    """Get API settings with caching."""
    return APISettings()


@lru_cache()
def get_logging_settings() -> LoggingSettings:
    """Get logging settings with caching."""
    return LoggingSettings()


@lru_cache()
def get_training_host_settings() -> TrainingHostSettings:
    """Get training host service settings with caching."""
    return TrainingHostSettings()


@lru_cache()
def get_cli_settings() -> CLISettings:
    """Get CLI client settings with caching."""
    return CLISettings()


# Clear settings cache (for testing)
def clear_settings_cache() -> None:
    """Clear settings cache."""
    get_api_settings.cache_clear()
    get_logging_settings.cache_clear()
    get_training_host_settings.cache_clear()
    get_cli_settings.cache_clear()


# Export IB config for convenience
__all__ = [
    "APISettings",
    "LoggingSettings",
    "TrainingHostSettings",
    "CLISettings",
    "get_api_settings",
    "get_logging_settings",
    "get_training_host_settings",
    "get_cli_settings",
    "clear_settings_cache",
    "IbConfig",
    "get_ib_config",
]
