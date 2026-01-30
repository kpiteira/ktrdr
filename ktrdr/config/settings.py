"""
KTRDR Settings Manager - Runtime configuration management.

This module provides access to configuration settings with environment-specific
overrides and environment variable support.
"""

from functools import lru_cache
from typing import Any, TypeVar
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .. import metadata
from .host_services import (
    ApiServiceSettings,
    get_api_service_settings,
)
from .ib_config import IbConfig, get_ib_config

T = TypeVar("T")


def deprecated_field(default: T, new_env: str, old_env: str, **kwargs: Any) -> T:
    """Create a field with both new and deprecated env var names.

    CRITICAL: When validation_alias is set, env_prefix is completely ignored
    for that field. The new_env name MUST be the full prefixed name (e.g.,
    KTRDR_DB_HOST, not just HOST).

    The new name is listed first in AliasChoices so it takes precedence.

    Args:
        default: The default value for the field.
        new_env: The new (preferred) env var name (e.g., KTRDR_DB_HOST).
        old_env: The deprecated env var name (e.g., DB_HOST).
        **kwargs: Additional kwargs passed to Field().

    Returns:
        A Pydantic FieldInfo configured with AliasChoices for both names.
        TypeVar ensures return type matches the default's type for mypy.
    """
    return Field(
        default=default,
        validation_alias=AliasChoices(new_env, old_env),
        **kwargs,
    )


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


class DatabaseSettings(BaseSettings):
    """Database connection settings.

    Provides PostgreSQL connection configuration with support for both
    new (KTRDR_DB_*) and deprecated (DB_*) environment variable names.

    Environment variables (new names - preferred):
        KTRDR_DB_HOST: Database host. Default: localhost
        KTRDR_DB_PORT: Database port. Default: 5432
        KTRDR_DB_NAME: Database name. Default: ktrdr
        KTRDR_DB_USER: Database user. Default: ktrdr
        KTRDR_DB_PASSWORD: Database password. Default: localdev (insecure)
        KTRDR_DB_ECHO: Enable SQLAlchemy echo mode. Default: false

    Deprecated names (still work, emit warnings at startup):
        DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_ECHO
    """

    host: str = deprecated_field("localhost", "KTRDR_DB_HOST", "DB_HOST")
    port: int = deprecated_field(5432, "KTRDR_DB_PORT", "DB_PORT")
    name: str = deprecated_field("ktrdr", "KTRDR_DB_NAME", "DB_NAME")
    user: str = deprecated_field("ktrdr", "KTRDR_DB_USER", "DB_USER")
    password: str = deprecated_field("localdev", "KTRDR_DB_PASSWORD", "DB_PASSWORD")
    echo: bool = deprecated_field(False, "KTRDR_DB_ECHO", "DB_ECHO")

    model_config = SettingsConfigDict(env_prefix="KTRDR_DB_", env_file=".env.local")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """Async database connection URL for asyncpg.

        Credentials are URL-encoded to handle special characters like @, :, /, etc.
        """
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{self.name}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_url(self) -> str:
        """Sync database connection URL for psycopg2.

        Credentials are URL-encoded to handle special characters like @, :, /, etc.
        """
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return f"postgresql+psycopg2://{user}:{password}@{self.host}:{self.port}/{self.name}"


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


@lru_cache
def get_db_settings() -> DatabaseSettings:
    """Get database settings with caching."""
    return DatabaseSettings()


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
    get_db_settings.cache_clear()


# Export IB config for convenience
__all__ = [
    # Settings classes
    "APISettings",
    "LoggingSettings",
    "OrphanDetectorSettings",
    "CheckpointSettings",
    "DatabaseSettings",
    "ApiServiceSettings",
    # Cached getters
    "get_api_settings",
    "get_logging_settings",
    "get_orphan_detector_settings",
    "get_checkpoint_settings",
    "get_db_settings",
    "get_api_service_settings",
    # Utilities
    "clear_settings_cache",
    "deprecated_field",
    # Compatibility aliases
    "CLISettings",
    "get_cli_settings",
    "IbConfig",
    "get_ib_config",
]
