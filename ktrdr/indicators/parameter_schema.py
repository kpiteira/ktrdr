"""
Parameter schema system for technical indicators.

This module provides a comprehensive parameter validation framework that supports:
- Type validation with detailed error messages
- Range validation for numeric parameters
- Constraint validation between parameters
- Schema-based parameter definitions
- Enhanced error reporting with context
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ktrdr import get_logger
from ktrdr.errors import DataError

logger = get_logger(__name__)


class ParameterType(str, Enum):
    """Supported parameter types for indicators."""

    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"
    LIST = "list"


@dataclass
class ParameterDefinition:
    """
    Definition of a single parameter for an indicator.

    Attributes:
        name: Parameter name
        param_type: Parameter type (int, float, string, bool, list)
        description: Human-readable description
        default: Default value
        min_value: Minimum value for numeric types
        max_value: Maximum value for numeric types
        options: Valid options for enum-like parameters
        required: Whether the parameter is required
    """

    name: str
    param_type: ParameterType
    description: str
    default: Any = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    options: Optional[list[Any]] = None
    required: bool = False

    def validate_value(self, value: Any) -> Any:
        """
        Validate a parameter value against this definition.

        Args:
            value: Value to validate

        Returns:
            Validated and potentially converted value

        Raises:
            DataError: If validation fails
        """
        # Handle None values
        if value is None:
            if self.required:
                raise DataError(
                    message=f"Parameter '{self.name}' is required",
                    error_code="PARAM-Required",
                    details={"parameter": self.name, "description": self.description},
                )
            return self.default

        # Type validation
        if self.param_type == ParameterType.INT:
            if not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise DataError(
                        message=f"Parameter '{self.name}' must be an integer",
                        error_code="PARAM-InvalidType",
                        details={
                            "parameter": self.name,
                            "expected": "int",
                            "received": type(value).__name__,
                            "value": str(value),
                        },
                    )

        elif self.param_type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    raise DataError(
                        message=f"Parameter '{self.name}' must be a number",
                        error_code="PARAM-InvalidType",
                        details={
                            "parameter": self.name,
                            "expected": "float",
                            "received": type(value).__name__,
                            "value": str(value),
                        },
                    )

        elif self.param_type == ParameterType.STRING:
            if not isinstance(value, str):
                raise DataError(
                    message=f"Parameter '{self.name}' must be a string",
                    error_code="PARAM-InvalidType",
                    details={
                        "parameter": self.name,
                        "expected": "str",
                        "received": type(value).__name__,
                        "value": str(value),
                    },
                )

        elif self.param_type == ParameterType.BOOL:
            if not isinstance(value, bool):
                # Try to convert common boolean representations
                if isinstance(value, str):
                    if value.lower() in ("true", "1", "yes", "on"):
                        value = True
                    elif value.lower() in ("false", "0", "no", "off"):
                        value = False
                    else:
                        raise DataError(
                            message=f"Parameter '{self.name}' must be a boolean",
                            error_code="PARAM-InvalidType",
                            details={
                                "parameter": self.name,
                                "expected": "bool",
                                "received": type(value).__name__,
                                "value": str(value),
                            },
                        )
                else:
                    raise DataError(
                        message=f"Parameter '{self.name}' must be a boolean",
                        error_code="PARAM-InvalidType",
                        details={
                            "parameter": self.name,
                            "expected": "bool",
                            "received": type(value).__name__,
                            "value": str(value),
                        },
                    )

        # Range validation for numeric types
        if self.param_type in (ParameterType.INT, ParameterType.FLOAT):
            if self.min_value is not None and value < self.min_value:
                raise DataError(
                    message=f"Parameter '{self.name}' must be >= {self.min_value}",
                    error_code="PARAM-BelowMinimum",
                    details={
                        "parameter": self.name,
                        "minimum": self.min_value,
                        "received": value,
                    },
                )

            if self.max_value is not None and value > self.max_value:
                raise DataError(
                    message=f"Parameter '{self.name}' must be <= {self.max_value}",
                    error_code="PARAM-AboveMaximum",
                    details={
                        "parameter": self.name,
                        "maximum": self.max_value,
                        "received": value,
                    },
                )

        # Options validation
        if self.options is not None and value not in self.options:
            raise DataError(
                message=f"Parameter '{self.name}' must be one of {self.options}",
                error_code="PARAM-InvalidOption",
                details={
                    "parameter": self.name,
                    "valid_options": self.options,
                    "received": value,
                },
            )

        return value


@dataclass
class ParameterConstraint:
    """
    Constraint that validates relationships between multiple parameters.

    Attributes:
        name: Constraint name for error reporting
        description: Human-readable description
        validator: Function that takes params dict and returns True if valid
        error_message: Custom error message when constraint fails
    """

    name: str
    description: str
    validator: Callable[[dict[str, Any]], bool]
    error_message: str

    def validate(self, params: dict[str, Any]) -> None:
        """
        Validate the constraint against parameters.

        Args:
            params: Dictionary of parameter values

        Raises:
            DataError: If constraint validation fails
        """
        try:
            if not self.validator(params):
                raise DataError(
                    message=self.error_message,
                    error_code="PARAM-ConstraintViolation",
                    details={
                        "constraint": self.name,
                        "description": self.description,
                        "parameters": params,
                    },
                )
        except KeyError as e:
            # Handle missing parameters in constraint validation
            raise DataError(
                message=f"Constraint '{self.name}' requires parameter {e}",
                error_code="PARAM-MissingForConstraint",
                details={
                    "constraint": self.name,
                    "missing_parameter": str(e).strip("'"),
                    "available_parameters": list(params.keys()),
                },
            )


class ParameterSchema:
    """
    Complete parameter schema for an indicator.

    Defines all parameters, their types, constraints, and validation rules.
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: list[ParameterDefinition],
        constraints: Optional[list[ParameterConstraint]] = None,
    ):
        """
        Initialize parameter schema.

        Args:
            name: Schema name (typically indicator name)
            description: Schema description
            parameters: List of parameter definitions
            constraints: List of parameter constraints
        """
        self.name = name
        self.description = description
        self.parameters = {param.name: param for param in parameters}
        self.constraints = constraints or []

        logger.debug(
            f"Created parameter schema '{name}' with {len(parameters)} parameters"
        )

    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Validate parameters against this schema.

        Args:
            params: Parameters to validate

        Returns:
            Validated parameters with defaults applied

        Raises:
            DataError: If validation fails
        """
        validated_params = {}

        # Validate each parameter
        for param_name, param_def in self.parameters.items():
            value = params.get(param_name)
            validated_value = param_def.validate_value(value)
            validated_params[param_name] = validated_value

        # Check for unknown parameters
        unknown_params = set(params.keys()) - set(self.parameters.keys())
        if unknown_params:
            raise DataError(
                message=f"Unknown parameters: {', '.join(unknown_params)}",
                error_code="PARAM-Unknown",
                details={
                    "unknown_parameters": list(unknown_params),
                    "valid_parameters": list(self.parameters.keys()),
                },
            )

        # Validate constraints
        for constraint in self.constraints:
            constraint.validate(validated_params)

        logger.debug(
            f"Successfully validated {len(validated_params)} parameters for {self.name}"
        )
        return validated_params

    def get_defaults(self) -> dict[str, Any]:
        """
        Get default values for all parameters.

        Returns:
            Dictionary of parameter defaults
        """
        return {
            param_name: param_def.default
            for param_name, param_def in self.parameters.items()
            if param_def.default is not None
        }

    def to_dict(self) -> dict[str, Any]:
        """
        Convert schema to dictionary for API serialization.

        Returns:
            Schema as dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                param_name: {
                    "type": param_def.param_type.value,
                    "description": param_def.description,
                    "default": param_def.default,
                    "min_value": param_def.min_value,
                    "max_value": param_def.max_value,
                    "options": param_def.options,
                    "required": param_def.required,
                }
                for param_name, param_def in self.parameters.items()
            },
            "constraints": [
                {
                    "name": constraint.name,
                    "description": constraint.description,
                    "error_message": constraint.error_message,
                }
                for constraint in self.constraints
            ],
        }


# Built-in parameter constraint validators
def greater_than(param1: str, param2: str) -> Callable[[dict[str, Any]], bool]:
    """Create a constraint that validates param1 > param2."""

    def validator(params: dict[str, Any]) -> bool:
        return params[param1] > params[param2]

    return validator


def less_than(param1: str, param2: str) -> Callable[[dict[str, Any]], bool]:
    """Create a constraint that validates param1 < param2."""

    def validator(params: dict[str, Any]) -> bool:
        return params[param1] < params[param2]

    return validator


def greater_equal(param1: str, param2: str) -> Callable[[dict[str, Any]], bool]:
    """Create a constraint that validates param1 >= param2."""

    def validator(params: dict[str, Any]) -> bool:
        return params[param1] >= params[param2]

    return validator


def less_equal(param1: str, param2: str) -> Callable[[dict[str, Any]], bool]:
    """Create a constraint that validates param1 <= param2."""

    def validator(params: dict[str, Any]) -> bool:
        return params[param1] <= params[param2]

    return validator
