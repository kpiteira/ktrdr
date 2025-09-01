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
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
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

    # Enhanced configuration options for TASK-1.5b
    health_check_interval: int = 300  # 5 minutes default
    health_check_timeout: int = 10  # Dedicated health check timeout
    enable_metrics_collection: bool = True  # Enable detailed metrics
    enable_request_tracing: bool = False  # Enable request tracing
    connection_keep_alive: bool = True  # Keep connections alive
    max_connection_age: int = 3600  # 1 hour max connection age


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

        # Enhanced metrics for TASK-1.5b
        self._start_time = time.time()
        self._response_times: list[float] = []
        self._requests_by_status_code: dict[int, int] = defaultdict(int)
        self._requests_by_endpoint: dict[str, int] = defaultdict(int)
        self._total_bytes_sent = 0
        self._total_bytes_received = 0

        # Health check caching
        self._health_check_cache: Optional[dict[str, Any]] = None
        self._health_check_cache_time: Optional[float] = None

        # Request tracing
        self._trace_data: dict[str, dict[str, Any]] = {}

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
    async def check_health(
        self, timeout: Optional[int] = None, cache_ttl: int = 0
    ) -> dict[str, Any]:
        """
        Perform health check with configurable timeout and caching.

        Args:
            timeout: Custom timeout for health check (uses default if None)
            cache_ttl: Cache TTL in seconds (0 = no cache, default behavior)

        Returns:
            Health check response dictionary

        Raises:
            HostServiceConnectionError: If health check fails
            HostServiceTimeoutError: If health check times out
        """
        # Check cache first if TTL > 0
        if cache_ttl > 0 and self._health_check_cache is not None:
            cache_age = time.time() - (self._health_check_cache_time or 0)
            if cache_age < cache_ttl:
                logger.debug(
                    f"{self.get_service_name()}: Using cached health check result"
                )
                return self._health_check_cache.copy()

        original_timeout = self.timeout

        try:
            if timeout is not None:
                self.timeout = timeout

            endpoint = await self.get_health_check_endpoint()
            result = await self._call_host_service_get(endpoint)

            # Cache result if TTL > 0
            if cache_ttl > 0:
                self._health_check_cache = result.copy()
                self._health_check_cache_time = time.time()

            logger.info(f"{self.get_service_name()}: Health check passed")
            return result

        finally:
            self.timeout = original_timeout

    def clear_health_check_cache(self) -> None:
        """Clear the health check cache."""
        self._health_check_cache = None
        self._health_check_cache_time = None
        logger.debug(f"{self.get_service_name()}: Health check cache cleared")

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

    # Enhanced Metrics for TASK-1.5b
    def get_detailed_metrics(self) -> dict[str, Any]:
        """Return detailed metrics including response times and bandwidth."""
        avg_response_time = (
            sum(self._response_times) / len(self._response_times)
            if self._response_times
            else 0
        )

        return {
            "average_response_time": avg_response_time,
            "fastest_response_time": (
                min(self._response_times) if self._response_times else 0
            ),
            "slowest_response_time": (
                max(self._response_times) if self._response_times else 0
            ),
            "total_bytes_sent": self._total_bytes_sent,
            "total_bytes_received": self._total_bytes_received,
            "requests_by_status_code": dict(self._requests_by_status_code),
            "requests_by_endpoint": dict(self._requests_by_endpoint),
        }

    def get_performance_summary(self) -> dict[str, Any]:
        """Return performance summary for monitoring."""
        uptime = time.time() - self._start_time
        requests_per_second = self._requests_made / uptime if uptime > 0 else 0
        error_rate = (
            (self._errors_encountered / self._requests_made * 100)
            if self._requests_made > 0
            else 0
        )

        avg_response_time = (
            sum(self._response_times) / len(self._response_times)
            if self._response_times
            else 0
        )

        return {
            "uptime": uptime,
            "requests_per_second": requests_per_second,
            "error_rate": error_rate,
            "average_response_time": avg_response_time,
            "connection_pool_utilization": 0,  # Placeholder - would need httpx pool stats
        }

    def reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        self._requests_made = 0
        self._errors_encountered = 0
        self._last_request_time = None
        self._start_time = time.time()
        self._response_times.clear()
        self._requests_by_status_code.clear()
        self._requests_by_endpoint.clear()
        self._total_bytes_sent = 0
        self._total_bytes_received = 0
        self._trace_data.clear()
        logger.info(f"{self.get_service_name()}: Metrics reset")

    def get_connection_pool_stats(self) -> dict[str, Any]:
        """Return connection pool statistics."""
        # Placeholder implementation - would need access to httpx client internals
        return {
            "active_connections": 0,
            "idle_connections": 0,
            "total_connections": 0,
            "connection_pool_limit": self.config.connection_pool_limit,
            "connections_created": 0,
            "connections_closed": 0,
        }

    def get_memory_usage_stats(self) -> dict[str, Any]:
        """Return memory usage statistics."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return {
            "current_memory_mb": memory_info.rss / 1024 / 1024,
            "peak_memory_mb": memory_info.vms / 1024 / 1024,
            "connection_pool_memory_mb": 0,  # Would need httpx pool memory stats
            "request_cache_memory_mb": 0,  # Would need cache memory calculation
            "metrics_memory_mb": 0,  # Would need metrics memory calculation
        }

    # Request Tracing for TASK-1.5b
    async def _call_host_service_post_with_tracing(
        self, endpoint: str, data: dict[str, Any]
    ) -> str:
        """POST request with tracing support."""
        trace_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            await self._call_host_service_post(endpoint, data)
            end_time = time.time()

            # Store trace data
            self._trace_data[trace_id] = {
                "request_id": trace_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration_ms": (end_time - start_time) * 1000,
                "endpoint": endpoint,
                "method": "POST",
                "success": True,
            }

            return trace_id

        except Exception as e:
            end_time = time.time()
            self._trace_data[trace_id] = {
                "request_id": trace_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration_ms": (end_time - start_time) * 1000,
                "endpoint": endpoint,
                "method": "POST",
                "success": False,
                "error": str(e),
            }
            raise

    def get_trace_data(self, trace_id: str) -> Optional[dict[str, Any]]:
        """Get trace data for a specific request."""
        return self._trace_data.get(trace_id)

    # Performance Benchmarking for TASK-1.5b
    async def run_throughput_benchmark(
        self,
        duration_seconds: int = 5,
        concurrent_requests: int = 10,
        endpoint: str = "/benchmark",
    ) -> dict[str, Any]:
        """Run throughput benchmark."""
        # Placeholder implementation for benchmarking
        return {
            "requests_per_second": 0,
            "average_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "total_requests": 0,
            "failed_requests": 0,
            "duration_seconds": duration_seconds,
        }

    def get_latency_distribution(self) -> dict[str, Any]:
        """Get latency distribution statistics."""
        if not self._response_times:
            return {
                "percentiles": {},
                "histogram": {},
                "min": 0,
                "max": 0,
                "mean": 0,
                "stddev": 0,
            }

        sorted_times = sorted(self._response_times)
        n = len(sorted_times)

        return {
            "percentiles": {
                "p50": sorted_times[int(n * 0.5)],
                "p95": sorted_times[int(n * 0.95)],
                "p99": sorted_times[int(n * 0.99)],
            },
            "histogram": {},  # Would implement histogram buckets
            "min": min(sorted_times),
            "max": max(sorted_times),
            "mean": sum(sorted_times) / n,
            "stddev": 0,  # Would calculate standard deviation
        }

    async def run_stress_test(
        self,
        max_concurrent_requests: int = 100,
        ramp_up_time_seconds: int = 10,
        sustain_time_seconds: int = 30,
        endpoint: str = "/stress",
    ) -> dict[str, Any]:
        """Run stress test."""
        # Placeholder implementation for stress testing
        return {
            "max_concurrent_achieved": 0,
            "requests_per_second_peak": 0,
            "error_rate_under_stress": 0,
            "connection_pool_exhausted": False,
            "memory_pressure_events": 0,
        }
