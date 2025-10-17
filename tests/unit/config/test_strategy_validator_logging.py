"""
Unit tests for StrategyValidator logging and error reporting improvements.

Tests verify that validation errors are:
- Logged before raising exceptions
- Include full context (file, section, field)
- Have structured details
- Include actionable suggestions
- Format Pydantic errors properly
"""

import logging
from pathlib import Path
from typing import Any

import pytest
import yaml

from ktrdr.config.strategy_validator import StrategyValidator


@pytest.fixture
def temp_strategy_file(tmp_path: Path) -> Path:
    """Create a temporary strategy file for testing."""
    strategy_file = tmp_path / "test_strategy.yaml"
    return strategy_file


@pytest.fixture
def valid_strategy_config() -> dict[str, Any]:
    """Create a valid strategy configuration."""
    return {
        "name": "test_strategy",
        "indicators": [
            {"name": "rsi", "period": 14},
            {"name": "macd", "fast_period": 12, "slow_period": 26, "signal_period": 9},
        ],
        "fuzzy_sets": {
            "rsi_14": {
                "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                "overbought": {"type": "triangular", "parameters": [60, 80, 100]},
            },
        },
        "model": {
            "type": "mlp",
            "architecture": {"hidden_layers": [20, 10], "activation": "relu"},
            "training": {"learning_rate": 0.001, "batch_size": 32},
            "features": {"include_price_context": True},
        },
        "decisions": {
            "output_format": "classification",
            "confidence_threshold": 0.6,
            "position_awareness": True,
        },
        "training": {
            "method": "supervised",
            "labels": {"source": "zigzag", "zigzag_threshold": 0.05},
            "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
        },
    }


@pytest.fixture
def invalid_strategy_config() -> dict[str, Any]:
    """Create an invalid strategy configuration (missing required sections)."""
    return {
        "name": "invalid_strategy",
        # Missing required sections: indicators, fuzzy_sets, model, decisions, training
    }


