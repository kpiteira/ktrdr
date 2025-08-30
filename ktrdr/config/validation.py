"""
Input validation utilities for KTRDR.

This module provides functions for validating user-provided parameters
to prevent security issues and ensure data integrity.
"""

import re
from datetime import datetime
from pathlib import Path
from re import Pattern
from typing import Any, Optional, Union

from ktrdr import get_logger
from ktrdr.errors import ValidationError

logger = get_logger(__name__)


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
            )

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
