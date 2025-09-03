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

# Optional dependency import with graceful fallback
try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

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


# Memory management constants
MAX_RESPONSE_TIMES = 1000  # Keep last 1000 response times
MAX_TRACE_DATA = 100  # Keep last 100 traces
MAX_ENDPOINT_STATS = 200  # Keep stats for last 200 endpoints


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

        # Cancellation support - set by calling code before operations
        self._current_cancellation_token: Optional[Any] = None

        # HTTP client and connection pool (initialized in async context)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._connection_pool: Optional[httpx.AsyncClient] = None

        # Statistics and monitoring
        self._requests_made = 0
        self._errors_encountered = 0
        self._last_request_time: Optional[datetime] = None

        # Enhanced metrics for TASK-1.5b (with memory bounds)
        self._start_time = time.time()
        self._response_times: list[float] = []
        self._requests_by_status_code: dict[int, int] = defaultdict(int)
        self._requests_by_endpoint: dict[str, int] = defaultdict(int)
        self._total_bytes_sent = 0
        self._total_bytes_received = 0

        # Health check caching
        self._health_check_cache: Optional[dict[str, Any]] = None
        self._health_check_cache_time: Optional[float] = None

        # Request tracing (with memory bounds)
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

    def _check_cancellation(
        self,
        cancellation_token: Optional[Any],
        operation_description: str = "operation",
    ) -> bool:
        """
        Check if cancellation has been requested.

        Args:
            cancellation_token: Token to check for cancellation
            operation_description: Description of current operation for logging

        Returns:
            True if cancellation was requested, False otherwise

        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        if cancellation_token is None:
            return False

        # Check if token has cancellation method
        is_cancelled = False
        if hasattr(cancellation_token, "is_cancelled_requested"):
            is_cancelled = cancellation_token.is_cancelled_requested
        elif hasattr(cancellation_token, "is_set"):
            is_cancelled = cancellation_token.is_set()
        elif hasattr(cancellation_token, "cancelled"):
            is_cancelled = cancellation_token.cancelled()

        if is_cancelled:
            logger.info(f"🛑 Cancellation requested during {operation_description}")
            # Import here to avoid circular imports
            import asyncio

            raise asyncio.CancelledError(
                f"Operation cancelled during {operation_description}"
            )

        return False

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
        """Cleanup HTTP client and close connections with proper exception handling."""
        if self._http_client:
            try:
                await self._http_client.aclose()
            except Exception as e:
                logger.warning(
                    f"{self.get_service_name()}: Error during connection cleanup: {e}"
                )
            finally:
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
                # Check for cancellation before each attempt
                self._check_cancellation(
                    self._current_cancellation_token,
                    f"POST {endpoint} attempt {attempt + 1}",
                )

                request_start_time = time.time()
                response = await self._http_client.post(
                    url, json=data, timeout=self.timeout
                )

                # Handle HTTP errors
                response.raise_for_status()

                # Update statistics (optimized for performance)
                response_time = time.time() - request_start_time
                self._add_response_time(response_time)
                self._update_request_statistics(response, endpoint, "POST")

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

                # Check for cancellation before retry delay
                self._check_cancellation(
                    self._current_cancellation_token, f"POST {endpoint} retry delay"
                )

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
                # Check for cancellation before each attempt
                self._check_cancellation(
                    self._current_cancellation_token,
                    f"GET {endpoint} attempt {attempt + 1}",
                )

                request_start_time = time.time()
                response = await self._http_client.get(
                    url, params=params or {}, timeout=self.timeout
                )

                # Handle HTTP errors
                response.raise_for_status()

                # Update statistics (optimized for performance)
                response_time = time.time() - request_start_time
                self._add_response_time(response_time)
                self._update_request_statistics(response, endpoint, "GET")

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

                # Check for cancellation before retry delay
                self._check_cancellation(
                    self._current_cancellation_token, f"GET {endpoint} retry delay"
                )

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

    # Helper Methods for Performance and Memory Management
    def _add_response_time(self, time_seconds: float) -> None:
        """Add response time with memory bounds."""
        self._response_times.append(time_seconds)
        if len(self._response_times) > MAX_RESPONSE_TIMES:
            self._response_times.pop(0)

    def _track_endpoint_usage(self, endpoint: str) -> None:
        """Track endpoint usage with memory bounds."""
        self._requests_by_endpoint[endpoint] += 1

        # Prevent unbounded growth
        if len(self._requests_by_endpoint) > MAX_ENDPOINT_STATS:
            # Remove least used endpoints
            sorted_endpoints = sorted(
                self._requests_by_endpoint.items(), key=lambda x: x[1]
            )
            endpoints_to_remove = len(sorted_endpoints) - MAX_ENDPOINT_STATS + 1
            for endpoint_name, _ in sorted_endpoints[:endpoints_to_remove]:
                del self._requests_by_endpoint[endpoint_name]

    def _update_request_statistics(self, response, endpoint: str, method: str) -> None:
        """Update request statistics efficiently."""
        # Basic counters
        self._requests_made += 1
        self._last_request_time = datetime.now(timezone.utc)

        # Track by status code and endpoint (with safe extraction)
        try:
            status_code = getattr(response, "status_code", 200)
            if isinstance(status_code, int):
                self._requests_by_status_code[status_code] += 1
        except (TypeError, AttributeError):
            # Fallback for mock objects or unexpected response types
            self._requests_by_status_code[200] += 1

        self._track_endpoint_usage(endpoint)

        # Track bytes if available
        try:
            if hasattr(response, "num_bytes_downloaded"):
                bytes_downloaded = getattr(response, "num_bytes_downloaded", 0)
                if isinstance(bytes_downloaded, (int, float)):
                    self._total_bytes_received += int(bytes_downloaded)
        except (TypeError, AttributeError):
            pass

        # Estimate content size from response (fallback method)
        try:
            if hasattr(response, "headers") and response.headers:
                content_length = response.headers.get("content-length")
                if content_length and isinstance(content_length, (str, int)):
                    self._total_bytes_received += int(content_length)
        except (ValueError, TypeError, AttributeError):
            pass

    def _add_trace_data(self, trace_id: str, trace_data: dict[str, Any]) -> None:
        """Add trace data with memory bounds."""
        self._trace_data[trace_id] = trace_data

        # Prevent unbounded growth
        if len(self._trace_data) > MAX_TRACE_DATA:
            # Remove oldest traces
            oldest_trace = min(
                self._trace_data.items(), key=lambda x: x[1].get("start_time", 0)
            )
            del self._trace_data[oldest_trace[0]]

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
        """Return memory usage statistics with graceful psutil handling."""
        if psutil is None:
            return {
                "error": "psutil not available",
                "current_memory_mb": 0,
                "peak_memory_mb": 0,
                "connection_pool_memory_mb": 0,
                "request_cache_memory_mb": 0,
                "metrics_memory_mb": 0,
            }

        try:
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            return {
                "current_memory_mb": memory_info.rss / 1024 / 1024,
                "peak_memory_mb": memory_info.vms / 1024 / 1024,
                "connection_pool_memory_mb": 0,  # Would need httpx pool memory stats
                "request_cache_memory_mb": 0,  # Would need cache memory calculation
                "metrics_memory_mb": 0,  # Would need metrics memory calculation
            }
        except Exception as e:
            logger.warning(f"Error getting memory stats: {e}")
            return {
                "error": f"Failed to get memory stats: {e}",
                "current_memory_mb": 0,
                "peak_memory_mb": 0,
                "connection_pool_memory_mb": 0,
                "request_cache_memory_mb": 0,
                "metrics_memory_mb": 0,
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

            # Store trace data with memory bounds
            trace_data = {
                "request_id": trace_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration_ms": (end_time - start_time) * 1000,
                "endpoint": endpoint,
                "method": "POST",
                "success": True,
            }
            self._add_trace_data(trace_id, trace_data)

            return trace_id

        except Exception as e:
            end_time = time.time()
            trace_data = {
                "request_id": trace_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration_ms": (end_time - start_time) * 1000,
                "endpoint": endpoint,
                "method": "POST",
                "success": False,
                "error": str(e),
            }
            self._add_trace_data(trace_id, trace_data)
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
        """Run throughput benchmark.

        WARNING: This is a placeholder implementation returning zeros.
        Use get_performance_summary() for basic metrics until fully implemented.
        """
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
        """Run stress test.

        WARNING: This is a placeholder implementation returning zeros.
        Use get_detailed_metrics() for current performance data until fully implemented.
        """
        return {
            "max_concurrent_achieved": 0,
            "requests_per_second_peak": 0,
            "error_rate_under_stress": 0,
            "connection_pool_exhausted": False,
            "memory_pressure_events": 0,
        }
