"""
AsyncHostService Base Class

Provides unified host service communication patterns across all external service integrations.
This establishes the foundation for consistent async patterns between IB Host Service
and Training Host Service communication.

Architecture Compliance:
- HTTP Communication: Standardized patterns for all host service calls
- Connection Pooling: Shared HTTP client management
- Error Handling: Unified exception hierarchy
- Resource Management: Proper async context manager patterns
- Health Monitoring: Consistent health check interface
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ktrdr.logging import get_logger

logger = get_logger(__name__)


# Custom Exception Hierarchy
class HostServiceError(Exception):
    """Base exception for host service failures."""

    def __init__(self, message: str, service_name: str = "Unknown"):
        self.message = message
        self.service_name = service_name
        super().__init__(message)


class HostServiceConnectionError(HostServiceError):
    """Exception for connection-specific failures."""

    pass


class HostServiceTimeoutError(HostServiceError):
    """Exception for timeout-specific failures."""

    pass


# Configuration Data Class
@dataclass
class HostServiceConfig:
    """Configuration for AsyncHostService instances."""

    base_url: str
    timeout: int = 30
    max_retries: int = 3
    connection_pool_limit: int = 20


# Abstract Base Class
class AsyncHostService(ABC):
    """
    Base class for all host service communication.

    Provides standardized HTTP communication patterns, connection pooling,
    error handling, and resource management for external service integrations.

    Architecture Pattern:
    - Async Context Manager: Proper lifecycle management
    - Connection Pooling: Shared HTTP client for efficiency
    - Error Handling: Consistent exception hierarchy
    - Progress Support: Integration with progress reporting
    - Health Monitoring: Standardized health check interface
    """

    def __init__(
        self, config: HostServiceConfig, timeout: int = 30, max_retries: int = 3
    ):
        """
        Initialize AsyncHostService with configuration.

        Args:
            config: Service configuration with URLs and timeouts
            timeout: Request timeout in seconds (overrides config)
            max_retries: Maximum retry attempts for failed requests
        """
        self.config = config
        self.timeout = timeout if timeout != 30 else config.timeout
        self.max_retries = max_retries if max_retries != 3 else config.max_retries

        # HTTP client and connection pool (initialized in async context)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._connection_pool: Optional[httpx.AsyncClient] = None

        # Statistics and monitoring
        self._requests_made = 0
        self._errors_encountered = 0
        self._last_request_time: Optional[datetime] = None

        logger.info(
            f"Initialized {self.get_service_name()} host service adapter "
            f"(timeout={self.timeout}s, retries={self.max_retries})"
        )

    # Abstract Methods (must be implemented by subclasses)
    @abstractmethod
    def get_service_name(self) -> str:
        """Return service identifier for logging and metrics."""
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        """Return service base URL from configuration."""
        pass

    @abstractmethod
    async def get_health_check_endpoint(self) -> str:
        """Return endpoint for health checking."""
        pass

    # Async Context Manager Protocol
    async def __aenter__(self) -> "AsyncHostService":
        """Setup connection pool and HTTP client."""
        await self._setup_connection_pool()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup HTTP client and connection pool."""
        await self._cleanup_connection_pool()

    # Connection Pool Management
    async def _setup_connection_pool(self) -> None:
        """Initialize HTTP client with connection pooling."""
        # Connection limits for efficiency
        limits = httpx.Limits(
            max_connections=self.config.connection_pool_limit,
            max_keepalive_connections=10,
        )

        # Configure timeouts
        timeout = httpx.Timeout(self.timeout)

        # Create HTTP client with connection pooling
        self._http_client = httpx.AsyncClient(
            limits=limits, timeout=timeout, follow_redirects=True
        )
        self._connection_pool = self._http_client

        logger.debug(
            f"{self.get_service_name()}: Connection pool initialized "
            f"(max_connections={self.config.connection_pool_limit}, timeout={self.timeout}s)"
        )

    async def _cleanup_connection_pool(self) -> None:
        """Cleanup HTTP client and close connections."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            self._connection_pool = None
            logger.debug(f"{self.get_service_name()}: Connection pool cleaned up")

    # HTTP Communication Methods
    async def _call_host_service_post(
        self, endpoint: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Standardized POST requests with retry logic and error handling.

        Args:
            endpoint: API endpoint (e.g., "/data/fetch")
            data: JSON data to send in request body

        Returns:
            JSON response as dictionary

        Raises:
            HostServiceConnectionError: For connection failures
            HostServiceTimeoutError: For timeout failures
            HostServiceError: For other service failures
        """
        if not self._http_client:
            raise HostServiceError(
                "HTTP client not initialized. Use async context manager.",
                self.get_service_name(),
            )

        url = f"{self.get_base_url()}{endpoint}"

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._http_client.post(
                    url, json=data, timeout=self.timeout
                )

                # Handle HTTP errors
                response.raise_for_status()

                # Update statistics
                self._requests_made += 1
                self._last_request_time = datetime.now(timezone.utc)

                logger.debug(
                    f"{self.get_service_name()}: POST {endpoint} successful "
                    f"(status={response.status_code})"
                )

                return response.json()

            except httpx.TimeoutException as e:
                if attempt == self.max_retries:
                    self._errors_encountered += 1
                    raise HostServiceTimeoutError(
                        f"Request timed out after {attempt + 1} attempts: {str(e)}",
                        self.get_service_name(),
                    ) from e

                # Exponential backoff
                delay = 2**attempt
                logger.warning(
                    f"{self.get_service_name()}: POST {endpoint} timeout "
                    f"(attempt {attempt + 1}/{self.max_retries + 1}), retrying in {delay}s"
                )
                await asyncio.sleep(delay)

            except httpx.HTTPError as e:
                self._errors_encountered += 1
                raise HostServiceConnectionError(
                    f"HTTP error for POST {endpoint}: {str(e)}", self.get_service_name()
                ) from e

            except Exception as e:
                self._errors_encountered += 1
                raise HostServiceError(
                    f"Unexpected error for POST {endpoint}: {str(e)}",
                    self.get_service_name(),
                ) from e

        # This should never be reached as all paths above raise exceptions
        raise HostServiceError(
            f"Unexpected control flow in POST {endpoint}", self.get_service_name()
        )

    async def _call_host_service_get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Standardized GET requests with retry logic and error handling.

        Args:
            endpoint: API endpoint (e.g., "/status")
            params: Query parameters as dictionary

        Returns:
            JSON response as dictionary

        Raises:
            HostServiceConnectionError: For connection failures
            HostServiceTimeoutError: For timeout failures
            HostServiceError: For other service failures
        """
        if not self._http_client:
            raise HostServiceError(
                "HTTP client not initialized. Use async context manager.",
                self.get_service_name(),
            )

        url = f"{self.get_base_url()}{endpoint}"

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._http_client.get(
                    url, params=params or {}, timeout=self.timeout
                )

                # Handle HTTP errors
                response.raise_for_status()

                # Update statistics
                self._requests_made += 1
                self._last_request_time = datetime.now(timezone.utc)

                logger.debug(
                    f"{self.get_service_name()}: GET {endpoint} successful "
                    f"(status={response.status_code})"
                )

                return response.json()

            except httpx.TimeoutException as e:
                if attempt == self.max_retries:
                    self._errors_encountered += 1
                    raise HostServiceTimeoutError(
                        f"Request timed out after {attempt + 1} attempts: {str(e)}",
                        self.get_service_name(),
                    ) from e

                # Exponential backoff
                delay = 2**attempt
                logger.warning(
                    f"{self.get_service_name()}: GET {endpoint} timeout "
                    f"(attempt {attempt + 1}/{self.max_retries + 1}), retrying in {delay}s"
                )
                await asyncio.sleep(delay)

            except httpx.HTTPError as e:
                self._errors_encountered += 1
                raise HostServiceConnectionError(
                    f"HTTP error for GET {endpoint}: {str(e)}", self.get_service_name()
                ) from e

            except Exception as e:
                self._errors_encountered += 1
                raise HostServiceError(
                    f"Unexpected error for GET {endpoint}: {str(e)}",
                    self.get_service_name(),
                ) from e

        # This should never be reached as all paths above raise exceptions
        raise HostServiceError(
            f"Unexpected control flow in GET {endpoint}", self.get_service_name()
        )

    # Health Check Interface
    async def check_health(self, timeout: Optional[int] = None) -> dict[str, Any]:
        """
        Perform health check with configurable timeout.

        Args:
            timeout: Custom timeout for health check (uses default if None)

        Returns:
            Health check response dictionary

        Raises:
            HostServiceConnectionError: If health check fails
            HostServiceTimeoutError: If health check times out
        """
        original_timeout = self.timeout

        try:
            if timeout is not None:
                self.timeout = timeout

            endpoint = await self.get_health_check_endpoint()
            result = await self._call_host_service_get(endpoint)

            logger.info(f"{self.get_service_name()}: Health check passed")
            return result

        finally:
            self.timeout = original_timeout

    # Statistics and Monitoring
    def get_request_count(self) -> int:
        """Return total number of requests made."""
        return self._requests_made

    def get_error_count(self) -> int:
        """Return total number of errors encountered."""
        return self._errors_encountered

    def get_statistics(self) -> dict[str, Any]:
        """
        Return comprehensive statistics dictionary.

        Returns:
            Dictionary with request statistics and performance metrics
        """
        return {
            "requests_made": self._requests_made,
            "errors_encountered": self._errors_encountered,
            "last_request_time": (
                self._last_request_time.isoformat() if self._last_request_time else None
            ),
            "service_name": self.get_service_name(),
            "base_url": self.get_base_url(),
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "connection_pool_limit": self.config.connection_pool_limit,
        }
