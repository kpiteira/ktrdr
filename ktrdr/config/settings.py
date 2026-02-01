"""
KTRDR Settings Manager - Runtime configuration management.

This module provides access to configuration settings with environment-specific
overrides and environment variable support.
"""

import logging as python_logging
from functools import lru_cache
from typing import Any, TypeVar
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .. import metadata

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
        KTRDR_API_CORS_ORIGINS: JSON array of allowed origins
            (e.g. '["http://localhost:3000","http://localhost:8080"]')
        KTRDR_API_CORS_ALLOW_CREDENTIALS: Allow credentials for CORS
        KTRDR_API_CORS_ALLOW_METHODS: JSON array of allowed HTTP methods
            (e.g. '["GET","POST","OPTIONS"]')
        KTRDR_API_CORS_ALLOW_HEADERS: JSON array of allowed HTTP headers
            (e.g. '["Authorization","Content-Type"]')
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

    def get_log_level_int(self) -> int:
        """Convert string log level to Python logging constant.

        Returns:
            Python logging level constant (e.g., logging.INFO, logging.DEBUG)
        """
        level_map = {
            "DEBUG": python_logging.DEBUG,
            "INFO": python_logging.INFO,
            "WARNING": python_logging.WARNING,
            "ERROR": python_logging.ERROR,
            "CRITICAL": python_logging.CRITICAL,
        }
        return level_map[self.level]


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

    Provides orphan detection configuration with support for both new
    (KTRDR_ORPHAN_*) and deprecated (ORPHAN_*) environment variable names.

    Environment variables (new names - preferred):
        KTRDR_ORPHAN_TIMEOUT_SECONDS: Time (seconds) before an unclaimed operation
            is marked as orphaned. Default: 60
        KTRDR_ORPHAN_CHECK_INTERVAL_SECONDS: How often (seconds) to check for
            orphaned operations. Default: 15

    Deprecated names (still work, emit warnings at startup):
        ORPHAN_TIMEOUT_SECONDS, ORPHAN_CHECK_INTERVAL_SECONDS
    """

    timeout_seconds: int = deprecated_field(
        60,
        "KTRDR_ORPHAN_TIMEOUT_SECONDS",
        "ORPHAN_TIMEOUT_SECONDS",
        gt=0,
        description="Time in seconds before an unclaimed operation is marked FAILED",
    )
    check_interval_seconds: int = deprecated_field(
        15,
        "KTRDR_ORPHAN_CHECK_INTERVAL_SECONDS",
        "ORPHAN_CHECK_INTERVAL_SECONDS",
        gt=0,
        description="Interval in seconds between orphan detection checks",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_ORPHAN_",
        env_file=".env.local",
        extra="ignore",
    )


class OperationsSettings(BaseSettings):
    """Operations Service Settings.

    Provides configuration for the operations tracking service with support
    for both new (KTRDR_OPS_*) and deprecated (OPERATIONS_*) environment
    variable names.

    Environment variables (new names - preferred):
        KTRDR_OPS_CACHE_TTL: Cache TTL in seconds for operation lookups. Default: 1.0
        KTRDR_OPS_MAX_OPERATIONS: Maximum operations to track in memory. Default: 10000
        KTRDR_OPS_CLEANUP_INTERVAL_SECONDS: Interval between cleanup runs. Default: 3600
        KTRDR_OPS_RETENTION_DAYS: Days to retain completed operations. Default: 7

    Deprecated names (still work, emit warnings at startup):
        OPERATIONS_CACHE_TTL → KTRDR_OPS_CACHE_TTL
    """

    # Cache settings
    cache_ttl: float = deprecated_field(
        1.0,
        "KTRDR_OPS_CACHE_TTL",
        "OPERATIONS_CACHE_TTL",
        ge=0,
        description="Cache TTL in seconds for operation lookups (0 = no cache)",
    )

    # Capacity settings
    max_operations: int = Field(
        default=10000,
        gt=0,
        description="Maximum operations to track in memory",
    )

    # Cleanup settings
    cleanup_interval_seconds: int = Field(
        default=3600,
        gt=0,
        description="Interval in seconds between cleanup runs",
    )
    retention_days: int = Field(
        default=7,
        gt=0,
        description="Days to retain completed operations",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_OPS_",
        env_file=".env.local",
        extra="ignore",
    )


class CheckpointSettings(BaseSettings):
    """Checkpoint Settings.

    Configures checkpoint saving for long-running operations like training.
    Settings control checkpoint frequency and storage location.

    Provides checkpoint configuration with support for both new (KTRDR_CHECKPOINT_*)
    and deprecated (CHECKPOINT_*) environment variable names.

    Environment variables (new names - preferred):
        KTRDR_CHECKPOINT_EPOCH_INTERVAL: Save checkpoint every N epochs. Default: 10
        KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS: Save checkpoint every M seconds. Default: 300
        KTRDR_CHECKPOINT_DIR: Directory for checkpoint artifacts. Default: /app/data/checkpoints
        KTRDR_CHECKPOINT_MAX_AGE_DAYS: Auto-cleanup checkpoints older than N days. Default: 30

    Deprecated names (still work, emit warnings at startup):
        CHECKPOINT_EPOCH_INTERVAL, CHECKPOINT_TIME_INTERVAL_SECONDS,
        CHECKPOINT_DIR, CHECKPOINT_MAX_AGE_DAYS
    """

    epoch_interval: int = deprecated_field(
        10,
        "KTRDR_CHECKPOINT_EPOCH_INTERVAL",
        "CHECKPOINT_EPOCH_INTERVAL",
        gt=0,
        description="Save checkpoint every N epochs/units",
    )
    time_interval_seconds: int = deprecated_field(
        300,
        "KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS",
        "CHECKPOINT_TIME_INTERVAL_SECONDS",
        gt=0,
        description="Save checkpoint every M seconds",
    )
    dir: str = deprecated_field(
        "/app/data/checkpoints",
        "KTRDR_CHECKPOINT_DIR",
        "CHECKPOINT_DIR",
        description="Directory for checkpoint artifact storage",
    )
    max_age_days: int = deprecated_field(
        30,
        "KTRDR_CHECKPOINT_MAX_AGE_DAYS",
        "CHECKPOINT_MAX_AGE_DAYS",
        gt=0,
        description="Auto-cleanup checkpoints older than N days",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_CHECKPOINT_",
        env_file=".env.local",
        extra="ignore",
    )


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


class IBSettings(BaseSettings):
    """Interactive Brokers Settings.

    Provides IB Gateway connection configuration with support for both
    new (KTRDR_IB_*) and deprecated (IB_*) environment variable names.

    Environment variables (new names - preferred):
        KTRDR_IB_HOST: IB Gateway host. Default: 127.0.0.1
        KTRDR_IB_PORT: IB Gateway port. Default: 4002 (paper trading)
        KTRDR_IB_CLIENT_ID: Client ID for connection. Default: 1
        KTRDR_IB_TIMEOUT: Connection timeout in seconds. Default: 30
        KTRDR_IB_READONLY: Read-only mode. Default: false
        KTRDR_IB_RATE_LIMIT: Rate limit (requests). Default: 50
        KTRDR_IB_RATE_PERIOD: Rate period in seconds. Default: 60
        KTRDR_IB_MAX_RETRIES: Maximum retry attempts. Default: 3
        KTRDR_IB_RETRY_BASE_DELAY: Base retry delay in seconds. Default: 2.0
        KTRDR_IB_RETRY_MAX_DELAY: Max retry delay in seconds. Default: 60.0
        KTRDR_IB_PACING_DELAY: Pacing delay between requests. Default: 0.6
        KTRDR_IB_MAX_REQUESTS_PER_10MIN: Max requests per 10 minutes. Default: 60

    Deprecated names (still work, emit warnings at startup):
        IB_HOST, IB_PORT, IB_CLIENT_ID, IB_TIMEOUT, IB_READONLY,
        IB_RATE_LIMIT, IB_RATE_PERIOD, IB_MAX_RETRIES, IB_RETRY_DELAY,
        IB_RETRY_MAX_DELAY, IB_PACING_DELAY, IB_MAX_REQUESTS_10MIN
    """

    # Connection settings
    host: str = deprecated_field("127.0.0.1", "KTRDR_IB_HOST", "IB_HOST")
    port: int = deprecated_field(4002, "KTRDR_IB_PORT", "IB_PORT", ge=1, le=65535)
    client_id: int = deprecated_field(1, "KTRDR_IB_CLIENT_ID", "IB_CLIENT_ID")
    timeout: int = deprecated_field(30, "KTRDR_IB_TIMEOUT", "IB_TIMEOUT", gt=0)
    readonly: bool = deprecated_field(False, "KTRDR_IB_READONLY", "IB_READONLY")

    # Rate limiting settings
    rate_limit: int = deprecated_field(50, "KTRDR_IB_RATE_LIMIT", "IB_RATE_LIMIT", gt=0)
    rate_period: int = deprecated_field(
        60, "KTRDR_IB_RATE_PERIOD", "IB_RATE_PERIOD", gt=0
    )

    # Retry settings
    max_retries: int = deprecated_field(
        3, "KTRDR_IB_MAX_RETRIES", "IB_MAX_RETRIES", ge=0
    )
    retry_base_delay: float = deprecated_field(
        2.0, "KTRDR_IB_RETRY_BASE_DELAY", "IB_RETRY_DELAY", gt=0
    )
    retry_max_delay: float = deprecated_field(
        60.0, "KTRDR_IB_RETRY_MAX_DELAY", "IB_RETRY_MAX_DELAY", gt=0
    )

    # Pacing settings (based on IB documentation)
    pacing_delay: float = deprecated_field(
        0.6, "KTRDR_IB_PACING_DELAY", "IB_PACING_DELAY", ge=0
    )
    max_requests_per_10min: int = deprecated_field(
        60, "KTRDR_IB_MAX_REQUESTS_PER_10MIN", "IB_MAX_REQUESTS_10MIN", gt=0
    )

    # Static data fetching chunk sizes (not configurable via env vars)
    # These are IB-specific limits based on bar size
    _chunk_days: dict[str, float] = {
        "1 secs": 0.02,  # 30 minutes
        "5 secs": 0.08,  # 2 hours
        "15 secs": 0.17,  # 4 hours
        "30 secs": 0.33,  # 8 hours
        "1 min": 1,  # 1 day
        "2 mins": 2,  # 2 days (conservative)
        "3 mins": 3,  # 3 days (conservative)
        "5 mins": 7,  # 1 week
        "10 mins": 14,  # 2 weeks (conservative)
        "15 mins": 14,  # 2 weeks
        "20 mins": 20,  # 20 days (conservative)
        "30 mins": 30,  # 1 month
        "1 hour": 1,  # 1 day (IB limit for hourly data)
        "2 hours": 60,  # 2 months (conservative)
        "3 hours": 90,  # 3 months (conservative)
        "4 hours": 120,  # 4 months (conservative)
        "1 day": 365,  # 1 year
        "1 week": 730,  # 2 years
        "1 month": 365,  # 1 year
    }

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_IB_",
        env_file=".env.local",
        extra="ignore",
    )

    def get_connection_config(self) -> dict[str, Any]:
        """Get connection configuration for IbConnectionManager.

        Returns:
            Dictionary with host, port, client_id, timeout, readonly settings.
        """
        return {
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "timeout": self.timeout,
            "readonly": self.readonly,
        }

    def get_chunk_size(self, bar_size: str) -> float:
        """Get maximum chunk size in days for a given bar size.

        Args:
            bar_size: IB bar size string (e.g., "1 min", "1 day")

        Returns:
            Maximum days to request in a single chunk. Returns 1 for unknown bar sizes.
        """
        return self._chunk_days.get(bar_size, 1)

    def is_paper_trading(self) -> bool:
        """Check if configured for paper trading.

        Paper trading ports: TWS=7497, IB Gateway=4002
        """
        return self.port in [7497, 4002]

    def is_live_trading(self) -> bool:
        """Check if configured for live trading.

        Live trading ports: TWS=7496, IB Gateway=4001
        """
        return self.port in [7496, 4001]

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary.

        Returns:
            Dictionary with all IB settings including derived values.
        """
        return {
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "timeout": self.timeout,
            "readonly": self.readonly,
            "rate_limit": self.rate_limit,
            "rate_period": self.rate_period,
            "max_retries": self.max_retries,
            "retry_base_delay": self.retry_base_delay,
            "retry_max_delay": self.retry_max_delay,
            "pacing_delay": self.pacing_delay,
            "max_requests_per_10min": self.max_requests_per_10min,
            "is_paper": self.is_paper_trading(),
            "is_live": self.is_live_trading(),
        }


