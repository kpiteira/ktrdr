"""
Unit tests for enhanced ConfigurationError class.

Tests verify that configuration errors include all required fields:
- message: Human-readable error
- error_code: Machine-readable code
- context: Where error occurred (file, section, field)
- details: Structured data about the error
- suggestion: How to fix the error
"""

import pytest

from ktrdr.errors import ConfigurationError


class TestConfigurationError:
    """Tests for ConfigurationError class."""

    def test_basic_error_creation(self):
        """Test creating a basic configuration error with all required fields."""
        error = ConfigurationError(
            message="Indicator missing required field 'feature_id'",
            error_code="STRATEGY-MissingFeatureId",
            context={
                "file": "strategy.yaml",
                "section": "indicators[0]",
                "indicator_type": "rsi",
            },
            details={"indicator": {"type": "rsi", "period": 14}, "missing_field": "feature_id"},
            suggestion="Add 'feature_id' to indicator:\n  - type: \"rsi\"\n    feature_id: \"rsi_14\"  # ADD THIS\n    period: 14",
        )

        assert error.message == "Indicator missing required field 'feature_id'"
        assert error.error_code == "STRATEGY-MissingFeatureId"
        assert error.context == {
            "file": "strategy.yaml",
            "section": "indicators[0]",
            "indicator_type": "rsi",
        }
        assert error.details["missing_field"] == "feature_id"
        assert "feature_id" in error.suggestion

    def test_error_to_dict(self):
        """Test serializing error to dictionary for API responses."""
        error = ConfigurationError(
            message="Test error",
            error_code="TEST-Error",
            context={"file": "test.yaml"},
            details={"key": "value"},
            suggestion="Fix the test",
        )

        error_dict = error.to_dict()

        assert error_dict["message"] == "Test error"
        assert error_dict["error_code"] == "TEST-Error"
        assert error_dict["context"] == {"file": "test.yaml"}
        assert error_dict["details"] == {"key": "value"}
        assert error_dict["suggestion"] == "Fix the test"

    def test_error_format_user_message(self):
        """Test formatting user-friendly error message."""
        error = ConfigurationError(
            message="Duplicate feature_id found",
            error_code="STRATEGY-DuplicateFeatureId",
            context={
                "file": "strategy.yaml",
                "section": "indicators",
                "feature_id": "rsi_14",
            },
            details={
                "duplicates": ["rsi_14", "rsi_14"],
                "indices": [0, 2],
            },
            suggestion="Ensure each indicator has a unique feature_id",
        )

        formatted = error.format_user_message()

        # Should include all key information
        assert "Duplicate feature_id found" in formatted
        assert "STRATEGY-DuplicateFeatureId" in formatted
        assert "strategy.yaml" in formatted
        assert "indicators" in formatted
        assert "Ensure each indicator has a unique feature_id" in formatted

    def test_error_string_representation(self):
        """Test string representation of error."""
        error = ConfigurationError(
            message="Test error",
            error_code="TEST-Error",
            context={"file": "test.yaml"},
            details={},
            suggestion="",
        )

        error_str = str(error)
        assert "Test error" in error_str
        assert "TEST-Error" in error_str

    def test_error_with_minimal_fields(self):
        """Test that error works with only required fields."""
        error = ConfigurationError(
            message="Simple error",
            error_code="SIMPLE-Error",
        )

        assert error.message == "Simple error"
        assert error.error_code == "SIMPLE-Error"
        assert error.context == {}
        assert error.details == {}
        assert error.suggestion == ""

    def test_error_with_migration_suggestion(self):
        """Test error that includes migration tool command in suggestion."""
        error = ConfigurationError(
            message="Indicator missing required field 'feature_id'",
            error_code="STRATEGY-MissingFeatureId",
            context={"file": "strategy.yaml", "section": "indicators[0]"},
            details={"indicator_type": "rsi"},
            suggestion=(
                "Add 'feature_id' to indicator:\n\n"
                "indicators:\n"
                "  - type: \"rsi\"\n"
                "    feature_id: \"rsi_14\"  # ADD THIS\n"
                "    period: 14\n\n"
                "Or run migration tool:\n"
                "  python scripts/migrate_to_feature_ids.py strategy.yaml"
            ),
        )

        assert "migrate_to_feature_ids.py" in error.suggestion
        assert "python scripts/" in error.suggestion

    def test_error_context_with_nested_path(self):
        """Test error with deeply nested context path."""
        error = ConfigurationError(
            message="Invalid parameter value",
            error_code="CONFIG-InvalidValue",
            context={
                "file": "strategy.yaml",
                "section": "model.architecture.hidden_layers",
                "index": 0,
            },
            details={"expected": "int", "actual": "str", "value": "invalid"},
            suggestion="Hidden layers must be a list of integers",
        )

        assert error.context["section"] == "model.architecture.hidden_layers"
        assert error.context["index"] == 0

    def test_error_details_structured_data(self):
        """Test that details can contain complex structured data."""
        error = ConfigurationError(
            message="Validation failed",
            error_code="VALIDATION-Failed",
            context={"file": "strategy.yaml"},
            details={
                "errors": [
                    {"field": "indicators[0].feature_id", "issue": "missing"},
                    {"field": "indicators[2].feature_id", "issue": "duplicate"},
                ],
                "warnings": [{"field": "fuzzy_sets.orphan", "issue": "no matching indicator"}],
            },
            suggestion="Fix validation errors listed in details",
        )

        assert len(error.details["errors"]) == 2
        assert len(error.details["warnings"]) == 1
        assert error.details["errors"][0]["field"] == "indicators[0].feature_id"


