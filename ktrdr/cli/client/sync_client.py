"""Synchronous HTTP client for CLI commands.

This module provides SyncCLIClient, a synchronous HTTP client that uses
httpx.Client under the hood. It's designed for simple request/response
CLI commands that don't require async patterns.
"""

import time
from typing import Any, Optional

import httpx

from ktrdr.cli.client.core import (
    ClientConfig,
    calculate_backoff,
    parse_response,
    resolve_url,
    should_retry,
)
from ktrdr.cli.client.errors import ConnectionError, TimeoutError


class SyncCLIClient:
    """Synchronous HTTP client for CLI commands.

    Uses httpx.Client for HTTP operations with automatic retry handling,
    exponential backoff, and consistent error handling via the shared
    core module.

    Usage:
        with SyncCLIClient() as client:
            result = client.get("/indicators")

    Attributes:
        config: Immutable client configuration
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize the sync client.

        Args:
            base_url: Explicit base URL (overrides --url flag and config default)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for server errors
            retry_delay: Base delay between retries in seconds
        """
        effective_url = resolve_url(base_url)
        self.config = ClientConfig(
            base_url=effective_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        self._client: Optional[httpx.Client] = None

    def __enter__(self) -> "SyncCLIClient":
        """Enter context manager, creating httpx.Client.

        Returns:
            Self with active HTTP client
        """
        self._client = httpx.Client(timeout=self.config.timeout)
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit context manager, closing httpx.Client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> dict[str, Any]:
        """Make HTTP request with retry handling.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path (appended to base_url)
            json: JSON request body
            params: Query parameters
            timeout: Override default timeout for this request
            max_retries: Override default max_retries for this request

        Returns:
            Parsed JSON response

        Raises:
            ConnectionError: Cannot connect to server
            TimeoutError: Request exceeded timeout
            APIError: Server returned error response
        """
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'with SyncCLIClient() as client:'"
            )

        url = f"{self.config.base_url}{endpoint}"
        retries = max_retries if max_retries is not None else self.config.max_retries
        attempt = 0

        while True:
            try:
                response = self._client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    timeout=timeout or self.config.timeout,
                )

                # Check if we should retry on server error
                if should_retry(response.status_code, attempt, retries):
                    delay = calculate_backoff(attempt, self.config.retry_delay)
                    time.sleep(delay)
                    attempt += 1
                    continue

                # Parse response (raises APIError on error status codes)
                return parse_response(response)

            except httpx.ConnectError as e:
                if attempt < retries:
                    delay = calculate_backoff(attempt, self.config.retry_delay)
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise ConnectionError(
                    message=f"Could not connect to API at {url}",
                    details={"url": url, "error": str(e)},
                ) from e

            except httpx.TimeoutException as e:
                if attempt < retries:
                    delay = calculate_backoff(attempt, self.config.retry_delay)
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise TimeoutError(
                    message=f"Request timed out after {timeout or self.config.timeout}s",
                    details={"url": url, "timeout": timeout or self.config.timeout},
                ) from e

    def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Make GET request.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            timeout: Override default timeout

        Returns:
            Parsed JSON response
        """
        return self._make_request("GET", endpoint, params=params, timeout=timeout)

    def post(
        self,
        endpoint: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Make POST request.

        Args:
            endpoint: API endpoint path
            json: JSON request body
            params: Query parameters
            timeout: Override default timeout

        Returns:
            Parsed JSON response
        """
        return self._make_request(
            "POST", endpoint, json=json, params=params, timeout=timeout
        )

    def delete(
        self,
        endpoint: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Make DELETE request.

        Args:
            endpoint: API endpoint path
            json: JSON request body
            params: Query parameters
            timeout: Override default timeout

        Returns:
            Parsed JSON response
        """
        return self._make_request(
            "DELETE", endpoint, json=json, params=params, timeout=timeout
        )

    def health_check(self) -> bool:
        """Check if API server is reachable.

        Makes a simple request to verify connectivity. Does not raise
        exceptions - returns False on any error.

        Returns:
            True if server responds successfully, False otherwise
        """
        try:
            # Use /health endpoint with no retries and short timeout
            self._make_request(
                "GET",
                "/health",
                timeout=5.0,
                max_retries=0,
            )
            return True
        except Exception:
            return False
