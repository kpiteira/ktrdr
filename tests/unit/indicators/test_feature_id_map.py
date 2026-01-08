"""
Unit tests for IndicatorEngine feature_id_map functionality (v2 format).

NOTE: These tests are for v2 list-based indicator config format.
The feature_id_map is a v2-specific concept that will be removed in Task 8.5.
In v3 format, indicator_id serves directly as the feature identifier.

These tests validate backward compatibility with v2 format until full removal.
"""

import pytest

from ktrdr.indicators.indicator_engine import IndicatorEngine

# Skip entire module - v2 tests will be removed in Task 8.5
pytestmark = pytest.mark.skip(
    reason="v2 feature_id_map tests - v2 format will be removed in Task 8.5"
)


class TestFeatureIdMapInitialization:
    """Test feature_id_map is correctly built during IndicatorEngine initialization."""

    def test_feature_id_map_created_on_init(self):
        """Test that feature_id_map attribute is created during initialization."""
        # Given: A simple indicator config with feature_id
        configs = [{"name": "rsi", "feature_id": "rsi_14", "period": 14}]

        # When: Creating IndicatorEngine with configs
        engine = IndicatorEngine(indicators=configs)

        # Then: feature_id_map should exist as an attribute
        assert hasattr(
            engine, "feature_id_map"
        ), "IndicatorEngine should have feature_id_map attribute"
        assert isinstance(
            engine.feature_id_map, dict
        ), "feature_id_map should be a dictionary"

    def test_feature_id_map_single_indicator(self):
        """Test feature_id_map correctly maps column_name to feature_id for single indicator."""
        # Given: A single RSI indicator config
        configs = [{"name": "rsi", "feature_id": "rsi_14", "period": 14}]

        # When: Creating IndicatorEngine
        engine = IndicatorEngine(indicators=configs)

        # Then: feature_id_map should have correct mapping
        # RSI column name is "rsi_14" (from get_column_name), feature_id is "rsi_14"
        assert (
            "rsi_14" in engine.feature_id_map
        ), "Column name should be in feature_id_map"
        assert (
            engine.feature_id_map["rsi_14"] == "rsi_14"
        ), "Should map column name to feature_id"

    def test_feature_id_map_multiple_indicators(self):
        """Test feature_id_map with multiple indicators."""
        # Given: Multiple indicator configs with different feature_ids
        configs = [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14},
            {"name": "rsi", "feature_id": "rsi_21", "period": 21},
            {"name": "ema", "feature_id": "ema_20", "period": 20},
        ]

        # When: Creating IndicatorEngine
        engine = IndicatorEngine(indicators=configs)

        # Then: feature_id_map should have all mappings
        assert len(engine.feature_id_map) == 3, "Should have 3 mappings"
        assert engine.feature_id_map["rsi_14"] == "rsi_14"
        assert engine.feature_id_map["rsi_21"] == "rsi_21"
        assert engine.feature_id_map["ema_20"] == "ema_20"

    def test_feature_id_map_different_from_column_name(self):
        """Test feature_id_map when feature_id differs from auto-generated column name."""
        # Given: RSI with semantic feature_id (different from column name)
        configs = [{"name": "rsi", "feature_id": "rsi_fast", "period": 7}]

        # When: Creating IndicatorEngine
        engine = IndicatorEngine(indicators=configs)

        # Then: Should map technical column name to user-facing feature_id
        # Column name is "rsi_7" but feature_id is "rsi_fast"
        assert "rsi_7" in engine.feature_id_map, "Technical column name should be key"
        assert (
            engine.feature_id_map["rsi_7"] == "rsi_fast"
        ), "Should map to semantic feature_id"

    def test_feature_id_map_macd_multi_output(self):
        """Test feature_id_map with multi-output indicator (MACD)."""
        # Given: MACD indicator config
        configs = [
            {
                "name": "macd",
                "feature_id": "macd_12_26_9",
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            }
        ]

        # When: Creating IndicatorEngine
        engine = IndicatorEngine(indicators=configs)

        # Then: Should map MACD primary output (main line) to feature_id
        # MACD produces: MACD_12_26, MACD_signal_12_26_9, MACD_hist_12_26_9
        # Only primary output (MACD_12_26) should map to feature_id
        assert (
            "MACD_12_26" in engine.feature_id_map
        ), "MACD primary output should be in map"
        assert engine.feature_id_map["MACD_12_26"] == "macd_12_26_9"

    def test_feature_id_map_empty_config(self):
        """Test feature_id_map with no indicator configs."""
        # Given: No indicator configs
        engine = IndicatorEngine(indicators=None)

        # Then: feature_id_map should exist but be empty
        assert hasattr(engine, "feature_id_map")
        assert len(engine.feature_id_map) == 0, "feature_id_map should be empty"

    def test_feature_id_map_with_indicator_instances(self):
        """Test feature_id_map with direct indicator instances (backward compatibility)."""
        # Given: Direct indicator instances (not configs)
        from ktrdr.indicators.rsi_indicator import RSIIndicator

        indicator = RSIIndicator(period=14)
        engine = IndicatorEngine(indicators=[indicator])

        # Then: feature_id_map should exist but be empty (no configs to map from)
        assert hasattr(engine, "feature_id_map")
        assert len(engine.feature_id_map) == 0, "No mappings without configs"


