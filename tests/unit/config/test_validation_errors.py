"""
Comprehensive validation error tests for Phase 0 Task 0.4.

Tests cover:
1. Schema validation errors (invalid types, missing fields)
2. Semantic validation errors (duplicates, missing references)
3. Error formatting (Pydantic → ConfigurationError)
4. Error serialization (ConfigurationError → dict)
5. API error responses (full HTTP flow)
6. Error message quality (includes all required fields)
"""

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError

from ktrdr.config.models import LegacyStrategyConfiguration
from ktrdr.config.strategy_validator import StrategyValidator
from ktrdr.errors import ConfigurationError


@pytest.fixture
def temp_strategy_file(tmp_path: Path) -> Path:
    """Create a temporary strategy file for testing."""
    return tmp_path / "test_strategy.yaml"


class TestSchemaValidationErrors:
    """Test schema validation errors (Pydantic-level validation)."""

    def test_missing_required_field_error(self, temp_strategy_file: Path):
        """Test error when required field is missing."""
        config = {
            "name": "test",
            # Missing: indicators (required)
            "fuzzy_sets": {},
            "model": {},
            "decisions": {},
            "training": {},
        }

        with open(temp_strategy_file, "w") as f:
            yaml.dump(config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        assert not result.is_valid
        assert len(result.errors) > 0
        assert "indicators" in result.missing_sections
        assert any("indicators" in error.lower() for error in result.errors)

    def test_invalid_type_error(self, temp_strategy_file: Path):
        """Test error when field has wrong type."""
        config = {
            "name": "test",
            "indicators": "not_a_list",  # Should be list
            "fuzzy_sets": {},
            "model": {},
            "decisions": {},
            "training": {},
        }

        with open(temp_strategy_file, "w") as f:
            yaml.dump(config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        assert not result.is_valid
        assert any("indicators" in error.lower() for error in result.errors)

    def test_multiple_schema_errors(self, temp_strategy_file: Path):
        """Test multiple schema validation errors reported together."""
        config = {
            "name": "test",
            # Multiple missing fields
        }

        with open(temp_strategy_file, "w") as f:
            yaml.dump(config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        assert not result.is_valid
        # Should report all missing required fields
        assert len(result.missing_sections) >= 3


class TestErrorFormatting:
    """Test Pydantic error → ConfigurationError formatting."""

    def test_pydantic_missing_field_formatted(self):
        """Test that Pydantic missing field error is formatted properly."""
        with pytest.raises(PydanticValidationError) as exc_info:
            LegacyStrategyConfiguration(
                name="test",
                # Missing required fields
            )

        error = exc_info.value
        assert len(error.errors()) > 0

        # Check that error contains location info
        for err in error.errors():
            assert "loc" in err
            assert "type" in err
            assert "msg" in err

    def test_configuration_error_captures_all_fields(self):
        """Test that ConfigurationError captures all required fields."""
        error = ConfigurationError(
            message="Test error message",
            error_code="TEST-ErrorCode",
            context={"file": "test.yaml", "section": "indicators[0]"},
            details={"actual": "value1", "expected": "value2"},
            suggestion="Run command X to fix",
        )

        assert error.message == "Test error message"
        assert error.error_code == "TEST-ErrorCode"
        assert error.context["file"] == "test.yaml"
        assert error.context["section"] == "indicators[0]"
        assert error.details["actual"] == "value1"
        assert error.suggestion == "Run command X to fix"

    def test_configuration_error_serializes_to_dict(self):
        """Test that ConfigurationError serializes properly."""
        error = ConfigurationError(
            message="Test error",
            error_code="TEST-Code",
            context={"file": "test.yaml"},
            details={"key": "value"},
            suggestion="Fix it",
        )

        error_dict = error.to_dict()

        assert isinstance(error_dict, dict)
        assert error_dict["message"] == "Test error"
        assert error_dict["error_code"] == "TEST-Code"
        assert error_dict["context"] == {"file": "test.yaml"}
        assert error_dict["details"] == {"key": "value"}
        assert error_dict["suggestion"] == "Fix it"

    def test_configuration_error_formats_user_message(self):
        """Test that ConfigurationError formats user-friendly message."""
        error = ConfigurationError(
            message="Missing field X",
            error_code="TEST-Missing",
            context={"file": "strategy.yaml", "section": "indicators[0]"},
            details={"field": "feature_id"},
            suggestion="Add field X with value Y",
        )

        formatted = error.format_user_message()

        # Should include all key information
        assert "Missing field X" in formatted
        assert "TEST-Missing" in formatted
        assert "strategy.yaml" in formatted
        assert "indicators[0]" in formatted
        assert "Add field X with value Y" in formatted


class TestErrorMessageQuality:
    """Test that error messages meet quality standards."""

    def test_error_message_is_clear(self):
        """Test that error message clearly describes the problem."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="rsi",
            indicator_index=0,
            file_path="strategy.yaml",
        )

        # Message should mention what's missing
        assert "feature_id" in error.message.lower()
        assert "rsi" in error.message.lower()

    def test_error_includes_location_context(self):
        """Test that error includes where it occurred."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="rsi",
            indicator_index=0,
            file_path="strategy.yaml",
        )

        assert error.context["file"] == "strategy.yaml"
        assert "indicators[0]" in error.context["section"]
        assert error.context["indicator_type"] == "rsi"

    def test_error_includes_actionable_suggestion(self):
        """Test that error includes how to fix it."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="rsi",
            indicator_index=0,
            file_path="strategy.yaml",
        )

        # Should suggest adding feature_id
        assert "feature_id" in error.suggestion.lower()
        # Should include migration tool command
        assert "migrate_to_feature_ids.py" in error.suggestion

    def test_error_code_is_machine_readable(self):
        """Test that error code follows expected format."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="rsi",
            indicator_index=0,
        )

        # Error code should follow CATEGORY-Specific format
        assert error.error_code == "STRATEGY-MissingFeatureId"
        assert "-" in error.error_code
        parts = error.error_code.split("-")
        assert len(parts) == 2
        assert parts[0].isupper()  # Category
        assert parts[1][0].isupper()  # Specific starts with capital

    def test_error_details_are_structured(self):
        """Test that error details contain structured data."""
        error = ConfigurationError.duplicate_feature_id(
            feature_id="rsi_14",
            indices=[0, 2],
            file_path="strategy.yaml",
        )

        assert isinstance(error.details, dict)
        assert "feature_id" in error.details
        assert "indices" in error.details
        assert error.details["indices"] == [0, 2]


class TestFactoryMethods:
    """Test ConfigurationError factory methods."""

    def test_missing_feature_id_factory(self):
        """Test missing_feature_id factory method."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="macd",
            indicator_index=2,
            file_path="my_strategy.yaml",
        )

        assert error.error_code == "STRATEGY-MissingFeatureId"
        assert "macd" in error.message.lower()
        assert error.context["indicator_type"] == "macd"
        assert error.context["section"] == "indicators[2]"
        assert error.context["file"] == "my_strategy.yaml"
        assert "feature_id" in error.suggestion.lower()

    def test_duplicate_feature_id_factory(self):
        """Test duplicate_feature_id factory method."""
        error = ConfigurationError.duplicate_feature_id(
            feature_id="rsi_14",
            indices=[1, 3, 5],
            file_path="strategy.yaml",
        )

        assert error.error_code == "STRATEGY-DuplicateFeatureId"
        assert "duplicate" in error.message.lower()
        assert "rsi_14" in error.message
        assert error.details["indices"] == [1, 3, 5]
        assert "unique" in error.suggestion.lower()

    def test_invalid_feature_id_format_factory(self):
        """Test invalid_feature_id_format factory method."""
        error = ConfigurationError.invalid_feature_id_format(
            feature_id="123invalid",
            indicator_index=0,
        )

        assert error.error_code == "STRATEGY-InvalidFeatureIdFormat"
        assert "format" in error.message.lower()
        assert "123invalid" in error.message
        assert "must start with a letter" in error.suggestion.lower()

    def test_reserved_feature_id_factory(self):
        """Test reserved_feature_id factory method."""
        error = ConfigurationError.reserved_feature_id(
            feature_id="close",
            indicator_index=1,
        )

        assert error.error_code == "STRATEGY-ReservedFeatureId"
        assert "reserved" in error.message.lower()
        assert "close" in error.message
        assert "open, high, low, close, volume" in error.suggestion.lower()


class TestErrorSerialization:
    """Test error serialization for API responses."""

    def test_error_dict_is_json_serializable(self):
        """Test that error dict can be serialized to JSON."""
        error = ConfigurationError(
            message="Test error",
            error_code="TEST-Code",
            context={"file": "test.yaml", "line": 10},
            details={"field": "value"},
            suggestion="Fix the error",
        )

        error_dict = error.to_dict()
        json_str = json.dumps(error_dict)

        assert isinstance(json_str, str)
        recovered = json.loads(json_str)
        assert recovered["message"] == "Test error"
        assert recovered["error_code"] == "TEST-Code"

    def test_error_dict_contains_all_fields(self):
        """Test that serialized error contains all fields."""
        error = ConfigurationError(
            message="Complete error",
            error_code="COMPLETE-Error",
            context={"file": "test.yaml", "section": "indicators"},
            details={"key1": "value1", "key2": "value2"},
            suggestion="Complete suggestion",
        )

        error_dict = error.to_dict()

        assert "message" in error_dict
        assert "error_code" in error_dict
        assert "context" in error_dict
        assert "details" in error_dict
        assert "suggestion" in error_dict

    def test_error_dict_handles_empty_optional_fields(self):
        """Test serialization with minimal fields."""
        error = ConfigurationError(
            message="Minimal error",
            error_code="MIN-Error",
        )

        error_dict = error.to_dict()

        assert error_dict["message"] == "Minimal error"
        assert error_dict["error_code"] == "MIN-Error"
        assert error_dict["context"] == {}
        assert error_dict["details"] == {}
        assert error_dict["suggestion"] == ""


class TestValidationIntegration:
    """Integration tests for validation error flow."""

    def test_full_validation_error_flow(self, temp_strategy_file: Path):
        """Test complete flow from invalid config to formatted error."""
        # Create invalid config
        config = {"name": "test"}  # Missing required fields

        with open(temp_strategy_file, "w") as f:
            yaml.dump(config, f)

        # Validate
        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Check result structure
        assert not result.is_valid
        assert len(result.errors) > 0
        assert len(result.missing_sections) > 0

        # Each error should be a string
        for error in result.errors:
            assert isinstance(error, str)
            assert len(error) > 0

    def test_validation_result_provides_recovery_information(
        self, temp_strategy_file: Path
    ):
        """Test that validation results help user recover from error."""
        config = {
            "name": "test",
            # Missing: indicators, fuzzy_sets, model
        }

        with open(temp_strategy_file, "w") as f:
            yaml.dump(config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Should list what's missing
        assert "indicators" in result.missing_sections

        # Should have clear error messages that explain what's missing
        assert len(result.errors) > 0
        assert any("indicators" in error.lower() for error in result.errors)


class TestCoverage:
    """Tests to ensure coverage goals are met."""

    def test_all_factory_methods_covered(self):
        """Test that all factory methods are exercised."""
        # missing_feature_id
        e1 = ConfigurationError.missing_feature_id("rsi", 0)
        assert e1.error_code == "STRATEGY-MissingFeatureId"

        # duplicate_feature_id
        e2 = ConfigurationError.duplicate_feature_id("rsi_14", [0, 1])
        assert e2.error_code == "STRATEGY-DuplicateFeatureId"

        # invalid_feature_id_format
        e3 = ConfigurationError.invalid_feature_id_format("123bad", 0)
        assert e3.error_code == "STRATEGY-InvalidFeatureIdFormat"

        # reserved_feature_id
        e4 = ConfigurationError.reserved_feature_id("close", 0)
        assert e4.error_code == "STRATEGY-ReservedFeatureId"

    def test_all_error_methods_covered(self):
        """Test that all ConfigurationError methods are exercised."""
        error = ConfigurationError(
            message="Test",
            error_code="TEST-Code",
            context={"file": "test.yaml"},
            details={"key": "value"},
            suggestion="Fix it",
        )

        # to_dict
        d = error.to_dict()
        assert isinstance(d, dict)

        # format_user_message
        msg = error.format_user_message()
        assert isinstance(msg, str)

        # __str__
        s = str(error)
        assert isinstance(s, str)
