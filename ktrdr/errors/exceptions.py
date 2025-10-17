"""
Exception hierarchy for the KTRDR application.

This module defines a comprehensive hierarchy of exceptions that can be
raised by various parts of the application, categorized according to
the error classification in the architecture blueprint.
"""

from typing import Any, Optional

from ktrdr.errors.error_codes import ErrorCodes


class KtrdrError(Exception):
    """
    Base exception class for all KTRDR application errors.

    All custom exceptions in the application should inherit from this class
    to ensure consistent error handling.

    Attributes:
        message: Human-readable error message
        error_code: Optional error code for reference and documentation
        details: Optional dictionary with additional error details
        suggestion: Optional suggestion text for how to fix the error
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        """
        Initialize a new KtrdrError.

        Args:
            message: Human-readable error message
            error_code: Optional error code for reference and documentation
            details: Optional dictionary with additional error details
            suggestion: Optional suggestion text for how to fix the error
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestion = suggestion
        super().__init__(message)


# --- Data Errors ---


class DataError(KtrdrError):
    """
    Base class for errors related to data operations.

    Use for issues with data availability, data sources, or data processing.
    The fix typically requires **data source action** or **checking data availability**.

    This class of errors covers:
    - Missing data for requested symbol/timeframe
    - Data source is unreachable (e.g., IB Gateway down)
    - Data format issues
    - Corrupt or malformed data
    - Insufficient data for calculations

    Examples:
        No data available:
            >>> raise DataError(
            ...     message="No data available for AAPL 1h",
            ...     error_code="DATA-NoDataAvailable",
            ...     details={
            ...         "symbol": "AAPL",
            ...         "timeframe": "1h",
            ...         "requested_range": "2024-01-01 to 2024-12-31"
            ...     }
            ... )

        Data source unreachable:
            >>> raise DataError(
            ...     message="Cannot connect to IB Gateway",
            ...     error_code="DATA-SourceUnavailable",
            ...     details={"source": "IB Gateway", "port": 4002}
            ... )

        API endpoint usage (returns 503):
            >>> try:
            ...     load_data(symbol, timeframe)
            ... except DataError as e:
            ...     logger.error(f"Data error: {e.message}")
            ...     raise HTTPException(status_code=503, detail=e.to_dict()) from e

    See Also:
        - docs/architecture/error-handling/error-classes.md
        - DataFormatError: For format-specific issues
        - DataNotFoundError: For missing data files
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
    Exception raised when API request parameter validation fails.

    Use for user input validation, NOT for configuration file issues.
    The fix typically requires **changing request parameters** rather than editing files.

    This class is used for validating user-provided API parameters:
    - Invalid parameter values
    - Out-of-range values
    - Type mismatches
    - Missing required parameters

    Examples:
        Invalid timeframe:
            >>> raise ValidationError(
            ...     message="Invalid timeframe '5x'",
            ...     error_code="VALIDATION-InvalidTimeframe",
            ...     details={
            ...         "provided": "5x",
            ...         "valid_options": ["1m", "5m", "15m", "1h", "1d"]
            ...     }
            ... )

        Out of range:
            >>> raise ValidationError(
            ...     message="Validation split must be between 0.0 and 1.0",
            ...     error_code="VALIDATION-OutOfRange",
            ...     details={"provided": 1.5, "min": 0.0, "max": 1.0}
            ... )

        API endpoint usage (returns 422):
            >>> try:
            ...     validate_parameters(params)
            ... except ValidationError as e:
            ...     logger.error(f"Validation error: {e.message}")
            ...     raise HTTPException(status_code=422, detail=e.to_dict()) from e

    See Also:
        - docs/architecture/error-handling/error-classes.md
        - ConfigurationError: For configuration file issues
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

    Use for issues with configuration files, strategy YAML files, or system setup.
    The fix typically requires **editing a file** rather than changing API parameters.

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

    Examples:
        Manual construction:
            >>> raise ConfigurationError(
            ...     message="Strategy validation failed: 1 error(s) found",
            ...     error_code="STRATEGY-ValidationFailed",
            ...     context={"strategy_name": "mtf_forex_neural", "error_count": 1},
            ...     details={"errors": [{"category": "fuzzy_sets", "message": "..."}]},
            ...     suggestion="Fix the validation errors:\\nfuzzy_sets: ..."
            ... )

        Using factory method:
            >>> raise ConfigurationError.missing_feature_id(
            ...     indicator_type="rsi",
            ...     indicator_index=0,
            ...     file_path="strategies/my_strategy.yaml"
            ... )

        API endpoint usage:
            >>> try:
            ...     validate_strategy(config)
            ... except ConfigurationError as e:
            ...     logger.error(f"Configuration error: {e.format_user_message()}")
            ...     raise HTTPException(status_code=400, detail=e.to_dict()) from e

    See Also:
        - docs/architecture/error-handling/error-classes.md
        - docs/architecture/decisions/0001-error-types-for-api-responses.md
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
            error_code=ErrorCodes.STRATEGY_MISSING_FEATURE_ID,
            context={
                "file": file_path,
                "section": f"indicators[{indicator_index}]",
                "indicator_type": indicator_type,
            },
            details={"indicator_type": indicator_type, "index": indicator_index},
            suggestion=(
                f"Add 'feature_id' to indicator:\n\n"
                f"indicators:\n"
                f'  - type: "{indicator_type}"\n'
                f'    feature_id: "{indicator_type}_14"  # ADD THIS\n'
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
            error_code=ErrorCodes.STRATEGY_DUPLICATE_FEATURE_ID,
            context={
                "file": file_path,
                "section": "indicators",
                "feature_id": feature_id,
            },
            details={"feature_id": feature_id, "indices": indices},
            suggestion=(
                "Ensure each indicator has a unique feature_id.\n"
                "Use parameters in feature_id for distinction:\n\n"
                '  - type: "rsi"\n'
                '    feature_id: "rsi_14"  # Use period\n'
                "    period: 14\n\n"
                '  - type: "rsi"\n'
                '    feature_id: "rsi_21"  # Different period\n'
                "    period: 21"
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
            error_code=ErrorCodes.STRATEGY_INVALID_FEATURE_ID_FORMAT,
            context={
                "file": file_path,
                "section": f"indicators[{indicator_index}]",
                "feature_id": feature_id,
            },
            details={"feature_id": feature_id, "index": indicator_index},
            suggestion=(
                "feature_id must start with a letter and contain only:\n"
                "  - Letters (a-z, A-Z)\n"
                "  - Numbers (0-9)\n"
                "  - Underscore (_) or dash (-)\n\n"
                "Valid examples:\n"
                "  - 'rsi_14' (good)\n"
                "  - 'macd_standard' (good)\n"
                "  - '123_invalid' (bad - starts with number)\n"
                "  - 'rsi@14' (bad - contains special character)"
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
            error_code=ErrorCodes.STRATEGY_RESERVED_FEATURE_ID,
            context={
                "file": file_path,
                "section": f"indicators[{indicator_index}]",
                "feature_id": feature_id,
            },
            details={
                "feature_id": feature_id,
                "index": indicator_index,
                "reserved_words": reserved_words,
            },
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
