"""
Unit tests for data-related API endpoints.

Tests the data endpoints for handling data retrieval operations.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from ktrdr.errors import DataNotFoundError, DataError


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient
    from ktrdr.api.main import app

    return TestClient(app)


@pytest.fixture
def mock_data_service():
    """Create a mock DataService for testing endpoints."""
    with patch("ktrdr.api.dependencies.DataService") as mock_class:
        mock_instance = mock_class.return_value
        # Set up async methods to return AsyncMock objects
        mock_instance.get_available_symbols = AsyncMock()
        mock_instance.get_available_timeframes = AsyncMock()
        mock_instance.load_data = AsyncMock()
        mock_instance.get_data_range = AsyncMock()
        yield mock_instance


@pytest.mark.api
def test_get_symbols_endpoint_success(client, mock_data_service):
    """Test successful retrieval of symbols."""
    # Set up mock to return sample symbols (with all required fields)
    mock_data_service.get_available_symbols.return_value = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "type": "stock",
            "exchange": "NASDAQ",
            "currency": "USD",
            "available_timeframes": ["1d", "1h"],
            "trading_hours": {
                "timezone": "America/New_York",
                "regular_hours": {"start": "09:30", "end": "16:00"},
                "extended_hours": [{"start": "04:00", "end": "09:30", "type": "pre"}],
                "trading_days": [0, 1, 2, 3, 4]
            }
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corp.",
            "type": "stock",
            "exchange": "NASDAQ",
            "currency": "USD",
            "available_timeframes": ["1d"],
            "trading_hours": {
                "timezone": "America/New_York",
                "regular_hours": {"start": "09:30", "end": "16:00"},
                "extended_hours": [{"start": "04:00", "end": "09:30", "type": "pre"}],
                "trading_days": [0, 1, 2, 3, 4]
            }
        },
    ]

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.get("/api/v1/symbols")

    # Check the response status code
    assert response.status_code == 200

    # Parse the response JSON
    data = response.json()

    # Verify the response structure
    assert data["success"] is True
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 2

    # Check the symbols returned
    symbols = [item["symbol"] for item in data["data"]]
    assert "AAPL" in symbols
    assert "MSFT" in symbols

    # Verify the mock was called
    mock_data_service.get_available_symbols.assert_called_once()


@pytest.mark.api
def test_get_symbols_endpoint_error(client, mock_data_service):
    """Test handling of errors in the symbols endpoint."""
    # Set up mock to raise an exception
    mock_data_service.get_available_symbols.side_effect = Exception("Test error")

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.get("/api/v1/symbols")

    # Check the response status code - DataError is translated to 400 in the API
    assert response.status_code == 400

    # Verify the response structure for error
    data = response.json()
    assert data["success"] is False
    assert "error" in data

    # Verify the mock was called
    mock_data_service.get_available_symbols.assert_called_once()


@pytest.mark.api
def test_get_timeframes_endpoint_success(client, mock_data_service):
    """Test successful retrieval of timeframes."""
    # Set up mock to return sample timeframes
    mock_data_service.get_available_timeframes.return_value = [
        {"id": "1d", "name": "Daily", "description": "Daily interval data"},
        {"id": "1h", "name": "Hourly", "description": "Hourly interval data"},
    ]

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.get("/api/v1/timeframes")

    # Check the response status code
    assert response.status_code == 200

    # Parse the response JSON
    data = response.json()

    # Verify the response structure
    assert data["success"] is True
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 2

    # Verify the mock was called
    mock_data_service.get_available_timeframes.assert_called_once()


@pytest.mark.api
def test_get_timeframes_endpoint_error(client, mock_data_service):
    """Test handling of errors in the timeframes endpoint."""
    # Set up mock to raise an exception
    mock_data_service.get_available_timeframes.side_effect = Exception("Test error")

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.get("/api/v1/timeframes")

    # Check the response status code - DataError is translated to 400 in the API
    assert response.status_code == 400

    # Verify the response structure for error
    data = response.json()
    assert data["success"] is False
    assert "error" in data

    # Verify the mock was called
    mock_data_service.get_available_timeframes.assert_called_once()


@pytest.mark.api
def test_load_data_endpoint_success(client, mock_data_service):
    """Test successful data loading."""
    # Set up mock to return operation response (new format)
    mock_data_service.load_data.return_value = {
        "status": "success",
        "fetched_bars": 3,
        "cached_before": True,
        "merged_file": "data/AAPL_1d.csv",
        "gaps_analyzed": 0,
        "segments_fetched": 1,
        "ib_requests_made": 0,
        "execution_time_seconds": 0.1,
        "error_message": None
    }

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.post(
            "/api/v1/data/load",
            json={
                "symbol": "AAPL",
                "timeframe": "1d",
                "start_date": "2023-01-01",
                "end_date": "2023-01-03",
                "mode": "full"
            },
        )

    # Check the response status code
    assert response.status_code == 200

    # Parse the response JSON
    data = response.json()

    # Verify the response structure (new format)
    assert data["success"] is True
    assert "data" in data
    assert "status" in data["data"]
    assert "fetched_bars" in data["data"]
    assert "execution_time_seconds" in data["data"]

    # Check operation results
    assert data["data"]["status"] == "success"
    assert data["data"]["fetched_bars"] == 3
    assert isinstance(data["data"]["execution_time_seconds"], (int, float))

    # Verify that the mock was called
    assert mock_data_service.load_data.call_count == 1
    call_args = mock_data_service.load_data.call_args[1]
    assert call_args["symbol"] == "AAPL"
    assert call_args["timeframe"] == "1d"
    assert call_args["include_metadata"] is True


@pytest.mark.api
def test_load_data_endpoint_not_found(client, mock_data_service):
    """Test handling of data not found error."""
    # Set up mock to raise DataNotFoundError
    mock_data_service.load_data.side_effect = DataNotFoundError(
        message="Data not found for NONEXISTENT (1d)",
        error_code="DATA-FileNotFound",
        details={"symbol": "NONEXISTENT", "timeframe": "1d"},
    )

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.post(
            "/api/v1/data/load", json={"symbol": "NONEXISTENT", "timeframe": "1d"}
        )

    # Check the response status code for not found
    assert response.status_code == 404

    # Verify the response structure for error - our custom error format
    data = response.json()
    assert "error" in data
    assert "success" in data
    assert data["success"] is False
    assert "message" in data["error"]
    assert "not found" in data["error"]["message"].lower()

    # Verify the mock was called
    mock_data_service.load_data.assert_called_once()


@pytest.mark.api
def test_load_data_endpoint_data_error(client, mock_data_service):
    """Test handling of DataError."""
    # Set up mock to raise DataError
    mock_data_service.load_data.side_effect = DataError(
        message="Failed to load data for AAPL (1d): Invalid data format",
        error_code="DATA-LoadError",
        details={"symbol": "AAPL", "timeframe": "1d"},
    )

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.post(
            "/api/v1/data/load", json={"symbol": "AAPL", "timeframe": "1d"}
        )

    # Check the response status code for the error
    assert (
        response.status_code == 400
    )  # Since DataError maps to 400 in the exception handlers

    # Verify the response structure for error
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "DATA-LoadError"

    # Verify the mock was called
    mock_data_service.load_data.assert_called_once()


@pytest.mark.api
def test_load_data_endpoint_unexpected_error(client, mock_data_service):
    """Test handling of unexpected errors."""
    # Set up mock to raise an unexpected exception
    mock_data_service.load_data.side_effect = ValueError("Unexpected error")

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.post(
            "/api/v1/data/load", json={"symbol": "AAPL", "timeframe": "1d"}
        )

    # Check the response status code - generic exceptions are wrapped in DataError (400)
    assert response.status_code == 400

    # Verify the response structure for error
    data = response.json()
    assert data["success"] is False
    assert "error" in data

    # Verify the mock was called
    mock_data_service.load_data.assert_called_once()


@pytest.mark.api
def test_data_range_endpoint_success(client, mock_data_service):
    """Test successful retrieval of data range."""
    # Set up mock to return sample data range
    mock_data_service.get_data_range.return_value = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "start_date": datetime(2023, 1, 1),
        "end_date": datetime(2023, 1, 31),
        "point_count": 31,
    }

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.post(
            "/api/v1/data/range", json={"symbol": "AAPL", "timeframe": "1d"}
        )

    # Check the response status code
    assert response.status_code == 200

    # Parse the response JSON
    data = response.json()

    # Verify the response structure
    assert data["success"] is True
    assert "data" in data
    assert "symbol" in data["data"]
    assert "timeframe" in data["data"]
    assert "start_date" in data["data"]
    assert "end_date" in data["data"]
    assert "point_count" in data["data"]

    # Check data values
    assert data["data"]["symbol"] == "AAPL"
    assert data["data"]["timeframe"] == "1d"
    assert data["data"]["point_count"] == 31

    # Verify the mock was called
    mock_data_service.get_data_range.assert_called_once_with(
        symbol="AAPL", timeframe="1d"
    )


@pytest.mark.api
def test_data_range_endpoint_not_found(client, mock_data_service):
    """Test handling of data not found in range endpoint."""
    # Set up mock to raise DataNotFoundError
    mock_data_service.get_data_range.side_effect = DataNotFoundError(
        message="Data not found for NONEXISTENT (1d)",
        error_code="DATA-FileNotFound",
        details={"symbol": "NONEXISTENT", "timeframe": "1d"},
    )

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.post(
            "/api/v1/data/range", json={"symbol": "NONEXISTENT", "timeframe": "1d"}
        )

    # Check the response status code for not found
    assert response.status_code == 404

    # Verify the response structure for error - FastAPI's HTTPException format
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()

    # Verify the mock was called
    mock_data_service.get_data_range.assert_called_once()


@pytest.mark.api
def test_data_range_endpoint_error(client, mock_data_service):
    """Test handling of errors in data range endpoint."""
    # Set up mock to raise a generic exception
    mock_data_service.get_data_range.side_effect = Exception("Test error")

    # Make the request
    with patch(
        "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
    ):
        response = client.post(
            "/api/v1/data/range", json={"symbol": "AAPL", "timeframe": "1d"}
        )

    # Check the response status code for error
    assert response.status_code == 400

    # Verify the response structure for error
    data = response.json()
    assert data["success"] is False
    assert "error" in data

    # Verify the mock was called
    mock_data_service.get_data_range.assert_called_once()
