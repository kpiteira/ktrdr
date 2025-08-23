"""UnifiedAsyncCLI base class for connection reuse and performance optimization."""

import asyncio
import httpx
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class UnifiedAsyncCLIError(Exception):
    """Exception raised by UnifiedAsyncCLI."""

    def __init__(
        self,
        message: str,
        error_code: str = "CLI-Error",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class UnifiedAsyncCLI:
    """
    UnifiedAsyncCLI base class for eliminating per-command event loop and HTTP client creation overhead.

    This class provides:
    - Single HTTP client instance reused across commands
    - Proper async context manager lifecycle
    - Thread-safe operation
    - Configuration injection for timeouts and retries
    - Graceful error handling and resource cleanup
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the UnifiedAsyncCLI.

        Args:
            base_url: Base URL of the API server
            timeout: Default timeout in seconds for requests
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Delay between retry attempts in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry - initialize HTTP client."""
        if self._http_client is not None:
            raise UnifiedAsyncCLIError(
                "UnifiedAsyncCLI is already initialized",
                error_code="CLI-AlreadyInitialized",
            )

        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        logger.debug("UnifiedAsyncCLI HTTP client initialized")
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
            logger.debug("UnifiedAsyncCLI HTTP client closed")
        return False  # Don't suppress exceptions

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Dict[str, Any]:
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
            UnifiedAsyncCLIError: For various error conditions
        """
        if self._http_client is None:
            raise UnifiedAsyncCLIError(
                "UnifiedAsyncCLI is not properly initialized. Use async context manager.",
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
                        return response.json()
                    except Exception as e:
                        raise UnifiedAsyncCLIError(
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

                    raise UnifiedAsyncCLIError(
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

                        raise UnifiedAsyncCLIError(
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
                    raise UnifiedAsyncCLIError(
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
                    raise UnifiedAsyncCLIError(
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

            except UnifiedAsyncCLIError:
                # Re-raise our own exceptions without wrapping
                raise
            except Exception as e:
                raise UnifiedAsyncCLIError(
                    f"Unexpected error making API request: {str(e)}",
                    error_code="CLI-UnexpectedError",
                    details={
                        "url": url,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                ) from e

        # Should never reach here due to the loop structure, but needed for type checking
        raise UnifiedAsyncCLIError(
            "Unexpected code path reached",
            error_code="CLI-InternalError",
            details={"url": url},
        )
