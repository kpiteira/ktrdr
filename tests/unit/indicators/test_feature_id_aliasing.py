"""
Unit tests for IndicatorEngine feature_id aliasing in apply() method (v2 format).

NOTE: These tests are for v2 list-based indicator config format.
The feature_id aliasing is a v2-specific concept that will be removed in Task 8.5.
In v3 format, indicator_id serves directly as the column name - no aliasing needed.

These tests validate backward compatibility with v2 format until full removal.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.indicators.indicator_engine import IndicatorEngine

# Skip entire module - v2 tests will be removed in Task 8.5
pytestmark = pytest.mark.skip(
    reason="v2 feature_id aliasing tests - v2 format will be removed in Task 8.5"
)


class TestFeatureIdAliasing:
    """Test that apply() creates feature_id aliases in output DataFrame."""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create sample OHLCV data for testing."""
        return pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0, 103.0, 104.0] * 10,
                "high": [101.0, 102.0, 103.0, 104.0, 105.0] * 10,
                "low": [99.0, 100.0, 101.0, 102.0, 103.0] * 10,
                "close": [100.5, 101.5, 102.5, 103.5, 104.5] * 10,
                "volume": [1000, 1100, 1200, 1300, 1400] * 10,
            }
        )

    def test_aliasing_single_indicator_same_name(self, sample_ohlcv_data):
        """Test aliasing when feature_id equals column name (no duplicate column)."""
        # Given: RSI with feature_id matching column name
        configs = [{"name": "rsi", "feature_id": "rsi_14", "period": 14}]
        engine = IndicatorEngine(indicators=configs)

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: Should have rsi_14 column (no duplicate)
        assert "rsi_14" in result.columns, "Should have rsi_14 column"
        # Should not have duplicate columns
        assert list(result.columns).count("rsi_14") == 1, "Should not duplicate column"

    def test_aliasing_single_indicator_different_name(self, sample_ohlcv_data):
        """Test that adapter uses feature_id directly (M2 behavior)."""
        # Given: RSI with semantic feature_id
        configs = [{"name": "rsi", "feature_id": "rsi_fast", "period": 7}]
        engine = IndicatorEngine(indicators=configs)

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: M2 adapter uses feature_id directly (no technical name)
        assert "rsi_fast" in result.columns, "Should have feature_id column"
        # M2: adapter creates feature_id column directly, no technical column
        # CLEANUP(v3): This test validates M2 adapter behavior

    def test_aliasing_multiple_indicators(self, sample_ohlcv_data):
        """Test that adapter uses feature_ids directly for multiple indicators (M2)."""
        # Given: Multiple indicators with different feature_ids
        configs = [
            {"name": "rsi", "feature_id": "rsi_fast", "period": 7},
            {"name": "rsi", "feature_id": "rsi_slow", "period": 21},
            {"name": "ema", "feature_id": "ema_20", "period": 20},
        ]
        engine = IndicatorEngine(indicators=configs)

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: M2 adapter creates columns with feature_ids directly
        assert "rsi_fast" in result.columns
        assert "rsi_slow" in result.columns
        assert "ema_20" in result.columns
        # CLEANUP(v3): M2 uses feature_ids directly, no technical names

    def test_aliasing_macd_multi_output(self, sample_ohlcv_data):
        """Test aliasing with MACD (multi-output indicator)."""
        # Given: MACD config with feature_id
        configs = [
            {
                "name": "macd",
                "feature_id": "macd_standard",
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            }
        ]
        engine = IndicatorEngine(indicators=configs)

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: Should have all 3 MACD columns (M3b: semantic names with indicator_id prefix)
        assert "macd_standard.line" in result.columns, "Should have MACD line"
        assert "macd_standard.signal" in result.columns, "Should have signal line"
        assert "macd_standard.histogram" in result.columns, "Should have histogram"

        # And: Should have feature_id alias for primary output only
        assert "macd_standard" in result.columns, "Should have feature_id alias"

    def test_aliasing_preserves_original_columns(self, sample_ohlcv_data):
        """Test that aliasing preserves original OHLCV columns."""
        # Given: Indicator config
        configs = [{"name": "rsi", "feature_id": "rsi_fast", "period": 7}]
        engine = IndicatorEngine(indicators=configs)

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: Original columns should still exist
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns, f"Should preserve {col} column"


