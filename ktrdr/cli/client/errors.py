"""Exception hierarchy for CLI client errors.

This module defines custom exceptions for HTTP client operations,
providing structured error information with status codes and details.
"""

from typing import Any, Optional


class CLIClientError(Exception):
    """Base exception for CLI client errors.

    All CLI client exceptions inherit from this class, allowing
    callers to catch any client error with a single except clause.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code if applicable, None otherwise.
        details: Additional error context as a dictionary.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ConnectionError(CLIClientError):
    """Failed to connect to API server.

    Raised when the client cannot establish a connection to the
    API server (network error, server unreachable, etc.).
    """

    pass


class TimeoutError(CLIClientError):
    """Request timed out.

    Raised when a request exceeds the configured timeout,
    including after all retry attempts have been exhausted.
    """

    pass


class APIError(CLIClientError):
    """API returned an error response.

    Raised when the API server returns an error status code (4xx/5xx).
    The status_code attribute contains the HTTP response code.

    Attributes:
        retryable: Whether this error may be resolved by retrying.
            - 5xx errors are retryable by default (transient server issues)
            - 4xx errors are not retryable (client/validation errors)
            - Can be overridden by explicit 'retryable' field in details
    """

    # Status codes that are retryable by default
    _RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

    @property
    def retryable(self) -> bool:
        """Determine if this error is retryable.

        Checks for explicit 'retryable' field in details first,
        then falls back to status code based logic.

        Returns:
            True if the error may be resolved by retrying.
        """
        # Check for explicit override in details
        if "retryable" in self.details:
            return bool(self.details["retryable"])

        # Fall back to status code based logic
        if self.status_code is None:
            return False

        return self.status_code in self._RETRYABLE_STATUS_CODES

    def __str__(self) -> str:
        """Return clean error message without status code.

        For user-facing output, shows just the message.
        Use verbose_str() for debugging with status code.
        """
        return self.message

    def verbose_str(self) -> str:
        """Return detailed error string with status code.

        Useful for debugging and verbose output modes.

        Returns:
            Error message with status code appended.
        """
        if self.status_code is not None:
            return f"{self.message} ({self.status_code})"
        return self.message