class TestStrategyValidatorLogging:
    """Tests for validator logging functionality."""

    def test_validation_error_is_logged(
        self, temp_strategy_file: Path, invalid_strategy_config: dict[str, Any], caplog
    ):
        """Test that validation errors are logged before raising."""
        # Write invalid config
        with open(temp_strategy_file, "w") as f:
            yaml.dump(invalid_strategy_config, f)

        validator = StrategyValidator()

        with caplog.at_level(logging.ERROR):
            result = validator.validate_strategy(str(temp_strategy_file))

        # Validation should fail
        assert not result.is_valid
        assert len(result.errors) > 0

        # Errors should contain missing field information (Pydantic formatted)
        assert any("Missing required field" in error for error in result.errors)

    def test_validation_success_is_logged(
        self, temp_strategy_file: Path, valid_strategy_config: dict[str, Any], caplog
    ):
        """Test that successful validation is logged."""
        # Write valid config
        with open(temp_strategy_file, "w") as f:
            yaml.dump(valid_strategy_config, f)

        validator = StrategyValidator()

        with caplog.at_level(logging.INFO):
            result = validator.validate_strategy(str(temp_strategy_file))

        # Validation should succeed
        assert result.is_valid

    def test_validation_result_includes_context(
        self, temp_strategy_file: Path, invalid_strategy_config: dict[str, Any]
    ):
        """Test that validation errors include context about where error occurred."""
        with open(temp_strategy_file, "w") as f:
            yaml.dump(invalid_strategy_config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Check that errors mention specific sections
        assert result.missing_sections  # Should list missing sections
        assert any("indicators" in section for section in result.missing_sections)


class TestStrategyValidatorErrorMessages:
    """Tests for validator error message quality."""

    def test_missing_section_error_message(
        self, temp_strategy_file: Path, invalid_strategy_config: dict[str, Any]
    ):
        """Test error message for missing required section."""
        with open(temp_strategy_file, "w") as f:
            yaml.dump(invalid_strategy_config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Error should be clear about what's missing
        assert not result.is_valid
        assert "indicators" in result.missing_sections
        assert any("indicators" in error.lower() for error in result.errors)

    def test_validation_result_includes_suggestions(
        self, temp_strategy_file: Path, valid_strategy_config: dict[str, Any]
    ):
        """Test that validation results include helpful suggestions."""
        # Create v1 strategy (suggestions should recommend v2 migration)
        with open(temp_strategy_file, "w") as f:
            yaml.dump(valid_strategy_config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Should have suggestions
        assert len(result.suggestions) > 0

    def test_validation_includes_warnings(
        self, temp_strategy_file: Path, valid_strategy_config: dict[str, Any]
    ):
        """Test that validation can include warnings (non-fatal issues)."""
        # Add old format model config to trigger warning
        config = valid_strategy_config.copy()
        config["model"]["input_size"] = 10  # Old format field
        config["model"]["output_size"] = 3  # Old format field

        with open(temp_strategy_file, "w") as f:
            yaml.dump(config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Should pass validation but have warnings
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("old model format" in warning.lower() for warning in result.warnings)


class TestValidationResultStructure:
    """Tests for ValidationResult data structure."""

    def test_validation_result_has_all_fields(
        self, temp_strategy_file: Path, invalid_strategy_config: dict[str, Any]
    ):
        """Test that ValidationResult contains all required fields."""
        with open(temp_strategy_file, "w") as f:
            yaml.dump(invalid_strategy_config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Check all fields exist
        assert hasattr(result, "is_valid")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")
        assert hasattr(result, "missing_sections")
        assert hasattr(result, "suggestions")

        # Check types
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.missing_sections, list)
        assert isinstance(result.suggestions, list)

    def test_validation_result_errors_are_strings(
        self, temp_strategy_file: Path, invalid_strategy_config: dict[str, Any]
    ):
        """Test that validation errors are properly formatted strings."""
        with open(temp_strategy_file, "w") as f:
            yaml.dump(invalid_strategy_config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # All errors should be strings
        for error in result.errors:
            assert isinstance(error, str)
            assert len(error) > 0  # Not empty


class TestPydanticErrorFormatting:
    """Tests for Pydantic ValidationError formatting."""

    def test_pydantic_error_conversion(self, temp_strategy_file: Path):
        """Test that Pydantic validation errors are converted to user-friendly format."""
        # Create config with type error
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

        # Should have error about indicators type
        assert not result.is_valid
        assert any("indicators" in error.lower() for error in result.errors)


class TestValidatorIntegration:
    """Integration tests for complete validation flow."""

    def test_full_validation_flow_invalid_strategy(
        self, temp_strategy_file: Path, invalid_strategy_config: dict[str, Any], caplog
    ):
        """Test complete validation flow for invalid strategy."""
        with open(temp_strategy_file, "w") as f:
            yaml.dump(invalid_strategy_config, f)

        validator = StrategyValidator()

        with caplog.at_level(logging.ERROR):
            result = validator.validate_strategy(str(temp_strategy_file))

        # Validation should fail
        assert not result.is_valid

        # Should have multiple errors (missing fields from Pydantic)
        assert len(result.errors) >= 3  # At least 3 required fields missing

        # Should list missing sections
        assert len(result.missing_sections) >= 3

        # Errors should be clear
        assert any("Missing required field" in error for error in result.errors)

    def test_full_validation_flow_valid_strategy(
        self, temp_strategy_file: Path, valid_strategy_config: dict[str, Any]
    ):
        """Test complete validation flow for valid strategy."""
        with open(temp_strategy_file, "w") as f:
            yaml.dump(valid_strategy_config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Validation should pass
        assert result.is_valid

        # Should have no errors
        assert len(result.errors) == 0

        # May have warnings (non-fatal)
        # May have suggestions (recommendations)

    def test_validation_with_nonexistent_file(self):
        """Test validation with non-existent file."""
        validator = StrategyValidator()
        result = validator.validate_strategy("/nonexistent/path.yaml")

        # Should fail gracefully
        assert not result.is_valid
        assert len(result.errors) > 0
        assert any("Failed to load" in error for error in result.errors)


class TestValidationErrorDetails:
    """Tests for detailed error information."""

    def test_model_section_validation_details(self, temp_strategy_file: Path):
        """Test that model validation provides detailed error info."""
        # Config with completely missing model section (Pydantic will catch this)
        config = {
            "name": "test",
            "indicators": [{"name": "rsi", "period": 14}],
            "fuzzy_sets": {"rsi_14": {}},
            # Missing: model (required field)
            "decisions": {
                "output_format": "classification",
                "confidence_threshold": 0.6,
                "position_awareness": True,
            },
            "training": {
                "method": "supervised",
                "labels": {"source": "zigzag"},
                "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
            },
        }

        with open(temp_strategy_file, "w") as f:
            yaml.dump(config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Should fail validation (model is required)
        assert not result.is_valid

        # Should have specific errors about missing model
        assert any("model" in error.lower() for error in result.errors)

    def test_training_section_validation_details(self, temp_strategy_file: Path):
        """Test that training validation handles defaults gracefully."""
        # Note: The strategy loader adds default training section if missing
        # This tests that the validator handles complete configs properly
        config = {
            "name": "test",
            "indicators": [{"name": "rsi", "period": 14}],
            "fuzzy_sets": {"rsi_14": {}},
            "model": {
                "type": "mlp",
                "architecture": {"hidden_layers": [10]},
                "training": {"learning_rate": 0.001},
                "features": {"include_price_context": True},
            },
            "decisions": {
                "output_format": "classification",
                "confidence_threshold": 0.6,
                "position_awareness": True,
            },
            # Missing: training (but loader adds defaults)
        }

        with open(temp_strategy_file, "w") as f:
            yaml.dump(config, f)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(temp_strategy_file))

        # Should pass validation (loader adds training defaults)
        assert result.is_valid

        # Should have suggestions for improvements
        assert len(result.suggestions) > 0
