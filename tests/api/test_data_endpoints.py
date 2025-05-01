"""
Unit tests for data-related API endpoints.

Tests the data endpoints for handling data retrieval operations.
"""
import pytest
from unittest.mock import patch, MagicMock
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
    with patch('ktrdr.api.dependencies.DataService') as mock_class:
        mock_instance = mock_class.return_value
        yield mock_instance


@pytest.mark.api
def test_get_symbols_endpoint_success(client, mock_data_service):
    """Test successful retrieval of symbols."""
    # Set up mock to return sample symbols
    mock_data_service.get_available_symbols.return_value = [
        {
            "symbol": "AAPL", 
            "name": "Apple Inc.", 
            "type": "stock", 
            "exchange": "NASDAQ", 
            "available_timeframes": ["1d", "1h"]
        },
        {
            "symbol": "MSFT", 
            "name": "Microsoft Corp.", 
            "type": "stock", 
            "exchange": "NASDAQ", 
            "available_timeframes": ["1d"]
        }
    ]
    
    # Make the request
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
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
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
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
        {
            "id": "1d",
            "name": "Daily",
            "description": "Daily interval data"
        },
        {
            "id": "1h",
            "name": "Hourly",
            "description": "Hourly interval data"
        }
    ]
    
    # Make the request
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
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
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
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
    # Set up mock to return sample data
    mock_data_service.load_data.return_value = {
        "dates": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "ohlcv": [
            [100.0, 105.0, 95.0, 102.0, 1000],
            [101.0, 106.0, 96.0, 103.0, 1100],
            [102.0, 107.0, 97.0, 104.0, 1200]
        ],
        "metadata": {
            "symbol": "AAPL",
            "timeframe": "1d",
            "points": 3
        }
    }
    
    # Make the request
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
        response = client.post(
            "/api/v1/data/load",
            json={
                "symbol": "AAPL",
                "timeframe": "1d",
                "start_date": "2023-01-01",
                "end_date": "2023-01-03",
                "include_metadata": True
            }
        )
    
    # Check the response status code
    assert response.status_code == 200
    
    # Parse the response JSON
    data = response.json()
    
    # Verify the response structure
    assert data["success"] is True
    assert "data" in data
    assert "dates" in data["data"]
    assert "ohlcv" in data["data"]
    assert "metadata" in data["data"]
    
    # Check data contents
    assert len(data["data"]["dates"]) == 3
    assert len(data["data"]["ohlcv"]) == 3
    assert data["data"]["metadata"]["symbol"] == "AAPL"
    
    # Verify that the mock was called - we don't check the parameters exactly
    # because the API converts string dates to datetime objects
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
        details={"symbol": "NONEXISTENT", "timeframe": "1d"}
    )
    
    # Make the request
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
        response = client.post(
            "/api/v1/data/load",
            json={
                "symbol": "NONEXISTENT",
                "timeframe": "1d"
            }
        )
    
    # Check the response status code for not found
    assert response.status_code == 404
    
    # Verify the response structure for error - FastAPI's HTTPException format
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()
    
    # Verify the mock was called
    mock_data_service.load_data.assert_called_once()


@pytest.mark.api
def test_load_data_endpoint_data_error(client, mock_data_service):
    """Test handling of DataError."""
    # Set up mock to raise DataError
    mock_data_service.load_data.side_effect = DataError(
        message="Failed to load data for AAPL (1d): Invalid data format",
        error_code="DATA-LoadError",
        details={"symbol": "AAPL", "timeframe": "1d"}
    )
    
    # Make the request
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
        response = client.post(
            "/api/v1/data/load",
            json={
                "symbol": "AAPL",
                "timeframe": "1d"
            }
        )
    
    # Check the response status code for the error
    assert response.status_code == 400  # Since DataError maps to 400 in the exception handlers
    
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
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
        response = client.post(
            "/api/v1/data/load",
            json={
                "symbol": "AAPL",
                "timeframe": "1d"
            }
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
        "point_count": 31
    }
    
    # Make the request
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
        response = client.post(
            "/api/v1/data/range",
            json={
                "symbol": "AAPL",
                "timeframe": "1d"
            }
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
        symbol="AAPL",
        timeframe="1d"
    )


@pytest.mark.api
def test_data_range_endpoint_not_found(client, mock_data_service):
    """Test handling of data not found in range endpoint."""
    # Set up mock to raise DataNotFoundError
    mock_data_service.get_data_range.side_effect = DataNotFoundError(
        message="Data not found for NONEXISTENT (1d)",
        error_code="DATA-FileNotFound",
        details={"symbol": "NONEXISTENT", "timeframe": "1d"}
    )
    
    # Make the request
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
        response = client.post(
            "/api/v1/data/range",
            json={
                "symbol": "NONEXISTENT",
                "timeframe": "1d"
            }
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
    with patch('ktrdr.api.dependencies.get_data_service', return_value=mock_data_service):
        response = client.post(
            "/api/v1/data/range",
            json={
                "symbol": "AAPL",
                "timeframe": "1d"
            }
        )
    
    # Check the response status code for error
    assert response.status_code == 400
    
    # Verify the response structure for error
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    
    # Verify the mock was called
    mock_data_service.get_data_range.assert_called_once()