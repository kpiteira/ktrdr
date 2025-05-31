"""
Exception hierarchy for the KTRDR application.

This module defines a comprehensive hierarchy of exceptions that can be
raised by various parts of the application, categorized according to
the error classification in the architecture blueprint.
"""

from typing import Optional, Dict, Any


class KtrdrError(Exception):
    """
    Base exception class for all KTRDR application errors.

    All custom exceptions in the application should inherit from this class
    to ensure consistent error handling.

    Attributes:
        message: Human-readable error message
        error_code: Optional error code for reference and documentation
        details: Optional dictionary with additional error details
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize a new KtrdrError.

        Args:
            message: Human-readable error message
            error_code: Optional error code for reference and documentation
            details: Optional dictionary with additional error details
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


# --- Data Errors ---


class DataError(KtrdrError):
    """
    Base class for errors related to data operations.

    This class of errors covers issues with missing, corrupt, or invalid data.
    """

    pass


class DataFormatError(DataError):
    """Exception raised when data format is invalid."""

    pass


class DataNotFoundError(DataError):
    """Exception raised when data file is not found."""

    pass


class DataCorruptionError(DataError):
    """Exception raised when data is corrupt or malformed."""

    pass


class DataValidationError(DataError):
    """Exception raised when data fails validation checks."""

    pass


# --- Validation Errors ---


class ValidationError(KtrdrError):
    """
    Exception raised when input validation fails.

    This class is used for validating user-provided parameters
    and other input validation purposes.
    """

    pass


# --- Security Errors ---


class SecurityError(KtrdrError):
    """
    Base class for security-related errors.

    This class of errors covers security violations, unauthorized access attempts,
    path traversal attacks, and other security concerns.
    """

    pass


class PathTraversalError(SecurityError):
    """Exception raised when a path traversal attempt is detected."""

    pass


class InvalidInputError(SecurityError):
    """Exception raised when input validation fails for security reasons."""

    pass


class UnauthorizedAccessError(SecurityError):
    """Exception raised when an unauthorized access attempt is detected."""

    pass


# --- Connection Errors ---


class ConnectionError(KtrdrError):
    """
    Base class for errors related to network connectivity.

    This class of errors covers network issues, API timeouts,
    or service unavailability.
    """

    pass


class ApiTimeoutError(ConnectionError):
    """Exception raised when an API call times out."""

    pass


class ServiceUnavailableError(ConnectionError):
    """Exception raised when a required service is unavailable."""

    pass


class NetworkError(ConnectionError):
    """Exception raised for general network connectivity issues."""

    pass


class AuthenticationError(ConnectionError):
    """Exception raised when authentication with a service fails."""

    pass


# --- Configuration Errors ---


class ConfigurationError(KtrdrError):
    """
    Base class for errors related to configuration.

    This class of errors covers invalid settings or configuration problems.
    """

    pass


class MissingConfigurationError(ConfigurationError):
    """Exception raised when a required configuration setting is missing."""

    pass


class InvalidConfigurationError(ConfigurationError):
    """Exception raised when a configuration setting is invalid."""

    pass


class ConfigurationFileError(ConfigurationError):
    """Exception raised when there's an issue with a configuration file."""

    pass


# --- Processing Errors ---


class ProcessingError(KtrdrError):
    """
    Base class for errors related to data processing.

    This class of errors covers calculation failures or unexpected results.
    """

    pass


class CalculationError(ProcessingError):
    """Exception raised when a calculation fails."""

    pass


class ParsingError(ProcessingError):
    """Exception raised when parsing data fails."""

    pass


class TransformationError(ProcessingError):
    """Exception raised when data transformation fails."""

    pass


# --- System Errors ---


class SystemError(KtrdrError):
    """
    Base class for system-level errors.

    This class of errors covers resource limitations, unexpected crashes,
    or environment issues.
    """

    pass


class ResourceExhaustedError(SystemError):
    """Exception raised when a system resource is exhausted."""

    pass


class EnvironmentError(SystemError):
    """Exception raised when there's an issue with the environment."""

    pass


class CriticalError(SystemError):
    """Exception raised for critical system failures requiring immediate attention."""

    pass


# --- Retry-related Errors ---


class RetryableError(KtrdrError):
    """Base class for errors that can be retried."""

    pass


class MaxRetriesExceededError(KtrdrError):
    """Exception raised when the maximum number of retries is exceeded."""

    pass


# --- Fallback-related Errors ---


class FallbackNotAvailableError(KtrdrError):
    """Exception raised when no fallback strategy is available."""

    pass
