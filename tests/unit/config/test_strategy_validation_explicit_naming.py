"""
Tests for strategy validation with explicit indicator naming (Phase 3).

Tests validation of:
- Indicator-fuzzy set matching (simplified with explicit names)
- Indicator definition completeness (indicator + name fields)
- Name format validation
"""

from ktrdr.config.strategy_validator import StrategyValidator


class TestIndicatorFuzzyMatching:
    """Test simplified indicator-fuzzy matching validation."""

    def test_valid_matching_all_indicators_have_fuzzy_sets(self):
        """Test that validation passes when all indicators have fuzzy sets."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "rsi_14", "period": 14},
            {"indicator": "macd", "name": "macd_standard", "fast_period": 12},
        ]

        fuzzy_sets = {
            "rsi_14": {"oversold": [0, 20, 40]},
            "macd_standard": {"bullish": [0, 10, 50]},
        }

        result = validator._validate_indicator_fuzzy_matching(indicators, fuzzy_sets)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_fuzzy_set_for_indicator(self):
        """Test that missing fuzzy set for an indicator is an error."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "rsi_14", "period": 14},
            {"indicator": "macd", "name": "macd_standard", "fast_period": 12},
        ]

        fuzzy_sets = {
            "rsi_14": {"oversold": [0, 20, 40]},
            # macd_standard missing!
        }

        result = validator._validate_indicator_fuzzy_matching(indicators, fuzzy_sets)

        assert not result.is_valid
        assert len(result.errors) == 1
        assert "macd_standard" in result.errors[0]
        assert "no corresponding fuzzy_sets" in result.errors[0].lower()

    def test_orphan_fuzzy_set_is_warning(self):
        """Test that fuzzy set without matching indicator is a warning (not error)."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "rsi_14", "period": 14},
        ]

        fuzzy_sets = {
            "rsi_14": {"oversold": [0, 20, 40]},
            "macd_extra": {"bullish": [0, 10, 50]},  # No matching indicator
        }

        result = validator._validate_indicator_fuzzy_matching(indicators, fuzzy_sets)

        assert result.is_valid  # Still valid (just a warning)
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert "macd_extra" in result.warnings[0]
        assert "doesn't match any indicator" in result.warnings[0].lower()

    def test_multiple_missing_fuzzy_sets(self):
        """Test that multiple missing fuzzy sets all reported."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "rsi_14", "period": 14},
            {"indicator": "macd", "name": "macd_standard", "fast_period": 12},
            {"indicator": "ema", "name": "ema_50", "period": 50},
        ]

        fuzzy_sets = {
            "rsi_14": {"oversold": [0, 20, 40]},
            # macd_standard and ema_50 missing
        }

        result = validator._validate_indicator_fuzzy_matching(indicators, fuzzy_sets)

        assert not result.is_valid
        assert len(result.errors) == 2
        assert any("macd_standard" in err for err in result.errors)
        assert any("ema_50" in err for err in result.errors)

    def test_empty_indicators_list(self):
        """Test validation with no indicators."""
        validator = StrategyValidator()

        indicators = []
        fuzzy_sets = {}

        result = validator._validate_indicator_fuzzy_matching(indicators, fuzzy_sets)

        assert result.is_valid
        assert len(result.errors) == 0