class TestConfigurationErrorFactory:
    """Tests for common configuration error factory methods."""

    def test_missing_feature_id_error(self):
        """Test factory method for missing feature_id error."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="rsi",
            indicator_index=0,
            file_path="strategy.yaml",
        )

        assert error.error_code == "STRATEGY-MissingFeatureId"
        assert "feature_id" in error.message.lower()
        assert error.context["indicator_type"] == "rsi"
        assert error.context["section"] == "indicators[0]"
        assert "migrate_to_feature_ids.py" in error.suggestion

    def test_duplicate_feature_id_error(self):
        """Test factory method for duplicate feature_id error."""
        error = ConfigurationError.duplicate_feature_id(
            feature_id="rsi_14",
            indices=[0, 2],
            file_path="strategy.yaml",
        )

        assert error.error_code == "STRATEGY-DuplicateFeatureId"
        assert "duplicate" in error.message.lower()
        assert error.context["feature_id"] == "rsi_14"
        assert error.details["indices"] == [0, 2]

    def test_invalid_feature_id_format_error(self):
        """Test factory method for invalid feature_id format error."""
        error = ConfigurationError.invalid_feature_id_format(
            feature_id="123invalid",
            indicator_index=0,
            file_path="strategy.yaml",
        )

        assert error.error_code == "STRATEGY-InvalidFeatureIdFormat"
        assert "format" in error.message.lower()
        assert error.context["feature_id"] == "123invalid"
        assert "must start with a letter" in error.suggestion.lower()

    def test_reserved_feature_id_error(self):
        """Test factory method for reserved feature_id error."""
        error = ConfigurationError.reserved_feature_id(
            feature_id="close",
            indicator_index=0,
            file_path="strategy.yaml",
        )

        assert error.error_code == "STRATEGY-ReservedFeatureId"
        assert "reserved" in error.message.lower()
        assert error.context["feature_id"] == "close"
        assert "open, high, low, close, volume" in error.suggestion.lower()


class TestConfigurationErrorIntegration:
    """Integration tests for ConfigurationError with exception handling."""

    def test_error_can_be_raised_and_caught(self):
        """Test that ConfigurationError can be raised and caught properly."""
        with pytest.raises(ConfigurationError) as exc_info:
            raise ConfigurationError(
                message="Test error",
                error_code="TEST-Error",
            )

        error = exc_info.value
        assert error.message == "Test error"
        assert error.error_code == "TEST-Error"

    def test_error_preserves_traceback(self):
        """Test that error preserves stack trace information."""
        try:
            raise ConfigurationError(
                message="Deep error",
                error_code="DEEP-Error",
            )
        except ConfigurationError as e:
            assert e.message == "Deep error"
            # Error should be catchable and re-raisable
            with pytest.raises(ConfigurationError):
                raise e

    def test_error_in_api_context(self):
        """Test serializing error for API response."""
        error = ConfigurationError(
            message="API error",
            error_code="API-Error",
            context={"endpoint": "/strategies/validate"},
            details={"request_id": "12345"},
            suggestion="Check API documentation",
        )

        # Should be able to convert to dict for JSON response
        error_dict = error.to_dict()
        assert isinstance(error_dict, dict)
        assert "message" in error_dict
        assert "error_code" in error_dict
        assert "context" in error_dict
        assert "details" in error_dict
        assert "suggestion" in error_dict

        # Should be JSON-serializable
        import json

        json_str = json.dumps(error_dict)
        assert isinstance(json_str, str)
        recovered = json.loads(json_str)
        assert recovered["message"] == "API error"
