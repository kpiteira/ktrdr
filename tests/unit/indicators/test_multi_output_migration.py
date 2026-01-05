"""
Tests for multi-output indicator migration to semantic column names.

Milestone 3b: Multi-output indicators return DataFrames with semantic column names
only (e.g., "upper", "middle", "lower"), without parameter embedding. The engine
handles prefixing with indicator_id.
"""

import pandas as pd
import pytest

from ktrdr.indicators import IndicatorEngine
from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0] * 20,
            "high": [101.0, 102.0, 103.0, 104.0, 105.0] * 20,
            "low": [99.0, 100.0, 101.0, 102.0, 103.0] * 20,
            "close": [100.5, 101.5, 102.5, 103.5, 104.5] * 20,
            "volume": [1000, 1100, 1200, 1300, 1400] * 20,
        }
    )


class TestBollingerBandsMigration:
    """Test Task 3b.1: BollingerBands returns semantic column names only."""

    def test_compute_returns_semantic_columns(self, sample_ohlcv_data):
        """BollingerBands compute() returns DataFrame with semantic names only."""
        indicator = BollingerBandsIndicator(period=20, multiplier=2.0)
        result = indicator.compute(sample_ohlcv_data)

        # Should return DataFrame (not Series)
        assert isinstance(result, pd.DataFrame), "Multi-output should return DataFrame"

        # Column names should match get_output_names() exactly
        expected_columns = {"upper", "middle", "lower"}
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected {expected_columns}, got {actual_columns}"

        # No parameter embedding in column names
        for col in result.columns:
            assert (
                "_20_" not in col
            ), f"Column '{col}' should not contain parameter suffix"
            assert (
                "_2.0" not in col
            ), f"Column '{col}' should not contain parameter suffix"

    def test_columns_match_get_output_names(self, sample_ohlcv_data):
        """Column names match get_output_names() exactly."""
        indicator = BollingerBandsIndicator(period=20, multiplier=2.0)
        result = indicator.compute(sample_ohlcv_data)

        expected = indicator.get_output_names()
        actual = list(result.columns)

        # Sort for comparison (order doesn't matter for this test)
        assert sorted(actual) == sorted(
            expected
        ), f"Columns {actual} should match get_output_names() {expected}"

    def test_values_unchanged(self, sample_ohlcv_data):
        """Regression test: values should be unchanged after migration."""
        indicator = BollingerBandsIndicator(period=20, multiplier=2.0)
        result = indicator.compute(sample_ohlcv_data)

        # Spot checks: bands should be calculated correctly
        assert len(result) == len(sample_ohlcv_data), "Result length should match input"

        # Check that we have valid values (not all NaN)
        assert (
            result["upper"].notna().sum() > 0
        ), "Upper band should have non-NaN values"
        assert (
            result["middle"].notna().sum() > 0
        ), "Middle band should have non-NaN values"
        assert (
            result["lower"].notna().sum() > 0
        ), "Lower band should have non-NaN values"

        # Upper band should be greater than middle, middle greater than lower
        # (for valid points)
        valid_idx = result["middle"].notna()
        assert (
            result.loc[valid_idx, "upper"] > result.loc[valid_idx, "middle"]
        ).all(), "Upper band should be > middle band"
        assert (
            result.loc[valid_idx, "middle"] > result.loc[valid_idx, "lower"]
        ).all(), "Middle band should be > lower band"


class TestBollingerBandsThroughAdapter:
    """Test BollingerBands works through IndicatorEngine adapter with prefixing."""

    def test_adapter_prefixes_columns(self, sample_ohlcv_data):
        """Adapter prefixes semantic columns with indicator_id."""
        engine = IndicatorEngine()
        indicator = BollingerBandsIndicator(period=20, multiplier=2.0)
        indicator_id = "bbands_20_2"

        result = engine.compute_indicator(sample_ohlcv_data, indicator, indicator_id)

        # Should have prefixed columns
        expected_columns = {
            f"{indicator_id}.upper",
            f"{indicator_id}.middle",
            f"{indicator_id}.lower",
            indicator_id,  # Alias for primary output
        }
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected prefixed columns {expected_columns}, got {actual_columns}"

    def test_adapter_creates_alias(self, sample_ohlcv_data):
        """Adapter creates alias column for bare indicator_id."""
        engine = IndicatorEngine()
        indicator = BollingerBandsIndicator(period=20, multiplier=2.0)
        indicator_id = "bbands_20_2"

        result = engine.compute_indicator(sample_ohlcv_data, indicator, indicator_id)

        # Alias should exist
        assert (
            indicator_id in result.columns
        ), f"Alias column '{indicator_id}' should exist"

        # Alias should point to primary output (upper)
        primary_col = f"{indicator_id}.upper"
        assert (
            primary_col in result.columns
        ), f"Primary column '{primary_col}' should exist"

        # Values should match
        pd.testing.assert_series_equal(
            result[indicator_id],
            result[primary_col],
            check_names=False,
        )

    def test_multiple_bbands_no_collision(self, sample_ohlcv_data):
        """Multiple BollingerBands with different params don't collide."""
        engine = IndicatorEngine()

        # Two BollingerBands with different parameters
        bbands1 = BollingerBandsIndicator(period=20, multiplier=2.0)
        bbands2 = BollingerBandsIndicator(period=10, multiplier=1.5)

        result1 = engine.compute_indicator(sample_ohlcv_data, bbands1, "bbands_20_2")
        result2 = engine.compute_indicator(sample_ohlcv_data, bbands2, "bbands_10_1.5")

        # Combine results
        combined = pd.concat([result1, result2], axis=1)

        # All columns should be unique (no collisions)
        assert len(combined.columns) == len(
            set(combined.columns)
        ), f"Columns should be unique, got duplicates: {combined.columns}"

        # Both sets of prefixed columns should exist
        assert "bbands_20_2.upper" in combined.columns
        assert "bbands_10_1.5.upper" in combined.columns


