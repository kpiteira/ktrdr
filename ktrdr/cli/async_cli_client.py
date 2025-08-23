"""AsyncCLIClient base class for connection reuse and performance optimization."""

import asyncio
import logging
from typing import Any, Optional

import httpx

from ..config.settings import get_cli_settings

logger = logging.getLogger(__name__)


class AsyncCLIClientError(Exception):
    """Exception raised by AsyncCLIClient."""

    def __init__(
        self,
        message: str,
        error_code: str = "CLI-Error",
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class AsyncCLIClient:
    """
    AsyncCLIClient base class for eliminating per-command event loop and HTTP client creation overhead.

    This class provides:
    - Single HTTP client instance reused across commands
    - Proper async context manager lifecycle
    - Thread-safe operation
    - Configuration injection for timeouts and retries
    - Graceful error handling and resource cleanup
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ):
        """
        Initialize the AsyncCLIClient.

        Args:
            base_url: Base URL of the API server (uses config default if None)
            timeout: Default timeout in seconds for requests (uses config default if None)
            max_retries: Maximum number of retry attempts for failed requests (uses config default if None)
            retry_delay: Delay between retry attempts in seconds (uses config default if None)
        """
        # Load configuration
        cli_settings = get_cli_settings()

        # Use provided values or fall back to configuration
        self.base_url = (base_url or cli_settings.base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else cli_settings.timeout
        self.max_retries = (
            max_retries if max_retries is not None else cli_settings.max_retries
        )
        self.retry_delay = (
            retry_delay if retry_delay is not None else cli_settings.retry_delay
        )
        self._http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AsyncCLIClient":
        """Async context manager entry - initialize HTTP client."""
        if self._http_client is not None:
            raise AsyncCLIClientError(
                "AsyncCLIClient is already initialized",
                error_code="CLI-AlreadyInitialized",
            )

        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        logger.debug("AsyncCLIClient HTTP client initialized")
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> Optional[bool]:
        """Async context manager exit - cleanup HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            logger.debug("AsyncCLIClient HTTP client closed")
        return False  # Don't suppress exceptions

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Make an HTTP request with error handling and retries.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path
            json_data: JSON payload for request body
            params: Query parameters
            timeout: Custom timeout for this request
            retries: Custom retry count for this request

        Returns:
            Parsed JSON response as dictionary

        Raises:
            AsyncCLIClientError: For various error conditions
        """
        if self._http_client is None:
            raise AsyncCLIClientError(
                "AsyncCLIClient is not properly initialized. Use async context manager.",
                error_code="CLI-NotInitialized",
            )

        url = f"{self.base_url}{endpoint}"
        request_timeout = timeout or self.timeout
        max_attempts = (retries if retries is not None else self.max_retries) + 1

        logger.debug(f"Making {method} request to {url}")

        for attempt in range(max_attempts):
            try:
                response = await self._http_client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                    timeout=request_timeout,
                )

                if 200 <= response.status_code < 300:
                    # Success
                    try:
                        return response.json()  # type: ignore[no-any-return]
                    except Exception as e:
                        raise AsyncCLIClientError(
                            "Invalid JSON response from API",
                            error_code="CLI-InvalidResponse",
                            details={
                                "url": url,
                                "status_code": response.status_code,
                                "response_text": response.text[:500],
                                "error": str(e),
                            },
                        ) from e

                elif 400 <= response.status_code < 500:
                    # Client error - don't retry
                    try:
                        error_detail = response.json()
                    except Exception:
                        error_detail = {"message": response.text}

                    raise AsyncCLIClientError(
                        f"API request failed: {error_detail.get('message', 'Unknown error')}",
                        error_code=f"CLI-{response.status_code}",
                        details={
                            "url": url,
                            "status_code": response.status_code,
                            "error_detail": error_detail,
                        },
                    )

                else:
                    # Server error - might retry
                    error_msg = f"API server error (HTTP {response.status_code})"
                    if attempt == max_attempts - 1:
                        # Last attempt - raise error
                        try:
                            error_detail = response.json()
                        except Exception:
                            error_detail = {"message": response.text}

                        raise AsyncCLIClientError(
                            error_msg,
                            error_code=f"CLI-ServerError-{response.status_code}",
                            details={
                                "url": url,
                                "status_code": response.status_code,
                                "error_detail": error_detail,
                                "attempts": max_attempts,
                            },
                        )
                    else:
                        # Retry after delay
                        logger.warning(
                            f"{error_msg}, retrying in {self.retry_delay}s (attempt {attempt + 1}/{max_attempts})"
                        )
                        await asyncio.sleep(self.retry_delay)
                        continue

            except httpx.ConnectError as e:
                if attempt == max_attempts - 1:
                    raise AsyncCLIClientError(
                        "Could not connect to API server",
                        error_code="CLI-ConnectionError",
                        details={
                            "url": url,
                            "base_url": self.base_url,
                            "error": str(e),
                            "suggestion": "Make sure the API server is running at the configured URL",
                        },
                    ) from e
                else:
                    logger.warning(
                        f"Connection failed, retrying in {self.retry_delay}s (attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(self.retry_delay)
                    continue

            except httpx.TimeoutException as e:
                if attempt == max_attempts - 1:
                    raise AsyncCLIClientError(
                        f"Request timed out after {request_timeout}s",
                        error_code="CLI-TimeoutError",
                        details={
                            "url": url,
                            "timeout": request_timeout,
                            "error": str(e),
                        },
                    ) from e
                else:
                    logger.warning(
                        f"Request timed out, retrying in {self.retry_delay}s (attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(self.retry_delay)
                    continue

            except AsyncCLIClientError:
                # Re-raise our own exceptions without wrapping
                raise
            except Exception as e:
                raise AsyncCLIClientError(
                    f"Unexpected error making API request: {str(e)}",
                    error_code="CLI-UnexpectedError",
                    details={
                        "url": url,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                ) from e

        # Should never reach here due to the loop structure, but needed for type checking
        raise AsyncCLIClientError(
            "Unexpected code path reached",
            error_code="CLI-InternalError",
            details={"url": url},
        )
