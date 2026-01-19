"""
Unit tests for BacktestingOperationAdapter.

Tests verify that the backtesting adapter correctly implements the OperationAdapter
interface and provides domain-specific logic for backtesting operations.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from rich.console import Console

from ktrdr.cli.operation_adapters import BacktestingOperationAdapter, OperationAdapter


class TestBacktestingOperationAdapter:
    """Test the BacktestingOperationAdapter implementation."""

    def test_is_operation_adapter(self):
        """Verify BacktestingOperationAdapter implements OperationAdapter."""
        adapter = BacktestingOperationAdapter(
            strategy_name="neuro_mean_reversion",
            symbol="AAPL",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000.0,
        )
        assert isinstance(adapter, OperationAdapter)

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        adapter = BacktestingOperationAdapter(
            strategy_name="neuro_mean_reversion",
            symbol="AAPL",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000.0,
            commission=0.002,
            slippage=0.001,
        )

        assert adapter.strategy_name == "neuro_mean_reversion"
        assert adapter.symbol == "AAPL"
        assert adapter.timeframe == "1d"
        assert adapter.start_date == "2024-01-01"
        assert adapter.end_date == "2024-12-31"
        assert adapter.initial_capital == 100000.0
        assert adapter.commission == 0.002
        assert adapter.slippage == 0.001

    def test_initialization_with_default_parameters(self):
        """Test initialization with default commission and slippage."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test_strategy",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=50000.0,
        )

        assert adapter.commission == 0.001  # Default
        assert adapter.slippage == 0.001  # Default

    def test_get_start_endpoint_returns_correct_path(self):
        """Verify get_start_endpoint returns the correct API path."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test",
            symbol="TEST",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000.0,
        )

        endpoint = adapter.get_start_endpoint()
        assert endpoint == "/backtests/start"
        assert isinstance(endpoint, str)
        assert endpoint.startswith("/")

    def test_get_start_payload_returns_complete_payload(self):
        """Verify get_start_payload returns all required fields."""
        adapter = BacktestingOperationAdapter(
            strategy_name="momentum",
            symbol="MSFT",
            timeframe="4h",
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=75000.0,
            commission=0.0015,
            slippage=0.0005,
        )

        payload = adapter.get_start_payload()

        # Verify payload structure
        assert isinstance(payload, dict)
        assert payload["strategy_name"] == "momentum"
        assert payload["symbol"] == "MSFT"
        assert payload["timeframe"] == "4h"
        assert payload["start_date"] == "2023-01-01"
        assert payload["end_date"] == "2023-12-31"
        assert payload["initial_capital"] == 75000.0
        assert payload["commission"] == 0.0015
        assert payload["slippage"] == 0.0005

    def test_get_start_payload_includes_model_path_if_provided(self):
        """Verify model_path is included in payload when provided."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test",
            symbol="AAPL",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000.0,
            model_path="models/neuro_mean_reversion/1d_v21/model.pt",
        )

        payload = adapter.get_start_payload()
        assert "model_path" in payload
        assert payload["model_path"] == "models/neuro_mean_reversion/1d_v21/model.pt"

    def test_get_start_payload_excludes_model_path_if_not_provided(self):
        """Verify model_path is not in payload when not provided."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test",
            symbol="AAPL",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000.0,
        )

        payload = adapter.get_start_payload()
        assert "model_path" not in payload

    def test_parse_start_response_extracts_operation_id(self):
        """Verify parse_start_response correctly extracts operation_id."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test",
            symbol="TEST",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000.0,
        )

        # Standard response format
        response = {
            "operation_id": "op_backtest_20250105_abc123",
            "status": "started",
        }

        operation_id = adapter.parse_start_response(response)
        assert operation_id == "op_backtest_20250105_abc123"
        assert isinstance(operation_id, str)

    def test_parse_start_response_handles_nested_operation_id(self):
        """Verify parse_start_response handles nested data structure."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test",
            symbol="TEST",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000.0,
        )

        # Nested response format (fallback)
        response = {
            "success": True,
            "data": {"operation_id": "op_backtest_20250105_xyz789"},
        }

        operation_id = adapter.parse_start_response(response)
        assert operation_id == "op_backtest_20250105_xyz789"

    @pytest.mark.asyncio
    async def test_display_results_shows_summary(self):
        """Verify display_results shows backtest summary."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test_strategy",
            symbol="AAPL",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=100000.0,
        )

        console = Console()
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        final_status = {
            "operation_id": "op_backtest_123",
            "status": "completed",
            "results": {
                "total_return": 2340.50,
                "sharpe_ratio": 1.23,
                "max_drawdown": -5000.0,
                "total_trades": 25,
                "win_rate": 0.56,
            },
        }

        # Should not raise
        await adapter.display_results(final_status, console, mock_client)

    @pytest.mark.asyncio
    async def test_display_results_handles_missing_results(self):
        """Verify display_results handles missing results gracefully."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test",
            symbol="TEST",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000.0,
        )

        console = Console()
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        final_status = {
            "operation_id": "op_backtest_123",
            "status": "completed",
            # No results field
        }

        # Should not raise
        await adapter.display_results(final_status, console, mock_client)

    def test_adapter_stores_all_parameters(self):
        """Verify all initialization parameters are stored."""
        adapter = BacktestingOperationAdapter(
            strategy_name="strategy1",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000.0,
            commission=0.002,
            slippage=0.0015,
            model_path="models/test.pt",
        )

        # All parameters should be accessible
        assert hasattr(adapter, "strategy_name")
        assert hasattr(adapter, "symbol")
        assert hasattr(adapter, "timeframe")
        assert hasattr(adapter, "start_date")
        assert hasattr(adapter, "end_date")
        assert hasattr(adapter, "initial_capital")
        assert hasattr(adapter, "commission")
        assert hasattr(adapter, "slippage")
        assert hasattr(adapter, "model_path")

    def test_multiple_adapters_are_independent(self):
        """Verify multiple adapter instances don't interfere."""
        adapter1 = BacktestingOperationAdapter(
            strategy_name="strategy1",
            symbol="AAPL",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=100000.0,
        )

        adapter2 = BacktestingOperationAdapter(
            strategy_name="strategy2",
            symbol="MSFT",
            timeframe="4h",
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=50000.0,
        )

        # Verify independence
        assert adapter1.strategy_name != adapter2.strategy_name
        assert adapter1.symbol != adapter2.symbol
        assert adapter1.timeframe != adapter2.timeframe
        assert adapter1.initial_capital != adapter2.initial_capital


