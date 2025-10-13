"""
Tests for explicit indicator naming feature.

This module tests the new two-field system: 'indicator' + 'name'
ensuring proper validation, uniqueness checks, and backward compatibility migration.
"""

import pytest

from ktrdr.config.models import IndicatorConfig, StrategyConfigurationV2
from ktrdr.errors import ConfigurationError
from pydantic import ValidationError


class TestIndicatorConfigExplicitNaming:
    """Test IndicatorConfig with explicit naming (indicator + name fields)."""

    def test_indicator_config_requires_indicator_field(self):
        """Test that 'indicator' field is required."""
        # Missing 'indicator' field should raise validation error
        with pytest.raises(ValidationError) as excinfo:
            IndicatorConfig(name="rsi_14", params={"period": 14})

        error_msg = str(excinfo.value)
        assert "indicator" in error_msg.lower()

    def test_indicator_config_requires_name_field(self):
        """Test that 'name' field is required."""
        # Missing 'name' field should raise validation error
        with pytest.raises(ValidationError) as excinfo:
            IndicatorConfig(indicator="rsi", params={"period": 14})

        error_msg = str(excinfo.value)
        assert "name" in error_msg.lower()

    def test_indicator_config_with_explicit_naming(self):
        """Test creating IndicatorConfig with explicit indicator + name."""
        config = IndicatorConfig(
            indicator="rsi",
            name="rsi_14",
            params={"period": 14}
        )

        assert config.indicator == "rsi"
        assert config.name == "rsi_14"
        assert config.params == {"period": 14}

    def test_indicator_config_with_descriptive_names(self):
        """Test that descriptive names are allowed."""
        config = IndicatorConfig(
            indicator="macd",
            name="macd_standard",
            params={"fast_period": 12, "slow_period": 26, "signal_period": 9}
        )

        assert config.indicator == "macd"
        assert config.name == "macd_standard"

    def test_indicator_config_name_validation_empty(self):
        """Test that empty names are rejected."""
        with pytest.raises(ValidationError) as excinfo:
            IndicatorConfig(
                indicator="rsi",
                name="",
                params={"period": 14}
            )

        error_msg = str(excinfo.value)
        assert "name" in error_msg.lower() or "empty" in error_msg.lower()

    def test_indicator_config_name_validation_whitespace_only(self):
        """Test that whitespace-only names are rejected."""
        with pytest.raises(ValidationError) as excinfo:
            IndicatorConfig(
                indicator="rsi",
                name="   ",
                params={"period": 14}
            )

        error_msg = str(excinfo.value)
        assert "name" in error_msg.lower() or "empty" in error_msg.lower()

    def test_indicator_config_name_validation_invalid_characters(self):
        """Test that names with invalid characters are rejected."""
        invalid_names = [
            "rsi@14",  # Special character
            "rsi 14",  # Space
            "rsi#fast", # Hash
            "123rsi",  # Starts with number (should start with letter)
        ]

        for invalid_name in invalid_names:
            with pytest.raises(ValidationError) as excinfo:
                IndicatorConfig(
                    indicator="rsi",
                    name=invalid_name,
                    params={"period": 14}
                )

            error_msg = str(excinfo.value)
            assert "name" in error_msg.lower() or "invalid" in error_msg.lower()

    def test_indicator_config_name_validation_valid_characters(self):
        """Test that names with valid characters (letters, numbers, underscore, dash) are accepted."""
        valid_names = [
            "rsi_14",
            "rsi-fast",
            "RSI_Fast",
            "macd_standard",
            "bb_tight_20_2",
            "ema50",
        ]

        for valid_name in valid_names:
            config = IndicatorConfig(
                indicator="test",
                name=valid_name,
                params={}
            )
            assert config.name == valid_name

    def test_indicator_config_flat_yaml_format(self):
        """Test that flat YAML format (params at top level) works."""
        # Simulate YAML parsing where parameters are at top level
        config_dict = {
            "indicator": "rsi",
            "name": "rsi_14",
            "period": 14,
            "source": "close"
        }

        config = IndicatorConfig(**config_dict)

        assert config.indicator == "rsi"
        assert config.name == "rsi_14"
        assert config.params == {"period": 14, "source": "close"}

    def test_indicator_config_nested_params_format(self):
        """Test that nested params format also works."""
        config_dict = {
            "indicator": "macd",
            "name": "macd_standard",
            "params": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            }
        }

        config = IndicatorConfig(**config_dict)

        assert config.indicator == "macd"
        assert config.name == "macd_standard"
        assert config.params == {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9
        }


