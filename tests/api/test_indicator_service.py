"""
Tests for the indicator service.

This module contains tests for the indicator service functionality.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import pandas as pd
from datetime import datetime

from ktrdr.api.services.indicator_service import IndicatorService
from ktrdr.api.models.indicators import IndicatorCalculateRequest, IndicatorConfig
from ktrdr.errors import DataError, ConfigurationError, ProcessingError


@pytest.fixture
def indicator_service():
    """Create an indicator service instance for testing."""
    return IndicatorService()


@pytest.fixture
def mock_data_frame():
    """Create a mock DataFrame for testing indicators."""
    # Create a simple DataFrame with OHLCV data
    dates = pd.date_range(start='2023-01-01', periods=10)
    data = {
        'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        'high': [102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
        'low': [98, 99, 100, 101, 102, 103, 104, 105, 106, 107],
        'close': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        'volume': [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900]
    }
    return pd.DataFrame(data, index=dates)


@pytest.mark.asyncio
async def test_get_available_indicators(indicator_service):
    """Test retrieval of available indicators."""
    indicators = await indicator_service.get_available_indicators()
    
    # Verify that indicators were retrieved
    assert indicators is not None
    assert len(indicators) > 0
    
    # Check that each indicator has the required fields
    for indicator in indicators:
        assert indicator.id is not None
        assert indicator.name is not None
        assert indicator.description is not None
        assert indicator.type is not None
        assert indicator.parameters is not None


@pytest.mark.asyncio
async def test_calculate_indicators_with_valid_request(indicator_service, mock_data_frame):
    """Test indicator calculation with a valid request."""
    # Mock the data_manager to return our test DataFrame
    with patch.object(indicator_service.data_manager, 'load', return_value=mock_data_frame):
        # Create a sample request
        request = IndicatorCalculateRequest(
            symbol="AAPL",
            timeframe="1d",
            indicators=[
                IndicatorConfig(
                    id="RSIIndicator",
                    parameters={"period": 5, "source": "close"}
                )
            ]
        )
        
        # Calculate indicators
        dates, indicator_values, metadata = await indicator_service.calculate_indicators(request)
        
        # Verify results
        assert dates is not None
        assert len(dates) == 10  # Should match our mock data frame
        assert indicator_values is not None
        assert len(indicator_values) >= 1  # At least one indicator result
        assert metadata is not None
        assert metadata['symbol'] == "AAPL"
        assert metadata['timeframe'] == "1d"


@pytest.mark.asyncio
async def test_calculate_indicators_with_data_error(indicator_service):
    """Test indicator calculation with data loading error."""
    # Mock data_manager to raise DataError
    with patch.object(
        indicator_service.data_manager, 
        'load', 
        side_effect=DataError("No data", "DATA-NotFound", {})
    ):
        # Create a sample request
        request = IndicatorCalculateRequest(
            symbol="UNKNOWN",
            timeframe="1d",
            indicators=[
                IndicatorConfig(
                    id="RSIIndicator",
                    parameters={"period": 14}
                )
            ]
        )
        
        # Verify that DataError is raised
        with pytest.raises(DataError):
            await indicator_service.calculate_indicators(request)


@pytest.mark.asyncio
async def test_calculate_indicators_with_unknown_indicator(indicator_service, mock_data_frame):
    """Test indicator calculation with unknown indicator."""
    # Mock data_manager to return our test DataFrame
    with patch.object(indicator_service.data_manager, 'load', return_value=mock_data_frame):
        # Create a sample request with unknown indicator
        request = IndicatorCalculateRequest(
            symbol="AAPL",
            timeframe="1d",
            indicators=[
                IndicatorConfig(
                    id="UnknownIndicator",
                    parameters={}
                )
            ]
        )
        
        # Verify that ConfigurationError is raised
        with pytest.raises(ConfigurationError):
            await indicator_service.calculate_indicators(request)


@pytest.mark.asyncio
async def test_calculate_indicators_with_invalid_parameters(indicator_service, mock_data_frame):
    """Test indicator calculation with invalid parameters."""
    # Mock data_manager to return our test DataFrame
    with patch.object(indicator_service.data_manager, 'load', return_value=mock_data_frame):
        # Create a sample request with invalid parameters (negative period)
        request = IndicatorCalculateRequest(
            symbol="AAPL",
            timeframe="1d",
            indicators=[
                IndicatorConfig(
                    id="RSIIndicator",
                    parameters={"period": -5}
                )
            ]
        )
        
        # Expecting a ConfigurationError due to invalid parameters
        with pytest.raises(ConfigurationError):
            await indicator_service.calculate_indicators(request)


@pytest.mark.asyncio
async def test_health_check_healthy(indicator_service):
    """Test health check when service is healthy."""
    # Mock the BUILT_IN_INDICATORS dictionary
    with patch('ktrdr.api.services.indicator_service.BUILT_IN_INDICATORS', 
               {'RSIIndicator': MagicMock(), 'SMAIndicator': MagicMock(), 'MACDIndicator': MagicMock()}):
        
        result = await indicator_service.health_check()
        
        # Verify result structure
        assert isinstance(result, dict)
        assert result["status"] == "healthy"
        assert "available_indicators" in result
        assert result["available_indicators"] == 3
        assert "first_5_indicators" in result
        assert len(result["first_5_indicators"]) == 3
        assert "message" in result


@pytest.mark.asyncio
async def test_health_check_error(indicator_service):
    """Test health check when service encounters errors."""
    # Mock BUILT_IN_INDICATORS to raise an exception when accessed
    with patch('ktrdr.api.services.indicator_service.BUILT_IN_INDICATORS', 
               new_callable=PropertyMock, side_effect=Exception("Test error")):
        
        result = await indicator_service.health_check()
        
        # Verify result structure
        assert isinstance(result, dict)
        assert result["status"] == "unhealthy"
        assert "message" in result
        assert "indicator service health check failed" in result["message"].lower()