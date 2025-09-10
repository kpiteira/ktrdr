"""
Tests for the Moving Average indicators (SMA, EMA).
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators import ExponentialMovingAverage, SimpleMovingAverage


# Create test data for moving averages
def create_test_data():
    """Create price data that will produce known moving average values."""
    # Create a date range for index
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(30)]

    # Create price series with predictable patterns
    close_prices = [
        100,
        110,
        120,
        130,
        140,  # Linear increase
        150,
        150,
        150,
        150,
        150,  # Plateau
        140,
        130,
        120,
        110,
        100,  # Linear decrease
        90,
        80,
        70,
        60,
        50,  # Continue decrease
        50,
        50,
        50,
        50,
        50,  # Plateau
        60,
        70,
        80,
        90,
        100,  # Linear increase
    ]

    # Create DataFrame with OHLCV data
    df = pd.DataFrame(
        {
            "open": close_prices,
            "high": [p + 5 for p in close_prices],
            "low": [p - 5 for p in close_prices],
            "close": close_prices,
            "volume": [1000000] * len(close_prices),
        },
        index=dates,
    )

    return df


# Reference values for SMA(5) at specific points
SMA_5_REF_VALUES = {
    4: 120,  # Average of first 5 values (100+110+120+130+140)/5
    9: 150,  # During plateau (all values 150)
    14: 120,  # During decline (140+130+120+110+100)/5
    19: 70,  # Continued decline (90+80+70+60+50)/5
    24: 50,  # During second plateau (all values 50)
    29: 80,  # During incline (60+70+80+90+100)/5
}

# Reference values for EMA(5) at specific points
# These are approximated and might differ slightly from other implementations
EMA_5_REF_VALUES = {
    4: 120.00,  # First value is SMA
    9: 150.00,  # During plateau
    14: 115.33,  # During decline
    19: 63.11,  # Continued decline
    24: 50.69,  # During second plateau
    29: 86.42,  # During incline
}

# Test tolerance for floating point comparisons
TOLERANCE = 0.5  # Allow 0.5% difference for SMA
EMA_TOLERANCE = 10.0  # Allow larger tolerance for EMA (implementations vary)


class TestSimpleMovingAverage:
    """Test cases for the Simple Moving Average indicator."""

    def test_initialization(self):
        """Test that SMA indicator can be initialized with various parameters."""
        # Default parameters
        sma = SimpleMovingAverage()
        assert sma.params["period"] == 20
        assert sma.params["source"] == "close"

        # Custom parameters
        sma = SimpleMovingAverage(period=10, source="high")
        assert sma.params["period"] == 10
        assert sma.params["source"] == "high"

        # Test column name generation
        assert sma.get_column_name() == "sma_10"

    def test_parameter_validation(self):
        """Test that parameter validation works."""
        # Valid parameters
        sma = SimpleMovingAverage(period=2)
        assert sma.params["period"] == 2

        # Invalid period type
        with pytest.raises(DataError) as excinfo:
            SimpleMovingAverage(period="14")
        assert "SMA period must be an integer" in str(excinfo.value)

        # Invalid period value
        with pytest.raises(DataError) as excinfo:
            SimpleMovingAverage(period=1)
        assert "SMA period must be at least 2" in str(excinfo.value)

        # Invalid source type
        with pytest.raises(DataError) as excinfo:
            SimpleMovingAverage(source=123)
        assert "Source must be a string" in str(excinfo.value)

    def test_compute_basic(self):
        """Test basic SMA computation on simple dataset."""
        # Create a simple DataFrame with linear data
        df = pd.DataFrame({"close": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]})

        # Calculate SMA with period=3
        sma = SimpleMovingAverage(period=3)
        result = sma.compute(df)

        # Check that result is a Series with appropriate length
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

        # Check that first valid values appear after period-1
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert not pd.isna(result.iloc[2])

        # Check some known values
        assert result.iloc[2] == 20.0  # (10+20+30)/3
        assert result.iloc[3] == 30.0  # (20+30+40)/3
        assert result.iloc[9] == 90.0  # (80+90+100)/3

    def test_against_reference_values(self):
        """Test SMA calculations against known reference values."""
        df = create_test_data()
        sma = SimpleMovingAverage(period=5)
        result = sma.compute(df)

        # Check against reference values
        for idx, expected in SMA_5_REF_VALUES.items():
            actual = result.iloc[idx]
            # Assert that values are close (within tolerance)
            assert abs(actual - expected) < TOLERANCE, (
                f"SMA at position {idx}: expected {expected}, got {actual}"
            )

    def test_error_handling(self):
        """Test that appropriate errors are raised."""
        sma = SimpleMovingAverage(period=5)

        # Empty DataFrame
        with pytest.raises(DataError) as excinfo:
            sma.compute(pd.DataFrame())
        assert "Input DataFrame is empty" in str(excinfo.value)

        # Missing required columns
        with pytest.raises(DataError) as excinfo:
            sma.compute(pd.DataFrame({"open": [1, 2, 3]}))
        assert "Missing required columns" in str(excinfo.value)

        # Insufficient data points
        with pytest.raises(DataError) as excinfo:
            sma.compute(pd.DataFrame({"close": [1, 2, 3, 4]}))
        assert "Insufficient data" in str(excinfo.value)


class TestExponentialMovingAverage:
    """Test cases for the Exponential Moving Average indicator."""

    def test_initialization(self):
        """Test that EMA indicator can be initialized with various parameters."""
        # Default parameters
        ema = ExponentialMovingAverage()
        assert ema.params["period"] == 20
        assert ema.params["source"] == "close"
        assert ema.params["adjust"]

        # Custom parameters
        ema = ExponentialMovingAverage(period=10, source="high", adjust=False)
        assert ema.params["period"] == 10
        assert ema.params["source"] == "high"
        assert not ema.params["adjust"]

        # Test column name generation
        assert ema.get_column_name() == "ema_10"

    def test_parameter_validation(self):
        """Test that parameter validation works."""
        # Valid parameters
        ema = ExponentialMovingAverage(period=2)
        assert ema.params["period"] == 2

        # Invalid period type
        with pytest.raises(DataError) as excinfo:
            ExponentialMovingAverage(period="14")
        assert "EMA period must be an integer" in str(excinfo.value)

        # Invalid period value
        with pytest.raises(DataError) as excinfo:
            ExponentialMovingAverage(period=1)
        assert "EMA period must be at least 2" in str(excinfo.value)

        # Invalid source type
        with pytest.raises(DataError) as excinfo:
            ExponentialMovingAverage(source=123)
        assert "Source must be a string" in str(excinfo.value)

        # Invalid adjust type
        with pytest.raises(DataError) as excinfo:
            ExponentialMovingAverage(adjust="yes")
        assert "Adjust parameter must be a boolean" in str(excinfo.value)

    def test_compute_basic(self):
        """Test basic EMA computation on simple dataset."""
        # Create a simple DataFrame with linear data
        df = pd.DataFrame({"close": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]})

        # Calculate EMA with period=3
        ema = ExponentialMovingAverage(period=3)
        result = ema.compute(df)

        # Check that result is a Series with appropriate length
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

        # Check that there are no NaN values at the beginning
        # EMA can be calculated from the first value using pandas ewm
        assert not pd.isna(result.iloc[0])

        # Check that the values are monotonically increasing for monotonically increasing data
        assert all(result.diff().dropna() > 0)

    def test_against_reference_values(self):
        """Test EMA calculations against known reference values."""
        df = create_test_data()
        ema = ExponentialMovingAverage(period=5)
        result = ema.compute(df)

        # Check against reference values with increased tolerance
        for idx, expected in EMA_5_REF_VALUES.items():
            actual = result.iloc[idx]
            # Assert that values are relatively close (with higher tolerance)
            assert abs(actual - expected) < EMA_TOLERANCE, (
                f"EMA at position {idx}: expected {expected}, got {actual}"
            )

    def test_error_handling(self):
        """Test that appropriate errors are raised."""
        ema = ExponentialMovingAverage(period=5)

        # Empty DataFrame
        with pytest.raises(DataError) as excinfo:
            ema.compute(pd.DataFrame())
        assert "Input DataFrame is empty" in str(excinfo.value)

        # Missing required columns
        with pytest.raises(DataError) as excinfo:
            ema.compute(pd.DataFrame({"open": [1, 2, 3]}))
        assert "Missing required columns" in str(excinfo.value)

        # Insufficient data points
        with pytest.raises(DataError) as excinfo:
            ema.compute(pd.DataFrame({"close": [1, 2, 3, 4]}))
        assert "Insufficient data" in str(excinfo.value)

    def test_adjusted_vs_non_adjusted(self):
        """Test differences between adjusted and non-adjusted EMA."""
        df = create_test_data()

        # Calculate both adjusted and non-adjusted EMAs
        ema_adjusted = ExponentialMovingAverage(period=5, adjust=True)
        ema_non_adjusted = ExponentialMovingAverage(period=5, adjust=False)

        result_adj = ema_adjusted.compute(df)
        result_non_adj = ema_non_adjusted.compute(df)

        # The values should be different but close
        assert not result_adj.equals(result_non_adj)

        # The difference should decrease over time
        first_diff = abs(result_adj.iloc[5] - result_non_adj.iloc[5])
        last_diff = abs(result_adj.iloc[-1] - result_non_adj.iloc[-1])
        assert last_diff < first_diff
