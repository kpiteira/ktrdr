"""
API data models tests.

This module tests the data models for API requests and responses.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from ktrdr.api.models.data import (
    DataLoadRequest,
    OHLCVData,
    OHLCVPoint,
    SymbolInfo,
    TimeframeInfo,
)


class TestDataLoadRequest:
    """Tests for the DataLoadRequest model."""

    def test_valid_request(self):
        """Test that a valid data load request is created correctly."""
        request = DataLoadRequest(
            symbol="AAPL",
            timeframe="1d",
            start_date="2023-01-01",
            end_date="2023-01-31",
        )
        assert request.symbol == "AAPL"
        assert request.timeframe == "1d"
        assert request.start_date == "2023-01-01"
        assert request.end_date == "2023-01-31"
        assert request.mode == "local"  # Default value

    def test_request_without_dates(self):
        """Test that a request can be created without dates."""
        request = DataLoadRequest(symbol="MSFT", timeframe="1h")
        assert request.symbol == "MSFT"
        assert request.timeframe == "1h"
        assert request.start_date is None
        assert request.end_date is None

    def test_invalid_timeframe(self):
        """Test that invalid timeframe raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            DataLoadRequest(symbol="AAPL", timeframe="invalid")  # Invalid timeframe
        # Check that the error message mentions timeframe
        assert "timeframe" in str(exc_info.value)

    def test_start_date_after_end_date(self):
        """Test that start_date after end_date raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            DataLoadRequest(
                symbol="AAPL",
                timeframe="1d",
                start_date="2023-02-01",  # After end_date
                end_date="2023-01-01",
            )
        # Check that the error message mentions date validation
        assert "start_date" in str(exc_info.value) or "end_date" in str(exc_info.value)


class TestOHLCVPoint:
    """Tests for the OHLCVPoint model."""

    def test_valid_ohlcv_point(self):
        """Test that a valid OHLCV point is created correctly."""
        point = OHLCVPoint(
            timestamp=datetime(2023, 1, 1),
            open=150.0,
            high=155.0,
            low=148.0,
            close=153.0,
            volume=1000000.0,
        )
        assert point.timestamp == datetime(2023, 1, 1)
        assert point.open == 150.0
        assert point.high == 155.0
        assert point.low == 148.0
        assert point.close == 153.0
        assert point.volume == 1000000.0

    def test_high_less_than_open_or_close(self):
        """Test that high less than open or close raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVPoint(
                timestamp=datetime(2023, 1, 1),
                open=150.0,
                high=145.0,  # Lower than open
                low=140.0,
                close=148.0,
                volume=1000000.0,
            )
        assert "high price" in str(exc_info.value)

    def test_low_greater_than_open_or_close(self):
        """Test that low greater than open or close raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVPoint(
                timestamp=datetime(2023, 1, 1),
                open=150.0,
                high=155.0,
                low=152.0,  # Higher than close
                close=148.0,
                volume=1000000.0,
            )
        assert "low price" in str(exc_info.value)

    def test_high_less_than_low(self):
        """Test that high less than low raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVPoint(
                timestamp=datetime(2023, 1, 1),
                open=150.0,
                high=145.0,
                low=148.0,  # Higher than high
                close=149.0,
                volume=1000000.0,
            )
        # Check that the error message mentions either high price or low price
        error_msg = str(exc_info.value)
        assert "high price" in error_msg or "low price" in error_msg


class TestOHLCVData:
    """Tests for the OHLCVData model."""

    def test_valid_ohlcv_data(self):
        """Test that valid OHLCV data is created correctly."""
        data = OHLCVData(
            dates=["2023-01-01", "2023-01-02"],
            ohlcv=[
                [150.0, 155.0, 148.0, 153.0, 1000000.0],
                [153.0, 158.0, 151.0, 157.0, 1200000.0],
            ],
            metadata={"symbol": "AAPL", "timeframe": "1d"},
        )
        assert len(data.dates) == 2
        assert len(data.ohlcv) == 2
        assert data.ohlcv[0][3] == 153.0  # close price
        assert data.metadata["symbol"] == "AAPL"

    def test_mismatched_dates_and_ohlcv_length(self):
        """Test that mismatched dates and OHLCV lengths raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            OHLCVData(
                dates=["2023-01-01", "2023-01-02", "2023-01-03"],  # 3 dates
                ohlcv=[
                    [150.0, 155.0, 148.0, 153.0, 1000000.0],
                    [153.0, 158.0, 151.0, 157.0, 1200000.0],  # But only 2 OHLCV points
                ],
            )
        assert "dates and ohlcv" in str(exc_info.value)

    def test_invalid_ohlcv_format(self):
        """Test that invalid OHLCV format raises validation error."""
        # Test with wrong number of values
        with pytest.raises(ValidationError) as exc_info:
            OHLCVData(
                dates=["2023-01-01"],
                ohlcv=[[150.0, 155.0, 148.0, 153.0]],  # Missing volume
            )
        assert "5 values" in str(exc_info.value)

        # Test with invalid price relationships
        with pytest.raises(ValidationError) as exc_info:
            OHLCVData(
                dates=["2023-01-01"],
                ohlcv=[[150.0, 145.0, 140.0, 148.0, 1000000.0]],  # High < Open
            )
        assert "high price" in str(exc_info.value)


class TestSymbolAndTimeframeInfo:
    """Tests for the SymbolInfo and TimeframeInfo models."""

    def test_valid_symbol_info(self):
        """Test that valid symbol info is created correctly."""
        symbol_info = SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            type="stock",
            exchange="NASDAQ",
            currency="USD",  # Required field in current model
            available_timeframes=["1d", "1h", "15m"],
        )
        assert symbol_info.symbol == "AAPL"
        assert symbol_info.name == "Apple Inc."
        assert symbol_info.type == "stock"
        assert symbol_info.exchange == "NASDAQ"
        assert symbol_info.currency == "USD"
        assert len(symbol_info.available_timeframes) == 3
        assert "1d" in symbol_info.available_timeframes

    def test_valid_timeframe_info(self):
        """Test that valid timeframe info is created correctly."""
        timeframe_info = TimeframeInfo(
            id="1d", name="Daily", description="Daily price data"
        )
        assert timeframe_info.id == "1d"
        assert timeframe_info.name == "Daily"
        assert timeframe_info.description == "Daily price data"