class TestBacktestingOperationAdapterOptionalSymbolTimeframe:
    """Test optional symbol/timeframe behavior (like TrainingOperationAdapter)."""

    def test_initialization_with_symbol_timeframe_none(self):
        """Test initialization with symbol and timeframe as None."""
        adapter = BacktestingOperationAdapter(
            strategy_name="test_strategy",
            symbol=None,
            timeframe=None,
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=50000.0,
        )

        assert adapter.symbol is None
        assert adapter.timeframe is None
        assert adapter.strategy_name == "test_strategy"

    def test_get_start_payload_omits_symbol_when_none(self):
        """Verify symbol is not in payload when None (backend reads from strategy)."""
        adapter = BacktestingOperationAdapter(
            strategy_name="momentum",
            symbol=None,
            timeframe="1h",
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=75000.0,
        )

        payload = adapter.get_start_payload()

        # symbol should NOT be in payload when None
        assert "symbol" not in payload
        # timeframe should still be present
        assert payload["timeframe"] == "1h"
        assert payload["strategy_name"] == "momentum"

    def test_get_start_payload_omits_timeframe_when_none(self):
        """Verify timeframe is not in payload when None (backend reads from strategy)."""
        adapter = BacktestingOperationAdapter(
            strategy_name="momentum",
            symbol="AAPL",
            timeframe=None,
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=75000.0,
        )

        payload = adapter.get_start_payload()

        # timeframe should NOT be in payload when None
        assert "timeframe" not in payload
        # symbol should still be present
        assert payload["symbol"] == "AAPL"
        assert payload["strategy_name"] == "momentum"

    def test_get_start_payload_omits_both_when_none(self):
        """Verify both symbol and timeframe omitted when None."""
        adapter = BacktestingOperationAdapter(
            strategy_name="momentum",
            symbol=None,
            timeframe=None,
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=75000.0,
        )

        payload = adapter.get_start_payload()

        # Neither should be in payload
        assert "symbol" not in payload
        assert "timeframe" not in payload
        # Other fields should be present
        assert payload["strategy_name"] == "momentum"
        assert payload["start_date"] == "2023-01-01"
        assert payload["end_date"] == "2023-12-31"
        assert payload["initial_capital"] == 75000.0

    def test_get_start_payload_includes_both_when_provided(self):
        """Verify symbol and timeframe included when explicitly provided."""
        adapter = BacktestingOperationAdapter(
            strategy_name="momentum",
            symbol="MSFT",
            timeframe="4h",
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=75000.0,
        )

        payload = adapter.get_start_payload()

        # Both should be in payload when provided
        assert payload["symbol"] == "MSFT"
        assert payload["timeframe"] == "4h"
