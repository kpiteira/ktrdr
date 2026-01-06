"""Tests for FeatureCache with new indicator column format (M4)."""

import pandas as pd
import pytest

from ktrdr.backtesting.feature_cache import FeatureCache


class TestFeatureCacheNewFormat:
    """Test FeatureCache with new semantic column format."""

    @pytest.fixture
    def simple_indicators_df(self):
        """Create test DataFrame with new format columns."""
        return pd.DataFrame(
            {
                "rsi_14": [50.0, 60.0, 70.0],
                "bbands_20_2.upper": [1.1, 1.2, 1.3],
                "bbands_20_2.middle": [1.0, 1.1, 1.2],
                "bbands_20_2.lower": [0.9, 1.0, 1.1],
                "bbands_20_2": [1.1, 1.2, 1.3],  # alias to primary (upper)
                "macd_12_26_9.line": [0.01, 0.02, 0.03],
                "macd_12_26_9.signal": [0.01, 0.015, 0.025],
                "macd_12_26_9.histogram": [0.0, 0.005, 0.005],
                "macd_12_26_9": [0.01, 0.02, 0.03],  # alias to primary (line)
            }
        )

    def test_direct_column_lookup(self, simple_indicators_df):
        """Test direct lookup of single-output indicator."""
        cache = FeatureCache.from_dataframe(simple_indicators_df)

        assert cache.get_indicator_value("rsi_14", 0) == 50.0
        assert cache.get_indicator_value("rsi_14", 1) == 60.0
        assert cache.get_indicator_value("rsi_14", 2) == 70.0

    def test_dot_notation_lookup(self, simple_indicators_df):
        """Test lookup with dot notation for multi-output indicators."""
        cache = FeatureCache.from_dataframe(simple_indicators_df)

        # Explicit output reference
        assert cache.get_indicator_value("bbands_20_2.upper", 0) == 1.1
        assert cache.get_indicator_value("bbands_20_2.middle", 0) == 1.0
        assert cache.get_indicator_value("bbands_20_2.lower", 0) == 0.9

    def test_alias_lookup(self, simple_indicators_df):
        """Test lookup using alias (bare indicator_id for multi-output)."""
        cache = FeatureCache.from_dataframe(simple_indicators_df)

        # Bare reference should resolve to alias column (primary output)
        assert cache.get_indicator_value("bbands_20_2", 0) == 1.1  # upper
        assert cache.get_indicator_value("macd_12_26_9", 0) == 0.01  # line

    def test_missing_column_raises_error(self, simple_indicators_df):
        """Test that missing columns raise KeyError with clear message."""
        cache = FeatureCache.from_dataframe(simple_indicators_df)

        with pytest.raises(KeyError, match="Column 'nonexistent' not found"):
            cache.get_indicator_value("nonexistent", 0)

    def test_invalid_index_raises_error(self, simple_indicators_df):
        """Test that invalid index raises IndexError."""
        cache = FeatureCache.from_dataframe(simple_indicators_df)

        with pytest.raises(IndexError):
            cache.get_indicator_value("rsi_14", 999)

    def test_nan_value_handling(self):
        """Test handling of NaN values in indicators."""
        df = pd.DataFrame(
            {
                "rsi_14": [50.0, float("nan"), 70.0],
            }
        )
        cache = FeatureCache.from_dataframe(df)

        # Should return NaN, not raise error
        value = cache.get_indicator_value("rsi_14", 1)
        assert pd.isna(value)

    def test_from_dataframe_factory_method(self, simple_indicators_df):
        """Test factory method for creating cache from DataFrame."""
        cache = FeatureCache.from_dataframe(simple_indicators_df)

        assert cache.indicators_df is not None
        assert len(cache.indicators_df) == 3
        assert "rsi_14" in cache.indicators_df.columns

    def test_backward_compatibility_with_strategy_config(self):
        """Test that existing strategy_config constructor still works."""
        strategy_config = {
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {"rsi_14": {"low": 0, "high": 100}},
        }

        # Should not raise error
        cache = FeatureCache(strategy_config)
        assert cache.strategy_config == strategy_config
