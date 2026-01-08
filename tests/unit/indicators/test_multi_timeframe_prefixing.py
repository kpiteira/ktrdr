"""
Unit tests for multi-timeframe indicator column prefixing.

These tests verify that apply_multi_timeframe() prefixes indicator columns
with timeframe names to prevent collisions when combining data from different
timeframes (e.g., both 5m and 1h producing 'rsi_14' should become '5m_rsi_14'
and '1h_rsi_14').

Updated for v3 format - uses dict-based indicator configs.

Bug reference: HANDOFF_M5.md - "Backtest Indicator Column Name Collision"
"""

import pandas as pd
import pytest

from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators.indicator_engine import IndicatorEngine


class TestMultiTimeframePrefixing:
    """Test that apply_multi_timeframe prefixes columns with timeframe."""

    @pytest.fixture
    def sample_ohlcv(self) -> pd.DataFrame:
        """Create sample OHLCV data for testing."""
        return pd.DataFrame(
            {
                "open": [100.0 + i for i in range(100)],
                "high": [101.0 + i for i in range(100)],
                "low": [99.0 + i for i in range(100)],
                "close": [100.0 + i for i in range(100)],
                "volume": [1000] * 100,
            }
        )

    @pytest.fixture
    def indicator_configs(self) -> dict:
        """Standard indicator configs with RSI (v3 format)."""
        return {"rsi_14": IndicatorDefinition(type="rsi", period=14)}

    def test_multi_timeframe_prefixes_indicator_columns(
        self, sample_ohlcv: pd.DataFrame, indicator_configs: dict
    ):
        """Test that indicator columns are prefixed with timeframe.

        When apply_multi_timeframe is called, the returned DataFrames should
        have indicator columns prefixed with their timeframe, e.g., '1h_rsi_14'
        instead of 'rsi_14'.
        """
        multi_data = {
            "1h": sample_ohlcv.copy(),
            "5m": sample_ohlcv.copy(),
        }

        engine = IndicatorEngine(indicators=indicator_configs)
        result = engine.apply_multi_timeframe(multi_data)

        # Each timeframe's result should have prefixed columns
        assert "1h" in result
        assert "5m" in result

        # Check 1h timeframe has prefixed RSI column
        assert (
            "1h_rsi_14" in result["1h"].columns
        ), f"Expected '1h_rsi_14' in 1h columns, got: {list(result['1h'].columns)}"

        # Check 5m timeframe has prefixed RSI column
        assert (
            "5m_rsi_14" in result["5m"].columns
        ), f"Expected '5m_rsi_14' in 5m columns, got: {list(result['5m'].columns)}"

    def test_no_unprefixed_indicator_columns(
        self, sample_ohlcv: pd.DataFrame, indicator_configs: dict
    ):
        """Test that raw indicator columns (without prefix) are NOT present.

        The original column name (e.g., 'rsi_14') should be replaced by
        the prefixed version (e.g., '1h_rsi_14'), not exist alongside it.
        """
        multi_data = {"1h": sample_ohlcv.copy()}

        engine = IndicatorEngine(indicators=indicator_configs)
        result = engine.apply_multi_timeframe(multi_data)

        # The unprefixed column should NOT exist (prevents collision potential)
        # Only OHLCV columns remain unprefixed
        ohlcv_cols = {"open", "high", "low", "close", "volume"}
        indicator_cols = [c for c in result["1h"].columns if c not in ohlcv_cols]

        for col in indicator_cols:
            assert col.startswith(
                "1h_"
            ), f"Indicator column '{col}' should be prefixed with '1h_'"

    def test_ohlcv_columns_not_prefixed(
        self, sample_ohlcv: pd.DataFrame, indicator_configs: dict
    ):
        """Test that OHLCV columns retain original names (not prefixed).

        Only indicator columns should be prefixed. The base OHLCV columns
        should remain as 'open', 'high', 'low', 'close', 'volume'.
        """
        multi_data = {"1h": sample_ohlcv.copy()}

        engine = IndicatorEngine(indicators=indicator_configs)
        result = engine.apply_multi_timeframe(multi_data)

        # OHLCV columns should NOT be prefixed
        assert "open" in result["1h"].columns
        assert "high" in result["1h"].columns
        assert "low" in result["1h"].columns
        assert "close" in result["1h"].columns
        assert "volume" in result["1h"].columns

        # The prefixed versions should NOT exist
        assert "1h_open" not in result["1h"].columns
        assert "1h_close" not in result["1h"].columns

    def test_multi_output_indicators_prefixed(self, sample_ohlcv: pd.DataFrame):
        """Test that multi-output indicators (like MACD) are also prefixed."""
        macd_configs = {
            "macd_std": IndicatorDefinition(
                type="macd", fast_period=12, slow_period=26, signal_period=9
            )
        }

        multi_data = {"1h": sample_ohlcv.copy()}

        engine = IndicatorEngine(indicators=macd_configs)
        result = engine.apply_multi_timeframe(multi_data)

        # MACD produces multiple columns - all should be prefixed
        # v3 format: macd_std.line, macd_std.signal, macd_std.histogram
        macd_cols = [c for c in result["1h"].columns if "macd" in c.lower()]

        for col in macd_cols:
            assert col.startswith(
                "1h_"
            ), f"MACD column '{col}' should be prefixed with '1h_'"

    def test_all_indicator_columns_prefixed(
        self, sample_ohlcv: pd.DataFrame, indicator_configs: dict
    ):
        """Test that all indicator columns are prefixed with timeframe.

        Verifies that apply_multi_timeframe prefixes all non-OHLCV columns
        with the timeframe identifier to prevent collisions.
        """
        multi_data = {"1h": sample_ohlcv.copy()}

        engine = IndicatorEngine(indicators=indicator_configs)
        result = engine.apply_multi_timeframe(multi_data)

        # All indicator columns should be prefixed with timeframe
        ohlcv_cols = {"open", "high", "low", "close", "volume"}
        non_ohlcv = [c for c in result["1h"].columns if c not in ohlcv_cols]

        # All non-OHLCV columns should be prefixed
        for col in non_ohlcv:
            assert col.startswith(
                "1h_"
            ), f"Column '{col}' should be prefixed with '1h_'"


