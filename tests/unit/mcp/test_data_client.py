"""Tests for DataAPIClient"""

from unittest.mock import AsyncMock, patch

import pytest
from clients.data_client import DataAPIClient


@pytest.fixture
def data_client():
    """Create a DataAPIClient instance for testing"""
    return DataAPIClient(base_url="http://test:8000", timeout=10.0)


class TestGetCachedData:
    """Tests for get_cached_data method"""

    @pytest.mark.asyncio
    async def test_get_cached_data_with_all_params(self, data_client):
        """Test get_cached_data accepts all parameters as keyword args"""
        mock_response = {
            "success": True,
            "data": {
                "dates": ["2024-01-01", "2024-01-02"],
                "ohlcv": [[100, 105, 99, 103, 1000], [103, 107, 102, 106, 1200]],
                "metadata": {"points": 2},
            },
        }

        with patch.object(
            data_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            # This should work with keyword arguments
            result = await data_client.get_cached_data(
                symbol="AAPL",
                timeframe="1h",
                start_date="2024-01-01",
                end_date="2024-01-02",
                trading_hours_only=True,
                limit=50,
            )

            # Verify the request was made correctly
            mock_request.assert_called_once_with(
                "GET",
                "/data/AAPL/1h",
                params={
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-02",
                    "trading_hours_only": True,
                },
            )

            # Verify response
            assert result["success"] is True
            assert len(result["data"]["dates"]) == 2

    @pytest.mark.asyncio
    async def test_get_cached_data_with_limit_truncation(self, data_client):
        """Test that limit parameter truncates results client-side"""
        mock_response = {
            "success": True,
            "data": {
                "dates": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
                "ohlcv": [[100, 105, 99, 103, 1000]] * 4,
                "metadata": {"points": 4},
            },
        }

        with patch.object(
            data_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await data_client.get_cached_data(
                symbol="AAPL", timeframe="1h", limit=2
            )

            # Verify truncation happened
            assert len(result["data"]["dates"]) == 2
            assert result["data"]["metadata"]["points"] == 2
            assert result["data"]["metadata"]["limited_by_client"] is True
