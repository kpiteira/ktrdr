"""Tests for IndicatorsAPIClient"""

from unittest.mock import AsyncMock, patch

import pytest
from clients.indicators_client import IndicatorsAPIClient


@pytest.fixture
def indicators_client():
    """Create an IndicatorsAPIClient instance for testing"""
    return IndicatorsAPIClient(base_url="http://test:8000", timeout=10.0)


class TestListIndicators:
    """Tests for list_indicators method"""

    @pytest.mark.asyncio
    async def test_list_indicators_returns_data_array(self, indicators_client):
        """Test list_indicators extracts data from response"""
        mock_response = {
            "success": True,
            "data": [
                {
                    "id": "RSI",
                    "name": "Relative Strength Index",
                    "type": "momentum",
                    "parameters": [],
                },
                {
                    "id": "SMA",
                    "name": "Simple Moving Average",
                    "type": "trend",
                    "parameters": [],
                },
            ],
        }

        with patch.object(
            indicators_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await indicators_client.list_indicators()

            # Verify request
            mock_request.assert_called_once_with("GET", "/indicators/")

            # Verify response extraction
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["id"] == "RSI"

    @pytest.mark.asyncio
    async def test_list_indicators_handles_empty_data(self, indicators_client):
        """Test list_indicators handles missing data field gracefully"""
        mock_response = {"success": True}

        with patch.object(
            indicators_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await indicators_client.list_indicators()

            # Should return empty list when data field missing
            assert result == []