class TestStrategyConfigIndicatorNameUniqueness:
    """Test that StrategyConfigurationV2 validates indicator name uniqueness."""

    def test_duplicate_indicator_names_rejected(self):
        """Test that duplicate indicator names are rejected."""
        strategy_dict = {
            "name": "Test Strategy",
            "version": "1.0.0",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "AAPL"},
                "timeframes": {"mode": "single", "timeframe": "1d"}
            },
            "deployment": {
                "target_symbols": {"mode": "universal"},
                "target_timeframes": {"mode": "single", "timeframe": "1d"}
            },
            "indicators": [
                {
                    "indicator": "rsi",
                    "name": "rsi_14",  # Duplicate name!
                    "period": 14
                },
                {
                    "indicator": "rsi",
                    "name": "rsi_14",  # Duplicate name!
                    "period": 7
                }
            ],
            "fuzzy_sets": {},
            "model": {},
            "decisions": {},
            "training": {}
        }

        with pytest.raises(ValidationError) as excinfo:
            StrategyConfigurationV2(**strategy_dict)

        error_msg = str(excinfo.value)
        assert "duplicate" in error_msg.lower() or "unique" in error_msg.lower()
        assert "rsi_14" in error_msg

    def test_unique_indicator_names_accepted(self):
        """Test that unique indicator names are accepted."""
        strategy_dict = {
            "name": "Test Strategy",
            "version": "1.0.0",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "AAPL"},
                "timeframes": {"mode": "single", "timeframe": "1d"}
            },
            "deployment": {
                "target_symbols": {"mode": "universal"},
                "target_timeframes": {"mode": "single", "timeframe": "1d"}
            },
            "indicators": [
                {
                    "indicator": "rsi",
                    "name": "rsi_14",
                    "period": 14
                },
                {
                    "indicator": "rsi",
                    "name": "rsi_fast",  # Different name
                    "period": 7
                }
            ],
            "fuzzy_sets": {
                "rsi_14": {"oversold": [0, 20, 40]},
                "rsi_fast": {"oversold": [0, 30, 50]}
            },
            "model": {"type": "test"},
            "decisions": {"rules": []},
            "training": {"epochs": 10}
        }

        config = StrategyConfigurationV2(**strategy_dict)
        assert len(config.indicators) == 2
        assert config.indicators[0]["name"] == "rsi_14"
        assert config.indicators[1]["name"] == "rsi_fast"

    def test_single_indicator_no_duplicate_error(self):
        """Test that a single indicator doesn't trigger duplicate errors."""
        strategy_dict = {
            "name": "Test Strategy",
            "version": "1.0.0",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "AAPL"},
                "timeframes": {"mode": "single", "timeframe": "1d"}
            },
            "deployment": {
                "target_symbols": {"mode": "universal"},
                "target_timeframes": {"mode": "single", "timeframe": "1d"}
            },
            "indicators": [
                {
                    "indicator": "rsi",
                    "name": "rsi_14",
                    "period": 14
                }
            ],
            "fuzzy_sets": {"rsi_14": {"oversold": [0, 20, 40]}},
            "model": {"type": "test"},
            "decisions": {"rules": []},
            "training": {"epochs": 10}
        }

        config = StrategyConfigurationV2(**strategy_dict)
        assert len(config.indicators) == 1

    def test_empty_indicators_list_accepted(self):
        """Test that empty indicators list doesn't cause validation errors."""
        strategy_dict = {
            "name": "Test Strategy",
            "version": "1.0.0",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "AAPL"},
                "timeframes": {"mode": "single", "timeframe": "1d"}
            },
            "deployment": {
                "target_symbols": {"mode": "universal"},
                "target_timeframes": {"mode": "single", "timeframe": "1d"}
            },
            "indicators": [],
            "fuzzy_sets": {},
            "model": {"type": "test"},
            "decisions": {"rules": []},
            "training": {"epochs": 10}
        }

        config = StrategyConfigurationV2(**strategy_dict)
        assert len(config.indicators) == 0


class TestLegacyFormatDetection:
    """Test detection and rejection of legacy format without explicit naming."""

    def test_legacy_format_missing_indicator_field_rejected(self):
        """Test that legacy format (missing 'indicator' field) is rejected."""
        # Legacy format: only has 'type' field (or 'name' in old format)
        with pytest.raises(ValidationError) as excinfo:
            IndicatorConfig(type="rsi", params={"period": 14})

        error_msg = str(excinfo.value)
        # Should indicate that 'indicator' field is required
        assert "indicator" in error_msg.lower()

    def test_legacy_format_missing_name_field_rejected(self):
        """Test that format missing 'name' field is rejected."""
        with pytest.raises(ValidationError) as excinfo:
            IndicatorConfig(indicator="rsi", params={"period": 14})

        error_msg = str(excinfo.value)
        assert "name" in error_msg.lower()