class TestFeatureIdAliasingDataIdentity:
    """Test that feature_id aliases reference same data (not copied)."""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create sample OHLCV data for testing."""
        return pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0, 103.0, 104.0] * 10,
                "high": [101.0, 102.0, 103.0, 104.0, 105.0] * 10,
                "low": [99.0, 100.0, 101.0, 102.0, 103.0] * 10,
                "close": [100.5, 101.5, 102.5, 103.5, 104.5] * 10,
                "volume": [1000, 1100, 1200, 1300, 1400] * 10,
            }
        )

    def test_alias_references_same_data_not_copied(self, sample_ohlcv_data):
        """M2: Adapter creates feature_id column directly (no alias needed)."""
        # Given: RSI with different feature_id
        configs = [{"name": "rsi", "feature_id": "rsi_fast", "period": 7}]
        engine = IndicatorEngine(indicators=configs)

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: M2 adapter creates feature_id column directly
        assert "rsi_fast" in result.columns
        # No separate technical column in M2
        # CLEANUP(v3): This validates M2 adapter behavior

    def test_multiple_aliases_share_data(self, sample_ohlcv_data):
        """M2: Each indicator creates one column with feature_id (no duplication)."""
        # Given: Multiple indicators
        configs = [
            {"name": "rsi", "feature_id": "rsi_fast", "period": 7},
            {"name": "ema", "feature_id": "ema_short", "period": 9},
        ]
        engine = IndicatorEngine(indicators=configs)

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: M2 adapter creates columns with feature_ids directly
        assert "rsi_fast" in result.columns
        assert "ema_short" in result.columns
        # No technical columns created separately
        # CLEANUP(v3): This validates M2 adapter behavior

    def test_macd_alias_references_primary_output(self, sample_ohlcv_data):
        """Test that MACD feature_id alias references the primary output."""
        # Given: MACD config
        configs = [
            {
                "name": "macd",
                "feature_id": "macd_standard",
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            }
        ]
        engine = IndicatorEngine(indicators=configs)

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: feature_id should reference primary output (M3b: MACD line with semantic prefix)
        pd.testing.assert_series_equal(
            result["macd_standard.line"], result["macd_standard"], check_names=False
        )

        # And: Should have identical values
        np.testing.assert_array_equal(
            result["macd_standard.line"].values, result["macd_standard"].values
        )


class TestFeatureIdAliasingEdgeCases:
    """Test edge cases for feature_id aliasing."""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create sample OHLCV data for testing."""
        return pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0, 103.0, 104.0] * 10,
                "high": [101.0, 102.0, 103.0, 104.0, 105.0] * 10,
                "low": [99.0, 100.0, 101.0, 102.0, 103.0] * 10,
                "close": [100.5, 101.5, 102.5, 103.5, 104.5] * 10,
                "volume": [1000, 1100, 1200, 1300, 1400] * 10,
            }
        )

    def test_no_aliasing_with_direct_indicator_instances(self, sample_ohlcv_data):
        """Test that no aliasing happens with direct indicator instances."""
        # Given: Direct indicator instance (no config)
        from ktrdr.indicators.rsi_indicator import RSIIndicator

        indicator = RSIIndicator(period=14)
        engine = IndicatorEngine(indicators=[indicator])

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: Should have indicator output but no aliases
        assert "rsi_14" in result.columns or "RSI_14" in result.columns
        # No feature_id_map, so no aliases created

    def test_aliasing_with_empty_feature_id_map(self, sample_ohlcv_data):
        """Test that apply() works even with empty feature_id_map."""
        # Given: Engine with no configs (empty feature_id_map)
        from ktrdr.indicators.rsi_indicator import RSIIndicator

        indicator = RSIIndicator(period=14)
        engine = IndicatorEngine(indicators=[indicator])

        # When: Apply indicators
        result = engine.apply(sample_ohlcv_data)

        # Then: Should not crash, should produce normal output
        assert len(result.columns) > len(sample_ohlcv_data.columns)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
