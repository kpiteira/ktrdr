"""
Tests for the RSI indicator.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators.rsi_indicator import RSIIndicator


# Create test data with known RSI values
def create_test_data():
    """Create price data that will produce known RSI values."""
    # Create a date range for index
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(30)]

    # Create price series that will produce predictable RSI values
    # First create an uptrend followed by a downtrend
    close_prices = [
        100,
        102,
        104,
        106,
        108,  # 5 days up
        107,
        106,
        105,
        104,
        103,  # 5 days down
        102,
        101,
        100,
        99,
        98,  # 5 more days down
        99,
        100,
        101,
        102,
        103,  # 5 days up
        105,
        107,
        109,
        111,
        113,  # 5 more days up
        112,
        111,
        110,
        109,
        108,  # 5 days down
    ]

    # Create DataFrame with OHLCV data
    df = pd.DataFrame(
        {
            "open": close_prices,
            "high": [p + 1 for p in close_prices],
            "low": [p - 1 for p in close_prices],
            "close": close_prices,
            "volume": [1000000] * len(close_prices),
        },
        index=dates,
    )

    return df


class TestRSIIndicator:
    """Test cases for the RSI indicator."""

    def test_initialization(self):
        """Test that RSI indicator can be initialized with various parameters."""
        # Default parameters
        rsi = RSIIndicator()
        assert rsi.params["period"] == 14
        assert rsi.params["source"] == "close"

        # Custom parameters
        rsi = RSIIndicator(period=7, source="high")
        assert rsi.params["period"] == 7
        assert rsi.params["source"] == "high"

    def test_parameter_validation(self):
        """Test that parameter validation works via Pydantic Params."""
        # Valid parameters
        rsi = RSIIndicator(period=2)
        assert rsi.params["period"] == 2

        # Invalid period type - Pydantic rejects non-int with strict=True
        with pytest.raises(DataError) as excinfo:
            RSIIndicator(period="14")
        assert excinfo.value.error_code == "INDICATOR-InvalidParameters"
        assert "validation_errors" in excinfo.value.details

        # Invalid period value - too small
        with pytest.raises(DataError) as excinfo:
            RSIIndicator(period=1)
        assert excinfo.value.error_code == "INDICATOR-InvalidParameters"
        assert "validation_errors" in excinfo.value.details

        # Invalid source type - Pydantic rejects non-string with strict=True
        with pytest.raises(DataError) as excinfo:
            RSIIndicator(source=123)
        assert excinfo.value.error_code == "INDICATOR-InvalidParameters"
        assert "validation_errors" in excinfo.value.details

    def test_compute_basic(self):
        """Test basic RSI computation on simple dataset."""
        # Create a simple DataFrame with some price data
        df = pd.DataFrame(
            {
                "close": [
                    10,
                    11,
                    12,
                    11,
                    10,
                    9,
                    10,
                    11,
                    12,
                    13,
                    14,
                    13,
                    12,
                    11,
                    12,
                    13,
                    14,
                    15,
                    14,
                    13,
                ]
            }
        )

        # Calculate RSI with period=5
        rsi = RSIIndicator(period=5)
        result = rsi.compute(df)

        # Check that result is a Series with appropriate length
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

        # Check that first valid values appear after period
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[4])
        assert not pd.isna(result.iloc[5])

        # Check that RSI is bounded between 0 and 100
        assert result.min() >= 0
        assert result.max() <= 100

    def test_rsi_directional_behavior(self):
        """Test that RSI follows expected directional behavior."""
        df = create_test_data()
        rsi = RSIIndicator(period=14)
        result = rsi.compute(df)

        # Check that RSI increases during uptrends
        # Position 15-19 is an uptrend, RSI should increase
        assert result.iloc[19] > result.iloc[15], "RSI should increase during uptrends"

        # Check that RSI continues to increase with strong uptrends
        # Position 20-24 is a continued uptrend, RSI should be higher than before
        assert (
            result.iloc[24] > result.iloc[19]
        ), "RSI should increase with continued uptrends"

        # Check that RSI decreases during downtrends
        # Position 25-29 is a downtrend, RSI should decrease
        assert (
            result.iloc[29] < result.iloc[24]
        ), "RSI should decrease during downtrends"

        # Check that RSI values are in expected ranges
        # After strong uptrend, RSI should be overbought (>70)
        assert (
            result.iloc[24] > 70
        ), "RSI should be overbought (>70) after strong uptrend"

        # After downtrend, RSI should be lower than peak value
        assert (
            result.iloc[29] < result.iloc[24] * 0.9
        ), "RSI should decrease significantly after downtrend"

    def test_error_handling(self):
        """Test that appropriate errors are raised."""
        rsi = RSIIndicator(period=14)

        # Empty DataFrame
        with pytest.raises(DataError) as excinfo:
            rsi.compute(pd.DataFrame())
        assert "Input DataFrame is empty" in str(excinfo.value)

        # Missing required columns
        with pytest.raises(DataError) as excinfo:
            rsi.compute(pd.DataFrame({"open": [1, 2, 3]}))
        assert "Missing required columns" in str(excinfo.value)

        # Insufficient data points
        with pytest.raises(DataError) as excinfo:
            rsi.compute(pd.DataFrame({"close": [1, 2, 3]}))
        assert "Insufficient data" in str(excinfo.value)

    def test_edge_cases(self):
        """Test RSI behavior with edge cases."""
        # Create data with no price changes (constant price)
        df_constant = pd.DataFrame({"close": [100] * 20})  # 20 days of constant price

        rsi = RSIIndicator(period=5)
        result = rsi.compute(df_constant)

        # RSI should be 50 for constant prices after the initial period
        for i in range(6, 20):
            assert abs(result.iloc[i] - 50.0) < 0.01

        # Create data with only gains (price always increasing)
        df_only_gains = pd.DataFrame(
            {"close": [100 + i for i in range(20)]}  # Strictly increasing
        )

        result = rsi.compute(df_only_gains)
        # RSI should approach 100 for continuous gains
        assert result.iloc[-1] > 95

        # Create data with only losses (price always decreasing)
        df_only_losses = pd.DataFrame(
            {"close": [100 - i for i in range(20)]}  # Strictly decreasing
        )

        result = rsi.compute(df_only_losses)
        # RSI should approach 0 for continuous losses
        assert result.iloc[-1] < 5
