"""
Tests for the parameter schema validation system.

This module tests the comprehensive parameter validation framework
including type validation, range validation, and constraint validation.

Note: The ParameterSchema class and indicator-specific schemas (RSI_SCHEMA, etc.)
have been replaced by the Params pattern with Pydantic validation. These tests
cover the underlying ParameterDefinition and ParameterConstraint utilities.
"""

import pytest

from ktrdr.errors import DataError
from ktrdr.indicators.parameter_schema import (
    ParameterConstraint,
    ParameterDefinition,
    ParameterType,
    greater_than,
    less_than,
)


class TestParameterDefinition:
    """Test ParameterDefinition validation logic."""

    def test_integer_parameter_validation(self):
        """Test integer parameter validation."""
        param = ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Test period",
            default=14,
            min_value=1,
            max_value=100,
        )

        # Valid values
        assert param.validate_value(10) == 10
        assert param.validate_value(None) == 14  # default

        # Type conversion
        assert param.validate_value("20") == 20

        # Range validation
        with pytest.raises(DataError, match="must be >= 1"):
            param.validate_value(0)

        with pytest.raises(DataError, match="must be <= 100"):
            param.validate_value(101)

        # Type validation
        with pytest.raises(DataError, match="must be an integer"):
            param.validate_value("abc")

    def test_float_parameter_validation(self):
        """Test float parameter validation."""
        param = ParameterDefinition(
            name="multiplier",
            param_type=ParameterType.FLOAT,
            description="Test multiplier",
            default=2.0,
            min_value=0.1,
            max_value=5.0,
        )

        # Valid values
        assert param.validate_value(1.5) == 1.5
        assert param.validate_value(2) == 2.0  # int to float
        assert param.validate_value("2.5") == 2.5  # string to float

        # Range validation
        with pytest.raises(DataError, match="must be >= 0.1"):
            param.validate_value(0.05)

    def test_string_parameter_validation(self):
        """Test string parameter validation."""
        param = ParameterDefinition(
            name="source",
            param_type=ParameterType.STRING,
            description="Price source",
            default="close",
            options=["open", "high", "low", "close"],
        )

        # Valid values
        assert param.validate_value("high") == "high"
        assert param.validate_value(None) == "close"  # default

        # Options validation
        with pytest.raises(DataError, match="must be one of"):
            param.validate_value("invalid")

        # Type validation
        with pytest.raises(DataError, match="must be a string"):
            param.validate_value(123)

    def test_boolean_parameter_validation(self):
        """Test boolean parameter validation."""
        param = ParameterDefinition(
            name="adjust",
            param_type=ParameterType.BOOL,
            description="Use adjustment",
            default=True,
        )

        # Valid values
        assert param.validate_value(True) is True
        assert param.validate_value(False) is False

        # String conversion
        assert param.validate_value("true") is True
        assert param.validate_value("false") is False
        assert param.validate_value("1") is True
        assert param.validate_value("0") is False

        # Invalid values
        with pytest.raises(DataError, match="must be a boolean"):
            param.validate_value("maybe")

    def test_required_parameter(self):
        """Test required parameter validation."""
        param = ParameterDefinition(
            name="symbol",
            param_type=ParameterType.STRING,
            description="Trading symbol",
            required=True,
        )

        # Valid value
        assert param.validate_value("AAPL") == "AAPL"

        # Missing value
        with pytest.raises(DataError, match="is required"):
            param.validate_value(None)


class TestParameterConstraint:
    """Test ParameterConstraint validation logic."""

    def test_less_than_constraint(self):
        """Test less than constraint validation."""
        constraint = ParameterConstraint(
            name="test_constraint",
            description="Fast must be less than slow",
            validator=less_than("fast", "slow"),
            error_message="Fast must be less than slow",
        )

        # Valid case
        constraint.validate({"fast": 5, "slow": 10})  # Should not raise

        # Invalid case
        with pytest.raises(DataError, match="Fast must be less than slow"):
            constraint.validate({"fast": 10, "slow": 5})

    def test_greater_than_constraint(self):
        """Test greater than constraint validation."""
        constraint = ParameterConstraint(
            name="test_constraint",
            description="Period must be greater than window",
            validator=greater_than("period", "window"),
            error_message="Period must be greater than window",
        )

        # Valid case
        constraint.validate({"period": 10, "window": 5})  # Should not raise

        # Invalid case
        with pytest.raises(DataError, match="Period must be greater than window"):
            constraint.validate({"period": 5, "window": 10})

    def test_missing_parameter_in_constraint(self):
        """Test constraint with missing parameter."""
        constraint = ParameterConstraint(
            name="test_constraint",
            description="Test constraint",
            validator=less_than("param1", "param2"),
            error_message="Test error",
        )

        with pytest.raises(DataError, match="requires parameter"):
            constraint.validate({"param1": 5})  # Missing param2
