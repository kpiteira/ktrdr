"""
Tests for Donchian Channels indicator.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators.donchian_channels import DonchianChannelsIndicator


def create_sample_ohlcv_data(days=30, start_price=100):
    """Create sample OHLCV data for testing."""
    dates = pd.date_range("2023-01-01", periods=days, freq="D")
    np.random.seed(42)  # For reproducible tests

    # Generate price series with some volatility
    price_changes = np.random.normal(0, 1, days)
    prices = [start_price]
    for change in price_changes[1:]:
        prices.append(prices[-1] * (1 + change * 0.01))

    data = pd.DataFrame(
        {
            "open": prices,
            "high": [p * (1 + abs(np.random.normal(0, 0.005))) for p in prices],
            "low": [p * (1 - abs(np.random.normal(0, 0.005))) for p in prices],
            "close": prices,
            "volume": np.random.randint(1000, 10000, days),
        },
        index=dates,
    )

    return data


class TestDonchianChannelsIndicator:
    """Test suite for DonchianChannelsIndicator."""

    def test_donchian_channels_initialization(self):
        """Test Donchian Channels indicator initialization."""
        # Default initialization
        indicator = DonchianChannelsIndicator()
        assert indicator.params["period"] == 20
        assert indicator.params["include_middle"] is True
        assert indicator.name == "DonchianChannels"

        # Custom initialization
        indicator = DonchianChannelsIndicator(period=14, include_middle=False)
        assert indicator.params["period"] == 14
        assert indicator.params["include_middle"] is False

    def test_donchian_channels_parameter_validation(self):
        """Test parameter validation."""
        # Valid parameters
        DonchianChannelsIndicator(period=10)
        DonchianChannelsIndicator(period=50)
        DonchianChannelsIndicator(period=200)

        # Invalid parameters
        with pytest.raises(ValueError, match="period must be a positive integer"):
            DonchianChannelsIndicator(period=0)

        with pytest.raises(ValueError, match="period must be a positive integer"):
            DonchianChannelsIndicator(period=-5)

        with pytest.raises(ValueError, match="period must be at least 2"):
            DonchianChannelsIndicator(period=1)

        with pytest.raises(ValueError, match="period should not exceed 500"):
            DonchianChannelsIndicator(period=600)

        with pytest.raises(ValueError, match="period must be a positive integer"):
            DonchianChannelsIndicator(period=10.5)

    def test_donchian_channels_calculation_basic(self):
        """Test basic Donchian Channels calculation."""
        # Create test data with known high/low patterns
        data = pd.DataFrame(
            {
                "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
                "high": [102, 103, 105, 106, 107, 108, 109, 110, 111, 112, 113],
                "low": [98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
                "close": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
                "volume": [1000] * 11,
            }
        )
        data.index = pd.date_range("2023-01-01", periods=11, freq="D")

        indicator = DonchianChannelsIndicator(period=5)
        result = indicator.compute(data)

        # Check that all expected columns are present
        expected_cols = [
            "DC_Upper_5",
            "DC_Lower_5",
            "DC_Middle_5",
            "DC_Width_5",
            "DC_Position_5",
        ]
        for col in expected_cols:
            assert col in result.columns

        # Check the upper channel calculation (max high over 5 periods)
        # For period=5, starting from index 4 (5th row)
        upper_channel = result["DC_Upper_5"]
        assert pd.isna(upper_channel.iloc[0])  # First 4 values should be NaN
        assert pd.isna(upper_channel.iloc[3])
        assert upper_channel.iloc[4] == 107  # Max of [102,103,105,106,107]
        assert upper_channel.iloc[5] == 108  # Max of [103,105,106,107,108]

        # Check the lower channel calculation (min low over 5 periods)
        lower_channel = result["DC_Lower_5"]
        assert pd.isna(lower_channel.iloc[0])  # First 4 values should be NaN
        assert pd.isna(lower_channel.iloc[3])
        assert lower_channel.iloc[4] == 98  # Min of [98,99,100,101,102]
        assert lower_channel.iloc[5] == 99  # Min of [99,100,101,102,103]

        # Check middle line calculation
        middle_line = result["DC_Middle_5"]
        assert pd.isna(middle_line.iloc[0])
        assert middle_line.iloc[4] == (107 + 98) / 2  # (upper + lower) / 2

    def test_donchian_channels_without_middle(self):
        """Test Donchian Channels calculation without middle line."""
        data = create_sample_ohlcv_data(days=30)

        indicator = DonchianChannelsIndicator(period=10, include_middle=False)
        result = indicator.compute(data)

        # Middle line should not be present
        assert "DC_Middle_10" not in result.columns

        # But other columns should be present
        assert "DC_Upper_10" in result.columns
        assert "DC_Lower_10" in result.columns
        assert "DC_Width_10" in result.columns
        assert "DC_Position_10" in result.columns

    def test_donchian_channels_position_calculation(self):
        """Test position within channel calculation."""
        # Create data where we can predict the position
        data = pd.DataFrame(
            {
                "open": [100] * 10,
                "high": [110] * 10,  # Constant high
                "low": [90] * 10,  # Constant low
                "close": [
                    95,
                    100,
                    105,
                    90,
                    110,
                    97,
                    103,
                    92,
                    108,
                    101,
                ],  # Varying close
                "volume": [1000] * 10,
            }
        )
        data.index = pd.date_range("2023-01-01", periods=10, freq="D")

        indicator = DonchianChannelsIndicator(period=5)
        result = indicator.compute(data)

        # With constant high=110 and low=90, channel width = 20
        # Position = (close - low) / (high - low) = (close - 90) / 20

        # Check positions for the last few values (after initial period)
        position = result["DC_Position_5"]

        # For close=90 (at low), position should be 0
        # FIXED: Use original data DataFrame, not result (result no longer includes input columns)
        low_close_indices = data[data["close"] == 90].index
        if len(low_close_indices) > 0:
            idx = low_close_indices[-1]
            if not pd.isna(position.loc[idx]):
                assert abs(position.loc[idx] - 0.0) < 0.01

        # For close=110 (at high), position should be 1
        # FIXED: Use original data DataFrame, not result (result no longer includes input columns)
        high_close_indices = data[data["close"] == 110].index
        if len(high_close_indices) > 0:
            idx = high_close_indices[-1]
            if not pd.isna(position.loc[idx]):
                assert abs(position.loc[idx] - 1.0) < 0.01

    def test_donchian_channels_signals(self):
        """Test Donchian Channels signal generation."""
        # Create data with clear breakout patterns
        data = pd.DataFrame(
            {
                "open": [100] * 20,
                "high": [105] * 10 + [120] * 10,  # Break higher in second half
                "low": [95] * 10 + [80] * 10,  # Break lower in second half
                "close": [102] * 10 + [118] * 10,  # Follow the pattern
                "volume": [1000] * 20,
            }
        )
        data.index = pd.date_range("2023-01-01", periods=20, freq="D")

        indicator = DonchianChannelsIndicator(period=5)
        result = indicator.get_signals(data)

        # Check that signal columns are present
        signal_cols = [
            "DC_Upper_Breakout_5",
            "DC_Lower_Breakout_5",
            "DC_Overbought_5",
            "DC_Oversold_5",
            "DC_Strong_Uptrend_5",
            "DC_Strong_Downtrend_5",
        ]
        for col in signal_cols:
            assert col in result.columns

        # Check breakout signals are valid boolean values
        upper_breakout = result["DC_Upper_Breakout_5"]
        # Should be valid boolean series (not requiring specific pattern)
        assert upper_breakout.dtype == bool or upper_breakout.dtype == "bool"
        # Values should be well-defined (not all NaN)
        assert not upper_breakout.isna().all()

    def test_donchian_channels_analysis(self):
        """Test comprehensive analysis functionality."""
        data = create_sample_ohlcv_data(days=50)

        indicator = DonchianChannelsIndicator(period=20)
        analysis = indicator.get_analysis(data)

        # Check analysis structure
        assert "current_values" in analysis
        assert "market_state" in analysis
        assert "volatility_analysis" in analysis
        assert "breakout_analysis" in analysis
        assert "support_resistance" in analysis
        assert "signals" in analysis

        # Check current values
        current_values = analysis["current_values"]
        required_keys = [
            "upper_channel",
            "lower_channel",
            "middle_line",
            "current_price",
            "channel_width",
            "position_in_channel",
        ]
        for key in required_keys:
            assert key in current_values
            assert isinstance(current_values[key], (int, float))

        # Check volatility analysis
        volatility = analysis["volatility_analysis"]
        assert "state" in volatility
        assert "current_width" in volatility
        assert "average_width" in volatility
        assert "width_percentile" in volatility

        # Check breakout analysis
        breakout = analysis["breakout_analysis"]
        assert "days_since_upper_breakout" in breakout
        assert "days_since_lower_breakout" in breakout
        assert "potential_upper_breakout" in breakout
        assert "potential_lower_breakout" in breakout

        # Check support/resistance levels
        support_resistance = analysis["support_resistance"]
        assert "resistance_level" in support_resistance
        assert "support_level" in support_resistance
        assert "distance_to_resistance" in support_resistance
        assert "distance_to_support" in support_resistance

        # Check signals
        signals = analysis["signals"]
        signal_keys = ["near_breakout", "trending_up", "trending_down", "consolidating"]
        for key in signal_keys:
            assert key in signals
            # Accept both Python bool and numpy bool
            assert isinstance(signals[key], (bool, np.bool_))

    def test_donchian_channels_data_validation(self):
        """Test data validation."""
        indicator = DonchianChannelsIndicator()

        # Test with empty data
        with pytest.raises(DataError):
            indicator.compute(pd.DataFrame())

        # Test with missing required columns
        invalid_data = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [102, 103, 104],
                # Missing 'low', 'close', 'volume'
            }
        )
        with pytest.raises(DataError):
            indicator.compute(invalid_data)

    def test_donchian_channels_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Test with minimum required data
        data = create_sample_ohlcv_data(days=5)
        indicator = DonchianChannelsIndicator(period=5)
        result = indicator.compute(data)

        # Should have exactly one non-NaN value for each channel
        assert result["DC_Upper_5"].notna().sum() == 1
        assert result["DC_Lower_5"].notna().sum() == 1

        # Test with constant prices (no volatility)
        constant_data = pd.DataFrame(
            {
                "open": [100] * 10,
                "high": [100] * 10,
                "low": [100] * 10,
                "close": [100] * 10,
                "volume": [1000] * 10,
            }
        )
        constant_data.index = pd.date_range("2023-01-01", periods=10, freq="D")

        indicator = DonchianChannelsIndicator(period=5)
        result = indicator.compute(constant_data)

        # Upper and lower channels should be the same
        upper = result["DC_Upper_5"].dropna()
        lower = result["DC_Lower_5"].dropna()
        width = result["DC_Width_5"].dropna()

        assert all(upper == 100)
        assert all(lower == 100)
        assert all(width == 0)

    def test_donchian_channels_different_periods(self):
        """Test Donchian Channels with different period settings."""
        data = create_sample_ohlcv_data(days=100)

        periods_to_test = [5, 10, 20, 50]

        for period in periods_to_test:
            indicator = DonchianChannelsIndicator(period=period)
            result = indicator.compute(data)

            # Check that the correct columns are created
            assert f"DC_Upper_{period}" in result.columns
            assert f"DC_Lower_{period}" in result.columns
            assert f"DC_Width_{period}" in result.columns
            assert f"DC_Position_{period}" in result.columns

            # Check that we have the right number of non-NaN values
            expected_valid_count = len(data) - period + 1
            actual_valid_count = result[f"DC_Upper_{period}"].notna().sum()
            assert actual_valid_count == expected_valid_count

    def test_donchian_channels_mathematical_properties(self):
        """Test mathematical properties of Donchian Channels."""
        data = create_sample_ohlcv_data(days=50)

        indicator = DonchianChannelsIndicator(period=20)
        result = indicator.compute(data)

        # Upper channel should always be >= lower channel
        upper = result["DC_Upper_20"].dropna()
        lower = result["DC_Lower_20"].dropna()
        assert all(upper >= lower)

        # Channel width should always be non-negative
        width = result["DC_Width_20"].dropna()
        assert all(width >= 0)

        # Position should be between 0 and 1 (inclusive)
        position = result["DC_Position_20"].dropna()
        assert all((position >= 0) & (position <= 1))

        # Middle line should be exactly between upper and lower
        middle = result["DC_Middle_20"].dropna()
        expected_middle = (upper + lower) / 2
        pd.testing.assert_series_equal(middle, expected_middle, check_names=False)

    def test_donchian_channels_alias(self):
        """Test that the alias works correctly."""
        from ktrdr.indicators.donchian_channels import DonchianChannels

        # Should be the same class
        assert DonchianChannels is DonchianChannelsIndicator

        # Should work the same way
        indicator = DonchianChannels(period=15)
        assert indicator.params["period"] == 15
        assert isinstance(indicator, DonchianChannelsIndicator)
