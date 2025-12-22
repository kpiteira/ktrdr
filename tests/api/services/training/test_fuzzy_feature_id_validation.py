"""Tests for fuzzy set validation using feature_id as source of truth.

This test covers the fix for the validation issue where Claude-designed strategies
used PascalCase indicator names (from API) but lowercase feature_ids for fuzzy sets.

The fix ensures feature_ids are included in valid targets for fuzzy set validation.
"""

from ktrdr.api.endpoints.strategies import _validate_strategy_config


class TestFuzzySetFeatureIdValidation:
    """Tests for fuzzy set validation with feature_id matching."""

    def test_pascalcase_indicator_with_lowercase_feature_id_passes(self):
        """Strategy with PascalCase indicator name but lowercase feature_id should pass.

        This was the root cause of validation failures for Claude-designed strategies:
        - API returns indicator names like 'Ichimoku', 'RSI', 'SuperTrend'
        - Claude uses these names in strategy configs
        - Fuzzy sets use feature_id (e.g., 'ichimoku_9') as keys
        - Validation should match fuzzy set keys against feature_ids, not just indicator names
        """
        config = {
            "indicators": [
                {
                    "name": "Ichimoku",  # PascalCase from API
                    "feature_id": "ichimoku_9",  # Lowercase feature_id
                    "params": {"conversion_period": 9},
                },
                {
                    "name": "RSI",  # PascalCase
                    "feature_id": "rsi_14",
                    "params": {"period": 14},
                },
            ],
            "fuzzy_sets": {
                "ichimoku_9": {  # Matches feature_id, not indicator name
                    "bearish_cloud": {
                        "type": "trapezoid",
                        "parameters": [-100, -100, -20, 0],
                    },
                    "neutral": {"type": "triangle", "parameters": [-20, 0, 20]},
                    "bullish_cloud": {
                        "type": "trapezoid",
                        "parameters": [0, 20, 100, 100],
                    },
                },
                "rsi_14": {
                    "oversold": {"type": "trapezoid", "parameters": [0, 0, 20, 30]},
                    "neutral": {"type": "triangle", "parameters": [20, 50, 80]},
                    "overbought": {
                        "type": "trapezoid",
                        "parameters": [70, 80, 100, 100],
                    },
                },
            },
        }

        issues = _validate_strategy_config(config, "test_strategy")
        errors = [i for i in issues if i.severity == "error"]

        # Should have no errors - feature_ids are valid targets
        assert len(errors) == 0, f"Unexpected errors: {[e.message for e in errors]}"

    def test_lowercase_indicator_with_matching_feature_id_passes(self):
        """Backward compatibility: lowercase indicator names still work."""
        config = {
            "indicators": [
                {
                    "name": "rsi",  # lowercase
                    "feature_id": "rsi_14",
                    "params": {"period": 14},
                }
            ],
            "fuzzy_sets": {
                "rsi_14": {
                    "oversold": {"type": "trapezoid", "parameters": [0, 0, 20, 30]},
                }
            },
        }

        issues = _validate_strategy_config(config, "test_strategy")
        errors = [i for i in issues if i.severity == "error"]

        assert len(errors) == 0

    def test_fuzzy_set_without_matching_feature_id_fails(self):
        """Fuzzy set that doesn't match any feature_id or indicator should fail."""
        config = {
            "indicators": [
                {
                    "name": "RSI",
                    "feature_id": "rsi_14",
                    "params": {"period": 14},
                }
            ],
            "fuzzy_sets": {
                "unknown_indicator": {  # No matching feature_id or indicator name
                    "high": {"type": "trapezoid", "parameters": [0, 0, 50, 100]},
                }
            },
        }

        issues = _validate_strategy_config(config, "test_strategy")
        errors = [i for i in issues if i.severity == "error"]

        # Should have error about invalid fuzzy set reference
        assert len(errors) > 0
        assert any("unknown_indicator" in e.message for e in errors)

    def test_multiple_indicators_with_different_case_feature_ids(self):
        """Multiple indicators with different casing all validate via feature_ids."""
        config = {
            "indicators": [
                {
                    "name": "SuperTrend",  # PascalCase
                    "feature_id": "supertrend_10",
                    "params": {"period": 10, "multiplier": 3.0},
                },
                {
                    "name": "BollingerBands",
                    "feature_id": "bb_20",
                    "params": {"period": 20, "std_dev": 2.0},
                },
                {
                    "name": "MACD",
                    "feature_id": "macd_standard",
                    "params": {},
                },
            ],
            "fuzzy_sets": {
                "supertrend_10": {
                    "bullish": {"type": "trapezoid", "parameters": [0, 0, 0.5, 1]},
                    "bearish": {"type": "trapezoid", "parameters": [-1, -0.5, 0, 0]},
                },
                "bb_20": {
                    "squeeze": {"type": "trapezoid", "parameters": [0, 0, 0.01, 0.02]},
                    "expansion": {
                        "type": "trapezoid",
                        "parameters": [0.02, 0.05, 1, 1],
                    },
                },
                "macd_standard": {
                    "bearish": {"type": "trapezoid", "parameters": [-10, -10, -2, 0]},
                    "bullish": {"type": "trapezoid", "parameters": [0, 2, 10, 10]},
                },
            },
        }

        issues = _validate_strategy_config(config, "test_strategy")
        errors = [i for i in issues if i.severity == "error"]

        assert len(errors) == 0, f"Unexpected errors: {[e.message for e in errors]}"

    def test_price_data_fuzzy_sets_still_work(self):
        """Built-in price data columns should still be valid fuzzy set targets."""
        config = {
            "indicators": [
                {
                    "name": "RSI",
                    "feature_id": "rsi_14",
                    "params": {"period": 14},
                }
            ],
            "fuzzy_sets": {
                "rsi_14": {
                    "oversold": {"type": "trapezoid", "parameters": [0, 0, 20, 30]},
                },
                "close": {  # Built-in price column
                    "low": {"type": "trapezoid", "parameters": [0, 0, 50, 100]},
                    "high": {"type": "trapezoid", "parameters": [100, 150, 200, 200]},
                },
                "volume": {  # Built-in volume column
                    "low": {"type": "trapezoid", "parameters": [0, 0, 1000, 5000]},
                },
            },
        }

        issues = _validate_strategy_config(config, "test_strategy")
        errors = [i for i in issues if i.severity == "error"]

        assert len(errors) == 0
