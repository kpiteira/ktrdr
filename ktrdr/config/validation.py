"""
Input and startup validation utilities for KTRDR.

This module provides:
1. Input validation - Functions for validating user-provided parameters
   to prevent security issues and ensure data integrity.
2. Startup validation - Explicit validation of settings at startup with
   KTRDR_ENV-aware insecure default detection.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from pydantic import ValidationError as PydanticValidationError

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError, ValidationError

if TYPE_CHECKING:
    from pydantic_settings import BaseSettings

logger = get_logger(__name__)


# =============================================================================
# Startup Validation (KTRDR_ENV-aware)
# =============================================================================

# Known insecure default values for secrets
# If current value matches these, it's considered insecure
INSECURE_DEFAULTS: dict[str, str] = {
    "KTRDR_DB_PASSWORD": "localdev",
    "KTRDR_AUTH_JWT_SECRET": "insecure-dev-secret",
}

# Settings classes to validate for each component
# For M1, only DatabaseSettings is validated; more will be added in later milestones


# Import lazily to avoid circular imports
def _get_database_settings_class() -> type["BaseSettings"]:
    """Get DatabaseSettings class (lazy import to avoid circular dependency)."""
    from ktrdr.config.settings import DatabaseSettings

    return DatabaseSettings


# Lists of settings classes for each component
BACKEND_SETTINGS: list[type["BaseSettings"]] = []
WORKER_SETTINGS: list[type["BaseSettings"]] = []

# Populate the lists lazily on first access
_settings_lists_initialized = False


def _init_settings_lists() -> None:
    """Initialize settings lists (called once on first use)."""
    global _settings_lists_initialized
    if _settings_lists_initialized:
        return

    from ktrdr.config.settings import (
        APISettings,
        AuthSettings,
        CheckpointSettings,
        IBHostServiceSettings,
        IBSettings,
        LoggingSettings,
        ObservabilitySettings,
        OperationsSettings,
        OrphanDetectorSettings,
        TrainingHostServiceSettings,
        WorkerSettings,
    )

    DatabaseSettings = _get_database_settings_class()

    # Backend needs all M1 + M2 + M3 settings
    BACKEND_SETTINGS.append(DatabaseSettings)
    BACKEND_SETTINGS.append(APISettings)
    BACKEND_SETTINGS.append(AuthSettings)
    BACKEND_SETTINGS.append(LoggingSettings)
    BACKEND_SETTINGS.append(ObservabilitySettings)
    BACKEND_SETTINGS.append(IBSettings)
    BACKEND_SETTINGS.append(IBHostServiceSettings)
    BACKEND_SETTINGS.append(TrainingHostServiceSettings)

    # Workers need database + logging + observability + M4 worker-specific settings
    WORKER_SETTINGS.append(DatabaseSettings)
    WORKER_SETTINGS.append(LoggingSettings)
    WORKER_SETTINGS.append(ObservabilitySettings)
    WORKER_SETTINGS.append(WorkerSettings)
    WORKER_SETTINGS.append(CheckpointSettings)
    WORKER_SETTINGS.append(OrphanDetectorSettings)
    WORKER_SETTINGS.append(OperationsSettings)

    _settings_lists_initialized = True


def detect_insecure_defaults() -> dict[str, str]:
    """Detect which secrets are still at their insecure default values.

    Checks the current settings values against known insecure defaults.
    Returns a dict of {env_var_name: current_value} for each insecure default found.

    Returns:
        Dictionary mapping env var names to their insecure values.
        Empty dict if all secrets are secure.
    """
    from ktrdr.config.settings import (
        clear_settings_cache,
        get_auth_settings,
        get_db_settings,
    )

    # Clear cache to ensure we get fresh values
    clear_settings_cache()

    insecure_found: dict[str, str] = {}

    # Check database password
    db_settings = get_db_settings()
    if db_settings.password == INSECURE_DEFAULTS.get("KTRDR_DB_PASSWORD"):
        insecure_found["KTRDR_DB_PASSWORD"] = db_settings.password

    # Check JWT secret
    auth_settings = get_auth_settings()
    if auth_settings.jwt_secret == INSECURE_DEFAULTS.get("KTRDR_AUTH_JWT_SECRET"):
        insecure_found["KTRDR_AUTH_JWT_SECRET"] = auth_settings.jwt_secret

    return insecure_found


def _format_insecure_warning(insecure: dict[str, str]) -> str:
    """Format the insecure defaults warning message.

    Args:
        insecure: Dict of {env_var_name: insecure_value}.

    Returns:
        Formatted warning string matching ARCHITECTURE.md spec.
    """
    lines = [
        "========================================",
        "WARNING: INSECURE DEFAULT CONFIGURATION",
        "========================================",
        "The following settings are using insecure defaults:",
    ]

    for env_var in insecure:
        # Don't log actual password values - just indicate they're at default
        lines.append(f"  - {env_var}: Using default value (not shown for security)")

    lines.extend(
        [
            "",
            "This is fine for local development but MUST NOT be used in production.",
            "",
            "To suppress this warning:",
            "  - Set these values via 1Password (recommended)",
            "  - Or create .env.local with secure values",
            "  - Or set KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS=true",
            "========================================",
        ]
    )

    return "\n".join(lines)


def _format_insecure_error(insecure: dict[str, str]) -> str:
    """Format the insecure defaults error message for production.

    Args:
        insecure: Dict of {env_var_name: insecure_value}.

    Returns:
        Formatted error string.
    """
    lines = [
        "CONFIGURATION ERROR",
        "====================",
        "Insecure defaults not allowed in production:",
    ]

    for env_var in insecure:
        lines.append(f"  - {env_var}: Must be explicitly set (not at default)")

    lines.extend(
        [
            "",
            "See: docs/configuration.md for all available settings",
            "====================",
        ]
    )

    return "\n".join(lines)


def _format_validation_error(errors: list[str]) -> str:
    """Format validation errors message.

    Args:
        errors: List of error strings.

    Returns:
        Formatted error string.
    """
    lines = [
        "CONFIGURATION ERROR",
        "====================",
        "Invalid settings:",
    ]

    for error in errors:
        lines.append(f"  - {error}")

    lines.extend(
        [
            "",
            "See: docs/configuration.md for all available settings",
            "====================",
        ]
    )

    return "\n".join(lines)


def validate_all(component: Literal["backend", "worker", "all"] = "all") -> None:
    """Validate all required settings at startup.

    This function should be called at application startup (main.py, worker entrypoints)
    to fail fast if configuration is invalid.

    Behavior:
    - Reads KTRDR_ENV via os.getenv() (not from Settings class)
    - Validates each Settings class for the given component
    - Collects ALL validation errors (doesn't stop at first)
    - Detects insecure defaults (secrets at dev default values)
    - KTRDR_ENV=production: insecure defaults are hard failures
    - KTRDR_ENV=development (or unset): insecure defaults emit warning

    Args:
        component: Which settings to validate - "backend", "worker", or "all".

    Raises:
        ConfigurationError: If validation fails or insecure defaults in production.
    """
    _init_settings_lists()

    # Read environment mode via os.getenv() (not from Settings to avoid circular dep)
    ktrdr_env = os.getenv("KTRDR_ENV", "development").lower()
    is_production = ktrdr_env == "production"
    acknowledge_insecure = (
        os.getenv("KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS", "").lower() == "true"
    )

    # Determine which settings classes to validate
    if component == "backend":
        settings_classes = BACKEND_SETTINGS
    elif component == "worker":
        settings_classes = WORKER_SETTINGS
    elif component == "all":
        # Combine both, preserving order (backend first, then worker) while avoiding duplicates
        settings_classes = []
        seen: set[type[BaseSettings]] = set()
        for cls in list(BACKEND_SETTINGS) + list(WORKER_SETTINGS):
            if cls not in seen:
                seen.add(cls)
                settings_classes.append(cls)
    else:
        raise ValueError(
            f"Unknown component '{component}'. Expected one of: 'backend', 'worker', 'all'."
        )

    # Collect validation errors
    errors: list[str] = []

    for settings_class in settings_classes:
        try:
            # Instantiate the settings class to trigger Pydantic validation
            settings_class()
        except PydanticValidationError as e:
            # Extract error details from Pydantic validation error
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                msg = error["msg"]
                errors.append(f"{field}: {msg}")

    # If there are validation errors, raise immediately
    if errors:
        error_msg = _format_validation_error(errors)
        logger.error(error_msg)
        raise ConfigurationError(
            message="Configuration validation failed",
            error_code="CONFIG-ValidationFailed",
            details={"errors": errors},
            suggestion="Fix the configuration errors listed above.",
        )

    # Check for insecure defaults
    insecure = detect_insecure_defaults()

    if insecure:
        if is_production:
            # Production mode: insecure defaults are hard failures
            error_msg = _format_insecure_error(insecure)
            logger.error(error_msg)
            raise ConfigurationError(
                message="Insecure defaults not allowed in production",
                error_code="CONFIG-InsecureDefaults",
                details={"insecure_settings": list(insecure.keys())},
                suggestion="Set secure values for the listed environment variables.",
            )
        elif not acknowledge_insecure:
            # Development mode: warn but don't fail (unless acknowledged)
            warning_msg = _format_insecure_warning(insecure)
            logger.warning(warning_msg)


class InputValidator:
    """
    Validates user-provided input parameters.

    Provides methods to validate different types of user input based on
    expected patterns, ranges, or other constraints.
    """

    @staticmethod
    def validate_string(
        value: str,
        min_length: int = 0,
        max_length: Optional[int] = None,
        pattern: Optional[Union[str, Pattern]] = None,
        allowed_values: Optional[set[str]] = None,
    ) -> str:
        """
        Validate a string value against constraints.

        Args:
            value: The string to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length (None for no limit)
            pattern: Regex pattern the string must match
            allowed_values: Set of allowed values

        Returns:
            The validated string

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, str):
            raise ValidationError(
                message=f"Expected string but got {type(value).__name__}",
                error_code="VAL-TypeError",
                details={"expected_type": "str", "actual_type": type(value).__name__},
            )

        if len(value) < min_length:
            raise ValidationError(
                message=f"String too short (min {min_length} chars)",
                error_code="VAL-StringTooShort",
                details={"min_length": min_length, "actual_length": len(value)},
            )

        if max_length is not None and len(value) > max_length:
            raise ValidationError(
                message=f"String too long (max {max_length} chars)",
                error_code="VAL-StringTooLong",
                details={"max_length": max_length, "actual_length": len(value)},
            )

        if pattern is not None:
            if isinstance(pattern, str):
                pattern = re.compile(pattern)

            if not pattern.match(value):
                raise ValidationError(
                    message="String does not match required pattern",
                    error_code="VAL-PatternMismatch",
                    details={"pattern": pattern.pattern},
                )

        if allowed_values is not None and value not in allowed_values:
            raise ValidationError(
                message=f"Value not in allowed set: {value}",
                error_code="VAL-InvalidValue",
                details={"allowed_values": list(allowed_values)},
            )

        return value

    @staticmethod
    def validate_numeric(
        value: Union[int, float],
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        allowed_values: Optional[set[Union[int, float]]] = None,
    ) -> Union[int, float]:
        """
        Validate a numeric value against constraints.

        Args:
            value: The number to validate
            min_value: Minimum allowed value (None for no minimum)
            max_value: Maximum allowed value (None for no maximum)
            allowed_values: Set of allowed values

        Returns:
            The validated numeric value

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, (int, float)):
            raise ValidationError(
                message=f"Expected numeric value but got {type(value).__name__}",
                error_code="VAL-TypeError",
                details={
                    "expected_type": "int or float",
                    "actual_type": type(value).__name__,
                },
            )

        if min_value is not None and value < min_value:
            raise ValidationError(
                message=f"Value {value} below minimum {min_value}",
                error_code="VAL-BelowMinimum",
                details={"min_value": min_value, "actual_value": value},
            )

        if max_value is not None and value > max_value:
            raise ValidationError(
                message=f"Value {value} above maximum {max_value}",
                error_code="VAL-AboveMaximum",
                details={"max_value": max_value, "actual_value": value},
            )

        if allowed_values is not None and value not in allowed_values:
            raise ValidationError(
                message=f"Value not in allowed set: {value}",
                error_code="VAL-InvalidValue",
                details={"allowed_values": list(allowed_values)},
            )

        return value

    @staticmethod
    def validate_date(
        value: str,
        min_date: Optional[datetime] = None,
        max_date: Optional[datetime] = None,
        format_string: str = "%Y-%m-%d",
    ) -> datetime:
        """
        Validate and parse a date string.

        Args:
            value: The date string to validate
            min_date: Minimum allowed date (None for no minimum)
            max_date: Maximum allowed date (None for no maximum)
            format_string: Format string for datetime parsing

        Returns:
            The parsed datetime object

        Raises:
            ValidationError: If validation fails
        """
        try:
            dt = datetime.strptime(value, format_string)
        except ValueError as e:
            raise ValidationError(
                message=f"Invalid date format: {value} (expected format: {format_string})",
                error_code="VAL-DateFormat",
                details={"format": format_string, "value": value, "error": str(e)},
            ) from e

        if min_date is not None and dt < min_date:
            raise ValidationError(
                message=f"Date {value} is before minimum date {min_date.strftime(format_string)}",
                error_code="VAL-DateTooEarly",
                details={
                    "min_date": min_date.strftime(format_string),
                    "actual_date": value,
                },
            )

        if max_date is not None and dt > max_date:
            raise ValidationError(
                message=f"Date {value} is after maximum date {max_date.strftime(format_string)}",
                error_code="VAL-DateTooLate",
                details={
                    "max_date": max_date.strftime(format_string),
                    "actual_date": value,
                },
            )

        return dt

    @staticmethod
    def validate_file_path(
        value: Union[str, Path],
        must_exist: bool = False,
        file_type: Optional[str] = None,
    ) -> Path:
        """
        Validate a file path.

        Args:
            value: The file path to validate
            must_exist: Whether the file must already exist
            file_type: Expected file extension (without the dot)

        Returns:
            The validated Path object

        Raises:
            ValidationError: If validation fails
        """
        path = Path(value) if isinstance(value, str) else value

        if must_exist and not path.exists():
            raise ValidationError(
                message=f"File does not exist: {path}",
                error_code="VAL-FileNotFound",
                details={"path": str(path)},
            )

        if file_type is not None and path.suffix.lower() != f".{file_type.lower()}":
            raise ValidationError(
                message=f"Expected file type {file_type}, got {path.suffix[1:] if path.suffix else 'no extension'}",
                error_code="VAL-WrongFileType",
                details={
                    "expected_type": file_type,
                    "actual_type": path.suffix[1:] if path.suffix else None,
                },
            )

        return path


def sanitize_parameter(name: str, value: Any) -> Any:
    """
    Sanitize a parameter value based on its name and type.

    Args:
        name: Parameter name
        value: Parameter value to sanitize

    Returns:
        The sanitized parameter value
    """
    # Sanitize based on parameter name patterns
    if "path" in name.lower() and isinstance(value, str):
        # Convert to Path and resolve to absolute path for path-like parameters
        return str(Path(value).resolve())

    # For other string parameters, ensure basic safety
    if isinstance(value, str):
        # Remove any control characters
        return "".join(c for c in value if ord(c) >= 32)

    return value


def sanitize_parameters(params: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize a dictionary of parameters.

    Args:
        params: Dictionary of parameter name-value pairs

    Returns:
        Dictionary with sanitized parameters
    """
    return {name: sanitize_parameter(name, value) for name, value in params.items()}
