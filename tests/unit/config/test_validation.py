"""
Tests for the input validation utilities.

This module tests validation of user-provided parameters.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from ktrdr.config.validation import (
    InputValidator,
    sanitize_parameter,
    sanitize_parameters,
)
from ktrdr.errors import ValidationError


class TestInputValidator:
    """Tests for the InputValidator class."""

    # String validation tests
    def test_validate_string_valid(self):
        """Test validating a valid string."""
        result = InputValidator.validate_string("test", min_length=2, max_length=10)
        assert result == "test"

    def test_validate_string_wrong_type(self):
        """Test validating a non-string value."""
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_string(123)
        assert "Expected string" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-TypeError"

    def test_validate_string_too_short(self):
        """Test validating a string that is too short."""
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_string("a", min_length=2)
        assert "String too short" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-StringTooShort"

    def test_validate_string_too_long(self):
        """Test validating a string that is too long."""
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_string("toolong", max_length=5)
        assert "String too long" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-StringTooLong"

    def test_validate_string_pattern(self):
        """Test validating a string against a pattern."""
        # Valid pattern
        result = InputValidator.validate_string("abc123", pattern=r"^[a-z]+[0-9]+$")
        assert result == "abc123"

        # Invalid pattern
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_string("123abc", pattern=r"^[a-z]+[0-9]+$")
        assert "does not match" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-PatternMismatch"

    def test_validate_string_allowed_values(self):
        """Test validating a string against allowed values."""
        # Valid value
        result = InputValidator.validate_string(
            "apple", allowed_values={"apple", "orange", "banana"}
        )
        assert result == "apple"

        # Invalid value
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_string(
                "grape", allowed_values={"apple", "orange", "banana"}
            )
        assert "not in allowed set" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-InvalidValue"

    # Numeric validation tests
    def test_validate_numeric_valid(self):
        """Test validating a valid numeric value."""
        result = InputValidator.validate_numeric(10, min_value=5, max_value=15)
        assert result == 10

    def test_validate_numeric_wrong_type(self):
        """Test validating a non-numeric value."""
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_numeric("10")
        assert "Expected numeric value" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-TypeError"

    def test_validate_numeric_too_small(self):
        """Test validating a numeric value that is too small."""
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_numeric(3, min_value=5)
        assert "below minimum" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-BelowMinimum"

    def test_validate_numeric_too_large(self):
        """Test validating a numeric value that is too large."""
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_numeric(20, max_value=15)
        assert "above maximum" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-AboveMaximum"

    def test_validate_numeric_allowed_values(self):
        """Test validating a numeric value against allowed values."""
        # Valid value
        result = InputValidator.validate_numeric(10, allowed_values={5, 10, 15})
        assert result == 10

        # Invalid value
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_numeric(12, allowed_values={5, 10, 15})
        assert "not in allowed set" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-InvalidValue"

    # Date validation tests
    def test_validate_date_valid(self):
        """Test validating a valid date string."""
        result = InputValidator.validate_date("2023-01-15")
        assert result == datetime(2023, 1, 15)

    def test_validate_date_invalid_format(self):
        """Test validating a date string with invalid format."""
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_date("15/01/2023")
        assert "Invalid date format" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-DateFormat"

    def test_validate_date_too_early(self):
        """Test validating a date that is too early."""
        min_date = datetime(2023, 1, 1)
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_date("2022-12-31", min_date=min_date)
        assert "before minimum date" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-DateTooEarly"

    def test_validate_date_too_late(self):
        """Test validating a date that is too late."""
        max_date = datetime(2023, 12, 31)
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_date("2024-01-01", max_date=max_date)
        assert "after maximum date" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-DateTooLate"

    def test_validate_date_custom_format(self):
        """Test validating a date with a custom format."""
        result = InputValidator.validate_date("15/01/2023", format_string="%d/%m/%Y")
        assert result == datetime(2023, 1, 15)

    # File path validation tests
    def test_validate_file_path_valid(self):
        """Test validating a valid file path."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            result = InputValidator.validate_file_path(tmp.name)
            assert isinstance(result, Path)

    def test_validate_file_path_not_exist(self):
        """Test validating a file path that doesn't exist."""
        with pytest.raises(ValidationError) as excinfo:
            InputValidator.validate_file_path(
                "/path/to/nonexistent/file.txt", must_exist=True
            )
        assert "does not exist" in str(excinfo.value)
        assert excinfo.value.error_code == "VAL-FileNotFound"

    def test_validate_file_path_wrong_type(self):
        """Test validating a file path with wrong file type."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            with pytest.raises(ValidationError) as excinfo:
                InputValidator.validate_file_path(tmp.name, file_type="csv")
            assert "Expected file type" in str(excinfo.value)
            assert excinfo.value.error_code == "VAL-WrongFileType"


class TestSanitizeFunctions:
    """Tests for the parameter sanitization functions."""

    def test_sanitize_parameter_path(self):
        """Test sanitizing a path parameter."""
        result = sanitize_parameter("file_path", "test/path")
        assert isinstance(result, str)
        assert Path(result).is_absolute()

    def test_sanitize_parameter_string(self):
        """Test sanitizing a string parameter."""
        # String with control characters
        result = sanitize_parameter("name", "test\x00\x01string")
        assert result == "teststring"  # Control chars removed

    def test_sanitize_parameter_non_string(self):
        """Test sanitizing a non-string parameter."""
        result = sanitize_parameter("count", 10)
        assert result == 10  # Unchanged

    def test_sanitize_parameters(self):
        """Test sanitizing multiple parameters."""
        params = {"path": "test/path", "name": "test\x00string", "count": 10}
        result = sanitize_parameters(params)
        assert len(result) == 3
        assert Path(result["path"]).is_absolute()
        assert result["name"] == "teststring"
        assert result["count"] == 10