class IBHostServiceSettings(BaseSettings):
    """IB Host Service Settings.

    Provides IB Host Service connection configuration with support for both
    new (KTRDR_IB_HOST_*) and deprecated (USE_IB_HOST_SERVICE) environment
    variable names.

    The IB Host Service is a native process that manages the connection to
    IB Gateway/TWS. The backend proxies requests through this service.

    Environment variables (new names - preferred):
        KTRDR_IB_HOST_HOST: IB host service host. Default: localhost
        KTRDR_IB_HOST_PORT: IB host service port. Default: 5001
        KTRDR_IB_HOST_ENABLED: Enable IB host service. Default: false
        KTRDR_IB_HOST_TIMEOUT: Request timeout in seconds. Default: 30.0
        KTRDR_IB_HOST_HEALTH_CHECK_INTERVAL: Health check interval. Default: 10.0
        KTRDR_IB_HOST_MAX_RETRIES: Max retry attempts. Default: 3
        KTRDR_IB_HOST_RETRY_DELAY: Delay between retries. Default: 1.0

    Deprecated names (still work, emit warnings at startup):
        USE_IB_HOST_SERVICE → KTRDR_IB_HOST_ENABLED
    """

    # Connection settings
    host: str = Field(
        default="localhost",
        description="IB host service hostname",
    )
    port: int = Field(
        default=5001,
        ge=1,
        le=65535,
        description="IB host service port",
    )
    enabled: bool = deprecated_field(
        False,
        "KTRDR_IB_HOST_ENABLED",
        "USE_IB_HOST_SERVICE",
        description="Whether IB host service is enabled",
    )

    # Request settings
    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Default timeout for requests in seconds",
    )
    health_check_interval: float = Field(
        default=10.0,
        gt=0,
        description="Seconds between health checks",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts for failed requests",
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0,
        description="Delay between retries in seconds",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_IB_HOST_",
        env_file=".env.local",
        extra="ignore",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def base_url(self) -> str:
        """Computed base URL from host and port.

        Returns:
            Base URL for the IB host service (e.g., http://localhost:5001)
        """
        return f"http://{self.host}:{self.port}"

    def get_health_url(self) -> str:
        """Get the health check endpoint URL.

        Returns:
            Health endpoint URL (e.g., http://localhost:5001/health)
        """
        return f"{self.base_url}/health"

    def get_detailed_health_url(self) -> str:
        """Get the detailed health check endpoint URL.

        Returns:
            Detailed health endpoint URL (e.g., http://localhost:5001/health/detailed)
        """
        return f"{self.base_url}/health/detailed"


class TrainingHostServiceSettings(BaseSettings):
    """Training Host Service Settings.

    Provides Training Host Service connection configuration with support for both
    new (KTRDR_TRAINING_HOST_*) and deprecated (USE_TRAINING_HOST_SERVICE)
    environment variable names.

    The Training Host Service is a native process that provides GPU-accelerated
    model training. The backend proxies training requests through this service.

    Environment variables (new names - preferred):
        KTRDR_TRAINING_HOST_HOST: Training host service host. Default: localhost
        KTRDR_TRAINING_HOST_PORT: Training host service port. Default: 5002
        KTRDR_TRAINING_HOST_ENABLED: Enable training host service. Default: false
        KTRDR_TRAINING_HOST_TIMEOUT: Request timeout in seconds. Default: 30.0
        KTRDR_TRAINING_HOST_HEALTH_CHECK_INTERVAL: Health check interval. Default: 10.0
        KTRDR_TRAINING_HOST_MAX_RETRIES: Max retry attempts. Default: 3
        KTRDR_TRAINING_HOST_RETRY_DELAY: Delay between retries. Default: 1.0

    Deprecated names (still work, emit warnings at startup):
        USE_TRAINING_HOST_SERVICE → KTRDR_TRAINING_HOST_ENABLED
    """

    # Connection settings
    host: str = Field(
        default="localhost",
        description="Training host service hostname",
    )
    port: int = Field(
        default=5002,
        ge=1,
        le=65535,
        description="Training host service port",
    )
    enabled: bool = deprecated_field(
        False,
        "KTRDR_TRAINING_HOST_ENABLED",
        "USE_TRAINING_HOST_SERVICE",
        description="Whether training host service is enabled",
    )

    # Request settings
    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Default timeout for requests in seconds",
    )
    health_check_interval: float = Field(
        default=10.0,
        gt=0,
        description="Seconds between health checks",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts for failed requests",
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0,
        description="Delay between retries in seconds",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_TRAINING_HOST_",
        env_file=".env.local",
        extra="ignore",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def base_url(self) -> str:
        """Computed base URL from host and port.

        Returns:
            Base URL for the training host service (e.g., http://localhost:5002)
        """
        return f"http://{self.host}:{self.port}"

    def get_health_url(self) -> str:
        """Get the health check endpoint URL.

        Returns:
            Health endpoint URL (e.g., http://localhost:5002/health)
        """
        return f"{self.base_url}/health"

    def get_detailed_health_url(self) -> str:
        """Get the detailed health check endpoint URL.

        Returns:
            Detailed health endpoint URL (e.g., http://localhost:5002/health/detailed)
        """
        return f"{self.base_url}/health/detailed"


class WorkerSettings(BaseSettings):
    """Worker Process Settings.

    Provides worker configuration with support for both new (KTRDR_WORKER_*)
    and deprecated (WORKER_*) environment variable names.

    The default port of 5003 fixes the WORKER_PORT bug (duplication #4 from
    config audit): training_worker.py defaulted to 5002 while worker_registration.py
    defaulted to 5004. Now there's a single authoritative default.

    Note: This class does NOT have a backend_url field. Workers should use
    get_api_client_settings().base_url (from M5's APIClientSettings) for the
    backend connection URL. This ensures a single source of truth.

    Environment variables (new names - preferred):
        KTRDR_WORKER_ID: Worker identifier. Default: None (auto-generated at runtime)
        KTRDR_WORKER_PORT: Worker port. Default: 5003 (canonical default)
        KTRDR_WORKER_HEARTBEAT_INTERVAL: Heartbeat interval in seconds. Default: 30
        KTRDR_WORKER_REGISTRATION_TIMEOUT: Registration timeout. Default: 10
        KTRDR_WORKER_ENDPOINT_URL: Explicit endpoint URL. Default: None (auto-detected)
        KTRDR_WORKER_PUBLIC_BASE_URL: Public URL for distributed deployments. Default: None

    Deprecated names (still work, emit warnings at startup):
        WORKER_ID, WORKER_PORT, WORKER_ENDPOINT_URL, WORKER_PUBLIC_BASE_URL
    """

    # Worker identification
    worker_id: str | None = deprecated_field(
        None,
        "KTRDR_WORKER_ID",
        "WORKER_ID",
        description="Worker identifier (auto-generated if not set)",
    )

    # Network settings - port 5003 is the canonical default (fixes bug)
    port: int = deprecated_field(
        5003,
        "KTRDR_WORKER_PORT",
        "WORKER_PORT",
        ge=1,
        le=65535,
        description="Worker service port (canonical default: 5003)",
    )

    # Heartbeat and registration settings
    heartbeat_interval: int = Field(
        default=30,
        gt=0,
        description="Interval in seconds between heartbeats to backend",
    )
    registration_timeout: int = Field(
        default=10,
        gt=0,
        description="Timeout in seconds for worker registration",
    )

    # Endpoint configuration (for distributed deployments)
    endpoint_url: str | None = deprecated_field(
        None,
        "KTRDR_WORKER_ENDPOINT_URL",
        "WORKER_ENDPOINT_URL",
        description="Explicit endpoint URL (if not set, auto-detected at runtime)",
    )
    public_base_url: str | None = deprecated_field(
        None,
        "KTRDR_WORKER_PUBLIC_BASE_URL",
        "WORKER_PUBLIC_BASE_URL",
        description="Public URL for distributed deployments (if not set, uses hostname)",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_WORKER_",
        env_file=".env.local",
        extra="ignore",
    )


class AgentSettings(BaseSettings):
    """Agent Process Settings.

    Provides agent configuration with support for both new (KTRDR_AGENT_*)
    and deprecated (AGENT_*) environment variable names.

    Environment variables (new names - preferred):
        KTRDR_AGENT_POLL_INTERVAL: Poll interval in seconds. Default: 5
        KTRDR_AGENT_MODEL: LLM model to use. Default: claude-sonnet-4-20250514
        KTRDR_AGENT_MAX_TOKENS: Max output tokens. Default: 4096
        KTRDR_AGENT_TIMEOUT_SECONDS: Request timeout in seconds. Default: 300
        KTRDR_AGENT_MAX_ITERATIONS: Max agentic iterations. Default: 10
        KTRDR_AGENT_MAX_INPUT_TOKENS: Max input context tokens. Default: 50000
        KTRDR_AGENT_DAILY_BUDGET: Daily cost budget in USD. Default: 5.0
        KTRDR_AGENT_BUDGET_DIR: Budget data directory. Default: data/budget
        KTRDR_AGENT_MAX_CONCURRENT_RESEARCHES: Max concurrent (0=unlimited). Default: 0
        KTRDR_AGENT_CONCURRENCY_BUFFER: Concurrency buffer. Default: 1
        KTRDR_AGENT_TRAINING_START_DATE: Default training start date
        KTRDR_AGENT_TRAINING_END_DATE: Default training end date
        KTRDR_AGENT_BACKTEST_START_DATE: Default backtest start date
        KTRDR_AGENT_BACKTEST_END_DATE: Default backtest end date

    Deprecated names (still work, emit warnings at startup):
        AGENT_POLL_INTERVAL, AGENT_MODEL, AGENT_MAX_TOKENS, AGENT_TIMEOUT_SECONDS,
        AGENT_MAX_ITERATIONS, AGENT_MAX_INPUT_TOKENS, AGENT_DAILY_BUDGET,
        AGENT_BUDGET_DIR, AGENT_MAX_CONCURRENT_RESEARCHES, AGENT_CONCURRENCY_BUFFER,
        AGENT_TRAINING_START_DATE, AGENT_TRAINING_END_DATE,
        AGENT_BACKTEST_START_DATE, AGENT_BACKTEST_END_DATE
    """

    # Polling and timing
    poll_interval: float = deprecated_field(
        5.0,
        "KTRDR_AGENT_POLL_INTERVAL",
        "AGENT_POLL_INTERVAL",
        gt=0,
        description="Poll interval in seconds for agent loops",
    )

    # LLM configuration
    model: str = deprecated_field(
        "claude-sonnet-4-20250514",
        "KTRDR_AGENT_MODEL",
        "AGENT_MODEL",
        description="LLM model identifier to use for agent",
    )
    max_tokens: int = deprecated_field(
        4096,
        "KTRDR_AGENT_MAX_TOKENS",
        "AGENT_MAX_TOKENS",
        gt=0,
        description="Maximum output tokens per request",
    )
    timeout_seconds: int = deprecated_field(
        300,
        "KTRDR_AGENT_TIMEOUT_SECONDS",
        "AGENT_TIMEOUT_SECONDS",
        gt=0,
        description="Request timeout in seconds",
    )
    max_iterations: int = deprecated_field(
        10,
        "KTRDR_AGENT_MAX_ITERATIONS",
        "AGENT_MAX_ITERATIONS",
        gt=0,
        description="Maximum agentic iterations per task",
    )
    max_input_tokens: int = deprecated_field(
        50000,
        "KTRDR_AGENT_MAX_INPUT_TOKENS",
        "AGENT_MAX_INPUT_TOKENS",
        gt=0,
        description="Maximum input context tokens",
    )

    # Budget settings
    daily_budget: float = deprecated_field(
        5.0,
        "KTRDR_AGENT_DAILY_BUDGET",
        "AGENT_DAILY_BUDGET",
        ge=0,
        description="Daily cost budget in USD (0 = disabled)",
    )
    budget_dir: str = deprecated_field(
        "data/budget",
        "KTRDR_AGENT_BUDGET_DIR",
        "AGENT_BUDGET_DIR",
        description="Directory for budget tracking data",
    )

    # Concurrency settings
    max_concurrent_researches: int = deprecated_field(
        0,
        "KTRDR_AGENT_MAX_CONCURRENT_RESEARCHES",
        "AGENT_MAX_CONCURRENT_RESEARCHES",
        ge=0,
        description="Max concurrent research agents (0 = unlimited)",
    )
    concurrency_buffer: int = deprecated_field(
        1,
        "KTRDR_AGENT_CONCURRENCY_BUFFER",
        "AGENT_CONCURRENCY_BUFFER",
        ge=0,
        description="Buffer for concurrency limits",
    )

    # Date defaults (optional)
    training_start_date: str | None = deprecated_field(
        None,
        "KTRDR_AGENT_TRAINING_START_DATE",
        "AGENT_TRAINING_START_DATE",
        description="Default training start date (YYYY-MM-DD)",
    )
    training_end_date: str | None = deprecated_field(
        None,
        "KTRDR_AGENT_TRAINING_END_DATE",
        "AGENT_TRAINING_END_DATE",
        description="Default training end date (YYYY-MM-DD)",
    )
    backtest_start_date: str | None = deprecated_field(
        None,
        "KTRDR_AGENT_BACKTEST_START_DATE",
        "AGENT_BACKTEST_START_DATE",
        description="Default backtest start date (YYYY-MM-DD)",
    )
    backtest_end_date: str | None = deprecated_field(
        None,
        "KTRDR_AGENT_BACKTEST_END_DATE",
        "AGENT_BACKTEST_END_DATE",
        description="Default backtest end date (YYYY-MM-DD)",
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_AGENT_",
        env_file=".env.local",
        extra="ignore",
    )


class ApiServiceSettings(BaseSettings):
    """API Server configuration for client connections.

    Provides API client configuration for CLI and other clients connecting
    to the KTRDR backend API server.

    Environment variables:
        api_base_url: Base URL for API client connections.
            Default: http://localhost:8000/api/v1
        KTRDR_API_CLIENT_TIMEOUT: Request timeout in seconds. Default: 30.0
        KTRDR_API_CLIENT_MAX_RETRIES: Max retry attempts. Default: 3
        KTRDR_API_CLIENT_RETRY_DELAY: Delay between retries. Default: 1.0
    """

    enabled: bool = Field(default=True)  # API is always "enabled" for clients

    base_url: str = Field(
        default=metadata.get("api.client_base_url", "http://localhost:8000/api/v1"),
        description="Base URL for API client connections",
        alias="api_base_url",
    )

    timeout: float = Field(default=metadata.get("api.client_timeout", 30.0))

    max_retries: int = Field(default=metadata.get("api.client_max_retries", 3))

    retry_delay: float = Field(default=metadata.get("api.client_retry_delay", 1.0))

    # These fields are inherited from the old HostServiceSettings base class
    health_check_interval: float = Field(
        default=10.0, description="Seconds between health checks"
    )

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_API_CLIENT_", extra="forbid", populate_by_name=True
    )

    def get_health_url(self) -> str:
        """API health endpoint.

        Returns:
            Health endpoint URL (e.g., http://localhost:8000/api/v1/system/health)
        """
        return f"{self.base_url.rstrip('/')}/system/health"


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
def get_operations_settings() -> OperationsSettings:
    """Get operations settings with caching."""
    return OperationsSettings()


