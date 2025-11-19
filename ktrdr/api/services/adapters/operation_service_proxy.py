"""
OperationServiceProxy - HTTP client for remote OperationsService instances.

This proxy provides a unified HTTP interface for querying OperationsService
on host services. It's shared across all service adapters (training, data, etc.)
and handles retries, timeouts, and error translation.

Architecture Pattern:
- Shared HTTP client (one instance used by multiple adapters)
- Async context manager for resource cleanup
- Error translation (HTTP errors → Python exceptions)
- Cursor-based incremental metrics reading

Usage:
    # As context manager (recommended)
    async with OperationServiceProxy("http://localhost:5002") as proxy:
        operation = await proxy.get_operation("op_123")

    # Manual lifecycle
    proxy = OperationServiceProxy("http://localhost:5002")
    try:
        operation = await proxy.get_operation("op_123")
    finally:
        await proxy.close()
"""

from typing import Any, Optional

import httpx

from ktrdr.logging import get_logger

logger = get_logger(__name__)


class OperationServiceProxy:
    """
    HTTP client for querying OperationsService on host services.

    This proxy wraps httpx.AsyncClient to provide a clean interface for
    operations queries. It's designed to be shared across multiple adapters
    (training, data, backtesting) that need to query operations on host services.

    Key Features:
    - Async context manager protocol
    - Cursor-based incremental metrics
    - Proper error handling (404 → KeyError, timeouts, connection errors)
    - Lazy client initialization
    - Thread-safe HTTP connection pooling

    Endpoints:
    - GET /api/v1/operations/{operation_id}?force_refresh=bool
    - GET /api/v1/operations/{operation_id}/metrics?cursor=int
    - DELETE /api/v1/operations/{operation_id}/cancel
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize proxy with host service URL.

        Args:
            base_url: Base URL of host service (e.g., "http://localhost:5002")
            timeout: Request timeout in seconds (default: 30.0)
            max_retries: Maximum retry attempts for failed requests (default: 3)
        """
        # Strip trailing slash for consistent URL construction
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # HTTP client (initialized lazily)
        self._client: Optional[httpx.AsyncClient] = None

        logger.debug(f"OperationServiceProxy initialized: base_url={self.base_url}")

    def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client (lazy initialization).

        Returns:
            Initialized httpx.AsyncClient instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=20,  # Connection pool size
                    max_keepalive_connections=10,
                ),
            )
        return self._client

    async def get_operation(
        self,
        operation_id: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Get operation information from host service.

        Args:
            operation_id: Operation identifier
            force_refresh: Force cache bypass on host service (default: False)

        Returns:
            dict: Operation data from host service

        Raises:
            KeyError: If operation not found (HTTP 404)
            httpx.ConnectError: If connection to host service fails
            httpx.TimeoutException: If request times out
        """
        url = f"{self.base_url}/api/v1/operations/{operation_id}"
        params = {}
        if force_refresh:
            params["force_refresh"] = force_refresh

        logger.debug(
            f"GET operation: operation_id={operation_id}, force_refresh={force_refresh}"
        )

        client = self._get_client()

        try:
            response = await client.get(url, params=params)

            # Handle 404 -> KeyError
            if response.status_code == 404:
                logger.warning(f"Operation not found: {operation_id}")
                raise KeyError(f"Operation not found: {operation_id}")

            # Raise for other HTTP errors
            response.raise_for_status()

            # TASK 3.1: Unwrap response - host service returns {success, data}
            # but backend expects just the operation object
            response_data = response.json()
            if isinstance(response_data, dict) and "data" in response_data:
                return response_data["data"]
            return response_data  # Fallback for non-wrapped responses

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying operation {operation_id}: {e}")
            raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Connection error querying operation {operation_id}: {e}")
            raise

    async def get_metrics(
        self,
        operation_id: str,
        cursor: int = 0,
    ) -> tuple[list[dict], int]:
        """
        Get incremental metrics from host service.

        Args:
            operation_id: Operation identifier
            cursor: Position in metrics history (0 = from beginning)

        Returns:
            tuple: (metrics_list, new_cursor)
                - metrics_list: List of new metrics since cursor
                - new_cursor: New cursor position for next query

        Raises:
            KeyError: If operation not found (HTTP 404)
            httpx.ConnectError: If connection to host service fails
            httpx.TimeoutException: If request times out
        """
        url = f"{self.base_url}/api/v1/operations/{operation_id}/metrics"
        params = {"cursor": cursor}

        logger.debug(f"GET metrics: operation_id={operation_id}, cursor={cursor}")

        client = self._get_client()

        try:
            response = await client.get(url, params=params)

            # Handle 404 -> KeyError
            if response.status_code == 404:
                logger.warning(f"Operation not found: {operation_id}")
                raise KeyError(f"Operation not found: {operation_id}")

            # Raise for other HTTP errors
            response.raise_for_status()

            # TASK 3.1: Unwrap response - host service returns {success, data}
            response_json = response.json()
            if isinstance(response_json, dict) and "data" in response_json:
                data = response_json["data"]
            else:
                data = response_json

            metrics = data.get("metrics", [])
            new_cursor = data.get("new_cursor", cursor)

            logger.debug(f"Received {len(metrics)} metrics, new cursor: {new_cursor}")

            return metrics, new_cursor

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying metrics for {operation_id}: {e}")
            raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Connection error querying metrics for {operation_id}: {e}")
            raise

    async def cancel_operation(
        self,
        operation_id: str,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Cancel an operation on the host service.

        Args:
            operation_id: Operation identifier on host service
            reason: Optional cancellation reason

        Returns:
            dict: Cancellation result from host service

        Raises:
            KeyError: If operation not found (HTTP 404)
            httpx.ConnectError: If connection to host service fails
            httpx.TimeoutException: If request times out
        """
        url = f"{self.base_url}/api/v1/operations/{operation_id}/cancel"

        logger.debug(f"DELETE operation: operation_id={operation_id}, reason={reason}")

        client = self._get_client()

        try:
            # httpx DELETE doesn't support json= parameter, but we can pass reason as query param
            # or use content= with manual JSON serialization if body is needed
            # For now, pass reason as query parameter
            params = {}
            if reason:
                params["reason"] = reason

            response = await client.delete(url, params=params)

            # Handle 404 -> KeyError
            if response.status_code == 404:
                logger.warning(f"Operation not found: {operation_id}")
                raise KeyError(f"Operation not found: {operation_id}")

            # Raise for other HTTP errors
            response.raise_for_status()

            # Unwrap response
            response_data = response.json()
            if isinstance(response_data, dict) and "data" in response_data:
                return response_data["data"]
            return response_data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error cancelling operation {operation_id}: {e}")
            raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Connection error cancelling operation {operation_id}: {e}")
            raise

    async def get_operation_state(
        self,
        operation_id: str,
    ) -> dict[str, Any]:
        """
        Get complete operation state from worker (Task 3.8).

        Queries the worker's /api/v1/operations/{operation_id}/state endpoint to
        retrieve cached checkpoint state. Returns ~1KB JSON metadata with artifact
        PATHS (not bytes), leveraging shared filesystem for artifact access.

        This method is called by OperationsService._get_operation_state() when creating
        cancellation checkpoints in distributed architecture.

        Args:
            operation_id: Operation identifier on worker

        Returns:
            dict: Complete state including checkpoint data and artifact paths.
                  Returns empty dict {} on any error (graceful fallback).

        Example:
            >>> async with OperationServiceProxy("http://localhost:5003") as proxy:
            ...     state = await proxy.get_operation_state("op_backtest_123")
            ...     print(state["checkpoint_data"]["current_bar_index"])  # 5000
            ...     print(state["artifacts"]["model.pt"])  # "data/checkpoints/.../model.pt"
        """
        url = f"{self.base_url}/api/v1/operations/{operation_id}/state"

        logger.debug(f"GET operation state: operation_id={operation_id}")

        client = self._get_client()

        try:
            response = await client.get(url)

            # Handle 404 -> return empty dict (graceful fallback)
            if response.status_code == 404:
                logger.debug(
                    f"Operation not found (returning empty state): {operation_id}"
                )
                return {}

            # Raise for other HTTP errors
            response.raise_for_status()

            # Unwrap response - worker returns {success, state}
            response_data = response.json()
            if isinstance(response_data, dict) and "state" in response_data:
                return response_data["state"]
            return response_data  # Fallback

        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error querying state for {operation_id}: {e}")
            return {}  # Graceful fallback
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Connection error querying state for {operation_id}: {e}")
            return {}  # Graceful fallback
        except Exception as e:
            logger.warning(f"Unexpected error querying state for {operation_id}: {e}")
            return {}  # Graceful fallback

    async def close(self) -> None:
        """
        Close HTTP client and cleanup resources.

        This method is idempotent - can be called multiple times safely.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("OperationServiceProxy closed")

    # Async context manager protocol

    async def __aenter__(self):
        """Enter async context manager."""
        # Initialize client
        self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager and cleanup resources."""
        await self.close()
        return False  # Don't suppress exceptions
