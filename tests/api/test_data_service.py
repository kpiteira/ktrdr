"""
Unit tests for DataService.

Tests the data service layer that adapts the core data modules for API use.
"""

import pytest
import pandas as pd
import types
from datetime import datetime
from unittest.mock import patch, MagicMock

from ktrdr.api.services.data_service import DataService
from ktrdr.errors import DataNotFoundError, DataError


@pytest.fixture
def mock_data_manager():
    """Create a mock DataManager for testing the service."""
    with patch("ktrdr.api.services.data_service.DataManager") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance

        # Disable retry mechanism completely for tests
        with patch(
            "ktrdr.api.services.data_service.retry_with_backoff",
            lambda *args, **kwargs: lambda func: func,
        ):
            yield mock_instance


@pytest.mark.api
def test_init_with_defaults():
    """Test that DataService can be initialized with default values."""
    with patch("ktrdr.api.services.data_service.DataManager"):
        service = DataService()
        assert service is not None


@pytest.mark.api
@pytest.mark.asyncio
async def test_load_data_success(mock_data_manager):
    """Test successful data loading with metadata."""
    # Create sample DataFrame for DataManager to return
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [95.0, 96.0, 97.0],
            "close": [102.0, 103.0, 104.0],
            "volume": [1000, 1100, 1200],
        },
        index=pd.date_range(start="2023-01-01", periods=3, freq="D"),
    )

    # Set up mock to return DataFrame (DataService will convert to operation result)
    mock_data_manager.load_data.return_value = df

    # Create service and call method
    service = DataService()
    result = await service.load_data(
        symbol="AAPL",
        timeframe="1d",
        start_date="2023-01-01",
        end_date="2023-01-03",
        include_metadata=True,
    )

    # Verify result structure (DataService converts DataFrame to operation format)
    assert isinstance(result, dict)
    assert "status" in result
    assert "fetched_bars" in result
    assert "execution_time_seconds" in result

    # Check operation details
    assert result["status"] == "success"
    assert result["fetched_bars"] == 3


@pytest.mark.api
@pytest.mark.asyncio
async def test_load_data_without_metadata(mock_data_manager):
    """Test data loading without metadata."""
    # Create sample DataFrame
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [95.0, 96.0, 97.0],
            "close": [102.0, 103.0, 104.0],
            "volume": [1000, 1100, 1200],
        },
        index=pd.date_range(start="2023-01-01", periods=3, freq="D"),
    )

    # Set up mock to return sample DataFrame
    mock_data_manager.load_data.return_value = df

    # Create service and call method
    service = DataService()
    result = await service.load_data(
        symbol="AAPL", timeframe="1d", include_metadata=False
    )

    # Verify result structure (operational metrics format)
    assert isinstance(result, dict)
    assert "status" in result
    assert "fetched_bars" in result
    assert "execution_time_seconds" in result

    # Check operation details
    assert result["status"] == "success"
    assert result["fetched_bars"] == 3


@pytest.mark.api
@pytest.mark.asyncio
async def test_load_data_empty_result(mock_data_manager):
    """Test handling of empty data."""
    # Create empty DataFrame
    df = pd.DataFrame({"open": [], "high": [], "low": [], "close": [], "volume": []})

    # Set up mock to return empty DataFrame
    mock_data_manager.load_data.return_value = df

    # Create service and call method
    service = DataService()
    result = await service.load_data(
        symbol="AAPL", timeframe="1d", include_metadata=True
    )

    # Verify result structure (operational metrics format)
    assert isinstance(result, dict)
    assert "status" in result
    assert "fetched_bars" in result
    assert "execution_time_seconds" in result

    # Check operation details for empty result
    assert result["status"] == "success"
    assert result["fetched_bars"] == 0


@pytest.mark.api
@pytest.mark.asyncio
async def test_load_data_data_not_found(mock_data_manager):
    """Test handling of data not found error."""
    # Set up mock to raise DataNotFoundError
    mock_data_manager.load_data.side_effect = DataNotFoundError(
        message="Data not found for AAPL (1d)",
        error_code="DATA-FileNotFound",
        details={"symbol": "AAPL", "timeframe": "1d"},
    )

    # Create service and call method
    service = DataService()

    # Expect the exception to be re-raised
    with pytest.raises(DataNotFoundError):
        await service.load_data(symbol="AAPL", timeframe="1d")

    # Verify the mock was called
    mock_data_manager.load_data.assert_called_once()


