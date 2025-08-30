"""
Unified Host Service Configuration System

This module provides a base class and specific implementations for managing
host service configurations (URLs, timeouts, etc.) across all KTRDR services.

Services supported:
- IB Host Service (port 5001)
- Training Host Service (port 5002)
- API Server (port 8000)
- Any future host services

Design principles:
- Single source of truth per service
- Environment variable overrides
- Consistent patterns across services
- No hardcoded URLs anywhere
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .. import metadata


class HostServiceSettings(BaseSettings):
    """
    Base class for all host service configurations.

    This provides common settings that all host services need:
    - enabled flag
    - base_url
    - timeout settings
    - health check configuration
    - retry logic

    Subclasses should:
    1. Set appropriate defaults
    2. Define env_prefix
    3. Add service-specific settings
    """

    enabled: bool = Field(
        default=False, description="Whether this host service is enabled"
    )

    base_url: str = Field(
        description="Base URL for the host service (e.g., http://localhost:5001)"
    )

    timeout: float = Field(
        default=30.0, description="Default timeout for requests in seconds"
    )

    health_check_interval: float = Field(
        default=10.0, description="Seconds between health checks"
    )

    max_retries: int = Field(
        default=3, description="Maximum retry attempts for failed requests"
    )

    retry_delay: float = Field(
        default=1.0, description="Delay between retries in seconds"
    )

    def get_health_url(self) -> str:
        """Get the health check endpoint URL."""
        return f"{self.base_url.rstrip('/')}/health"

    def get_detailed_health_url(self) -> str:
        """Get the detailed health check endpoint URL."""
        return f"{self.base_url.rstrip('/')}/health/detailed"


class IbHostServiceSettings(HostServiceSettings):
    """Interactive Brokers Host Service configuration."""

    enabled: bool = Field(
        default=metadata.get("host_service.enabled", False), alias="USE_IB_HOST_SERVICE"
    )

    base_url: str = Field(
        default=metadata.get("host_service.url", "http://localhost:5001"),
        alias="IB_HOST_SERVICE_URL",
    )

    model_config = SettingsConfigDict(env_prefix="IB_HOST_SERVICE_", extra="forbid")


class TrainingHostServiceSettings(HostServiceSettings):
    """Training Host Service configuration."""

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
        default=metadata.get("training_host.progress_poll_interval", 2.0),
        description="Seconds between progress polls for training operations",
    )

    session_timeout: float = Field(
        default=metadata.get("training_host.session_timeout", 3600.0),
        description="Maximum session duration in seconds",
    )

    model_config = SettingsConfigDict(
        env_prefix="TRAINING_HOST_SERVICE_", extra="forbid"
    )


class ApiServiceSettings(HostServiceSettings):
    """API Server configuration for client connections."""

    enabled: bool = Field(default=True)  # API is always "enabled" for clients

    base_url: str = Field(
        default=metadata.get("api.client_base_url", "http://localhost:8000/api/v1"),
        description="Base URL for API client connections",
        alias="api_base_url",
    )

    timeout: float = Field(default=metadata.get("api.client_timeout", 30.0))

    max_retries: int = Field(default=metadata.get("api.client_max_retries", 3))

    retry_delay: float = Field(default=metadata.get("api.client_retry_delay", 1.0))

    model_config = SettingsConfigDict(
        env_prefix="KTRDR_API_CLIENT_", extra="forbid", populate_by_name=True
    )

    def get_health_url(self) -> str:
        """API health endpoint."""
        return f"{self.base_url.rstrip('/')}/system/health"


# Cached getters for performance
@lru_cache
def get_ib_host_service_settings() -> IbHostServiceSettings:
    """Get IB Host Service settings with caching."""
    return IbHostServiceSettings()


@lru_cache
def get_training_host_service_settings() -> TrainingHostServiceSettings:
    """Get Training Host Service settings with caching."""
    return TrainingHostServiceSettings()


@lru_cache
def get_api_service_settings() -> ApiServiceSettings:
    """Get API service settings for client connections with caching."""
    return ApiServiceSettings()


# Convenience functions for quick access
def get_ib_host_url() -> str:
    """Get IB Host Service URL."""
    return get_ib_host_service_settings().base_url


def get_training_host_url() -> str:
    """Get Training Host Service URL."""
    return get_training_host_service_settings().base_url


def get_api_base_url() -> str:
    """Get API base URL for client connections."""
    return get_api_service_settings().base_url


# Validation helpers
def validate_service_url(url: str, service_name: str) -> bool:
    """
    Validate that a service URL is properly formatted.

    Args:
        url: URL to validate
        service_name: Name of the service for error messages

    Returns:
        True if valid

    Raises:
        ValueError: If URL is invalid
    """
    if not url:
        raise ValueError(f"{service_name} URL cannot be empty")

    if not url.startswith(("http://", "https://")):
        raise ValueError(f"{service_name} URL must start with http:// or https://")

    return True


def get_all_service_settings() -> dict[str, HostServiceSettings]:
    """
    Get all host service settings for debugging/monitoring.

    Returns:
        Dictionary mapping service names to their settings
    """
    return {
        "ib_host_service": get_ib_host_service_settings(),
        "training_host_service": get_training_host_service_settings(),
        "api_service": get_api_service_settings(),
    }
