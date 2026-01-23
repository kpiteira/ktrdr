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

        # M3b: Check that all expected semantic columns are present
        expected_cols = ["upper", "middle", "lower"]
        for col in expected_cols:
            assert col in result.columns

        # Check the upper channel calculation (max high over 5 periods)
        # For period=5, starting from index 4 (5th row)
        upper_channel = result["upper"]
        assert pd.isna(upper_channel.iloc[0])  # First 4 values should be NaN
        assert pd.isna(upper_channel.iloc[3])
        assert upper_channel.iloc[4] == 107  # Max of [102,103,105,106,107]
        assert upper_channel.iloc[5] == 108  # Max of [103,105,106,107,108]

        # Check the lower channel calculation (min low over 5 periods)
        lower_channel = result["lower"]
        assert pd.isna(lower_channel.iloc[0])  # First 4 values should be NaN
        assert pd.isna(lower_channel.iloc[3])
        assert lower_channel.iloc[4] == 98  # Min of [98,99,100,101,102]
        assert lower_channel.iloc[5] == 99  # Min of [99,100,101,102,103]

        # Check middle line calculation
        middle_line = result["middle"]
        assert pd.isna(middle_line.iloc[0])
        assert middle_line.iloc[4] == (107 + 98) / 2  # (upper + lower) / 2

    def test_donchian_channels_without_middle(self):
        """Test Donchian Channels calculation with middle line (M3b: always included)."""
        data = create_sample_ohlcv_data(days=30)

        # M3b: include_middle parameter ignored, middle always included in core outputs
        indicator = DonchianChannelsIndicator(period=10, include_middle=False)
        result = indicator.compute(data)

        # M3b: All core semantic columns should be present
        expected_cols = ["upper", "middle", "lower"]
        for col in expected_cols:
            assert col in result.columns

    def test_donchian_channels_position_calculation(self):
        """Test position within channel calculation via get_signals()."""
        data = create_sample_ohlcv_data(days=30)
        indicator = DonchianChannelsIndicator(period=10)

        signals = indicator.get_signals(data)

        # Position should be between 0 and 1 (where valid)
        assert "position" in signals.columns
        valid_positions = signals["position"].dropna()
        assert (valid_positions >= 0).all()
        assert (valid_positions <= 1).all()

    def test_donchian_channels_signals(self):
        """Test Donchian Channels signal generation."""
        data = create_sample_ohlcv_data(days=30)
        indicator = DonchianChannelsIndicator(period=10)

        signals = indicator.get_signals(data)

        # Check all expected signal columns exist
        expected_cols = [
            "upper_breakout",
            "lower_breakout",
            "overbought",
            "oversold",
            "strong_uptrend",
            "strong_downtrend",
            "position",
        ]
        for col in expected_cols:
            assert col in signals.columns

        # Breakout signals should be boolean
        assert signals["upper_breakout"].dtype == bool
        assert signals["lower_breakout"].dtype == bool

    def test_donchian_channels_analysis(self):
        """Test comprehensive analysis functionality."""
        data = create_sample_ohlcv_data(days=50)
        indicator = DonchianChannelsIndicator(period=10)

        analysis = indicator.get_analysis(data)

        # Check structure
        assert "current_values" in analysis
        assert "market_state" in analysis
        assert "volatility_analysis" in analysis
        assert "breakout_analysis" in analysis
        assert "support_resistance" in analysis
        assert "signals" in analysis

        # Check current_values has expected keys
        cv = analysis["current_values"]
        assert "upper_channel" in cv
        assert "lower_channel" in cv
        assert "position_in_channel" in cv

        # Upper should be >= lower
        assert cv["upper_channel"] >= cv["lower_channel"]

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
        indicator = DonchianChannelsIndicator(period=5)

        # Minimum data (exactly period length)
        data = create_sample_ohlcv_data(days=5)
        result = indicator.compute(data)
        assert len(result) == 5
        # Only last row should have valid values
        assert not pd.isna(result["upper"].iloc[-1])

    def test_donchian_channels_different_periods(self):
        """Test Donchian Channels with different period settings."""
        data = create_sample_ohlcv_data(days=50)

        for period in [5, 10, 20]:
            indicator = DonchianChannelsIndicator(period=period)
            result = indicator.compute(data)

            assert "upper" in result.columns
            assert "lower" in result.columns
            assert "middle" in result.columns

            # Longer periods should have more NaN values at start
            nan_count = result["upper"].isna().sum()
            assert nan_count == period - 1

    def test_donchian_channels_mathematical_properties(self):
        """Test mathematical properties of Donchian Channels."""
        data = create_sample_ohlcv_data(days=30)
        indicator = DonchianChannelsIndicator(period=10)
        result = indicator.compute(data)

        # Upper >= Middle >= Lower (where valid)
        valid_mask = ~result["upper"].isna()
        assert (
            result.loc[valid_mask, "upper"] >= result.loc[valid_mask, "middle"]
        ).all()
        assert (
            result.loc[valid_mask, "middle"] >= result.loc[valid_mask, "lower"]
        ).all()

        # Middle should be exactly (upper + lower) / 2
        expected_middle = (result["upper"] + result["lower"]) / 2
        pd.testing.assert_series_equal(
            result["middle"], expected_middle, check_names=False
        )

    def test_donchian_channels_alias(self):
        """Test that the alias works correctly."""
        from ktrdr.indicators.donchian_channels import DonchianChannels

        # Should be the same class
        assert DonchianChannels is DonchianChannelsIndicator

        # Should work the same way
        indicator = DonchianChannels(period=15)
        assert indicator.params["period"] == 15
        assert isinstance(indicator, DonchianChannelsIndicator)
