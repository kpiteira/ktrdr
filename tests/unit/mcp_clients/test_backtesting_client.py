"""Unit tests for BacktestingAPIClient"""

from unittest.mock import AsyncMock, patch

import pytest

from mcp.src.clients.backtesting_client import BacktestingAPIClient


class TestBacktestingAPIClient:
    """Test BacktestingAPIClient follows the expected API pattern"""

    @pytest.fixture
    def client(self):
        """Create a BacktestingAPIClient instance for testing"""
        return BacktestingAPIClient(base_url="http://localhost:8000/api/v1", timeout=30.0)

    @pytest.mark.asyncio
    async def test_start_backtest_formats_request_correctly(self, client):
        """Test that start_backtest() correctly formats the API request"""
        # Arrange
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "success": True,
                "operation_id": "op_backtest_12345",
                "status": "started"
            }

            # Act
            result = await client.start_backtest(
                strategy_name="neuro_mean_reversion",
                symbol="EURUSD",
                timeframe="1d",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            # Assert - default values are included, model_path NOT included when None
            mock_request.assert_called_once_with(
                "POST",
                "/backtests/start",
                json={
                    "strategy_name": "neuro_mean_reversion",
                    "symbol": "EURUSD",
                    "timeframe": "1d",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "initial_capital": 100000.0,  # default value included
                    "commission": 0.001,  # default value included
                    "slippage": 0.001,  # default value included
                    # model_path not included when None
                }
            )
            assert result["operation_id"] == "op_backtest_12345"
            assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_start_backtest_includes_optional_parameters(self, client):
        """Test that optional parameters are included when provided"""
        # Arrange
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "success": True,
                "operation_id": "op_backtest_12345"
            }

            # Act
            await client.start_backtest(
                strategy_name="test_strategy",
                symbol="AAPL",
                timeframe="1h",
                start_date="2024-01-01",
                end_date="2024-12-31",
                model_path="models/test.pt",
                initial_capital=50000.0,
                commission=0.002,
                slippage=0.001
            )

            # Assert
            call_args = mock_request.call_args
            payload = call_args[1]["json"]
            assert payload["model_path"] == "models/test.pt"
            assert payload["initial_capital"] == 50000.0
            assert payload["commission"] == 0.002
            assert payload["slippage"] == 0.001
