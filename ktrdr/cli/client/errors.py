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
    """

    def __str__(self) -> str:
        """Include status code in string representation."""
        if self.status_code is not None:
            return f"{self.message} ({self.status_code})"
        return self.message
