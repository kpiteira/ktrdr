"""
Error handling framework for KTRDR.

This module provides a comprehensive error handling framework including
exception hierarchy, centralized error handling, user-friendly error messages,
retry mechanisms, and graceful degradation support.
"""

from ktrdr.errors.exceptions import (
    ConfigurationError,
    ConfigurationFileError,
    ConnectionError,
    DataCorruptionError,
    DataError,
    DataFormatError,
    DataNotFoundError,
    DataValidationError,
    InvalidConfigurationError,
    InvalidInputError,
    KtrdrError,
    MissingConfigurationError,
    PathTraversalError,
    ProcessingError,
    SecurityError,
    SystemError,
    UnauthorizedAccessError,
    ValidationError,
)
from ktrdr.errors.graceful import (
    FallbackNotAvailableError,
    FallbackStrategy,
    fallback,
    with_partial_results,
)
from ktrdr.errors.handler import (
    ErrorHandler,
    error_to_user_message,
    get_error_code,
    get_recovery_steps,
)
from ktrdr.errors.retry import (
    MaxRetriesExceededError,
    RetryableError,
    RetryConfig,
    retry_with_backoff,
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
