"""
Error handling framework for KTRDR.

This module provides a comprehensive error handling framework including
exception hierarchy, centralized error handling, user-friendly error messages,
retry mechanisms, and graceful degradation support.
"""

from ktrdr.errors.exceptions import (
    KtrdrError,
    DataError,
    DataFormatError,
    DataNotFoundError,
    DataCorruptionError,
    DataValidationError,
    ValidationError,
    SecurityError,
    PathTraversalError,
    InvalidInputError,
    UnauthorizedAccessError,
    ConnectionError,
    ConfigurationError,
    MissingConfigurationError,
    InvalidConfigurationError,
    ConfigurationFileError,
    ProcessingError,
    SystemError,
)

from ktrdr.errors.handler import (
    ErrorHandler,
    error_to_user_message,
    get_error_code,
    get_recovery_steps,
)

from ktrdr.errors.retry import (
    retry_with_backoff,
    RetryConfig,
    RetryableError,
    MaxRetriesExceededError,
)

from ktrdr.errors.graceful import (
    fallback,
    FallbackStrategy,
    FallbackNotAvailableError,
    with_partial_results,
)

__all__ = [
    # Base exception
    "KtrdrError",
    # Exception hierarchy
    "DataError",
    "DataFormatError",
    "DataNotFoundError",
    "DataCorruptionError",
    "DataValidationError",
    "ValidationError",
    "SecurityError",
    "PathTraversalError",
    "InvalidInputError",
    "UnauthorizedAccessError",
    "ConnectionError",
    "ConfigurationError",
    "MissingConfigurationError",
    "InvalidConfigurationError",
    "ConfigurationFileError",
    "ProcessingError",
    "SystemError",
    # Error handler
    "ErrorHandler",
    "error_to_user_message",
    "get_error_code",
    "get_recovery_steps",
    # Retry mechanism
    "retry_with_backoff",
    "RetryConfig",
    "RetryableError",
    "MaxRetriesExceededError",
    # Graceful degradation
    "fallback",
    "FallbackStrategy",
    "FallbackNotAvailableError",
    "with_partial_results",
]
