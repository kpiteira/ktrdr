"""Asynchronous HTTP client for CLI commands.

This module provides AsyncCLIClient, an asynchronous HTTP client that uses
httpx.AsyncClient under the hood. It's designed for CLI commands that benefit
from async patterns, such as operation polling and connection reuse.
"""

import asyncio
from typing import Any, Callable, Optional, Protocol

import httpx

from ktrdr.cli.client.core import (
    ClientConfig,
    calculate_backoff,
    parse_response,
    resolve_url,
    should_retry,
)
from ktrdr.cli.client.errors import ConnectionError, TimeoutError


class OperationAdapter(Protocol):
    """Protocol for operation adapters used by execute_operation.

    This matches the existing adapter pattern used by TrainingAdapter
    and BacktestAdapter.
    """

    def get_start_endpoint(self) -> str:
        """Return endpoint to start the operation."""
        ...

    def get_start_payload(self) -> dict:
        """Return payload for starting the operation."""
        ...

    def extract_operation_id(self, response: dict) -> str:
        """Extract operation ID from start response."""
        ...

    def get_status_endpoint(self, operation_id: str) -> str:
        """Return endpoint to check operation status."""
        ...

    def process_result(self, status: dict) -> dict:
        """Process final result from operation status."""
        ...


class AsyncCLIClient:
    """Asynchronous HTTP client for CLI commands.

    Uses httpx.AsyncClient for HTTP operations with automatic retry handling,
    exponential backoff, and consistent error handling via the shared
    core module.

    Usage:
        async with AsyncCLIClient() as client:
            result = await client.get("/symbols")

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
        """Initialize the async client.

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
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AsyncCLIClient":
        """Enter async context manager, creating httpx.AsyncClient.

        Returns:
            Self with active HTTP client
        """
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit async context manager, closing httpx.AsyncClient."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _make_request(
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
                "Client not initialized. Use 'async with AsyncCLIClient() as client:'"
            )

        url = f"{self.config.base_url}{endpoint}"
        retries = max_retries if max_retries is not None else self.config.max_retries
        attempt = 0

        while True:
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    timeout=timeout or self.config.timeout,
                )

                # Check if we should retry on server error
                if should_retry(response.status_code, attempt, retries):
                    delay = calculate_backoff(attempt, self.config.retry_delay)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue

                # Parse response (raises APIError on error status codes)
                return parse_response(response)

            except httpx.ConnectError as e:
                if attempt < retries:
                    delay = calculate_backoff(attempt, self.config.retry_delay)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise ConnectionError(
                    message=f"Could not connect to API at {url}",
                    details={"url": url, "error": str(e)},
                ) from e

            except httpx.TimeoutException as e:
                if attempt < retries:
                    delay = calculate_backoff(attempt, self.config.retry_delay)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise TimeoutError(
                    message=f"Request timed out after {timeout or self.config.timeout}s",
                    details={"url": url, "timeout": timeout or self.config.timeout},
                ) from e

    async def get(
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
        return await self._make_request("GET", endpoint, params=params, timeout=timeout)

    async def post(
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
        return await self._make_request(
            "POST", endpoint, json=json, params=params, timeout=timeout
        )

    async def delete(
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
        return await self._make_request(
            "DELETE", endpoint, json=json, params=params, timeout=timeout
        )

    async def health_check(self) -> bool:
        """Check if API server is reachable.

        Makes a simple request to verify connectivity. Does not raise
        exceptions - returns False on any error.

        Returns:
            True if server responds successfully, False otherwise
        """
        try:
            # Use /health endpoint with no retries and short timeout
            await self._make_request(
                "GET",
                "/health",
                timeout=5.0,
                max_retries=0,
            )
            return True
        except Exception:
            return False

    async def execute_operation(
        self,
        adapter: OperationAdapter,
        on_progress: Optional[Callable[[int, str], None]] = None,
        poll_interval: float = 0.3,
    ) -> dict[str, Any]:
        """Execute a long-running operation with polling.

        This method starts an operation, polls for status, invokes progress
        callbacks, and returns the final result. Actual implementation
        is deferred to Task 1.5 (operations module).

        Args:
            adapter: Operation adapter defining endpoints and payload
            on_progress: Optional callback invoked with (progress_pct, message)
            poll_interval: Seconds between status polls

        Returns:
            Final operation result from adapter.process_result()

        Note:
            This is a placeholder that will be implemented in Task 1.5.
            Currently raises NotImplementedError.
        """
        raise NotImplementedError(
            "execute_operation will be implemented in Task 1.5 (operations module)"
        )