class TestMultiTimeframeNoPrefixOption:
    """Test the prefix_columns option for backward compatibility."""

    @pytest.fixture
    def sample_ohlcv(self) -> pd.DataFrame:
        """Create sample OHLCV data for testing."""
        return pd.DataFrame(
            {
                "open": [100.0 + i for i in range(100)],
                "high": [101.0 + i for i in range(100)],
                "low": [99.0 + i for i in range(100)],
                "close": [100.0 + i for i in range(100)],
                "volume": [1000] * 100,
            }
        )

    def test_prefix_columns_default_true(self, sample_ohlcv: pd.DataFrame):
        """Test that prefix_columns defaults to True (the safe behavior)."""
        configs = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}
        multi_data = {"1h": sample_ohlcv.copy()}

        engine = IndicatorEngine(indicators=configs)
        result = engine.apply_multi_timeframe(multi_data)

        # Default behavior should prefix columns
        assert "1h_rsi_14" in result["1h"].columns

    def test_prefix_columns_false_preserves_original_names(
        self, sample_ohlcv: pd.DataFrame
    ):
        """Test that prefix_columns=False preserves original column names.

        This is useful for single-timeframe scenarios or when the caller
        handles prefixing externally.
        """
        configs = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}
        multi_data = {"1h": sample_ohlcv.copy()}

        engine = IndicatorEngine(indicators=configs)
        result = engine.apply_multi_timeframe(multi_data, prefix_columns=False)

        # With prefix_columns=False, original names should be preserved
        assert "rsi_14" in result["1h"].columns
        # Prefixed version should NOT exist
        assert "1h_rsi_14" not in result["1h"].columns