class TestFeatureIdMapColumnNames:
    """Test that feature_id_map keys are actual column names from indicators."""

    def test_column_name_matches_indicator_output(self):
        """Test that map keys match actual column names from get_column_name()."""
        # Given: Config with feature_id
        configs = [{"name": "rsi", "feature_id": "rsi_14", "period": 14}]

        # When: Creating engine and getting indicator
        engine = IndicatorEngine(indicators=configs)
        indicator = engine.indicators[0]

        # Then: Map key should match indicator's get_column_name()
        expected_column_name = indicator.get_column_name()
        assert (
            expected_column_name in engine.feature_id_map
        ), f"Map should contain key '{expected_column_name}'"

    def test_ema_column_name_excludes_adjust_param(self):
        """Test that EMA column name excludes 'adjust' parameter."""
        # Given: EMA config (EMA excludes adjust from column name)
        configs = [
            {"name": "ema", "feature_id": "ema_20", "period": 20, "adjust": False}
        ]

        # When: Creating engine
        engine = IndicatorEngine(indicators=configs)

        # Then: Column name should be "ema_20" (without adjust parameter)
        assert "ema_20" in engine.feature_id_map
        assert "adjust" not in list(engine.feature_id_map.keys())[0]


class TestFeatureIdMapMultiOutput:
    """Test feature_id_map with various multi-output indicators."""

    def test_bollinger_bands_multi_output(self):
        """Test feature_id_map with Bollinger Bands (3 outputs: upper, middle, lower)."""
        # Given: Bollinger Bands config
        configs = [
            {
                "name": "BollingerBands",  # Use correct registered name
                "feature_id": "bbands_20_2",
                "period": 20,
                "multiplier": 2.0,
            }
        ]

        # When: Creating engine
        engine = IndicatorEngine(indicators=configs)

        # Then: Should map first output (upper) to feature_id
        # BollingerBands produces: upper_20_2.0, middle_20_2.0, lower_20_2.0 (parameterized names)
        # Primary output is "upper_20_2.0" (first column)
        assert "upper_20_2.0" in engine.feature_id_map
        assert engine.feature_id_map["upper_20_2.0"] == "bbands_20_2"

    def test_stochastic_multi_output(self):
        """Test feature_id_map with Stochastic (2 outputs: %K, %D)."""
        # Given: Stochastic config with correct parameter names
        configs = [
            {
                "name": "Stochastic",  # Use correct registered name
                "feature_id": "stoch_14_3_3",
                "k_period": 14,
                "d_period": 3,
                "smooth_k": 3,
            }
        ]

        # When: Creating engine
        engine = IndicatorEngine(indicators=configs)

        # Then: Should map first output (%K) to feature_id
        # Stochastic produces 2 columns, first one should be mapped
        assert (
            len(engine.feature_id_map) > 0
        ), "Should have at least one mapping for multi-output"
        # The first column from Stochastic should be mapped to feature_id
        assert "stoch_14_3_3" in engine.feature_id_map.values()

    def test_adx_multi_output(self):
        """Test feature_id_map with ADX (3 outputs: ADX, +DI, -DI)."""
        # Given: ADX config
        configs = [
            {
                "name": "ADX",  # Use correct registered name
                "feature_id": "adx_14",
                "period": 14,
            }
        ]

        # When: Creating engine
        engine = IndicatorEngine(indicators=configs)

        # Then: Should map first output to feature_id
        # ADX produces multiple columns
        # Primary output is first column
        assert len(engine.feature_id_map) > 0, "Should have mapping for ADX"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
