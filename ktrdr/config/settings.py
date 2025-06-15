"""
KTRDR Settings Manager - Runtime configuration management.

This module provides access to configuration settings with environment-specific
overrides and environment variable support.
"""

from pydantic import BaseSettings, Field, ConfigDict
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


# Cache settings to avoid repeated disk/env access
@lru_cache()
def get_api_settings() -> APISettings:
    """Get API settings with caching."""
    return APISettings()


@lru_cache()
def get_logging_settings() -> LoggingSettings:
    """Get logging settings with caching."""
    return LoggingSettings()


# Clear settings cache (for testing)
def clear_settings_cache() -> None:
    """Clear settings cache."""
    get_api_settings.cache_clear()
    get_logging_settings.cache_clear()


# Export IB config for convenience
__all__ = [
    "APISettings",
    "LoggingSettings",
    "get_api_settings",
    "get_logging_settings",
    "clear_settings_cache",
    "IbConfig",
    "get_ib_config",
]
