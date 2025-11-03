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


class TestGetSymbols:
    """Tests for get_symbols method"""

    @pytest.mark.asyncio
    async def test_get_symbols_returns_data_array(self, data_client):
        """Test get_symbols extracts data from response"""
        mock_response = {
            "success": True,
            "data": [
                {"symbol": "AAPL", "instrument_type": "stock"},
                {"symbol": "EURUSD", "instrument_type": "forex"},
            ],
        }

        with patch.object(
            data_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await data_client.get_symbols()

            # Verify request
            mock_request.assert_called_once_with("GET", "/symbols")

            # Verify response extraction
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_symbols_handles_empty_data(self, data_client):
        """Test get_symbols handles missing data field gracefully"""
        mock_response = {"success": True}

        with patch.object(
            data_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await data_client.get_symbols()

            # Should return empty list when data field missing
            assert result == []


class TestLoadDataOperation:
    """Tests for load_data_operation method"""

    @pytest.mark.asyncio
    async def test_load_data_operation_returns_operation_response(self, data_client):
        """Test load_data_operation returns full response for critical operation"""
        mock_response = {
            "success": True,
            "data": {
                "operation_id": "op_data_123",
                "symbol": "AAPL",
                "timeframe": "1h",
            },
        }

        with patch.object(
            data_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await data_client.load_data_operation(
                symbol="AAPL", timeframe="1h", mode="local"
            )

            # Verify request payload
            mock_request.assert_called_once_with(
                "POST",
                "/data/acquire/download",
                json={"symbol": "AAPL", "timeframe": "1h", "mode": "local"},
            )

            # Should return extracted data field (critical operation)
            assert result == mock_response["data"]
            assert result["operation_id"] == "op_data_123"
