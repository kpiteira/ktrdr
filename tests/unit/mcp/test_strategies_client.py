"""Tests for StrategiesAPIClient"""

from unittest.mock import AsyncMock, patch

import pytest
from clients.strategies_client import StrategiesAPIClient


@pytest.fixture
def strategies_client():
    """Create a StrategiesAPIClient instance for testing"""
    return StrategiesAPIClient(base_url="http://test:8000", timeout=10.0)


class TestListStrategies:
    """Tests for list_strategies method"""

    @pytest.mark.asyncio
    async def test_list_strategies_returns_strategies_array(self, strategies_client):
        """Test list_strategies extracts strategies from response"""
        mock_response = {
            "success": True,
            "strategies": [
                {
                    "name": "neuro_mean_reversion",
                    "description": "Neural network mean reversion strategy",
                    "training_status": "trained",
                },
                {
                    "name": "trend_following",
                    "description": "Trend following strategy",
                    "training_status": "untrained",
                },
            ],
        }

        with patch.object(
            strategies_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await strategies_client.list_strategies()

            # Verify request
            mock_request.assert_called_once_with("GET", "/strategies/")

            # Verify response extraction
            assert isinstance(result, dict)
            assert "strategies" in result
            assert len(result["strategies"]) == 2

    @pytest.mark.asyncio
    async def test_list_strategies_returns_full_response(self, strategies_client):
        """Test list_strategies returns the full response dict"""
        mock_response = {
            "success": True,
            "strategies": [],
        }

        with patch.object(
            strategies_client, "_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await strategies_client.list_strategies()

            # Should return entire response object
            assert result == mock_response
