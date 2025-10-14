"""
Exception hierarchy for the KTRDR application.

This module defines a comprehensive hierarchy of exceptions that can be
raised by various parts of the application, categorized according to
the error classification in the architecture blueprint.
"""

from typing import Any, Optional


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
        details: Optional[dict[str, Any]] = None,
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
    Enhanced configuration error with comprehensive error reporting.

    This class provides detailed error information including:
    - message: Human-readable error description
    - error_code: Machine-readable error code (e.g., STRATEGY-MissingFeatureId)
    - context: Where the error occurred (file, section, field)
    - details: Structured data about the error
    - suggestion: Actionable steps to fix the error

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code
        context: Dictionary with error location (file, section, field)
        details: Dictionary with structured error data
        suggestion: How to fix the error
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        details: Optional[dict[str, Any]] = None,
        suggestion: str = "",
    ) -> None:
        """
        Initialize a configuration error with comprehensive information.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            context: Where error occurred (file, section, field)
            details: Structured data about the error
            suggestion: How to fix the error
        """
        super().__init__(message, error_code, details)
        self.context = context or {}
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize error to dictionary for API responses.

        Returns:
            Dictionary with all error information
        """
        return {
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "details": self.details,
            "suggestion": self.suggestion,
        }

    def format_user_message(self) -> str:
        """
        Format a user-friendly error message with all context.

        Returns:
            Formatted error message string
        """
        parts = [f"Error: {self.message}"]

        if self.error_code:
            parts.append(f"Code: {self.error_code}")

        if self.context:
            context_parts = []
            if "file" in self.context:
                context_parts.append(f"File: {self.context['file']}")
            if "section" in self.context:
                context_parts.append(f"Section: {self.context['section']}")
            if context_parts:
                parts.append("Location: " + ", ".join(context_parts))

        if self.suggestion:
            parts.append(f"\nSuggestion: {self.suggestion}")

        return "\n".join(parts)

    def __str__(self) -> str:
        """String representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    @classmethod
    def missing_feature_id(
        cls, indicator_type: str, indicator_index: int, file_path: str = "strategy.yaml"
    ) -> "ConfigurationError":
        """
        Factory method for missing feature_id error.

        Args:
            indicator_type: Type of indicator missing feature_id
            indicator_index: Index of indicator in config
            file_path: Path to strategy file

        Returns:
            ConfigurationError for missing feature_id
        """
        return cls(
            message=f"Indicator '{indicator_type}' at index {indicator_index} missing required field 'feature_id'",
            error_code="STRATEGY-MissingFeatureId",
            context={
                "file": file_path,
                "section": f"indicators[{indicator_index}]",
                "indicator_type": indicator_type,
            },
            details={"indicator_type": indicator_type, "index": indicator_index},
            suggestion=(
                f"Add 'feature_id' to indicator:\n\n"
                f"indicators:\n"
                f"  - type: \"{indicator_type}\"\n"
                f"    feature_id: \"{indicator_type}_14\"  # ADD THIS\n"
                f"    period: 14\n\n"
                f"Or run migration tool:\n"
                f"  python scripts/migrate_to_feature_ids.py {file_path}"
            ),
        )

    @classmethod
    def duplicate_feature_id(
        cls, feature_id: str, indices: list[int], file_path: str = "strategy.yaml"
    ) -> "ConfigurationError":
        """
        Factory method for duplicate feature_id error.

        Args:
            feature_id: The duplicate feature_id
            indices: Indices where duplicate appears
            file_path: Path to strategy file

        Returns:
            ConfigurationError for duplicate feature_id
        """
        return cls(
            message=f"Duplicate feature_id '{feature_id}' found at indices {indices}",
            error_code="STRATEGY-DuplicateFeatureId",
            context={"file": file_path, "section": "indicators", "feature_id": feature_id},
            details={"feature_id": feature_id, "indices": indices},
            suggestion=(
                f"Ensure each indicator has a unique feature_id.\n"
                f"Use parameters in feature_id for distinction:\n\n"
                f"  - type: \"rsi\"\n"
                f"    feature_id: \"rsi_14\"  # Use period\n"
                f"    period: 14\n\n"
                f"  - type: \"rsi\"\n"
                f"    feature_id: \"rsi_21\"  # Different period\n"
                f"    period: 21"
            ),
        )

    @classmethod
    def invalid_feature_id_format(
        cls, feature_id: str, indicator_index: int, file_path: str = "strategy.yaml"
    ) -> "ConfigurationError":
        """
        Factory method for invalid feature_id format error.

        Args:
            feature_id: The invalid feature_id
            indicator_index: Index of indicator in config
            file_path: Path to strategy file

        Returns:
            ConfigurationError for invalid format
        """
        return cls(
            message=f"Invalid feature_id format: '{feature_id}' at index {indicator_index}",
            error_code="STRATEGY-InvalidFeatureIdFormat",
            context={
                "file": file_path,
                "section": f"indicators[{indicator_index}]",
                "feature_id": feature_id,
            },
            details={"feature_id": feature_id, "index": indicator_index},
            suggestion=(
                f"feature_id must start with a letter and contain only:\n"
                f"  - Letters (a-z, A-Z)\n"
                f"  - Numbers (0-9)\n"
                f"  - Underscore (_) or dash (-)\n\n"
                f"Valid examples:\n"
                f"  - 'rsi_14' (good)\n"
                f"  - 'macd_standard' (good)\n"
                f"  - '123_invalid' (bad - starts with number)\n"
                f"  - 'rsi@14' (bad - contains special character)"
            ),
        )

    @classmethod
    def reserved_feature_id(
        cls, feature_id: str, indicator_index: int, file_path: str = "strategy.yaml"
    ) -> "ConfigurationError":
        """
        Factory method for reserved feature_id error.

        Args:
            feature_id: The reserved feature_id
            indicator_index: Index of indicator in config
            file_path: Path to strategy file

        Returns:
            ConfigurationError for reserved word
        """
        reserved_words = ["open", "high", "low", "close", "volume"]
        return cls(
            message=f"Reserved feature_id '{feature_id}' at index {indicator_index}",
            error_code="STRATEGY-ReservedFeatureId",
            context={
                "file": file_path,
                "section": f"indicators[{indicator_index}]",
                "feature_id": feature_id,
            },
            details={"feature_id": feature_id, "index": indicator_index, "reserved_words": reserved_words},
            suggestion=(
                f"feature_id '{feature_id}' is reserved for price data.\n"
                f"Reserved words: {', '.join(reserved_words)}\n\n"
                f"Use a different name:\n"
                f"  - 'rsi_14' instead of 'close'\n"
                f"  - 'volume_sma_20' instead of 'volume'"
            ),
        )


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


# --- Service-specific Connection Errors ---


class ServiceConnectionError(ConnectionError):
    """
    Exception raised when connection to a service fails.

    This exception is specifically for async service communication
    failures such as IB Host Service or Training Host Service
    connection issues.
    """

    pass


class ServiceTimeoutError(ConnectionError):
    """
    Exception raised when a service request times out.

    This exception is specifically for async service communication
    timeouts during HTTP requests to host services.
    """

    pass


class ServiceConfigurationError(ConfigurationError):
    """
    Exception raised when service configuration is invalid.

    This exception is specifically for async service configuration
    issues such as missing URLs or invalid service settings.
    """

    pass
