"""CLI HTTP client module.

Provides unified HTTP clients for CLI commands with consistent
error handling, retry logic, and URL resolution.
"""

from ktrdr.cli.client.errors import (
    APIError,
    CLIClientError,
    ConnectionError,
    TimeoutError,
)

__all__ = [
    "CLIClientError",
    "ConnectionError",
    "TimeoutError",
    "APIError",
]
