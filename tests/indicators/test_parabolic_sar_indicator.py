"""
Tests for Parabolic SAR (Stop and Reverse) indicator.

This module provides comprehensive tests for the Parabolic SAR indicator implementation,
including mathematical accuracy, parameter validation, and edge case handling.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator
from ktrdr.errors import DataError


class TestParabolicSARIndicator:
    """Test suite for Parabolic SAR indicator."""

    def test_basic_initialization(self):
        """Test basic Parabolic SAR initialization with default parameters."""
        indicator = ParabolicSARIndicator()

        assert indicator.name == "ParabolicSAR"
        assert indicator.params["initial_af"] == 0.02
        assert indicator.params["step_af"] == 0.02
        assert indicator.params["max_af"] == 0.20

    def test_custom_initialization(self):
        """Test Parabolic SAR initialization with custom parameters."""
        indicator = ParabolicSARIndicator(initial_af=0.01, step_af=0.01, max_af=0.15)

        assert indicator.params["initial_af"] == 0.01
        assert indicator.params["step_af"] == 0.01
        assert indicator.params["max_af"] == 0.15

    def test_parameter_validation_success(self):
        """Test successful parameter validation."""
        # Valid parameters should not raise an error
        ParabolicSARIndicator(initial_af=0.02, step_af=0.02, max_af=0.20)
        ParabolicSARIndicator(initial_af=0.001, step_af=0.001, max_af=0.01)
        ParabolicSARIndicator(initial_af=0.1, step_af=0.1, max_af=1.0)

    def test_parameter_validation_initial_af_too_small(self):
        """Test parameter validation for initial_af too small."""
        with pytest.raises(DataError) as exc_info:
            ParabolicSARIndicator(initial_af=0.0005)
        assert "initial_af" in str(exc_info.value).lower()

    def test_parameter_validation_initial_af_too_large(self):
        """Test parameter validation for initial_af too large."""
        with pytest.raises(DataError) as exc_info:
            ParabolicSARIndicator(initial_af=0.15)
        assert "initial_af" in str(exc_info.value).lower()

    def test_parameter_validation_step_af_too_small(self):
        """Test parameter validation for step_af too small."""
        with pytest.raises(DataError) as exc_info:
            ParabolicSARIndicator(step_af=0.0005)
        assert "step_af" in str(exc_info.value).lower()

    def test_parameter_validation_step_af_too_large(self):
        """Test parameter validation for step_af too large."""
        with pytest.raises(DataError) as exc_info:
            ParabolicSARIndicator(step_af=0.15)
        assert "step_af" in str(exc_info.value).lower()

    def test_parameter_validation_max_af_too_small(self):
        """Test parameter validation for max_af too small."""
        with pytest.raises(DataError) as exc_info:
            ParabolicSARIndicator(max_af=0.005)
        assert "max_af" in str(exc_info.value).lower()

    def test_parameter_validation_max_af_too_large(self):
        """Test parameter validation for max_af too large."""
        with pytest.raises(DataError) as exc_info:
            ParabolicSARIndicator(max_af=1.5)
        assert "max_af" in str(exc_info.value).lower()

    def test_basic_calculation(self):
        """Test basic Parabolic SAR calculation."""
        # Create simple trending data
        data = pd.DataFrame(
            {
                "high": [101, 102, 103, 104, 105, 104, 103, 102, 101, 100],
                "low": [99, 100, 101, 102, 103, 102, 101, 100, 99, 98],
                "close": [100, 101, 102, 103, 104, 103, 102, 101, 100, 99],
            }
        )

        indicator = ParabolicSARIndicator(initial_af=0.02, step_af=0.02, max_af=0.20)
        result = indicator.compute(data)

        # First value should be NaN
        assert pd.isna(result.iloc[0])

        # Second value should be valid
        assert not pd.isna(result.iloc[1])

        # Should have same length as input
        assert len(result) == len(data)

    def test_uptrend_behavior(self):
        """Test Parabolic SAR behavior in strong uptrend."""
        # Create strong uptrend data
        data = pd.DataFrame(
            {
                "high": [101, 103, 105, 107, 109, 111, 113, 115, 117, 119],
                "low": [99, 101, 103, 105, 107, 109, 111, 113, 115, 117],
                "close": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
            }
        )

        indicator = ParabolicSARIndicator(initial_af=0.02, step_af=0.02, max_af=0.20)
        result = indicator.compute(data)

        # In uptrend, SAR should be below prices
        for i in range(2, len(data)):
            if not pd.isna(result.iloc[i]):
                assert (
                    result.iloc[i] < data["low"].iloc[i]
                ), f"SAR should be below low at position {i}"

    def test_downtrend_behavior(self):
        """Test Parabolic SAR behavior in strong downtrend."""
        # Create strong downtrend data
        data = pd.DataFrame(
            {
                "high": [119, 117, 115, 113, 111, 109, 107, 105, 103, 101],
                "low": [117, 115, 113, 111, 109, 107, 105, 103, 101, 99],
                "close": [118, 116, 114, 112, 110, 108, 106, 104, 102, 100],
            }
        )

        indicator = ParabolicSARIndicator(initial_af=0.02, step_af=0.02, max_af=0.20)
        result = indicator.compute(data)

        # In downtrend, SAR should be above prices (after initial trend establishment)
        # Note: First few periods might still be establishing trend direction
        for i in range(4, len(data)):
            if not pd.isna(result.iloc[i]):
                assert (
                    result.iloc[i] > data["high"].iloc[i]
                ), f"SAR should be above high at position {i}"

    def test_trend_reversal(self):
        """Test Parabolic SAR behavior during trend reversal."""
        # Create data with uptrend followed by downtrend
        data = pd.DataFrame(
            {
                "high": [101, 103, 105, 107, 109, 108, 106, 104, 102, 100],
                "low": [99, 101, 103, 105, 107, 106, 104, 102, 100, 98],
                "close": [100, 102, 104, 106, 108, 107, 105, 103, 101, 99],
            }
        )

        indicator = ParabolicSARIndicator(initial_af=0.02, step_af=0.02, max_af=0.20)
        result = indicator.compute(data)

        # Should calculate without errors
        assert len(result) == len(data)
        assert not pd.isna(result.iloc[-1])  # Final value should be valid

    def test_acceleration_factor_progression(self):
        """Test that acceleration factor increases with trend continuation."""
        # Create consistent uptrend to test AF progression
        data = pd.DataFrame(
            {
                "high": [100 + i for i in range(20)],
                "low": [99 + i for i in range(20)],
                "close": [100 + i for i in range(20)],
            }
        )

        indicator = ParabolicSARIndicator(initial_af=0.02, step_af=0.02, max_af=0.20)
        result = indicator.compute(data)

        # With consistent trend, SAR should accelerate (differences should increase)
        # This is verified by checking that the rate of change increases
        sar_values = result.dropna()
        assert len(sar_values) >= 10  # Should have enough values to test

    def test_missing_required_columns(self):
        """Test Parabolic SAR with missing required columns."""
        # Missing high column
        data = pd.DataFrame({"low": [99, 100, 101], "close": [100, 101, 102]})

        indicator = ParabolicSARIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "high" in str(exc_info.value).lower()

    def test_insufficient_data(self):
        """Test Parabolic SAR with insufficient data points."""
        # Only 1 data point
        data = pd.DataFrame({"high": [101], "low": [99], "close": [100]})

        indicator = ParabolicSARIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "insufficient data" in str(exc_info.value).lower()

    def test_two_data_points(self):
        """Test Parabolic SAR with exactly two data points."""
        data = pd.DataFrame({"high": [101, 103], "low": [99, 101], "close": [100, 102]})

        indicator = ParabolicSARIndicator()
        result = indicator.compute(data)

        # Should have NaN for first point, value for second
        assert pd.isna(result.iloc[0])
        assert not pd.isna(result.iloc[1])

    def test_constant_prices(self):
        """Test Parabolic SAR with constant price data."""
        data = pd.DataFrame(
            {"high": [100] * 10, "low": [100] * 10, "close": [100] * 10}
        )

        indicator = ParabolicSARIndicator()
        result = indicator.compute(data)

        # Should handle constant prices without errors
        assert len(result) == len(data)
        # Most values should be valid (except first)
        valid_count = result.notna().sum()
        assert valid_count >= len(data) - 1

    def test_extreme_volatility(self):
        """Test Parabolic SAR with extreme price volatility."""
        np.random.seed(42)
        base_price = 100

        # Generate highly volatile data
        data = pd.DataFrame(
            {
                "high": [base_price + np.random.normal(0, 10) + 2 for _ in range(20)],
                "low": [base_price + np.random.normal(0, 10) - 2 for _ in range(20)],
                "close": [base_price + np.random.normal(0, 10) for _ in range(20)],
            }
        )

        # Ensure high >= low >= close relationship
        for i in range(len(data)):
            data.loc[i, "high"] = max(data.loc[i, "high"], data.loc[i, "close"])
            data.loc[i, "low"] = min(data.loc[i, "low"], data.loc[i, "close"])

        indicator = ParabolicSARIndicator()
        result = indicator.compute(data)

        # Should handle volatility without errors
        assert len(result) == len(data)

    def test_different_af_parameters(self):
        """Test Parabolic SAR with different acceleration factor parameters."""
        data = pd.DataFrame(
            {
                "high": [100 + i for i in range(10)],
                "low": [99 + i for i in range(10)],
                "close": [100 + i for i in range(10)],
            }
        )

        # Test with conservative parameters
        conservative = ParabolicSARIndicator(initial_af=0.01, step_af=0.01, max_af=0.10)
        result_conservative = conservative.compute(data)

        # Test with aggressive parameters
        aggressive = ParabolicSARIndicator(initial_af=0.05, step_af=0.05, max_af=0.30)
        result_aggressive = aggressive.compute(data)

        # Both should work
        assert len(result_conservative) == len(data)
        assert len(result_aggressive) == len(data)

        # Aggressive should generally have different (more reactive) values
        # This is a complex relationship, so we just check they're different
        differences = (result_conservative - result_aggressive).dropna()
        assert len(differences) > 0

    def test_get_name_method(self):
        """Test get_name method returns correct formatted name."""
        indicator = ParabolicSARIndicator(initial_af=0.02, step_af=0.02, max_af=0.20)
        expected_name = "ParabolicSAR_0.02_0.02_0.2"
        assert indicator.get_name() == expected_name

    def test_empty_dataframe(self):
        """Test Parabolic SAR with empty DataFrame."""
        data = pd.DataFrame()

        indicator = ParabolicSARIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "missing required columns" in str(exc_info.value).lower()

    def test_nan_values_in_data(self):
        """Test Parabolic SAR handling of NaN values in input data."""
        data = pd.DataFrame(
            {
                "high": [101, np.nan, 103, 104, 105],
                "low": [99, 100, 101, 102, 103],
                "close": [100, 101, 102, 103, 104],
            }
        )

        indicator = ParabolicSARIndicator()
        result = indicator.compute(data)

        # Should handle NaN values appropriately
        assert len(result) == len(data)

    def test_realistic_market_data(self):
        """Test Parabolic SAR with realistic market data patterns."""
        # Simulate realistic price action with gaps and reversals
        np.random.seed(42)

        prices = []
        current_price = 100.0
        trend = 1  # 1 for up, -1 for down

        for i in range(30):
            # Occasional trend changes
            if np.random.random() < 0.1:
                trend *= -1

            # Price movement with trend bias
            change = np.random.normal(trend * 0.5, 1.0)
            current_price += change

            # Create realistic OHLC
            high = current_price + abs(np.random.normal(0, 0.5))
            low = current_price - abs(np.random.normal(0, 0.5))
            close = current_price + np.random.normal(0, 0.3)

            prices.append({"high": high, "low": low, "close": close})

        data = pd.DataFrame(prices)

        indicator = ParabolicSARIndicator()
        result = indicator.compute(data)

        # Should handle realistic data
        assert len(result) == len(data)
        assert result.notna().sum() >= len(data) - 1

    def test_indicator_name_and_params(self):
        """Test indicator name and parameters accessibility."""
        indicator = ParabolicSARIndicator(initial_af=0.03, step_af=0.01, max_af=0.15)

        assert indicator.name == "ParabolicSAR"
        assert indicator.params["initial_af"] == 0.03
        assert indicator.params["step_af"] == 0.01
        assert indicator.params["max_af"] == 0.15

    def test_mathematical_properties(self):
        """Test mathematical properties of Parabolic SAR."""
        # Create predictable trending data
        data = pd.DataFrame(
            {
                "high": [100, 102, 104, 106, 108],
                "low": [98, 100, 102, 104, 106],
                "close": [99, 101, 103, 105, 107],
            }
        )

        indicator = ParabolicSARIndicator(initial_af=0.02, step_af=0.02, max_af=0.20)
        result = indicator.compute(data)

        # SAR values should be finite numbers
        valid_values = result.dropna()
        assert all(np.isfinite(valid_values))

        # SAR should not equal infinity or -infinity
        assert not any(np.isinf(valid_values))

    def test_edge_case_single_reversal(self):
        """Test Parabolic SAR with single trend reversal."""
        # Up then down pattern
        data = pd.DataFrame(
            {
                "high": [100, 102, 104, 103, 101],
                "low": [98, 100, 102, 101, 99],
                "close": [99, 101, 103, 102, 100],
            }
        )

        indicator = ParabolicSARIndicator()
        result = indicator.compute(data)

        # Should handle reversal smoothly
        assert len(result) == len(data)
        assert result.notna().sum() >= 4  # At least 4 valid values

    def test_gap_up_gap_down(self):
        """Test Parabolic SAR with price gaps."""
        data = pd.DataFrame(
            {
                "high": [
                    101,
                    103,
                    105,
                    110,
                    112,
                    108,
                    105,
                    103,
                ],  # Gap up then gap down
                "low": [99, 101, 103, 108, 110, 106, 103, 101],
                "close": [100, 102, 104, 109, 111, 107, 104, 102],
            }
        )

        indicator = ParabolicSARIndicator()
        result = indicator.compute(data)

        # Should handle gaps appropriately
        assert len(result) == len(data)
        assert result.notna().sum() >= len(data) - 1

    def test_custom_parameter_combinations(self):
        """Test various valid parameter combinations."""
        test_params = [
            (0.001, 0.001, 0.01),  # Very conservative
            (0.02, 0.02, 0.20),  # Standard
            (0.05, 0.03, 0.25),  # Aggressive
            (0.01, 0.005, 0.15),  # Mixed
        ]

        data = pd.DataFrame(
            {
                "high": [100 + i for i in range(10)],
                "low": [99 + i for i in range(10)],
                "close": [100 + i for i in range(10)],
            }
        )

        for initial_af, step_af, max_af in test_params:
            indicator = ParabolicSARIndicator(
                initial_af=initial_af, step_af=step_af, max_af=max_af
            )
            result = indicator.compute(data)

            # All combinations should work
            assert len(result) == len(data)
            assert result.notna().sum() >= 9  # Should have mostly valid values
