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
        suggestion: Optional suggestion text for how to fix the error
        operation_id: Optional operation ID for context
        operation_type: Optional operation type (e.g., 'training', 'backtest')
        stage: Optional stage of operation where error occurred (e.g., 'validation', 'execution')
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        operation_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> None:
        """
        Initialize a new KtrdrError.

        Args:
            message: Human-readable error message
            error_code: Optional error code for reference and documentation
            details: Optional dictionary with additional error details
            suggestion: Optional suggestion text for how to fix the error
            operation_id: Optional operation ID for context
            operation_type: Optional operation type (e.g., 'training', 'backtest')
            stage: Optional stage of operation where error occurred
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestion = suggestion
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.stage = stage
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


class WorkerUnavailableError(ServiceUnavailableError):
    """Exception raised when no workers are available for an operation.

    This exception is raised when:
    - No workers of the required type are registered
    - All workers are busy
    - Workers haven't re-registered after backend restart

    The exception includes diagnostic context to help callers understand
    if this is a transient startup issue.

    Attributes:
        worker_type: Type of worker that was requested (e.g., "training", "backtesting")
        registered_count: Number of workers currently registered
        backend_uptime_seconds: How long the backend has been running
        hint: Helpful message about what to do

    Example:
        >>> raise WorkerUnavailableError(
        ...     worker_type="training",
        ...     registered_count=0,
        ...     backend_uptime_seconds=5.2,
        ... )
    """

    def __init__(
        self,
        worker_type: str,
        registered_count: int = 0,
        backend_uptime_seconds: float = 0.0,
        hint: Optional[str] = None,
    ) -> None:
        """Initialize a WorkerUnavailableError with diagnostic context.

        Args:
            worker_type: Type of worker that was requested
            registered_count: Number of workers currently registered
            backend_uptime_seconds: How long the backend has been running
            hint: Optional hint message (auto-generated if not provided)
        """
        self.worker_type = worker_type
        self.registered_count = registered_count
        self.backend_uptime_seconds = backend_uptime_seconds
        self.hint = hint or (
            "Workers auto-register after startup. "
            "Retry in a few seconds, or check worker container logs."
        )

        message = f"No {worker_type} workers available"
        super().__init__(
            message=message,
            error_code="WORKER_UNAVAILABLE",
            details={
                "worker_type": worker_type,
                "registered_workers": registered_count,
                "backend_uptime_seconds": backend_uptime_seconds,
                "hint": self.hint,
            },
        )

    def to_response_dict(self) -> dict:
        """Format for HTTP error response body.

        Returns:
            Dictionary suitable for HTTPException detail parameter.
        """
        return {
            "error": self.message,
            "worker_type": self.worker_type,
            "registered_workers": self.registered_count,
            "backend_uptime_seconds": self.backend_uptime_seconds,
            "hint": self.hint,
        }


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
        operation_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> None:
        """
        Initialize a configuration error with comprehensive information.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            context: Where error occurred (file, section, field)
            details: Structured data about the error
            suggestion: How to fix the error
            operation_id: Optional operation ID for context
            operation_type: Optional operation type
            stage: Optional stage of operation where error occurred
        """
        super().__init__(
            message,
            error_code,
            details,
            suggestion,
            operation_id,
            operation_type,
            stage,
        )
        self.context = context or {}

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
