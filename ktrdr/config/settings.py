"""
KTRDR Settings Manager - Runtime configuration management.

This module provides access to configuration settings with environment-specific
overrides and environment variable support.
"""

from functools import lru_cache
from typing import Any, TypeVar
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, computed_field, field_validator
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
    """API Server Settings.

    Provides API configuration with support for environment variables.
    Merges functionality from the previous ktrdr/api/config.py::APIConfig.

    Environment variables (all prefixed with KTRDR_API_):
        KTRDR_API_HOST: Host to bind. Default: 127.0.0.1
        KTRDR_API_PORT: Port to bind. Default: 8000
        KTRDR_API_ENVIRONMENT: Deployment environment (development/staging/production)
        KTRDR_API_LOG_LEVEL: Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        KTRDR_API_CORS_ORIGINS: Comma-separated list of allowed origins
        KTRDR_API_CORS_ALLOW_CREDENTIALS: Allow credentials for CORS
        KTRDR_API_CORS_ALLOW_METHODS: Comma-separated list of allowed methods
        KTRDR_API_CORS_ALLOW_HEADERS: Comma-separated list of allowed headers
        KTRDR_API_CORS_MAX_AGE: Max age for CORS preflight cache (seconds)
    """

    # API metadata
    title: str = Field(default=metadata.API_TITLE)
    description: str = Field(default=metadata.API_DESCRIPTION)
    version: str = Field(default=metadata.VERSION)

    # Server configuration
    host: str = Field(default="127.0.0.1", description="Host to bind the API server")
    port: int = Field(default=8000, description="Port to bind the API server")
    reload: bool = Field(default=True, description="Enable auto-reload for development")
    log_level: str = Field(
        default="INFO", description="Logging level for the API server"
    )

    # Environment
    environment: str = Field(
        default="development",
        description="Deployment environment (development, staging, production)",
    )

    # API routing
    api_prefix: str = Field(default=metadata.API_PREFIX)

    # CORS configuration
    cors_origins: list[str] = Field(
        default=["*"], description="List of allowed origins for CORS"
    )
    cors_allow_credentials: bool = Field(
        default=True, description="Allow credentials for CORS requests"
    )
    cors_allow_methods: list[str] = Field(
        default=["*"], description="List of allowed HTTP methods for CORS"
    )
    cors_allow_headers: list[str] = Field(
        default=["*"], description="List of allowed HTTP headers for CORS"
    )
    cors_max_age: int = Field(
        default=600,
        description="Maximum age (seconds) of CORS preflight responses to cache",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_API_",
        env_file=".env.local",
        extra="ignore",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate that environment is one of the allowed values."""
        allowed = ["development", "staging", "production"]
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate that log_level is one of the allowed values."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}, got '{v}'")
        return v.upper()


class AuthSettings(BaseSettings):
    """Authentication Settings.

    Provides JWT and authentication configuration with support for
    environment variables.

    Environment variables (all prefixed with KTRDR_AUTH_):
        KTRDR_AUTH_JWT_SECRET: Secret key for JWT signing. Default: insecure-dev-secret
        KTRDR_AUTH_JWT_ALGORITHM: JWT algorithm. Default: HS256
        KTRDR_AUTH_TOKEN_EXPIRE_MINUTES: Token expiration in minutes. Default: 60
    """

    jwt_secret: str = Field(
        default="insecure-dev-secret",
        description="Secret key for JWT token signing (MUST be changed in production)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Algorithm used for JWT signing",
    )
    token_expire_minutes: int = Field(
        default=60,
        gt=0,
        description="Token expiration time in minutes",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_AUTH_",
        env_file=".env.local",
        extra="ignore",
    )


class LoggingSettings(BaseSettings):
    """Logging Settings.

    Provides logging configuration with support for environment variables.

    Environment variables (all prefixed with KTRDR_LOG_):
        KTRDR_LOG_LEVEL: Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL). Default: INFO
        KTRDR_LOG_FORMAT: Log message format string. Default: timestamp + level + name + message
        KTRDR_LOG_JSON_OUTPUT: Enable JSON structured logging. Default: false
    """

    level: str = Field(
        default="INFO",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    format: str = Field(
        default="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        description="Log message format string",
    )
    json_output: bool = Field(
        default=False,
        description="Enable JSON structured logging output",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_LOG_",
        env_file=".env.local",
        extra="ignore",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate that level is one of the allowed values."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}, got '{v}'")
        return v.upper()


class ObservabilitySettings(BaseSettings):
    """Observability Settings.

    Provides OpenTelemetry/Jaeger tracing configuration with support for
    environment variables.

    Environment variables (all prefixed with KTRDR_OTEL_):
        KTRDR_OTEL_ENABLED: Enable tracing. Default: true
        KTRDR_OTEL_OTLP_ENDPOINT: OTLP gRPC endpoint for Jaeger. Default: http://jaeger:4317
        KTRDR_OTEL_SERVICE_NAME: Service name for traces. Default: ktrdr
        KTRDR_OTEL_CONSOLE_OUTPUT: Also output traces to console. Default: false

    Deprecated names (still work, emit warnings at startup):
        OTLP_ENDPOINT → KTRDR_OTEL_OTLP_ENDPOINT
    """

    enabled: bool = Field(
        default=True,
        description="Enable OpenTelemetry tracing",
    )
    otlp_endpoint: str = deprecated_field(
        "http://jaeger:4317",
        "KTRDR_OTEL_OTLP_ENDPOINT",
        "OTLP_ENDPOINT",
        description="OTLP gRPC endpoint for Jaeger",
    )
    service_name: str = Field(
        default="ktrdr",
        description="Service name for traces",
    )
    console_output: bool = Field(
        default=False,
        description="Also output traces to console (for debugging)",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_OTEL_",
        env_file=".env.local",
        extra="ignore",
    )


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
def get_auth_settings() -> AuthSettings:
    """Get auth settings with caching."""
    return AuthSettings()


@lru_cache
def get_logging_settings() -> LoggingSettings:
    """Get logging settings with caching."""
    return LoggingSettings()


@lru_cache
def get_observability_settings() -> ObservabilitySettings:
    """Get observability settings with caching."""
    return ObservabilitySettings()


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
    get_auth_settings.cache_clear()
    get_logging_settings.cache_clear()
    get_observability_settings.cache_clear()
    get_api_service_settings.cache_clear()
    get_orphan_detector_settings.cache_clear()
    get_checkpoint_settings.cache_clear()
    get_db_settings.cache_clear()


# Export IB config for convenience
__all__ = [
    # Settings classes
    "APISettings",
    "AuthSettings",
    "LoggingSettings",
    "ObservabilitySettings",
    "OrphanDetectorSettings",
    "CheckpointSettings",
    "DatabaseSettings",
    "ApiServiceSettings",
    # Cached getters
    "get_api_settings",
    "get_auth_settings",
    "get_logging_settings",
    "get_observability_settings",
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
