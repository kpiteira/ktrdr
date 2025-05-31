"""
Tests for the DataAdapter class in the visualization module.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ktrdr.visualization.data_adapter import DataAdapter
from ktrdr.errors import DataError


class TestDataAdapter:
    """
    Test suite for the DataAdapter class.
    """

    @pytest.fixture
    def sample_ohlc_df(self):
        """Create a sample OHLC DataFrame for testing."""
        dates = [datetime.now() - timedelta(days=i) for i in range(5)]

        return pd.DataFrame(
            {
                "date": dates,
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [105.0, 106.0, 107.0, 108.0, 109.0],
                "low": [95.0, 96.0, 97.0, 98.0, 99.0],
                "close": [102.0, 103.0, 104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )

    @pytest.fixture
    def sample_line_df(self):
        """Create a sample line data DataFrame for testing."""
        dates = [datetime.now() - timedelta(days=i) for i in range(5)]

        return pd.DataFrame(
            {"date": dates, "value": [110.0, 112.0, 114.0, 116.0, 118.0]}
        )

    @pytest.fixture
    def sample_histogram_df(self):
        """Create a sample histogram DataFrame for testing."""
        dates = [datetime.now() - timedelta(days=i) for i in range(5)]

        return pd.DataFrame({"date": dates, "value": [1000, -1100, 1200, -1300, 1400]})

    def test_transform_ohlc_basic(self, sample_ohlc_df):
        """Test basic OHLC transformation."""
        # Transform the data
        result = DataAdapter.transform_ohlc(sample_ohlc_df)

        # Check the result
        assert isinstance(result, list)
        assert len(result) == 5  # Same length as input

        # Check structure of first item
        item = result[0]
        assert "time" in item
        assert "open" in item
        assert "high" in item
        assert "low" in item
        assert "close" in item

        # Check data types
        assert isinstance(item["time"], int)  # Unix timestamp
        assert isinstance(item["open"], float)
        assert isinstance(item["high"], float)
        assert isinstance(item["low"], float)
        assert isinstance(item["close"], float)

    def test_transform_ohlc_missing_columns(self, sample_ohlc_df):
        """Test OHLC transformation with missing columns."""
        # Remove a required column
        df_missing = sample_ohlc_df.drop(columns=["high"])

        # This should raise a DataError
        with pytest.raises(DataError) as exc_info:
            DataAdapter.transform_ohlc(df_missing)

        # Check the error details
        assert "Missing required columns" in str(exc_info.value)
        assert exc_info.value.error_code == "DATA-MissingColumns"

    def test_transform_line_basic(self, sample_line_df):
        """Test basic line data transformation."""
        # Transform the data
        result = DataAdapter.transform_line(sample_line_df)

        # Check the result
        assert isinstance(result, list)
        assert len(result) == 5  # Same length as input

        # Check structure of first item
        item = result[0]
        assert "time" in item
        assert "value" in item

        # Check data types
        assert isinstance(item["time"], int)  # Unix timestamp
        assert isinstance(item["value"], float)

    def test_transform_line_custom_columns(self, sample_ohlc_df):
        """Test line transformation with custom column names."""
        # Use 'date' and 'close' as the columns for the line data
        result = DataAdapter.transform_line(
            sample_ohlc_df, time_column="date", value_column="close"
        )

        # Check the result
        assert isinstance(result, list)
        assert len(result) == 5

        # Verify the values match
        for i, row in enumerate(result):
            assert row["value"] == sample_ohlc_df["close"].iloc[i]

    def test_transform_histogram_basic(self, sample_histogram_df):
        """Test basic histogram transformation."""
        # Transform the data
        result = DataAdapter.transform_histogram(sample_histogram_df)

        # Check the result
        assert isinstance(result, list)
        assert len(result) == 5  # Same length as input

        # Check structure of first item
        item = result[0]
        assert "time" in item
        assert "value" in item
        assert "color" in item  # Color should be added based on value

        # Check data types
        assert isinstance(item["time"], int)  # Unix timestamp
        assert isinstance(item["value"], float)
        assert isinstance(item["color"], str)  # Color is a string

        # Check color assignment
        for i, item in enumerate(result):
            value = sample_histogram_df["value"].iloc[i]
            if value > 0:
                assert item["color"] == "#26a69a"  # Positive color
            else:
                assert item["color"] == "#ef5350"  # Negative color

    def test_transform_histogram_custom_colors(self, sample_histogram_df):
        """Test histogram transformation with custom colors."""
        # Custom colors
        pos_color = "#00FF00"
        neg_color = "#FF0000"

        # Transform with custom colors
        result = DataAdapter.transform_histogram(
            sample_histogram_df, positive_color=pos_color, negative_color=neg_color
        )

        # Check color assignment with custom colors
        for i, item in enumerate(result):
            value = sample_histogram_df["value"].iloc[i]
            if value > 0:
                assert item["color"] == pos_color
            else:
                assert item["color"] == neg_color

    def test_transform_ohlc_with_string_dates(self):
        """Test OHLC transformation with string dates."""
        # Create DataFrame with string dates
        df = pd.DataFrame(
            {
                "date": ["2023-01-01", "2023-01-02", "2023-01-03"],
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [95.0, 96.0, 97.0],
                "close": [102.0, 103.0, 104.0],
            }
        )

        # Transform the data - should parse string dates
        result = DataAdapter.transform_ohlc(df)

        # Check results
        assert len(result) == 3
        for item in result:
            assert isinstance(item["time"], int)

    def test_transform_with_nan_values(self):
        """Test transformation with NaN values."""
        # Create DataFrame with NaN values
        df = pd.DataFrame(
            {
                "date": [datetime.now() - timedelta(days=i) for i in range(3)],
                "value": [100.0, np.nan, 102.0],
            }
        )

        # Transform - should skip NaN values
        result = DataAdapter.transform_line(df)

        # Check result - one row should be skipped
        assert len(result) == 2