@lru_cache
def get_checkpoint_settings() -> CheckpointSettings:
    """Get checkpoint settings with caching."""
    return CheckpointSettings()


@lru_cache
def get_db_settings() -> DatabaseSettings:
    """Get database settings with caching."""
    return DatabaseSettings()


@lru_cache
def get_ib_settings() -> IBSettings:
    """Get IB settings with caching."""
    return IBSettings()


@lru_cache
def get_ib_host_service_settings() -> IBHostServiceSettings:
    """Get IB host service settings with caching."""
    return IBHostServiceSettings()


@lru_cache
def get_training_host_service_settings() -> TrainingHostServiceSettings:
    """Get training host service settings with caching."""
    return TrainingHostServiceSettings()


@lru_cache
def get_worker_settings() -> WorkerSettings:
    """Get worker settings with caching."""
    return WorkerSettings()


@lru_cache
def get_agent_settings() -> AgentSettings:
    """Get agent settings with caching."""
    return AgentSettings()


@lru_cache
def get_api_service_settings() -> ApiServiceSettings:
    """Get API service settings for client connections with caching."""
    return ApiServiceSettings()


def get_api_base_url() -> str:
    """Get API base URL for client connections.

    This is a convenience function for quick access to the API base URL
    without needing to work with the full settings object.

    Returns:
        API base URL string (e.g., http://localhost:8000/api/v1)
    """
    return get_api_service_settings().base_url


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
    get_operations_settings.cache_clear()
    get_checkpoint_settings.cache_clear()
    get_db_settings.cache_clear()
    get_ib_settings.cache_clear()
    get_ib_host_service_settings.cache_clear()
    get_training_host_service_settings.cache_clear()
    get_worker_settings.cache_clear()
    get_agent_settings.cache_clear()


# Export settings classes and getters
__all__ = [
    # Settings classes
    "APISettings",
    "AuthSettings",
    "LoggingSettings",
    "ObservabilitySettings",
    "OrphanDetectorSettings",
    "OperationsSettings",
    "CheckpointSettings",
    "DatabaseSettings",
    "ApiServiceSettings",
    "IBSettings",
    "IBHostServiceSettings",
    "TrainingHostServiceSettings",
    "WorkerSettings",
    "AgentSettings",
    # Cached getters
    "get_api_settings",
    "get_auth_settings",
    "get_logging_settings",
    "get_observability_settings",
    "get_orphan_detector_settings",
    "get_operations_settings",
    "get_checkpoint_settings",
    "get_db_settings",
    "get_api_service_settings",
    "get_api_base_url",
    "get_ib_settings",
    "get_ib_host_service_settings",
    "get_training_host_service_settings",
    "get_worker_settings",
    "get_agent_settings",
    # Utilities
    "clear_settings_cache",
    "deprecated_field",
    # Compatibility aliases (to be removed after M3.5)
    "CLISettings",
    "get_cli_settings",
]
