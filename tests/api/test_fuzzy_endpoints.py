"""
Unit tests for the fuzzy endpoints in the API.

These tests verify that the fuzzy API endpoints function correctly,
handle valid inputs appropriately, and return proper error responses
for invalid inputs.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from ktrdr.api.main import app
from ktrdr.errors import ConfigurationError, ProcessingError, DataError


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_fuzzy_service():
    """Create a mock FuzzyService for testing endpoints."""
    with patch('ktrdr.api.dependencies.FuzzyService') as mock_class:
        mock_instance = mock_class.return_value
        # Set up async methods as AsyncMock
        mock_instance.get_available_indicators = AsyncMock()
        mock_instance.get_fuzzy_sets = AsyncMock()
        mock_instance.fuzzify_indicator = AsyncMock()
        mock_instance.fuzzify_data = AsyncMock()
        yield mock_instance


@pytest.mark.endpoints
def test_get_fuzzy_indicators(client, mock_fuzzy_service):
    """Test the GET /api/v1/fuzzy/indicators endpoint."""
    # Set up mock to return expected data
    mock_fuzzy_service.get_available_indicators.return_value = [
        {"name": "rsi", "description": "Relative Strength Index", "parameters": {"period": 14}},
        {"name": "macd", "description": "Moving Average Convergence Divergence", 
         "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9}}
    ]
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.get("/api/v1/fuzzy/indicators")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "success" in data and data["success"] is True
    assert "data" in data
    indicators = data["data"]
    assert len(indicators) == 2
    assert indicators[0]["name"] == "rsi"
    assert indicators[1]["name"] == "macd"


@pytest.mark.endpoints
def test_get_fuzzy_sets(client, mock_fuzzy_service):
    """Test the GET /api/v1/fuzzy/sets/{indicator} endpoint."""
    # Set up mock to return expected data
    mock_fuzzy_service.get_fuzzy_sets.return_value = {
        "rsi": {
            "low": {"type": "triangular", "params": {"a": 0, "b": 0, "c": 30}},
            "medium": {"type": "triangular", "params": {"a": 30, "b": 50, "c": 70}},
            "high": {"type": "triangular", "params": {"a": 70, "b": 100, "c": 100}}
        }
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.get("/api/v1/fuzzy/sets/rsi")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "success" in data and data["success"] is True
    assert "data" in data
    fuzzy_sets = data["data"]
    assert "rsi" in fuzzy_sets
    assert "low" in fuzzy_sets["rsi"]
    assert "medium" in fuzzy_sets["rsi"]
    assert "high" in fuzzy_sets["rsi"]
    assert fuzzy_sets["rsi"]["medium"]["type"] == "triangular"
    assert fuzzy_sets["rsi"]["medium"]["params"]["b"] == 50


@pytest.mark.endpoints
def test_get_fuzzy_sets_invalid_indicator(client, mock_fuzzy_service):
    """Test the GET /api/v1/fuzzy/sets/{indicator} endpoint with an invalid indicator."""
    # Set up mock to raise an error
    mock_fuzzy_service.get_fuzzy_sets.side_effect = ConfigurationError(
        message="Invalid indicator", 
        error_code="FUZZY-InvalidIndicator",
        details={"indicator": "invalid_indicator"}
    )
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.get("/api/v1/fuzzy/sets/invalid_indicator")
    
    # Verify response
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert "success" in data["detail"] and data["detail"]["success"] is False
    assert data["detail"]["error"]["code"] == "FUZZY-InvalidIndicator"


@pytest.mark.endpoints
def test_fuzzify_indicator(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/evaluate endpoint."""
    # Set up mock to return expected data
    mock_fuzzy_service.fuzzify_indicator.return_value = {
        "indicator": "rsi",
        "values": [30, 45, 60, 75],
        "fuzzified": {
            "low": [0.7, 0.3, 0.0, 0.0],
            "medium": [0.3, 0.7, 0.7, 0.3],
            "high": [0.0, 0.0, 0.3, 0.7]
        }
    }
    
    # Create request data
    request_data = {
        "indicator": "rsi",
        "values": [30, 45, 60, 75]
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/evaluate", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "success" in data and data["success"] is True
    assert "data" in data
    result = data["data"]
    assert result["indicator"] == "rsi"
    assert "fuzzified" in result
    assert "low" in result["fuzzified"]
    assert len(result["fuzzified"]["low"]) == 4


@pytest.mark.endpoints
def test_fuzzify_indicator_invalid_data(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/evaluate endpoint with invalid data."""
    # Set up mock to raise an error
    mock_fuzzy_service.fuzzify_indicator.side_effect = ProcessingError(
        message="Invalid indicator values", 
        error_code="FUZZY-InvalidValues",
        details={"indicator": "rsi", "value_count": 0}
    )
    
    # Create request data with empty values
    request_data = {
        "indicator": "rsi",
        "values": []
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/evaluate", json=request_data)
    
    # Verify response
    assert response.status_code == 500  # The API currently returns 500 for this error
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert "success" in data["detail"] and data["detail"]["success"] is False


@pytest.mark.endpoints
def test_fuzzify_data(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/data endpoint."""
    # Current date for testing
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
    
    # Set up mock to return expected data
    mock_fuzzy_service.fuzzify_data.return_value = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "dates": dates,
        "indicators": {
            "rsi": {
                "rsi_low": [0.8, 0.6, 0.4, 0.2, 0.0],
                "rsi_medium": [0.2, 0.4, 0.8, 0.4, 0.2],
                "rsi_high": [0.0, 0.0, 0.2, 0.4, 0.8]
            }
        },
        "metadata": {
            "start_date": dates[-1],
            "end_date": dates[0],
            "points": 5
        }
    }
    
    # Create request data
    request_data = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "indicators": [
            {
                "name": "rsi",
                "source_column": "close",
                "parameters": {"period": 14}
            }
        ],
        "start_date": (today - timedelta(days=10)).isoformat(),
        "end_date": today.isoformat()
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/data", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "success" in data and data["success"] is True
    assert "data" in data
    result = data["data"]
    assert result["symbol"] == "AAPL"
    assert "indicators" in result
    assert "rsi" in result["indicators"]
    assert "rsi_low" in result["indicators"]["rsi"]
    assert len(result["indicators"]["rsi"]["rsi_low"]) == 5


@pytest.mark.endpoints
def test_fuzzify_data_missing_symbol(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/data endpoint with a missing symbol."""
    # Create request data with missing symbol
    request_data = {
        "timeframe": "1d",
        "indicators": [
            {
                "name": "rsi",
                "source_column": "close"
            }
        ]
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/data", json=request_data)
    
    # Verify response
    assert response.status_code == 500  # The API currently returns 500 for this error
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert "success" in data["detail"] and data["detail"]["success"] is False


@pytest.mark.endpoints
def test_fuzzify_data_data_error(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/data endpoint with a data error."""
    # Set up mock to raise a DataError
    mock_fuzzy_service.fuzzify_data.side_effect = DataError(
        message="Symbol not found", 
        error_code="DATA-SymbolNotFound",
        details={"symbol": "INVALID", "timeframe": "1d"}
    )
    
    # Create request data with invalid symbol
    request_data = {
        "symbol": "INVALID",
        "timeframe": "1d",
        "indicators": [
            {
                "name": "rsi",
                "source_column": "close"
            }
        ]
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/data", json=request_data)
    
    # Verify response
    assert response.status_code == 404  # Not Found
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert "success" in data["detail"] and data["detail"]["success"] is False
    assert data["detail"]["error"]["code"] == "DATA-SymbolNotFound"


@pytest.mark.endpoints
def test_fuzzify_data_invalid_indicator(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/data endpoint with an invalid indicator."""
    # Set up mock to raise a ConfigurationError
    mock_fuzzy_service.fuzzify_data.side_effect = ConfigurationError(
        message="Invalid indicator", 
        error_code="FUZZY-InvalidIndicator",
        details={"indicator": "invalid_indicator"}
    )
    
    # Create request data with invalid indicator
    request_data = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "indicators": [
            {
                "name": "invalid_indicator",
                "source_column": "close"
            }
        ]
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/data", json=request_data)
    
    # Verify response
    assert response.status_code == 400  # Bad Request
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert "success" in data["detail"] and data["detail"]["success"] is False
    assert data["detail"]["error"]["code"] == "FUZZY-InvalidIndicator"


@pytest.mark.endpoints
def test_fuzzify_data_processing_error(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/data endpoint with a processing error."""
    # Set up mock to raise a ProcessingError
    mock_fuzzy_service.fuzzify_data.side_effect = ProcessingError(
        message="Error calculating indicator", 
        error_code="INDICATOR-CalculationError",
        details={"indicator": "rsi", "error": "Division by zero"}
    )
    
    # Create request data
    request_data = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "indicators": [
            {
                "name": "rsi",
                "source_column": "close"
            }
        ]
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/data", json=request_data)
    
    # Verify response
    assert response.status_code == 500  # The API currently returns 500 for this error
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert "success" in data["detail"] and data["detail"]["success"] is False
    assert data["detail"]["error"]["code"] == "INDICATOR-CalculationError"


@pytest.mark.endpoints
def test_fuzzify_data_with_custom_fuzzy_sets(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/data endpoint with custom fuzzy sets."""
    # Current date for testing
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
    
    # Set up mock to return expected data
    mock_fuzzy_service.fuzzify_data.return_value = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "dates": dates,
        "indicators": {
            "rsi": {
                "custom_very_low": [0.9, 0.7, 0.3, 0.1, 0.0],
                "custom_low": [0.1, 0.3, 0.7, 0.3, 0.1],
                "custom_high": [0.0, 0.0, 0.3, 0.6, 0.9]
            }
        },
        "metadata": {
            "start_date": dates[-1],
            "end_date": dates[0],
            "points": 5
        }
    }
    
    # Create request data with custom fuzzy sets
    request_data = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "indicators": [
            {
                "name": "rsi",
                "source_column": "close",
                "parameters": {"period": 14},
                "fuzzy_sets": {
                    "custom_very_low": {"type": "triangular", "params": {"a": 0, "b": 0, "c": 20}},
                    "custom_low": {"type": "triangular", "params": {"a": 10, "b": 30, "c": 50}},
                    "custom_high": {"type": "triangular", "params": {"a": 50, "b": 70, "c": 100}}
                }
            }
        ]
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/data", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "success" in data and data["success"] is True
    assert "data" in data
    result = data["data"]
    assert "indicators" in result
    assert "rsi" in result["indicators"]
    assert "custom_very_low" in result["indicators"]["rsi"]
    assert "custom_low" in result["indicators"]["rsi"]
    assert "custom_high" in result["indicators"]["rsi"]


@pytest.mark.endpoints
def test_fuzzify_data_invalid_timeframe(client, mock_fuzzy_service):
    """Test the POST /api/v1/fuzzy/data endpoint with an invalid timeframe."""
    # Set up mock to raise a ConfigurationError
    mock_fuzzy_service.fuzzify_data.side_effect = ConfigurationError(
        message="Invalid timeframe", 
        error_code="DATA-InvalidTimeframe",
        details={"timeframe": "invalid", "supported": ["1m", "5m", "1h", "1d"]}
    )
    
    # Create request data with invalid timeframe
    request_data = {
        "symbol": "AAPL",
        "timeframe": "invalid",
        "indicators": [
            {
                "name": "rsi",
                "source_column": "close"
            }
        ]
    }
    
    # Make request to endpoint
    with patch('ktrdr.api.dependencies.get_fuzzy_service', return_value=mock_fuzzy_service):
        response = client.post("/api/v1/fuzzy/data", json=request_data)
    
    # Verify response
    assert response.status_code == 400  # Bad Request
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert "success" in data["detail"] and data["detail"]["success"] is False
    assert data["detail"]["error"]["code"] == "DATA-InvalidTimeframe"
    assert "supported" in data["detail"]["error"]["details"]