"""
Tests for Ichimoku Cloud (Ichimoku Kinko Hyo) indicator.

This module provides comprehensive tests for the Ichimoku Cloud indicator implementation,
including mathematical accuracy, parameter validation, and edge case handling.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator


class TestIchimokuIndicator:
    """Test suite for Ichimoku Cloud indicator."""

    def test_basic_initialization(self):
        """Test basic Ichimoku initialization with default parameters."""
        indicator = IchimokuIndicator()

        assert indicator.name == "Ichimoku"
        assert indicator.params["tenkan_period"] == 9
        assert indicator.params["kijun_period"] == 26
        assert indicator.params["senkou_b_period"] == 52
        assert indicator.params["displacement"] == 26

    def test_custom_initialization(self):
        """Test Ichimoku initialization with custom parameters."""
        indicator = IchimokuIndicator(
            tenkan_period=7, kijun_period=22, senkou_b_period=44, displacement=22
        )

        assert indicator.params["tenkan_period"] == 7
        assert indicator.params["kijun_period"] == 22
        assert indicator.params["senkou_b_period"] == 44
        assert indicator.params["displacement"] == 22

    def test_parameter_validation_success(self):
        """Test successful parameter validation."""
        # Valid parameters should not raise an error
        IchimokuIndicator(
            tenkan_period=9, kijun_period=26, senkou_b_period=52, displacement=26
        )
        IchimokuIndicator(
            tenkan_period=1, kijun_period=1, senkou_b_period=1, displacement=1
        )
        IchimokuIndicator(
            tenkan_period=50, kijun_period=100, senkou_b_period=200, displacement=100
        )

    def test_parameter_validation_tenkan_period_too_small(self):
        """Test parameter validation for tenkan_period too small."""
        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(tenkan_period=0)
        assert "tenkan_period" in str(exc_info.value).lower()

    def test_parameter_validation_tenkan_period_too_large(self):
        """Test parameter validation for tenkan_period too large."""
        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(tenkan_period=51)
        assert "tenkan_period" in str(exc_info.value).lower()

    def test_parameter_validation_kijun_period_too_small(self):
        """Test parameter validation for kijun_period too small."""
        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(kijun_period=0)
        assert "kijun_period" in str(exc_info.value).lower()

    def test_parameter_validation_kijun_period_too_large(self):
        """Test parameter validation for kijun_period too large."""
        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(kijun_period=101)
        assert "kijun_period" in str(exc_info.value).lower()

    def test_parameter_validation_senkou_b_period_too_small(self):
        """Test parameter validation for senkou_b_period too small."""
        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(senkou_b_period=0)
        assert "senkou_b_period" in str(exc_info.value).lower()

    def test_parameter_validation_senkou_b_period_too_large(self):
        """Test parameter validation for senkou_b_period too large."""
        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(senkou_b_period=201)
        assert "senkou_b_period" in str(exc_info.value).lower()

    def test_parameter_validation_displacement_too_small(self):
        """Test parameter validation for displacement too small."""
        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(displacement=0)
        assert "displacement" in str(exc_info.value).lower()

    def test_parameter_validation_displacement_too_large(self):
        """Test parameter validation for displacement too large."""
        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(displacement=101)
        assert "displacement" in str(exc_info.value).lower()

    def test_basic_calculation(self):
        """Test basic Ichimoku calculation with sufficient data."""
        # Create test data with enough points for Ichimoku (need 52+ for default parameters)
        data = pd.DataFrame(
            {
                "high": [100 + i * 0.5 for i in range(60)],
                "low": [99 + i * 0.5 for i in range(60)],
                "close": [100 + i * 0.5 for i in range(60)],
            }
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # Should return DataFrame with 5 components
        assert isinstance(result, pd.DataFrame)
        assert len(result.columns) == 5

        # Should have same length as input
        assert len(result) == len(data)

        # M3b: All components should use semantic column names
        expected_columns = ["tenkan", "kijun", "senkou_a", "senkou_b", "chikou"]
        for col in expected_columns:
            assert col in result.columns

    def test_tenkan_sen_calculation(self):
        """Test Tenkan-sen (Conversion Line) calculation."""
        # Create test data with enough points for Ichimoku and specific pattern for testing Tenkan-sen
        base_data = [102, 104, 106, 108, 110, 109, 107, 105, 103, 101, 103, 105]

        # Extend to meet minimum requirement (52 points) by repeating pattern
        extended_high = base_data * 5  # 60 points
        extended_low = [h - 2 for h in extended_high]
        extended_close = [h - 1 for h in extended_high]

        data = pd.DataFrame(
            {"high": extended_high, "low": extended_low, "close": extended_close}
        )

        indicator = IchimokuIndicator(
            tenkan_period=9, kijun_period=26, senkou_b_period=52, displacement=26
        )
        result = indicator.compute(data)

        # M3b: Tenkan-sen should use semantic column name
        tenkan_col = "tenkan"

        # First valid Tenkan-sen at position 8 (9th element, 0-indexed)
        # For extended data, just verify that Tenkan-sen calculation works
        assert not pd.isna(result[tenkan_col].iloc[8])

        # Test mathematical consistency: Tenkan-sen should be between min and max of its input range
        tenkan_val = result[tenkan_col].iloc[8]
        period_high = max(extended_high[0:9])
        period_low = min(extended_low[0:9])
        expected_tenkan = (period_high + period_low) / 2
        assert abs(tenkan_val - expected_tenkan) < 0.001

    def test_kijun_sen_calculation(self):
        """Test Kijun-sen (Base Line) calculation."""
        # Need enough data for full Ichimoku calculation (52+ points)
        highs = [100 + i for i in range(60)]
        lows = [99 + i for i in range(60)]
        closes = [100 + i for i in range(60)]

        data = pd.DataFrame({"high": highs, "low": lows, "close": closes})

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # M3b: Kijun-sen should use semantic column name
        kijun_col = "kijun"

        # First valid Kijun-sen at position 25 (26th element, 0-indexed)
        # 26-period high from position 0-25: max([100...125]) = 125
        # 26-period low from position 0-25: min([99...124]) = 99
        # Kijun-sen = (125 + 99) / 2 = 112
        assert not pd.isna(result[kijun_col].iloc[25])
        expected_kijun = (125 + 99) / 2
        assert abs(result[kijun_col].iloc[25] - expected_kijun) < 0.001

    def test_senkou_span_calculations(self):
        """Test Senkou Span A and B calculations."""
        # Create sufficient data for full Ichimoku calculation
        data = pd.DataFrame(
            {
                "high": [100 + i * 0.1 for i in range(60)],
                "low": [99 + i * 0.1 for i in range(60)],
                "close": [100 + i * 0.1 for i in range(60)],
            }
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # M3b: Senkou Spans should use semantic column names
        span_a_col = "senkou_a"
        span_b_col = "senkou_b"

        # Senkou Span A should be present from position 25 onward (when both Tenkan and Kijun are available)
        assert not pd.isna(result[span_a_col].iloc[25])

        # Senkou Span B should be present from position 51 onward (52-period calculation)
        assert not pd.isna(result[span_b_col].iloc[51])

    def test_chikou_span_calculation(self):
        """Test Chikou Span (Lagging Span) calculation."""
        data = pd.DataFrame(
            {
                "high": [100 + i for i in range(60)],
                "low": [99 + i for i in range(60)],
                "close": [100 + i for i in range(60)],
            }
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # M3b: Chikou Span should use semantic column name
        chikou_col = "chikou"

        # Should have same values as close price (no displacement in current implementation)
        for i in range(len(data)):
            assert abs(result[chikou_col].iloc[i] - data["close"].iloc[i]) < 0.001

    def test_missing_required_columns(self):
        """Test Ichimoku with missing required columns."""
        # Missing high column
        data = pd.DataFrame({"low": [99, 100, 101], "close": [100, 101, 102]})

        indicator = IchimokuIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "high" in str(exc_info.value).lower()

    def test_insufficient_data(self):
        """Test Ichimoku with insufficient data points."""
        # Only 10 data points, but need 52 for default parameters
        data = pd.DataFrame(
            {
                "high": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
                "low": [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
                "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            }
        )

        indicator = IchimokuIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "insufficient data" in str(exc_info.value).lower()

    def test_minimum_required_data(self):
        """Test Ichimoku with exactly minimum required data."""
        # Exactly 52 data points for default parameters
        data = pd.DataFrame(
            {
                "high": [100 + i for i in range(52)],
                "low": [99 + i for i in range(52)],
                "close": [100 + i for i in range(52)],
            }
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # Should work with exactly minimum data
        assert len(result) == 52

        # M3b: Senkou Span B should use semantic column name
        span_b_col = "senkou_b"
        assert not pd.isna(result[span_b_col].iloc[51])

    def test_custom_parameters(self):
        """Test Ichimoku with custom parameters requiring less data."""
        # Use smaller parameters to test with less data
        data = pd.DataFrame(
            {
                "high": [100 + i for i in range(20)],
                "low": [99 + i for i in range(20)],
                "close": [100 + i for i in range(20)],
            }
        )

        indicator = IchimokuIndicator(
            tenkan_period=3, kijun_period=7, senkou_b_period=15, displacement=7
        )
        result = indicator.compute(data)

        # Should work with custom parameters
        assert len(result) == 20

        # All components should be calculated
        assert len(result.columns) == 5

    def test_constant_prices(self):
        """Test Ichimoku with constant price data."""
        data = pd.DataFrame(
            {"high": [100] * 60, "low": [100] * 60, "close": [100] * 60}
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # Should handle constant prices
        assert len(result) == 60

        # All valid values should equal 100 for constant data
        for col in result.columns:
            valid_values = result[col].dropna()
            if len(valid_values) > 0:
                assert all(abs(val - 100.0) < 0.001 for val in valid_values)

    def test_extreme_volatility(self):
        """Test Ichimoku with extreme price volatility."""
        np.random.seed(42)

        # Generate highly volatile data
        data = pd.DataFrame(
            {
                "high": [100 + np.random.normal(0, 20) + 2 for _ in range(60)],
                "low": [100 + np.random.normal(0, 20) - 2 for _ in range(60)],
                "close": [100 + np.random.normal(0, 20) for _ in range(60)],
            }
        )

        # Ensure proper OHLC relationships
        for i in range(len(data)):
            data.loc[i, "high"] = max(data.loc[i, "high"], data.loc[i, "close"])
            data.loc[i, "low"] = min(data.loc[i, "low"], data.loc[i, "close"])

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # Should handle volatility without errors
        assert len(result) == 60

    def test_get_name_method(self):
        """Test get_name method returns correct formatted name."""
        indicator = IchimokuIndicator(
            tenkan_period=9, kijun_period=26, senkou_b_period=52, displacement=26
        )
        expected_name = "Ichimoku_9_26_52_26"
        assert indicator.get_name() == expected_name

    def test_empty_dataframe(self):
        """Test Ichimoku with empty DataFrame."""
        data = pd.DataFrame()

        indicator = IchimokuIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "missing required columns" in str(exc_info.value).lower()

    def test_nan_values_in_data(self):
        """Test Ichimoku handling of NaN values in input data."""
        data = pd.DataFrame(
            {
                "high": [101, np.nan, 103, 104, 105] + [100 + i for i in range(55)],
                "low": [99, 100, 101, 102, 103] + [99 + i for i in range(55)],
                "close": [100, 101, 102, 103, 104] + [100 + i for i in range(55)],
            }
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # Should handle NaN values appropriately
        assert len(result) == len(data)

    def test_realistic_market_data(self):
        """Test Ichimoku with realistic market data patterns."""
        # Simulate realistic trending market data
        np.random.seed(42)

        prices = []
        current_price = 100.0

        for i in range(80):
            # Create realistic trending behavior
            if i < 20:
                trend = 0.3  # Uptrend
            elif i < 40:
                trend = 0.0  # Sideways
            elif i < 60:
                trend = -0.2  # Downtrend
            else:
                trend = 0.4  # Recovery

            # Price movement with trend bias
            change = np.random.normal(trend, 1.0)
            current_price += change

            # Create realistic OHLC
            daily_range = abs(np.random.normal(0, 0.8))
            high = current_price + daily_range * 0.6
            low = current_price - daily_range * 0.4
            close = current_price + np.random.normal(0, 0.3)

            # Ensure proper relationships
            high = max(high, close)
            low = min(low, close)

            prices.append({"high": high, "low": low, "close": close})

        data = pd.DataFrame(prices)

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # Should handle realistic data
        assert len(result) == len(data)
        assert len(result.columns) == 5

    def test_indicator_name_and_params(self):
        """Test indicator name and parameters accessibility."""
        indicator = IchimokuIndicator(
            tenkan_period=7, kijun_period=22, senkou_b_period=44, displacement=22
        )

        assert indicator.name == "Ichimoku"
        assert indicator.params["tenkan_period"] == 7
        assert indicator.params["kijun_period"] == 22
        assert indicator.params["senkou_b_period"] == 44
        assert indicator.params["displacement"] == 22

    def test_mathematical_properties(self):
        """Test mathematical properties of Ichimoku components."""
        # Create predictable data
        data = pd.DataFrame(
            {
                "high": [100 + i for i in range(60)],
                "low": [99 + i for i in range(60)],
                "close": [100 + i for i in range(60)],
            }
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # All valid values should be finite numbers
        for col in result.columns:
            valid_values = result[col].dropna()
            assert all(np.isfinite(valid_values))

            # No infinity values
            assert not any(np.isinf(valid_values))

    def test_component_relationships(self):
        """Test relationships between Ichimoku components."""
        # Create test data with clear trend
        data = pd.DataFrame(
            {
                "high": [100 + i * 2 for i in range(60)],  # Strong uptrend
                "low": [99 + i * 2 for i in range(60)],
                "close": [100 + i * 2 for i in range(60)],
            }
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # In strong uptrend, components should generally follow expected relationships
        # This is a complex test, so we just verify basic mathematical consistency

        # M3b: Use semantic column names
        tenkan_col = "tenkan"
        kijun_col = "kijun"
        span_a_col = "senkou_a"

        # Senkou Span A should be average of Tenkan and Kijun where both are available
        for i in range(25, len(result)):  # After both Tenkan and Kijun are available
            if not pd.isna(result[tenkan_col].iloc[i]) and not pd.isna(
                result[kijun_col].iloc[i]
            ):
                expected_span_a = (
                    result[tenkan_col].iloc[i] + result[kijun_col].iloc[i]
                ) / 2
                actual_span_a = result[span_a_col].iloc[i]
                assert abs(actual_span_a - expected_span_a) < 0.001

    def test_edge_case_all_same_highs_lows(self):
        """Test Ichimoku when all highs and lows are the same within periods."""
        # Create data where high=low for extended periods
        data = pd.DataFrame(
            {
                "high": [100] * 30 + [101] * 30,  # Flat then jump
                "low": [100] * 30 + [101] * 30,
                "close": [100] * 30 + [101] * 30,
            }
        )

        indicator = IchimokuIndicator()
        result = indicator.compute(data)

        # Should handle edge case appropriately
        assert len(result) == 60
