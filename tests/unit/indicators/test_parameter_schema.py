"""
Tests for the parameter schema validation system.

This module tests the comprehensive parameter validation framework
including type validation, range validation, and constraint validation.
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
from ktrdr.indicators.schemas import MACD_SCHEMA, RSI_SCHEMA, SMA_SCHEMA


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


class TestParameterSchema:
    """Test ParameterSchema validation logic."""

    def test_schema_validation_success(self):
        """Test successful schema validation."""
        result = MACD_SCHEMA.validate(
            {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "source": "close",
            }
        )

        expected = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "source": "close",
        }
        assert result == expected

    def test_schema_with_defaults(self):
        """Test schema validation with default values."""
        result = MACD_SCHEMA.validate({})

        expected = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "source": "close",
        }
        assert result == expected

    def test_schema_constraint_validation(self):
        """Test schema constraint validation."""
        # Valid constraint
        MACD_SCHEMA.validate({"fast_period": 5, "slow_period": 10})

        # Invalid constraint
        with pytest.raises(
            DataError, match="Fast period must be less than slow period"
        ):
            MACD_SCHEMA.validate({"fast_period": 26, "slow_period": 12})

    def test_unknown_parameters(self):
        """Test unknown parameter detection."""
        with pytest.raises(DataError, match="Unknown parameters"):
            MACD_SCHEMA.validate({"invalid_param": 123})

    def test_schema_to_dict(self):
        """Test schema serialization to dictionary."""
        schema_dict = RSI_SCHEMA.to_dict()

        assert schema_dict["name"] == "RSI"
        assert (
            schema_dict["description"] == "Relative Strength Index momentum oscillator"
        )
        assert "period" in schema_dict["parameters"]
        assert "source" in schema_dict["parameters"]

        period_param = schema_dict["parameters"]["period"]
        assert period_param["type"] == "int"
        assert period_param["default"] == 14
        assert period_param["min_value"] == 2
        assert period_param["max_value"] == 100

    def test_schema_get_defaults(self):
        """Test getting default values from schema."""
        defaults = MACD_SCHEMA.get_defaults()

        expected = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "source": "close",
        }
        assert defaults == expected


class TestBuiltInSchemas:
    """Test built-in indicator schemas."""

    def test_rsi_schema(self):
        """Test RSI parameter schema."""
        # Valid parameters
        result = RSI_SCHEMA.validate({"period": 14, "source": "close"})
        assert result["period"] == 14
        assert result["source"] == "close"

        # Test defaults
        result = RSI_SCHEMA.validate({})
        assert result["period"] == 14
        assert result["source"] == "close"

        # Test validation
        with pytest.raises(DataError):
            RSI_SCHEMA.validate({"period": 1})  # Below minimum

    def test_sma_schema(self):
        """Test SMA parameter schema."""
        # Valid parameters
        result = SMA_SCHEMA.validate({"period": 20, "source": "high"})
        assert result["period"] == 20
        assert result["source"] == "high"

        # Test invalid source
        with pytest.raises(DataError):
            SMA_SCHEMA.validate({"source": "invalid"})

    def test_macd_schema_comprehensive(self):
        """Test MACD schema comprehensively."""
        # Test all parameter types
        result = MACD_SCHEMA.validate(
            {"fast_period": 5, "slow_period": 15, "signal_period": 7, "source": "high"}
        )

        assert result["fast_period"] == 5
        assert result["slow_period"] == 15
        assert result["signal_period"] == 7
        assert result["source"] == "high"

        # Test constraint
        with pytest.raises(
            DataError, match="Fast period must be less than slow period"
        ):
            MACD_SCHEMA.validate({"fast_period": 20, "slow_period": 10})


class TestErrorMessages:
    """Test detailed error message generation."""

    def test_parameter_error_details(self):
        """Test parameter validation error details."""
        try:
            MACD_SCHEMA.validate({"fast_period": "invalid"})
            assert False, "Should have raised DataError"
        except DataError as e:
            assert e.error_code == "PARAM-InvalidType"
            assert "fast_period" in e.details["parameter"]
            assert "expected" in e.details
            assert "received" in e.details

    def test_constraint_error_details(self):
        """Test constraint validation error details."""
        try:
            MACD_SCHEMA.validate({"fast_period": 30, "slow_period": 20})
            assert False, "Should have raised DataError"
        except DataError as e:
            assert e.error_code == "PARAM-ConstraintViolation"
            assert "constraint" in e.details
            assert "parameters" in e.details

    def test_range_error_details(self):
        """Test range validation error details."""
        try:
            RSI_SCHEMA.validate({"period": 0})
            assert False, "Should have raised DataError"
        except DataError as e:
            assert e.error_code == "PARAM-BelowMinimum"
            assert "minimum" in e.details
            assert "received" in e.details
