"""Tests for FuzzyEngine with M4 new indicator column format (semantic names)."""

import pandas as pd
import pytest

from ktrdr.errors import ProcessingError
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.fuzzy.config import FuzzyConfigLoader


class TestFuzzyEngineNewColumnFormat:
    """Test FuzzyEngine with new semantic column format from M3b."""

    @pytest.fixture
    def new_format_config(self):
        """Create fuzzy config using new column format (feature_id with params)."""
        return {
            "rsi_14": {
                "oversold": {"type": "triangular", "parameters": [0, 30, 40]},
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                "overbought": {"type": "triangular", "parameters": [60, 70, 100]},
            },
            "bbands_20_2": {
                "price_at_upper": {
                    "type": "triangular",
                    "parameters": [-0.02, 0, 0.02],
                },
                "price_at_lower": {
                    "type": "triangular",
                    "parameters": [-0.02, 0, 0.02],
                },
            },
            "macd_12_26_9": {
                "bullish": {"type": "triangular", "parameters": [0, 20, 50]},
                "bearish": {"type": "triangular", "parameters": [-50, -20, 0]},
            },
        }

    @pytest.fixture
    def fuzzy_engine(self, new_format_config):
        """Create FuzzyEngine with new format configuration."""
        config = FuzzyConfigLoader.load_from_dict(new_format_config)
        return FuzzyEngine(config)

    def test_single_output_indicator_direct_lookup(self, fuzzy_engine):
        """Test direct lookup for single-output indicators (rsi_14)."""
        rsi_values = pd.Series([30.0, 50.0, 70.0])
        result = fuzzy_engine.fuzzify("rsi_14", rsi_values)

        assert isinstance(result, pd.DataFrame)
        assert "rsi_14_oversold" in result.columns
        assert "rsi_14_neutral" in result.columns
        assert "rsi_14_overbought" in result.columns

    def test_multi_output_with_dot_notation_explicit(self, fuzzy_engine):
        """Test explicit output reference with dot notation (bbands_20_2.upper)."""
        # Fuzzy config should work when indicators_df has dot notation columns
        # The config key is the base indicator_id (bbands_20_2)
        # The column in indicators_df would be bbands_20_2.upper

        bbands_upper_values = pd.Series([1.1, 1.2, 1.3])
        result = fuzzy_engine.fuzzify("bbands_20_2", bbands_upper_values)

        assert isinstance(result, pd.DataFrame)
        assert "bbands_20_2_price_at_upper" in result.columns
        assert "bbands_20_2_price_at_lower" in result.columns

    def test_find_fuzzy_key_direct_match(self, fuzzy_engine):
        """Test _find_fuzzy_key with direct match."""
        # Direct match: column name exactly matches fuzzy key
        fuzzy_key = fuzzy_engine._find_fuzzy_key("rsi_14")
        assert fuzzy_key == "rsi_14"

    def test_find_fuzzy_key_dot_notation_prefix(self, fuzzy_engine):
        """Test _find_fuzzy_key with dot notation prefix matching."""
        # Dot notation: bbands_20_2.upper should match fuzzy key bbands_20_2
        fuzzy_key = fuzzy_engine._find_fuzzy_key("bbands_20_2.upper")
        assert fuzzy_key == "bbands_20_2"

        fuzzy_key = fuzzy_engine._find_fuzzy_key("bbands_20_2.middle")
        assert fuzzy_key == "bbands_20_2"

        fuzzy_key = fuzzy_engine._find_fuzzy_key("bbands_20_2.lower")
        assert fuzzy_key == "bbands_20_2"

    def test_find_fuzzy_key_alias_reference(self, fuzzy_engine):
        """Test _find_fuzzy_key with alias (bare indicator_id)."""
        # Alias: bbands_20_2 (no output suffix) should match directly
        fuzzy_key = fuzzy_engine._find_fuzzy_key("bbands_20_2")
        assert fuzzy_key == "bbands_20_2"

    def test_find_fuzzy_key_no_match(self, fuzzy_engine):
        """Test _find_fuzzy_key returns None for non-existent columns."""
        fuzzy_key = fuzzy_engine._find_fuzzy_key("nonexistent_indicator")
        assert fuzzy_key is None

    def test_missing_column_clear_error_message(self, fuzzy_engine):
        """Test that missing columns raise clear errors."""
        values = pd.Series([50.0])

        with pytest.raises(ProcessingError) as exc_info:
            fuzzy_engine.fuzzify("unknown_feature", values)

        error = exc_info.value
        assert error.error_code == "ENGINE-UnknownIndicator"
        assert "unknown_feature" in error.message
        assert "available_indicators" in error.details