class TestMACDMigration:
    """Test Task 3b.2: MACD returns semantic column names only."""

    def test_compute_returns_semantic_columns(self, sample_ohlcv_data):
        """MACD compute() returns DataFrame with semantic names only."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        indicator = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
        result = indicator.compute(sample_ohlcv_data)

        # Should return DataFrame (not Series)
        assert isinstance(result, pd.DataFrame), "Multi-output should return DataFrame"

        # Column names should match get_output_names() exactly
        expected_columns = {"line", "signal", "histogram"}
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected {expected_columns}, got {actual_columns}"

        # No parameter embedding in column names
        for col in result.columns:
            assert (
                "_12_" not in col
            ), f"Column '{col}' should not contain parameter suffix"
            assert (
                "_26_" not in col
            ), f"Column '{col}' should not contain parameter suffix"
            assert "MACD" not in col, f"Column '{col}' should not contain 'MACD' prefix"

    def test_columns_match_get_output_names(self, sample_ohlcv_data):
        """Column names match get_output_names() exactly."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        indicator = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
        result = indicator.compute(sample_ohlcv_data)

        expected = indicator.get_output_names()
        actual = list(result.columns)

        # Sort for comparison (order doesn't matter for this test)
        assert sorted(actual) == sorted(
            expected
        ), f"Columns {actual} should match get_output_names() {expected}"

    def test_adapter_prefixes_columns(self, sample_ohlcv_data):
        """Adapter prefixes semantic columns with indicator_id."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        engine = IndicatorEngine()
        indicator = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
        indicator_id = "macd_12_26_9"

        result = engine.compute_indicator(sample_ohlcv_data, indicator, indicator_id)

        # Should have prefixed columns
        expected_columns = {
            f"{indicator_id}.line",
            f"{indicator_id}.signal",
            f"{indicator_id}.histogram",
            indicator_id,  # Alias for primary output
        }
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected prefixed columns {expected_columns}, got {actual_columns}"


class TestStochasticMigration:
    """Test Task 3b.2: Stochastic returns semantic column names only."""

    def test_compute_returns_semantic_columns(self, sample_ohlcv_data):
        """Stochastic compute() returns DataFrame with semantic names only."""
        from ktrdr.indicators.stochastic_indicator import StochasticIndicator

        indicator = StochasticIndicator(k_period=14, d_period=3, smooth_k=3)
        result = indicator.compute(sample_ohlcv_data)

        # Should return DataFrame (not Series)
        assert isinstance(result, pd.DataFrame), "Multi-output should return DataFrame"

        # Column names should match get_output_names() exactly
        expected_columns = {"k", "d"}
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected {expected_columns}, got {actual_columns}"

        # No parameter embedding in column names
        for col in result.columns:
            assert (
                "_14_" not in col
            ), f"Column '{col}' should not contain parameter suffix"
            assert (
                "Stochastic" not in col
            ), f"Column '{col}' should not contain 'Stochastic' prefix"

    def test_adapter_prefixes_columns(self, sample_ohlcv_data):
        """Adapter prefixes semantic columns with indicator_id."""
        from ktrdr.indicators.stochastic_indicator import StochasticIndicator

        engine = IndicatorEngine()
        indicator = StochasticIndicator(k_period=14, d_period=3, smooth_k=3)
        indicator_id = "stoch_14_3"

        result = engine.compute_indicator(sample_ohlcv_data, indicator, indicator_id)

        # Should have prefixed columns
        expected_columns = {
            f"{indicator_id}.k",
            f"{indicator_id}.d",
            indicator_id,  # Alias for primary output
        }
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected prefixed columns {expected_columns}, got {actual_columns}"


class TestADXMigration:
    """Test Task 3b.2: ADX returns semantic column names only."""

    def test_compute_returns_semantic_columns(self, sample_ohlcv_data):
        """ADX compute() returns DataFrame with semantic names only."""
        from ktrdr.indicators.adx_indicator import ADXIndicator

        indicator = ADXIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        # Should return DataFrame (not Series)
        assert isinstance(result, pd.DataFrame), "Multi-output should return DataFrame"

        # Column names should match get_output_names() exactly
        expected_columns = {"adx", "plus_di", "minus_di"}
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected {expected_columns}, got {actual_columns}"

        # No parameter embedding in column names
        for col in result.columns:
            assert (
                "_14" not in col
            ), f"Column '{col}' should not contain parameter suffix"
            assert (
                "ADX" not in col and "DI" not in col
            ), f"Column '{col}' should be lowercase semantic name"

    def test_adapter_prefixes_columns(self, sample_ohlcv_data):
        """Adapter prefixes semantic columns with indicator_id."""
        from ktrdr.indicators.adx_indicator import ADXIndicator

        engine = IndicatorEngine()
        indicator = ADXIndicator(period=14)
        indicator_id = "adx_14"

        result = engine.compute_indicator(sample_ohlcv_data, indicator, indicator_id)

        # Should have prefixed columns
        expected_columns = {
            f"{indicator_id}.adx",
            f"{indicator_id}.plus_di",
            f"{indicator_id}.minus_di",
            indicator_id,  # Alias for primary output
        }
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected prefixed columns {expected_columns}, got {actual_columns}"


class TestAroonMigration:
    """Test Task 3b.2: Aroon returns semantic column names only."""

    def test_compute_returns_semantic_columns(self, sample_ohlcv_data):
        """Aroon compute() returns DataFrame with semantic names only."""
        from ktrdr.indicators.aroon_indicator import AroonIndicator

        indicator = AroonIndicator(period=14, include_oscillator=True)
        result = indicator.compute(sample_ohlcv_data)

        # Should return DataFrame (not Series)
        assert isinstance(result, pd.DataFrame), "Multi-output should return DataFrame"

        # Column names should match get_output_names() exactly
        expected_columns = {"up", "down", "oscillator"}
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected {expected_columns}, got {actual_columns}"

        # No parameter embedding in column names
        for col in result.columns:
            assert (
                "_14_" not in col
            ), f"Column '{col}' should not contain parameter suffix"
            assert (
                "Aroon" not in col
            ), f"Column '{col}' should not contain 'Aroon' prefix"

    def test_adapter_prefixes_columns(self, sample_ohlcv_data):
        """Adapter prefixes semantic columns with indicator_id."""
        from ktrdr.indicators.aroon_indicator import AroonIndicator

        engine = IndicatorEngine()
        indicator = AroonIndicator(period=14, include_oscillator=True)
        indicator_id = "aroon_14"

        result = engine.compute_indicator(sample_ohlcv_data, indicator, indicator_id)

        # Should have prefixed columns
        expected_columns = {
            f"{indicator_id}.up",
            f"{indicator_id}.down",
            f"{indicator_id}.oscillator",
            indicator_id,  # Alias for primary output
        }
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected prefixed columns {expected_columns}, got {actual_columns}"


class TestSuperTrendMigration:
    """Test Task 3b.2: SuperTrend returns semantic column names only."""

    def test_compute_returns_semantic_columns(self, sample_ohlcv_data):
        """SuperTrend compute() returns DataFrame with semantic names only."""
        from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator

        indicator = SuperTrendIndicator(period=10, multiplier=3.0)
        result = indicator.compute(sample_ohlcv_data)

        # Should return DataFrame (not Series)
        assert isinstance(result, pd.DataFrame), "Multi-output should return DataFrame"

        # Column names should match get_output_names() exactly
        expected_columns = {"trend", "direction"}
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected {expected_columns}, got {actual_columns}"

        # No parameter embedding in column names
        for col in result.columns:
            assert (
                "_10_" not in col
            ), f"Column '{col}' should not contain parameter suffix"
            assert (
                "SuperTrend" not in col and "ST" not in col
            ), f"Column '{col}' should be lowercase semantic name"

    def test_adapter_prefixes_columns(self, sample_ohlcv_data):
        """Adapter prefixes semantic columns with indicator_id."""
        from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator

        engine = IndicatorEngine()
        indicator = SuperTrendIndicator(period=10, multiplier=3.0)
        indicator_id = "supertrend_10_3"

        result = engine.compute_indicator(sample_ohlcv_data, indicator, indicator_id)

        # Should have prefixed columns
        expected_columns = {
            f"{indicator_id}.trend",
            f"{indicator_id}.direction",
            indicator_id,  # Alias for primary output
        }
        actual_columns = set(result.columns)

        assert (
            actual_columns == expected_columns
        ), f"Expected prefixed columns {expected_columns}, got {actual_columns}"
