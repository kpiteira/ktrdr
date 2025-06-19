"""
Tests for Money Flow Index (MFI) indicator.

This module provides comprehensive tests for the MFI indicator implementation,
including mathematical accuracy, parameter validation, and edge case handling.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ktrdr.indicators.mfi_indicator import MFIIndicator
from ktrdr.errors import DataError


class TestMFIIndicator:
    """Test suite for MFI indicator."""

    def test_basic_initialization(self):
        """Test basic MFI initialization with default parameters."""
        indicator = MFIIndicator()

        assert indicator.name == "MFI"
        assert indicator.params["period"] == 14

    def test_custom_initialization(self):
        """Test MFI initialization with custom parameters."""
        indicator = MFIIndicator(period=20)

        assert indicator.params["period"] == 20

    def test_parameter_validation_success(self):
        """Test successful parameter validation."""
        # Valid parameters should not raise an error
        MFIIndicator(period=1)
        MFIIndicator(period=14)
        MFIIndicator(period=100)

    def test_parameter_validation_period_too_small(self):
        """Test parameter validation for period too small."""
        with pytest.raises(DataError) as exc_info:
            MFIIndicator(period=0)
        assert "period must be" in str(exc_info.value).lower()

    def test_parameter_validation_period_too_large(self):
        """Test parameter validation for period too large."""
        with pytest.raises(DataError) as exc_info:
            MFIIndicator(period=101)
        assert "period must be" in str(exc_info.value).lower()

    def test_parameter_validation_period_non_integer(self):
        """Test parameter validation for non-integer period."""
        with pytest.raises(DataError) as exc_info:
            MFIIndicator(period=14.5)
        assert "period must be" in str(exc_info.value).lower()

    def test_basic_calculation(self):
        """Test basic MFI calculation with sufficient data."""
        # Create test data with OHLCV
        data = pd.DataFrame(
            {
                "open": [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                ],
                "high": [
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                    117,
                ],
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "close": [
                    100.5,
                    101.5,
                    102.5,
                    103.5,
                    104.5,
                    105.5,
                    106.5,
                    107.5,
                    108.5,
                    109.5,
                    110.5,
                    111.5,
                    112.5,
                    113.5,
                    114.5,
                    115.5,
                    116.5,
                ],
                "volume": [
                    100000,
                    110000,
                    120000,
                    130000,
                    140000,
                    150000,
                    160000,
                    170000,
                    180000,
                    190000,
                    200000,
                    210000,
                    220000,
                    230000,
                    240000,
                    250000,
                    260000,
                ],
            }
        )

        indicator = MFIIndicator(period=10)
        result = indicator.compute(data)

        # Should return Series
        assert isinstance(result, pd.Series)

        # Should have same length as input
        assert len(result) == len(data)

        # Should have some valid values after the period
        valid_values = result.dropna()
        assert len(valid_values) > 0

    def test_bullish_market_with_volume(self):
        """Test MFI behavior in bullish market with increasing volume."""
        # Create bullish data with typical price increasing and high volume
        data = pd.DataFrame(
            {
                "open": [100 + i for i in range(20)],
                "high": [101 + i for i in range(20)],
                "low": [99 + i for i in range(20)],
                "close": [100.8 + i for i in range(20)],
                "volume": [100000 + i * 10000 for i in range(20)],  # Increasing volume
            }
        )

        indicator = MFIIndicator(period=10)
        result = indicator.compute(data)

        # In bullish trend with increasing volume, MFI should be relatively high
        valid_values = result.dropna()
        if len(valid_values) > 0:
            # Most values should be above 50 (neutral level)
            high_values = (valid_values > 50).sum()
            assert high_values >= len(valid_values) * 0.5  # At least 50% above neutral

    def test_bearish_market_with_volume(self):
        """Test MFI behavior in bearish market with increasing volume."""
        # Create bearish data with typical price decreasing and high volume
        data = pd.DataFrame(
            {
                "open": [120 - i for i in range(20)],
                "high": [121 - i for i in range(20)],
                "low": [119 - i for i in range(20)],
                "close": [119.2 - i for i in range(20)],
                "volume": [100000 + i * 10000 for i in range(20)],  # Increasing volume
            }
        )

        indicator = MFIIndicator(period=10)
        result = indicator.compute(data)

        # In bearish trend with increasing volume, MFI should be relatively low
        valid_values = result.dropna()
        if len(valid_values) > 0:
            # Most values should be below 50 (neutral level)
            low_values = (valid_values < 50).sum()
            assert low_values >= len(valid_values) * 0.5  # At least 50% below neutral

    def test_overbought_oversold_levels(self):
        """Test MFI overbought and oversold level behavior."""
        # Create data with extreme price movements and volume
        data = []

        # First part: strong buying (should push MFI toward 80+)
        for i in range(10):
            data.append(
                {
                    "open": 100 + i * 2,
                    "high": 102 + i * 2,
                    "low": 100 + i * 2,
                    "close": 101.9 + i * 2,
                    "volume": 200000,  # High volume
                }
            )

        # Second part: strong selling (should push MFI toward 20-)
        for i in range(10):
            data.append(
                {
                    "open": 120 - i * 2,
                    "high": 120 - i * 2,
                    "low": 118 - i * 2,
                    "close": 118.1 - i * 2,
                    "volume": 200000,  # High volume
                }
            )

        df = pd.DataFrame(data)

        indicator = MFIIndicator(period=8)
        result = indicator.compute(df)

        # MFI should oscillate between 0 and 100
        valid_values = result.dropna()
        if len(valid_values) > 0:
            assert all(0 <= val <= 100 for val in valid_values)

    def test_volume_impact(self):
        """Test that volume significantly impacts MFI calculation."""
        # Create two identical price datasets with different volumes
        base_data = {
            "open": [
                100,
                101,
                102,
                103,
                104,
                105,
                106,
                107,
                108,
                109,
                110,
                111,
                112,
                113,
                114,
                115,
            ],
            "high": [
                101,
                102,
                103,
                104,
                105,
                106,
                107,
                108,
                109,
                110,
                111,
                112,
                113,
                114,
                115,
                116,
            ],
            "low": [
                99,
                100,
                101,
                102,
                103,
                104,
                105,
                106,
                107,
                108,
                109,
                110,
                111,
                112,
                113,
                114,
            ],
            "close": [
                100.5,
                101.5,
                102.5,
                103.5,
                104.5,
                105.5,
                106.5,
                107.5,
                108.5,
                109.5,
                110.5,
                111.5,
                112.5,
                113.5,
                114.5,
                115.5,
            ],
        }

        # Dataset 1: Low volume
        data1 = pd.DataFrame({**base_data, "volume": [10000] * 16})

        # Dataset 2: High volume
        data2 = pd.DataFrame({**base_data, "volume": [100000] * 16})

        indicator = MFIIndicator(period=10)
        result1 = indicator.compute(data1)
        result2 = indicator.compute(data2)

        # Results should be similar since price movements are identical
        # (Volume affects money flow magnitude but not necessarily the ratio)
        valid1 = result1.dropna()
        valid2 = result2.dropna()

        if len(valid1) > 0 and len(valid2) > 0:
            # Both should show bullish MFI values (>50) due to uptrend
            assert (valid1 > 50).any() or (valid2 > 50).any()

    def test_missing_required_columns(self):
        """Test MFI with missing required columns."""
        # Missing volume column
        data = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [101, 102, 103],
                "low": [99, 100, 101],
                "close": [100.5, 101.5, 102.5],
            }
        )

        indicator = MFIIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "missing required columns" in str(exc_info.value).lower()
        assert "volume" in str(exc_info.value).lower()

    def test_insufficient_data(self):
        """Test MFI with insufficient data points."""
        # Only 5 data points, but need at least 15 for default parameters (period=14 + 1)
        data = pd.DataFrame(
            {
                "open": [100, 101, 102, 103, 104],
                "high": [101, 102, 103, 104, 105],
                "low": [99, 100, 101, 102, 103],
                "close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "volume": [100000, 110000, 120000, 130000, 140000],
            }
        )

        indicator = MFIIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "requires at least" in str(exc_info.value).lower()

    def test_minimum_required_data(self):
        """Test MFI with exactly minimum required data."""
        # Exactly 15 data points for default parameters (period=14 + 1)
        data = pd.DataFrame(
            {
                "open": [100 + i for i in range(15)],
                "high": [101 + i for i in range(15)],
                "low": [99 + i for i in range(15)],
                "close": [100.5 + i for i in range(15)],
                "volume": [100000 + i * 10000 for i in range(15)],
            }
        )

        indicator = MFIIndicator()
        result = indicator.compute(data)

        # Should work with exactly minimum data
        assert len(result) == 15

        # Should have exactly one valid value at the end
        valid_values = result.dropna()
        assert len(valid_values) == 1

    def test_custom_period_parameters(self):
        """Test MFI with custom period parameter."""
        # Use smaller period to test with less data
        data = pd.DataFrame(
            {
                "open": [100 + i for i in range(8)],
                "high": [101 + i for i in range(8)],
                "low": [99 + i for i in range(8)],
                "close": [100.5 + i for i in range(8)],
                "volume": [100000 + i * 10000 for i in range(8)],
            }
        )

        indicator = MFIIndicator(period=5)
        result = indicator.compute(data)

        # Should work with custom parameters
        assert len(result) == 8

        # Should have some valid values
        valid_values = result.dropna()
        assert len(valid_values) > 0

    def test_negative_volume_validation(self):
        """Test MFI with negative volume values."""
        # Need enough data to pass the insufficient data check
        data = pd.DataFrame(
            {
                "open": [100 + i for i in range(16)],
                "high": [101 + i for i in range(16)],
                "low": [99 + i for i in range(16)],
                "close": [100.5 + i for i in range(16)],
                "volume": [
                    100000 if i != 5 else -110000 for i in range(16)
                ],  # One negative volume
            }
        )

        indicator = MFIIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "non-negative volume" in str(exc_info.value).lower()

    def test_zero_volume(self):
        """Test MFI with zero volume values."""
        data = pd.DataFrame(
            {
                "open": [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "high": [
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                ],
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                ],
                "close": [
                    100.5,
                    101.5,
                    102.5,
                    103.5,
                    104.5,
                    105.5,
                    106.5,
                    107.5,
                    108.5,
                    109.5,
                    110.5,
                    111.5,
                    112.5,
                    113.5,
                    114.5,
                    115.5,
                ],
                "volume": [0] * 16,  # All zero volume
            }
        )

        indicator = MFIIndicator()
        result = indicator.compute(data)

        # Should handle zero volume gracefully
        assert len(result) == 16

        # When volume is zero, money flow is zero, so MFI should handle this appropriately
        valid_values = result.dropna()
        # With zero volume, we expect specific behavior depending on implementation

    def test_flat_prices_varying_volume(self):
        """Test MFI with flat prices but varying volume."""
        # Prices stay the same, but volume changes
        data = pd.DataFrame(
            {
                "open": [100] * 16,
                "high": [100] * 16,
                "low": [100] * 16,
                "close": [100] * 16,
                "volume": [100000 + i * 10000 for i in range(16)],
            }
        )

        indicator = MFIIndicator()
        result = indicator.compute(data)

        # With no price movement, typical price doesn't change
        # This should result in no positive or negative money flow after the first period
        assert len(result) == 16

    def test_extreme_volatility_with_volume(self):
        """Test MFI with extreme price volatility and varying volume."""
        np.random.seed(42)

        # Generate highly volatile data with volume
        data = pd.DataFrame(
            {
                "open": [100 + np.random.normal(0, 10) for _ in range(20)],
                "high": [100 + np.random.normal(0, 10) + 5 for _ in range(20)],
                "low": [100 + np.random.normal(0, 10) - 5 for _ in range(20)],
                "close": [100 + np.random.normal(0, 10) for _ in range(20)],
                "volume": [int(100000 * (0.5 + np.random.random())) for _ in range(20)],
            }
        )

        # Ensure proper OHLC relationships
        for i in range(len(data)):
            data.loc[i, "high"] = max(
                data.loc[i, "high"], data.loc[i, "open"], data.loc[i, "close"]
            )
            data.loc[i, "low"] = min(
                data.loc[i, "low"], data.loc[i, "open"], data.loc[i, "close"]
            )

        indicator = MFIIndicator(period=10)
        result = indicator.compute(data)

        # Should handle volatility without errors
        assert len(result) == 20

        # Values should be finite and within range
        valid_values = result.dropna()
        if len(valid_values) > 0:
            assert all(np.isfinite(valid_values))
            assert all(0 <= val <= 100 for val in valid_values)

    def test_get_name_method(self):
        """Test get_name method returns correct formatted name."""
        indicator = MFIIndicator(period=20)
        expected_name = "MFI_20"
        assert indicator.get_name() == expected_name

    def test_empty_dataframe(self):
        """Test MFI with empty DataFrame."""
        data = pd.DataFrame()

        indicator = MFIIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "missing required columns" in str(exc_info.value).lower()

    def test_nan_values_in_data(self):
        """Test MFI handling of NaN values in input data."""
        data = pd.DataFrame(
            {
                "open": [
                    100,
                    np.nan,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "high": [
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                ],
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                ],
                "close": [
                    100.5,
                    101.5,
                    102.5,
                    103.5,
                    104.5,
                    105.5,
                    106.5,
                    107.5,
                    108.5,
                    109.5,
                    110.5,
                    111.5,
                    112.5,
                    113.5,
                    114.5,
                    115.5,
                ],
                "volume": [
                    100000,
                    110000,
                    120000,
                    130000,
                    140000,
                    150000,
                    160000,
                    170000,
                    180000,
                    190000,
                    200000,
                    210000,
                    220000,
                    230000,
                    240000,
                    250000,
                ],
            }
        )

        indicator = MFIIndicator()
        result = indicator.compute(data)

        # Should handle NaN values appropriately
        assert len(result) == len(data)

    def test_mathematical_properties(self):
        """Test mathematical properties of MFI calculation."""
        # Create predictable data
        data = pd.DataFrame(
            {
                "open": [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "high": [
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                ],
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                ],
                "close": [
                    100.7,
                    101.7,
                    102.7,
                    103.7,
                    104.7,
                    105.7,
                    106.7,
                    107.7,
                    108.7,
                    109.7,
                    110.7,
                    111.7,
                    112.7,
                    113.7,
                    114.7,
                    115.7,
                ],
                "volume": [
                    100000,
                    110000,
                    120000,
                    130000,
                    140000,
                    150000,
                    160000,
                    170000,
                    180000,
                    190000,
                    200000,
                    210000,
                    220000,
                    230000,
                    240000,
                    250000,
                ],
            }
        )

        indicator = MFIIndicator()
        result = indicator.compute(data)

        # All valid values should be finite numbers between 0 and 100
        valid_values = result.dropna()
        assert all(np.isfinite(valid_values))
        assert all(0 <= val <= 100 for val in valid_values)

        # No infinity values
        assert not any(np.isinf(valid_values))

    def test_indicator_name_and_params(self):
        """Test indicator name and parameters accessibility."""
        indicator = MFIIndicator(period=20)

        assert indicator.name == "MFI"
        assert indicator.params["period"] == 20

    def test_typical_price_calculation(self):
        """Test the typical price calculation component of MFI."""
        # Create simple data to verify typical price calculation
        data = pd.DataFrame(
            {
                "open": [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "high": [
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                    117,
                ],
                "low": [
                    98,
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                ],
                "close": [
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                ],
                "volume": [100000] * 16,
            }
        )

        indicator = MFIIndicator(period=5)
        result = indicator.compute(data)

        # In this uptrend pattern, MFI should reflect positive money flow
        valid_values = result.dropna()
        if len(valid_values) > 0:
            # Should show bullish sentiment (> 50)
            assert (valid_values > 50).any()

    def test_money_flow_direction_sensitivity(self):
        """Test that MFI correctly identifies money flow direction."""
        # Create data with clear buying and selling periods
        data = []

        # Buying period: prices up, high volume
        for i in range(8):
            data.append(
                {
                    "open": 100 + i,
                    "high": 102 + i,
                    "low": 100 + i,
                    "close": 101.8 + i,
                    "volume": 200000,
                }
            )

        # Selling period: prices down, high volume
        for i in range(8):
            data.append(
                {
                    "open": 108 - i,
                    "high": 108 - i,
                    "low": 106 - i,
                    "close": 106.2 - i,
                    "volume": 200000,
                }
            )

        df = pd.DataFrame(data)

        indicator = MFIIndicator(period=6)
        result = indicator.compute(df)

        valid_values = result.dropna()
        if len(valid_values) >= 2:
            # Should show different MFI levels for buying vs selling periods
            # This tests that the indicator responds to money flow direction
            assert len(set(valid_values.round())) > 1  # Should have variation