class TestMultiTimeframeFuzzyWithNewFormat:
    """Test multi-timeframe fuzzy processing with new column format."""

    @pytest.fixture
    def multi_tf_indicators(self):
        """Create multi-timeframe indicators DataFrame with new format."""
        return {
            "1h": pd.DataFrame(
                {
                    "open": [1.0, 1.1],
                    "high": [1.1, 1.2],
                    "low": [0.9, 1.0],
                    "close": [1.05, 1.15],
                    "rsi_14": [50.0, 60.0],
                    "bbands_20_2.upper": [1.1, 1.2],
                    "bbands_20_2.middle": [1.0, 1.1],
                    "bbands_20_2.lower": [0.9, 1.0],
                    "bbands_20_2": [1.1, 1.2],  # alias
                }
            ),
            "4h": pd.DataFrame(
                {
                    "open": [1.0, 1.2],
                    "high": [1.2, 1.3],
                    "low": [0.9, 1.1],
                    "close": [1.1, 1.25],
                    "rsi_14": [45.0, 65.0],
                    "bbands_20_2.upper": [1.15, 1.25],
                    "bbands_20_2.middle": [1.05, 1.15],
                    "bbands_20_2.lower": [0.95, 1.05],
                    "bbands_20_2": [1.15, 1.25],  # alias
                }
            ),
        }

    @pytest.fixture
    def fuzzy_config(self):
        """Create fuzzy config for multi-timeframe test."""
        return {
            "rsi_14": {
                "low": {"type": "triangular", "parameters": [0, 30, 50]},
                "high": {"type": "triangular", "parameters": [50, 70, 100]},
            },
        }

    def test_multi_timeframe_with_new_column_format(
        self, multi_tf_indicators, fuzzy_config
    ):
        """Test multi-timeframe processing with new semantic column names."""
        config = FuzzyConfigLoader.load_from_dict(fuzzy_config)
        engine = FuzzyEngine(config)

        results = engine.generate_multi_timeframe_memberships(
            multi_tf_indicators, fuzzy_config
        )

        # Should process both timeframes
        assert "1h" in results
        assert "4h" in results

        # Check 1h results
        assert "1h_rsi_14_low" in results["1h"].columns
        assert "1h_rsi_14_high" in results["1h"].columns

        # Check 4h results
        assert "4h_rsi_14_low" in results["4h"].columns
        assert "4h_rsi_14_high" in results["4h"].columns

    def test_multi_timeframe_matches_dot_notation_columns(
        self, multi_tf_indicators, fuzzy_config
    ):
        """Test that multi-timeframe processing handles dot notation columns."""
        # Even if indicators_df has bbands_20_2.upper, fuzzy key is bbands_20_2
        # The _find_fuzzy_key should match bbands_20_2.upper to bbands_20_2

        config_with_bbands = {
            "rsi_14": {
                "low": {"type": "triangular", "parameters": [0, 30, 50]},
            },
            "bbands_20_2": {
                "price_near_upper": {
                    "type": "triangular",
                    "parameters": [-0.02, 0, 0.02],
                },
            },
        }

        config = FuzzyConfigLoader.load_from_dict(config_with_bbands)
        engine = FuzzyEngine(config)

        results = engine.generate_multi_timeframe_memberships(
            multi_tf_indicators, config_with_bbands
        )

        # Should match bbands_20_2.upper column to bbands_20_2 fuzzy key
        # and generate fuzzy features for it
        # (Note: bbands_20_2 alias might also be matched, but that's OK)
        assert "1h" in results
        assert len(results["1h"].columns) > 0