class TestIndicatorDefinitionValidation:
    """Test validation of indicator definitions (Phase 3.2)."""

    def test_valid_indicator_definitions(self):
        """Test that valid indicator definitions pass."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "rsi_14", "period": 14},
            {"indicator": "macd", "name": "macd_standard", "fast_period": 12},
        ]

        result = validator._validate_indicator_definitions(indicators)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_indicator_field(self):
        """Test that missing 'indicator' field is an error."""
        validator = StrategyValidator()

        indicators = [
            {"name": "rsi_14", "period": 14},  # Missing 'indicator'
        ]

        result = validator._validate_indicator_definitions(indicators)

        assert not result.is_valid
        assert len(result.errors) == 1
        assert "indicator" in result.errors[0].lower()
        assert "required" in result.errors[0].lower()

    def test_missing_name_field(self):
        """Test that missing 'name' field is an error."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "period": 14},  # Missing 'name'
        ]

        result = validator._validate_indicator_definitions(indicators)

        assert not result.is_valid
        assert len(result.errors) == 1
        assert "name" in result.errors[0].lower()
        assert "required" in result.errors[0].lower()

    def test_invalid_name_format_starts_with_number(self):
        """Test that names starting with number are rejected."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "14_rsi", "period": 14},  # Starts with number
        ]

        result = validator._validate_indicator_definitions(indicators)

        assert not result.is_valid
        assert len(result.errors) == 1
        assert "14_rsi" in result.errors[0]
        assert "must start with letter" in result.errors[0].lower()

    def test_invalid_name_format_special_characters(self):
        """Test that names with invalid characters are rejected."""
        validator = StrategyValidator()

        invalid_names = ["rsi@14", "rsi#fast", "rsi 14", "rsi.fast"]

        for invalid_name in invalid_names:
            indicators = [
                {"indicator": "rsi", "name": invalid_name, "period": 14},
            ]

            result = validator._validate_indicator_definitions(indicators)

            assert not result.is_valid, f"Should reject name: {invalid_name}"
            assert len(result.errors) == 1
            assert invalid_name in result.errors[0]

    def test_valid_name_formats(self):
        """Test that valid name formats are accepted."""
        validator = StrategyValidator()

        valid_names = [
            "rsi_14",
            "rsi-fast",
            "RSI_Fast",
            "macd_standard",
            "bb_tight_20_2",
            "ema50",
            "MyIndicator",
        ]

        for valid_name in valid_names:
            indicators = [
                {"indicator": "test", "name": valid_name},
            ]

            result = validator._validate_indicator_definitions(indicators)

            assert result.is_valid, f"Should accept name: {valid_name}"
            assert len(result.errors) == 0

    def test_empty_name(self):
        """Test that empty name is rejected."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "", "period": 14},
        ]

        result = validator._validate_indicator_definitions(indicators)

        assert not result.is_valid
        assert len(result.errors) == 1
        assert "name" in result.errors[0].lower()

    def test_whitespace_only_name(self):
        """Test that whitespace-only name is rejected."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "   ", "period": 14},
        ]

        result = validator._validate_indicator_definitions(indicators)

        assert not result.is_valid
        assert len(result.errors) == 1

    def test_multiple_validation_errors(self):
        """Test that multiple errors are all reported."""
        validator = StrategyValidator()

        indicators = [
            {"name": "rsi_14", "period": 14},  # Missing 'indicator'
            {"indicator": "macd"},  # Missing 'name'
            {"indicator": "ema", "name": "123invalid"},  # Invalid name format
        ]

        result = validator._validate_indicator_definitions(indicators)

        assert not result.is_valid
        assert len(result.errors) == 3

    def test_indicator_index_in_error_messages(self):
        """Test that error messages include indicator index for clarity."""
        validator = StrategyValidator()

        indicators = [
            {"indicator": "rsi", "name": "rsi_14", "period": 14},  # Valid
            {"name": "macd_std"},  # Missing 'indicator' - index 1
            {"indicator": "ema"},  # Missing 'name' - index 2
        ]

        result = validator._validate_indicator_definitions(indicators)

        assert not result.is_valid
        assert len(result.errors) == 2
        # Should mention indicator #2 and #3 (1-indexed)
        assert any("#2" in err for err in result.errors)
        assert any("#3" in err for err in result.errors)


class TestIntegrationWithStrategyValidation:
    """Test that new validations integrate with existing strategy validation."""

    def test_strategy_validation_calls_indicator_validations(self):
        """Test that strategy validation includes indicator validations."""
        # This will test the integration once we implement it
        # For now, just a placeholder to remind us to test integration
        pass