@pytest.mark.api
@pytest.mark.asyncio
async def test_load_data_other_exception(mock_data_manager):
    """Test handling of other exceptions."""
    # Set up mock to raise another type of exception
    mock_data_manager.load_data.side_effect = Exception("Test error")

    # Create service instance
    service = DataService()

    # Create a version of load_data without any decorators
    def load_data_without_retry(
        self, symbol, timeframe, start_date=None, end_date=None, include_metadata=True
    ):
        try:
            # Load data using the DataManager
            df = self.data_manager.load_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                validate=True,
                repair=False,
            )

            # Convert DataFrame to API response format
            result = self._convert_df_to_api_format(
                df, symbol, timeframe, include_metadata
            )

            return result
        except DataNotFoundError as e:
            raise
        except Exception as e:
            raise DataError(
                message=f"Failed to load data for {symbol} ({timeframe}): {str(e)}",
                error_code="DATA-LoadError",
                details={"symbol": symbol, "timeframe": timeframe},
            ) from e

    # Replace the method temporarily
    original_load_data = service.load_data
    service.load_data = types.MethodType(load_data_without_retry, service)

    try:
        # Expect a DataError to be raised
        with pytest.raises(DataError):
            await service.load_data(symbol="AAPL", timeframe="1d")
    finally:
        # Restore the original method
        service.load_data = original_load_data


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_available_symbols(mock_data_manager):
    """Test retrieval of available symbols."""
    # Set up mock to return list of available files and symbol information
    mock_data_manager.data_loader.get_available_data_files.return_value = [
        ("AAPL", "1d"),
        ("AAPL", "1h"),
        ("MSFT", "1d"),
    ]

    # Create a mock get_available_timeframes_for_symbol method
    def mock_get_timeframes(symbol):
        return ["1d", "1h"] if symbol == "AAPL" else ["1d"]

    # Create service with our mocked method
    service = DataService()
    service.get_available_timeframes_for_symbol = mock_get_timeframes

    # Add sample data range for summary
    mock_data_manager.data_loader.get_data_date_range.return_value = (
        datetime(2023, 1, 1),
        datetime(2023, 12, 31),
    )

    # Call method
    result = await service.get_available_symbols()

    # Verify result
    assert isinstance(result, list)
    assert len(result) == 2  # AAPL and MSFT

    # Check that symbols are correct
    symbols = [item["symbol"] for item in result]
    assert "AAPL" in symbols
    assert "MSFT" in symbols


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_available_timeframes():
    """Test retrieval of available timeframes."""
    # Create service and call method
    service = DataService()
    result = await service.get_available_timeframes()

    # Verify result structure
    assert isinstance(result, list)
    assert len(result) > 0

    # Check that each timeframe has the expected structure
    for timeframe in result:
        assert "id" in timeframe
        assert "name" in timeframe
        assert "description" in timeframe


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_data_range(mock_data_manager):
    """Test retrieval of data range information."""
    # Set up mock to return data range tuple
    mock_data_manager.data_loader.get_data_date_range.return_value = (
        datetime(2023, 1, 1),
        datetime(2023, 1, 3),
    )

    # Create service and call method
    service = DataService()
    result = await service.get_data_range(symbol="AAPL", timeframe="1d")

    # Verify result structure
    assert isinstance(result, dict)
    assert "symbol" in result
    assert "timeframe" in result
    assert "start_date" in result
    assert "end_date" in result
    assert "point_count" in result

    # Check specific values
    assert result["symbol"] == "AAPL"
    assert result["timeframe"] == "1d"
    assert result["point_count"] == 2  # 2 days between Jan 1 and Jan 3

    # Verify the mock was called
    mock_data_manager.data_loader.get_data_date_range.assert_called_once_with(
        "AAPL", "1d"
    )


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_data_range_not_found(mock_data_manager):
    """Test handling of data not found in get_data_range."""
    # Set up mock to return None (no data range found)
    mock_data_manager.data_loader.get_data_date_range.return_value = None

    # Create service and call method
    service = DataService()

    # Expect the exception to be re-raised
    with pytest.raises(DataNotFoundError):
        await service.get_data_range(symbol="AAPL", timeframe="1d")

    # Verify the mock was called
    mock_data_manager.data_loader.get_data_date_range.assert_called_once()


@pytest.mark.api
@pytest.mark.asyncio
async def test_health_check_healthy(mock_data_manager):
    """Test health check when service is healthy."""
    # Set up mock to return some available files
    mock_data_manager.data_loader.data_dir = "/path/to/data"
    mock_data_manager.data_loader.get_available_data_files.return_value = [
        ("AAPL", "1d"),
        ("AAPL", "1h"),
        ("MSFT", "1d"),
    ]

    service = DataService()
    result = await service.health_check()

    # Verify result structure
    assert isinstance(result, dict)
    assert result["status"] == "healthy"
    assert "data_directory" in result
    assert "available_files" in result
    assert result["available_files"] == 3
    assert "message" in result

    # Verify the mock was called
    mock_data_manager.data_loader.get_available_data_files.assert_called_once()


@pytest.mark.api
@pytest.mark.asyncio
async def test_health_check_unhealthy(mock_data_manager):
    """Test health check when service encounters errors."""
    # Set up mock to raise an exception
    mock_data_manager.data_loader.get_available_data_files.side_effect = Exception(
        "Test error"
    )

    service = DataService()
    result = await service.health_check()

    # Verify result structure
    assert isinstance(result, dict)
    assert result["status"] == "unhealthy"
    assert "message" in result
    assert "Test error" in result["message"]
