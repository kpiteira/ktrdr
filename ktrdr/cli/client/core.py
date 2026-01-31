"""Core shared logic for CLI HTTP clients.

This module contains pure functions and configuration that are shared
between SyncCLIClient and AsyncCLIClient. It handles URL resolution,
retry policy, backoff calculation, and response parsing.
"""

import random
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from ktrdr.cli.client.errors import APIError
from ktrdr.cli.ib_diagnosis import (
    detect_ib_issue_from_api_response,
    should_show_ib_diagnosis,
)
from ktrdr.config.settings import get_api_base_url


@dataclass(frozen=True)
class ClientConfig:
    """Immutable configuration for CLI client instances.

    Attributes:
        base_url: Base URL for API requests (e.g., http://localhost:8000/api/v1)
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts for failed requests
        retry_delay: Base delay between retry attempts in seconds
    """

    base_url: str
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0


def resolve_url(explicit_url: Optional[str] = None) -> str:
    """Resolve the effective API URL based on priority.

    URL resolution priority:
    1. Explicit URL parameter (passed directly to client)
    2. --url flag override (global state from sandbox_detect)
    3. Sandbox detection (from .env.sandbox file)
    4. Config default (from host_services settings)

    For --url flag values that don't include an API path, /api/v1 is
    automatically appended to maintain compatibility with host:port URLs.

    Args:
        explicit_url: Explicitly provided URL, highest priority

    Returns:
        Resolved API base URL with trailing slash stripped
    """
    from ktrdr.cli import sandbox_detect

    if explicit_url:
        return explicit_url.rstrip("/")

    # Priority 2: --url flag override (set by CLI callback)
    url_override = sandbox_detect.get_url_override()
    if url_override:
        effective_url = url_override.rstrip("/")
        # Auto-append /api/v1 if no API path present (for --url flag)
        if "/api/" not in effective_url:
            effective_url = f"{effective_url}/api/v1"
        return effective_url

    # Priority 3: Sandbox detection from .env.sandbox file
    if sandbox_detect.find_env_sandbox() is not None:
        # Sandbox detected - use resolved URL with /api/v1 path
        sandbox_url = sandbox_detect.resolve_api_url()
        return f"{sandbox_url}/api/v1"

    # Priority 4: Config default
    return get_api_base_url().rstrip("/")


def should_retry(
    status_code: int,
    attempt: int,
    max_retries: int,
    retryable: Optional[bool] = None,
) -> bool:
    """Determine if a request should be retried based on status code and attempt count.

    By default, only server errors (5xx) are retried. Client errors (4xx) and
    success responses are not retried as they indicate issues that won't be
    resolved by retrying.

    The explicit retryable parameter can override status code logic:
    - retryable=False: Never retry (e.g., validation errors returned as 500)
    - retryable=True: Force retry even on 4xx (rare, but API can indicate)
    - retryable=None: Use status code based logic (default)

    Args:
        status_code: HTTP response status code
        attempt: Current attempt number (0-indexed)
        max_retries: Maximum number of retries allowed
        retryable: Explicit retryable flag from API response. If provided,
                   overrides status code based logic.

    Returns:
        True if the request should be retried, False otherwise
    """
    # Check if we have attempts remaining first
    if attempt >= max_retries:
        return False

    # Explicit retryable flag overrides status code logic
    if retryable is not None:
        return retryable

    # Only retry on server errors (5xx) by default
    return 500 <= status_code < 600


def calculate_backoff(attempt: int, base_delay: float) -> float:
    """Calculate exponential backoff delay with jitter.

    Uses the formula: base_delay * (2 ** attempt) + random(0, 1)

    The jitter helps prevent thundering herd problems when multiple
    clients retry simultaneously.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds

    Returns:
        Delay in seconds before next retry attempt
    """
    exponential_delay = base_delay * (2**attempt)
    jitter = random.random()  # [0, 1)
    return exponential_delay + jitter


def parse_response(response: httpx.Response) -> dict[str, Any]:
    """Parse HTTP response, extracting JSON and handling errors.

    Successful responses (2xx) have their JSON body extracted and returned.
    Error responses (4xx, 5xx) raise APIError with appropriate details.

    Args:
        response: httpx Response object

    Returns:
        Parsed JSON response as dictionary

    Raises:
        APIError: For non-2xx responses or JSON parsing failures
    """
    # Success response
    if 200 <= response.status_code < 300:
        try:
            return response.json()
        except Exception as e:
            raise APIError(
                message="Invalid JSON response from API",
                status_code=response.status_code,
                details={
                    "error": str(e),
                    "response_text": response.text[:500] if response.text else "",
                    "suggestion": "API server may be misconfigured or returning invalid data",
                },
            ) from e

    # Error response - extract error message
    try:
        error_data = response.json()
    except Exception:
        error_data = {"message": response.text}

    # Handle both FastAPI 'detail' and custom 'message' formats
    if isinstance(error_data, dict):
        error_message = (
            error_data.get("detail") or error_data.get("message") or "Unknown error"
        )
    else:
        error_message = str(error_data) if error_data else "Unknown error"

    # Add suggestions based on status code
    suggestion = None
    if response.status_code == 400:
        suggestion = "Check request parameters and try again"
    elif response.status_code == 401:
        suggestion = "Authentication required - check credentials"
    elif response.status_code == 403:
        suggestion = "Permission denied - verify access rights"
    elif response.status_code == 404:
        suggestion = "Resource not found - verify endpoint path"
    elif response.status_code == 422:
        suggestion = "Validation failed - check required fields and data types"
    elif response.status_code == 429:
        suggestion = "Rate limited - wait and retry"
    elif response.status_code >= 500:
        suggestion = "Server error - check API server logs or retry later"

    details = error_data if isinstance(error_data, dict) else {"raw": error_data}
    if suggestion:
        details["suggestion"] = suggestion

    raise APIError(
        message=error_message,
        status_code=response.status_code,
        details=details,
    )


def enhance_with_ib_diagnostics(
    error_data: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Enhance error data with IB Gateway diagnostics if applicable.

    When an error appears to be related to IB Gateway connectivity,
    this function adds diagnostic information that helps users
    understand and resolve the issue.

    Args:
        error_data: Original error response data

    Returns:
        Error data enhanced with ib_diagnosis key if IB issue detected,
        otherwise returns original data unchanged
    """
    if not error_data:
        return error_data

    if not should_show_ib_diagnosis(error_data):
        return error_data

    problem_type, message, details = detect_ib_issue_from_api_response(error_data)

    if problem_type is None:
        return error_data

    # Create a copy to avoid mutating the original
    enhanced = dict(error_data)
    enhanced["ib_diagnosis"] = {
        "problem_type": (
            problem_type.value if hasattr(problem_type, "value") else str(problem_type)
        ),
        "message": message,
        "details": details,
    }

    return enhanced
